"""Interactive Brokers execution module."""

import asyncio
from typing import Optional, Dict
from datetime import datetime
import logging

try:
    from ib_insync import IB, Stock, LimitOrder, MarketOrder, Order, StopOrder
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    print("Warning: ib_insync not available. Live trading will not work.")


logger = logging.getLogger(__name__)


class IBKRExecutor:
    """Interactive Brokers order execution handler."""
    
    def __init__(self, config: Dict):
        """Initialize IBKR executor.
        
        Args:
            config: Execution configuration dictionary
        """
        if not IB_INSYNC_AVAILABLE:
            raise ImportError("ib_insync not available. Install it with: pip install ib-insync")
        
        self.config = config
        self.ib = IB()
        self.connected = False
        
        # IBKR connection settings
        self.host = config.get('ibkr', {}).get('host', '127.0.0.1')
        self.port = config.get('ibkr', {}).get('port', 7497)
        self.client_id = config.get('ibkr', {}).get('client_id', 1)
        self.timeout = config.get('ibkr', {}).get('timeout', 30)
        
        # Risk settings
        self.risk_guard = config.get('risk_guard', True)
        self.kill_switch_enabled = config.get('kill_switch_enabled', True)
        
        # State
        self.positions: Dict[str, int] = {}  # symbol -> shares
        self.orders: Dict[str, Order] = {}
        self.kill_switch_triggered = False
    
    async def connect(self) -> bool:
        """Connect to IBKR.
        
        Returns:
            True if connected successfully
        """
        try:
            await self.ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout
            )
            self.connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from IBKR."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")
    
    async def get_account_value(self, key: str = 'NetLiquidation') -> float:
        """Get account value.
        
        Args:
            key: Account value key (e.g., 'NetLiquidation', 'TotalCashValue')
        
        Returns:
            Account value
        """
        if not self.connected:
            return 0.0
        
        try:
            account_values = self.ib.accountValues()
            for av in account_values:
                if av.tag == key:
                    return float(av.value)
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get account value: {e}")
            return 0.0
    
    async def get_positions(self) -> Dict[str, int]:
        """Get current positions.
        
        Returns:
            Dictionary mapping symbol to shares
        """
        if not self.connected:
            return {}
        
        try:
            positions = self.ib.positions()
            self.positions = {}
            for pos in positions:
                symbol = pos.contract.symbol
                shares = pos.position
                self.positions[symbol] = shares
            return self.positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {}
    
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str = 'limit',
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Optional[Order]:
        """Place an order.
        
        Args:
            symbol: Symbol to trade
            quantity: Number of shares (positive for buy, negative for sell)
            order_type: Order type ('limit' or 'market')
            limit_price: Limit price (required for limit orders)
            stop_price: Stop price (optional)
        
        Returns:
            Order object if placed successfully
        """
        if not self.connected:
            logger.error("Not connected to IBKR")
            return None
        
        if self.kill_switch_triggered:
            logger.warning("Kill switch triggered. Order rejected.")
            return None
        
        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Create order
            if order_type == 'limit' and limit_price:
                order = LimitOrder('BUY' if quantity > 0 else 'SELL', abs(quantity), limit_price)
            else:
                order = MarketOrder('BUY' if quantity > 0 else 'SELL', abs(quantity))
            
            # Add stop if provided
            if stop_price:
                # For simplicity, we'll use a separate stop order
                # In production, use bracket orders
                pass
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            self.orders[symbol] = order
            
            logger.info(f"Placed {order_type} order: {symbol} {quantity} @ {limit_price or 'MARKET'}")
            return order
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None
    
    async def cancel_order(self, symbol: str):
        """Cancel an order.
        
        Args:
            symbol: Symbol to cancel order for
        """
        if symbol in self.orders:
            try:
                self.ib.cancelOrder(self.orders[symbol])
                logger.info(f"Cancelled order for {symbol}")
            except Exception as e:
                logger.error(f"Failed to cancel order: {e}")
    
    async def close_position(self, symbol: str):
        """Close a position.
        
        Args:
            symbol: Symbol to close position for
        """
        positions = await self.get_positions()
        if symbol in positions:
            quantity = -positions[symbol]  # Opposite of current position
            await self.place_order(symbol, quantity, order_type='market')
            logger.info(f"Closed position for {symbol}")
    
    def trigger_kill_switch(self):
        """Trigger kill switch to halt all trading."""
        self.kill_switch_triggered = True
        logger.critical("KILL SWITCH TRIGGERED - All trading halted")
    
    def reset_kill_switch(self):
        """Reset kill switch."""
        self.kill_switch_triggered = False
        logger.info("Kill switch reset")
    
    async def monitor_risk(self, equity: float, drawdown: float, daily_pnl: float):
        """Monitor risk and trigger kill switch if needed.
        
        Args:
            equity: Current equity
            drawdown: Current drawdown percentage
            daily_pnl: Daily P&L
        """
        if not self.risk_guard:
            return
        
        # Check daily loss limit
        daily_loss_limit = self.config.get('risk', {}).get('daily_loss_limit_pct', 2.5)
        if daily_pnl < -(equity * daily_loss_limit / 100.0):
            logger.warning(f"Daily loss limit exceeded: {daily_pnl:.2f}")
            self.trigger_kill_switch()
        
        # Check drawdown limit
        max_drawdown = self.config.get('risk', {}).get('max_drawdown_pct', 18.0)
        if drawdown < -max_drawdown:
            logger.warning(f"Max drawdown exceeded: {drawdown:.2f}%")
            self.trigger_kill_switch()
    
    async def health_check(self) -> bool:
        """Perform health check.
        
        Returns:
            True if healthy
        """
        if not self.connected:
            return False
        
        try:
            # Check connection
            account_values = await self.get_account_value()
            if account_values == 0:
                logger.warning("Account value is zero or unavailable")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


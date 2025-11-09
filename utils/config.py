"""Configuration management for the trading system."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class SymbolConfig(BaseModel):
    """Symbol configuration."""
    primary: str
    context: list[str] = Field(default_factory=list)


class DataConfig(BaseModel):
    """Data configuration."""
    start_date: str
    end_date: Optional[str] = None
    interval: str = "1d"
    cache_dir: str = "data/"


class StrategyConfig(BaseModel):
    """Base strategy configuration."""
    enabled: bool = False


class TrendEMAConfig(StrategyConfig):
    """Trend-EMA strategy configuration."""
    ema_fast: int = 12
    ema_medium: int = 26
    ema_slow: int = 55
    rsi_period: int = 14
    rsi_long_threshold: float = 52.0
    rsi_short_threshold: float = 45
    long_only: bool = True
    regime_filter_enabled: bool = True
    regime_sma_period: int = 200
    dual_timeframe_enabled: bool = True
    dual_timeframe_ema: int = 100
    pullback_tolerance: float = 0.04
    continuation_tolerance: float = 0.03
    min_trend_strength: float = 0.0
    max_volatility: float = 0.35
    min_bars_between_signals: int = 1
    exit_buffer: float = 0.015
    fast_buffer: float = 0.0
    volatility_time_stop_bars: int = 10
    volatility_time_stop_threshold: float = 0.02
    adx_threshold: float = 20.0


class BreakoutMomentumConfig(StrategyConfig):
    """Breakout-Momentum strategy configuration."""
    lookback: int = 10
    rvol_threshold: float = 1.4
    adx_threshold: float = 18.0
    atr_buffer_mult: float = 0.25
    long_only: bool = True


class MeanReversionConfig(StrategyConfig):
    """Mean-Reversion strategy configuration."""
    lookback: int = 20
    std_dev: float = 2.5
    adx_threshold: float = 18
    bb_width_quantile: float = 0.3


class VolatilityOverlayConfig(StrategyConfig):
    """Volatility Overlay strategy configuration."""
    atr_period: int = 14
    vol_target_annual: float = 0.25
    min_size_mult: float = 0.5
    max_size_mult: float = 1.5


class RegimeFilterConfig(StrategyConfig):
    """Regime Filter strategy configuration."""
    qqq_sma_period: int = 200
    vix_threshold: float = 25
    risk_off_exposure: float = 0.25


class EnsembleConfig(StrategyConfig):
    """Ensemble strategy configuration."""
    weights: Dict[str, float] = Field(default_factory=dict)


class StrategiesConfig(BaseModel):
    """All strategies configuration."""
    trend_ema: TrendEMAConfig = Field(default_factory=TrendEMAConfig)
    breakout_momentum: BreakoutMomentumConfig = Field(default_factory=BreakoutMomentumConfig)
    mean_reversion: MeanReversionConfig = Field(default_factory=MeanReversionConfig)
    volatility_overlay: VolatilityOverlayConfig = Field(default_factory=VolatilityOverlayConfig)
    regime_filter: RegimeFilterConfig = Field(default_factory=RegimeFilterConfig)
    ensemble: EnsembleConfig = Field(default_factory=EnsembleConfig)


class RiskConfig(BaseModel):
    """Risk management configuration."""
    initial_capital: float = 100000
    per_trade_risk_pct: float = 5.0
    max_net_exposure: float = 2.4
    min_net_exposure: float = -1.0
    max_gross_exposure: float = 3.2
    stop_atr_mult: float = 2.2
    trailing_stop_atr_mult: float = 1.5
    trailing_start_r: float = 3.0
    trailing_mid_r: float = 6.0
    trailing_end_r: float = 12.0
    trailing_start_mult: float = 1.3
    trailing_mid_mult: float = 1.1
    trailing_end_mult: float = 1.0
    time_stop_bars: int = 0
    daily_loss_limit_pct: float = 3.0
    max_drawdown_pct: float = 30.0
    drawdown_recovery_exposure: float = 0.55
    pyramid_enabled: bool = True
    pyramid_max_adds: int = 3
    pyramid_add_thresholds: List[float] = Field(default_factory=lambda: [1.5, 3.0, 5.0])
    pyramid_add_scale: float = 0.7


class CostsConfig(BaseModel):
    """Trading costs configuration."""
    commission_per_share: float = 0.005
    slippage_bps: float = 5
    market_impact_bps: float = 3


class WalkForwardConfig(BaseModel):
    """Walk-forward validation configuration."""
    train_years: int = 3
    test_years: int = 1
    min_train_years: int = 2


class StressTestConfig(BaseModel):
    """Stress test configuration."""
    start: str
    end: str
    name: str


class BacktestingConfig(BaseModel):
    """Backtesting configuration."""
    walk_forward: WalkForwardConfig = Field(default_factory=WalkForwardConfig)
    benchmark_symbols: list[str] = Field(default_factory=list)
    stress_tests: list[StressTestConfig] = Field(default_factory=list)


class ReportingConfig(BaseModel):
    """Reporting configuration."""
    output_dir: str = "out/"
    generate_charts: bool = True
    generate_html: bool = True
    chart_format: str = "png"
    save_trade_log: bool = True
    save_metrics_json: bool = True


class IBKRConfig(BaseModel):
    """Interactive Brokers configuration."""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    timeout: int = 30


class ExecutionConfig(BaseModel):
    """Execution configuration."""
    mode: str = "paper"
    ibkr: IBKRConfig = Field(default_factory=IBKRConfig)
    risk_guard: bool = True
    kill_switch_enabled: bool = True


class Config(BaseModel):
    """Main configuration model."""
    symbol: SymbolConfig
    data: DataConfig
    strategies: StrategiesConfig
    risk: RiskConfig
    costs: CostsConfig
    backtesting: BacktestingConfig
    reporting: ReportingConfig
    execution: ExecutionConfig


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    return Config(**config_dict)


def save_config(config: Config, config_path: str) -> None:
    """Save configuration to YAML file."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    config_dict = config.model_dump(mode='python')
    with open(path, 'w') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)



class IBAdapter:
    def __init__(self, mode='paper'):
        self.mode = mode
        self._connected = False
        # Mock connected
        self._connected = True

    def status(self):
        return {'mode': self.mode, 'connected': self._connected, 'mock': True}

    def place_order(self, symbol, qty, order_type='MKT'):
        # Mock execution: pretend fill at market price
        return {'order_id': 'MOCK-1', 'status': 'filled', 'filled_qty': qty}

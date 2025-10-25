
def position_size(equity, per_trade_risk_pct=1.0, stop_loss_pct=5.0):
    # Very simple: risk per trade = per_trade_risk_pct% of equity, position size = risk / stop_loss_pct
    risk_amount = equity * (per_trade_risk_pct / 100.0)
    pos = risk_amount / (stop_loss_pct / 100.0 * equity)
    return max(0, pos)

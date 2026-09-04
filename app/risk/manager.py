def position_size(account_value: float, entry: float, stop: float, risk_fraction: float = 0.01) -> int:
    risk_per_share = abs(entry - stop)
    if account_value <= 0 or risk_per_share <= 0:
        return 0
    return max(0, int((account_value * risk_fraction) / risk_per_share))

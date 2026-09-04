from __future__ import annotations

import pandas as pd


def add_chart_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the indicators visible in the reference IBKR chart.

    Defaults: Ichimoku 9/26/52, Williams %R 14, MFI 14 and a 50-period EMA.
    """
    out = df.copy()
    high, low, close, volume = out["high"], out["low"], out["close"], out["volume"]

    # Ichimoku cloud
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    out["tenkan"] = tenkan
    out["kijun"] = kijun
    out["senkou_a"] = span_a
    out["senkou_b"] = span_b

    # Williams %R (14)
    hh = high.rolling(14).max()
    ll = low.rolling(14).min()
    out["williams_r"] = -100 * (hh - close) / (hh - ll).replace(0, pd.NA)

    # Money Flow Index (14)
    typical = (high + low + close) / 3
    raw_flow = typical * volume
    direction = typical.diff()
    positive = raw_flow.where(direction > 0, 0.0).rolling(14).sum()
    negative = raw_flow.where(direction < 0, 0.0).rolling(14).sum()
    money_ratio = positive / negative.replace(0, pd.NA)
    out["mfi14"] = 100 - (100 / (1 + money_ratio))

    out["ema50_chart"] = close.ewm(span=50, adjust=False).mean()
    out["volume_sma20"] = volume.rolling(20).mean()
    out["volume_ratio"] = volume / out["volume_sma20"].replace(0, pd.NA)

    # Current cloud state and displacement from cloud.
    cloud_top = pd.concat([out["senkou_a"], out["senkou_b"]], axis=1).max(axis=1)
    cloud_bottom = pd.concat([out["senkou_a"], out["senkou_b"]], axis=1).min(axis=1)
    out["cloud_top"] = cloud_top
    out["cloud_bottom"] = cloud_bottom
    out["above_cloud"] = close > cloud_top
    out["below_cloud"] = close < cloud_bottom
    return out


def chart_context(df: pd.DataFrame) -> dict:
    """Return a compact, machine-readable snapshot for strategy/AI layers."""
    r = df.iloc[-1]
    return {
        "close": float(r.close),
        "ema50": float(r.ema50_chart) if pd.notna(r.ema50_chart) else None,
        "williams_r": float(r.williams_r) if pd.notna(r.williams_r) else None,
        "mfi14": float(r.mfi14) if pd.notna(r.mfi14) else None,
        "volume_ratio": float(r.volume_ratio) if pd.notna(r.volume_ratio) else None,
        "above_cloud": bool(r.above_cloud) if pd.notna(r.above_cloud) else False,
        "below_cloud": bool(r.below_cloud) if pd.notna(r.below_cloud) else False,
        "cloud_top": float(r.cloud_top) if pd.notna(r.cloud_top) else None,
        "cloud_bottom": float(r.cloud_bottom) if pd.notna(r.cloud_bottom) else None,
    }

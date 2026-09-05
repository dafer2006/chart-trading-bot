import pandas as pd

from app.config import settings


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Moving averages used by the independent and combined strategies.
    out["ema9"] = out.close.ewm(span=settings.ema_fast_period, adjust=False).mean()
    out["ema20"] = out.close.ewm(span=20, adjust=False).mean()
    out["ema21"] = out.close.ewm(span=settings.ema_pullback_period, adjust=False).mean()
    out["ema50"] = out.close.ewm(span=50, adjust=False).mean()
    out["sma50"] = out.close.rolling(settings.sma_medium_period).mean()
    out["sma200"] = out.close.rolling(settings.sma_long_period).mean()

    # RSI(14) / configurable momentum period.
    delta = out.close.diff()
    gain = delta.clip(lower=0).ewm(
        alpha=1 / settings.momentum_period, adjust=False
    ).mean()
    loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / settings.momentum_period, adjust=False
    ).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["rsi14"] = 100 - 100 / (1 + rs)

    # Williams %R: -100 is the lowest part of the lookback range and 0 is the
    # highest. This is deliberately exposed as raw values for the strategy
    # state engine instead of converting it into a binary signal here.
    highest = out.high.rolling(settings.williams_period).max()
    lowest = out.low.rolling(settings.williams_period).min()
    denominator = (highest - lowest).replace(0, pd.NA)
    out["williams_r"] = -100 * (highest - out.close) / denominator

    # ATR and volume context.
    prev = out.close.shift(1)
    tr = pd.concat(
        [
            out.high - out.low,
            (out.high - prev).abs(),
            (out.low - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr14"] = tr.rolling(14).mean()
    out["volume20"] = out.volume.rolling(settings.volume_average_period).mean()
    out["volume_ratio"] = out.volume / out["volume20"].replace(0, pd.NA)

    # Previous-range breakout levels (no look-ahead).
    out["breakout_high"] = (
        out.high.rolling(settings.breakout_lookback_period).max().shift(1)
    )
    out["breakout_low"] = (
        out.low.rolling(settings.breakout_lookback_period).min().shift(1)
    )

    # Useful Williams state context. These columns do not create a trade
    # signal; the dedicated Williams strategy owns that decision.
    out["williams_prev"] = out["williams_r"].shift(1)
    out["williams_change"] = out["williams_r"].diff()
    out["williams_above_start"] = (
        out["williams_r"] >= settings.williams_start_level
    )
    out["price_above_ema21"] = out.close > out["ema21"]

    return out

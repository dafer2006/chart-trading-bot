# Chart Trading Bot

Automated chart/data analysis and trading framework for Interactive Brokers (IBKR).

## Current version

The first working foundation provides:

- IBKR historical market-data connection
- OHLCV candle processing
- EMA 20 / EMA 50
- RSI 14
- ATR 14
- 20-bar breakout detection
- Volume confirmation
- BUY/HOLD signal scoring
- ATR-based stop and reward/risk target
- Position-size calculation
- Paper-trading safety switch

## Project structure

```text
app/
  broker/       IBKR connection and market data
  analysis/     Indicators and chart-data analysis
  strategy/     Signal rules
  risk/         Position sizing and risk controls
  main.py       Application entry point
```

## Setup on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the IBKR host/port in `.env`. For TWS paper trading the usual API port is `7497`; for IB Gateway paper trading it is commonly `4002` (verify the setting in your installation).

Then run:

```powershell
python -m app.main
```

## Safety

`PAPER_TRADING=true` is the default. In this mode the application will analyze data but refuses to submit a live order. Do not switch to live execution until the strategy has been tested with paper trading and historical data.

## Strategy

The initial BUY signal is intentionally simple and transparent: bullish EMA alignment, RSI confirmation, above-average volume, and a 20-bar breakout are scored. The strategy layer is designed to be replaced with the user's exact chart rules.

## Next stages

1. Live candle monitoring and automatic rescanning.
2. Candlestick and price-action pattern engine.
3. Support/resistance and breakout quality analysis.
4. Configurable strategy rules from the desktop UI.
5. Paper-order manager and trade journal.
6. Backtesting and performance metrics.
7. Optional chart-image/vision analysis.
8. Live order execution only after explicit configuration and testing.

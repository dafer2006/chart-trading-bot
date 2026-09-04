# Chart Trading Bot

Desktop paper-trading bot for Interactive Brokers (IBKR). Market scanning and chart analysis run in a background worker so the UI stays responsive.

## Desktop UI

Run:

```powershell
python run_desktop.py
```

The window provides:

- Symbol search/input (default `BIAF`)
- Connect & Start button
- Stop button
- Connection/scanner status
- Latest BUY/SELL/HOLD signal
- Score, entry, stop and target
- Reasons behind the signal
- Table of orders submitted to the IBKR Paper account

The scanner runs in the background and rescans the symbol periodically. The UI thread is never used for market-data requests or analysis.

## Analysis

The current deterministic chart-style engine uses the supplied 10-minute chart concept:

- OHLCV candles
- EMA20 / EMA50
- Ichimoku 9/26/52
- Williams %R 14
- MFI 14
- Volume average and volume ratio
- 20-bar breakout/breakdown
- Doji and engulfing patterns
- Explainable signal scoring

## Paper orders

`PAPER_TRADING=true` is required. The broker layer accepts only TWS paper port `7497` or IB Gateway paper port `4002` when paper mode is enabled. Live trading is intentionally disabled by the code.

When a qualifying signal appears and there is no current position, the bot calculates quantity from the account NetLiquidation and configured risk percentage, then submits a **market order to the IBKR Paper account**. The UI records the order and displays entry/stop/target calculations.

The current order manager deliberately starts with the entry order only. Protective stop/target order automation will be added as a separate tested stage.

## Setup on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run_desktop.py
```

If PowerShell blocks activation, use the Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_desktop.py
```

## Configuration

The example configuration uses 10-minute candles, 7 days of history, `BIAF`, and a 60-second scan interval. Edit `.env` to change the symbol, timeframe, risk percentage, minimum score, and IBKR paper connection settings.

## Safety

Never place live credentials or secrets in GitHub. Keep `.env` local; it is ignored by Git. The application rejects live trading by design in this version.

## Roadmap

1. Protective paper SL/TP orders and position lifecycle.
2. Trade journal and P&L dashboard.
3. Historical backtesting.
4. Multi-symbol scanner.
5. Support/resistance and trendline engine.
6. Optional chart-image/vision layer.
7. Strategy parameters editable from the desktop UI.

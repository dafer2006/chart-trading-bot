from __future__ import annotations
import pandas as pd
from app.config import settings

try:
    from ib_async import IB, Stock, MarketOrder
except ImportError:
    IB = Stock = MarketOrder = None

class IBKRClient:
    def __init__(self):
        self.ib = IB() if IB else None

    async def connect(self):
        if self.ib is None:
            raise RuntimeError("Install dependencies first: pip install -r requirements.txt")
        if not self.ib.isConnected():
            await self.ib.connectAsync(settings.ib_host, settings.ib_port, clientId=settings.ib_client_id)

    async def disconnect(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()

    async def historical_bars(self, symbol=None):
        await self.connect()
        contract = Stock(symbol or settings.symbol, settings.exchange, settings.currency)
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified:
            raise RuntimeError(f"Contract not found: {symbol or settings.symbol}")
        bars = await self.ib.reqHistoricalDataAsync(contract, endDateTime="", durationStr=settings.history_duration,
            barSizeSetting=settings.timeframe, whatToShow="TRADES", useRTH=True, formatDate=1, keepUpToDate=False)
        df = pd.DataFrame([b.__dict__ for b in bars])
        if df.empty:
            raise RuntimeError("IBKR returned no historical bars")
        df = df.rename(columns={"date": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    async def place_market_order(self, symbol, action, quantity):
        if settings.paper_trading:
            raise RuntimeError("Paper trading mode: real order submission is disabled")
        await self.connect()
        contract = Stock(symbol, settings.exchange, settings.currency)
        await self.ib.qualifyContractsAsync(contract)
        return self.ib.placeOrder(contract, MarketOrder(action, quantity))

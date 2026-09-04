from __future__ import annotations
##//*from ib_async import IB, Stock, MarketOrder##
import pandas as pd
from app.config import settings

try:
    from ib_async import IB, Stock, MarketOrder
except ImportError:
    IB = Stock = MarketOrder = None


class IBKRClient:
    """IBKR market-data and PAPER-account order client."""

    def __init__(self):
        self.ib = IB() if IB else None

    async def connect(self):
        if self.ib is None:
            raise RuntimeError("Install dependencies first: pip install -r requirements.txt")
        if settings.paper_trading and settings.ib_port not in (7497, 4002):
            raise RuntimeError(f"Paper trading requires TWS 7497 or IB Gateway 4002; current port={settings.ib_port}")
        if not self.ib.isConnected():
            await self.ib.connectAsync(settings.ib_host, settings.ib_port, clientId=settings.ib_client_id, timeout=10)

    async def disconnect(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()

    async def account_value(self) -> float:
        await self.connect()
        values = await self.ib.accountSummaryAsync()
        for item in values:
            if item.tag == "NetLiquidation" and (not settings.account or item.account == settings.account):
                return float(item.value)
        raise RuntimeError("NetLiquidation was not available")

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

    async def current_position(self, symbol: str) -> float:
        await self.connect()
        for position in self.ib.positions():
            contract = getattr(position, "contract", None)
            if contract and contract.symbol.upper() == symbol.upper():
                return float(position.position)
        return 0.0

    async def place_market_order(self, symbol: str, action: str, quantity: int):
        if not settings.paper_trading:
            raise RuntimeError("Live trading is disabled by design in this version")
        if quantity <= 0:
            raise ValueError("Order quantity must be positive")
        await self.connect()
        contract = Stock(symbol.upper(), settings.exchange, settings.currency)
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified:
            raise RuntimeError(f"Contract not found: {symbol}")
        order = MarketOrder(action.upper(), int(quantity), transmit=True)
        return self.ib.placeOrder(contract, order)

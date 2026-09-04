from __future__ import annotations

import pandas as pd
from app.config import settings

try:
    from ib_async import IB, Stock, MarketOrder
except ImportError:
    IB = Stock = MarketOrder = None


class IBKRClient:
    """IBKR market-data and order client.

    This project is configured for an IBKR PAPER account by default.
    When paper_trading=True, only the standard paper API ports are accepted:
    TWS 7497 or IB Gateway 4002.
    """

    def __init__(self):
        self.ib = IB() if IB else None

    async def connect(self):
        if self.ib is None:
            raise RuntimeError("Install dependencies first: pip install -r requirements.txt")
        if settings.paper_trading and settings.ib_port not in (7497, 4002):
            raise RuntimeError(
                f"Paper trading is enabled, but IB_PORT={settings.ib_port}. "
                "Use TWS paper port 7497 or IB Gateway paper port 4002."
            )
        if not self.ib.isConnected():
            await self.ib.connectAsync(
                settings.ib_host,
                settings.ib_port,
                clientId=settings.ib_client_id,
            )

    async def disconnect(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()

    async def historical_bars(self, symbol=None):
        await self.connect()
        contract = Stock(symbol or settings.symbol, settings.exchange, settings.currency)
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified:
            raise RuntimeError(f"Contract not found: {symbol or settings.symbol}")
        bars = await self.ib.reqHistoricalDataAsync(
            contract,
            endDateTime="",
            durationStr=settings.history_duration,
            barSizeSetting=settings.timeframe,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
        )
        df = pd.DataFrame([b.__dict__ for b in bars])
        if df.empty:
            raise RuntimeError("IBKR returned no historical bars")
        df = df.rename(columns={"date": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    async def current_position(self, symbol: str) -> float:
        await self.connect()
        symbol = symbol.upper()
        for position in self.ib.positions():
            contract = getattr(position, "contract", None)
            if contract and contract.symbol.upper() == symbol:
                return float(position.position)
        return 0.0

    async def place_market_order(self, symbol: str, action: str, quantity: int):
        if not settings.paper_trading:
            raise RuntimeError(
                "Live trading is intentionally disabled in this version. "
                "Set up a separate reviewed live-trading configuration before enabling it."
            )
        if quantity <= 0:
            raise ValueError("Order quantity must be positive")

        await self.connect()
        contract = Stock(symbol.upper(), settings.exchange, settings.currency)
        qualified = await self.ib.qualifyContractsAsync(contract)
        if not qualified:
            raise RuntimeError(f"Contract not found: {symbol}")

        order = MarketOrder(action.upper(), int(quantity), transmit=True)
        trade = self.ib.placeOrder(contract, order)
        return trade

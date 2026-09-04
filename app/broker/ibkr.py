from __future__ import annotations

import pandas as pd

from app.config import settings

try:
    from ib_async import (
        IB,
        Stock,
        MarketOrder,
        LimitOrder,
    )
except ImportError:
    IB = None
    Stock = None
    MarketOrder = None
    LimitOrder = None


class IBKRClient:
    """
    IBKR client.

    يستخدم:
    - Market Data
    - Historical Data
    - Account information
    - Current positions
    - Paper Trading orders

    Live trading غير مسموح به في هذه النسخة.
    """

    def __init__(self):
        self.ib = IB() if IB else None

    # =========================================================
    # CONNECTION
    # =========================================================

    async def connect(self):

        if self.ib is None:
            raise RuntimeError(
                "ib_async is not installed. "
                "Run: pip install -r requirements.txt"
            )

        # حماية إضافية:
        # Paper Trading يجب أن يستخدم 7497 أو 4002
        if settings.paper_trading:

            if settings.ib_port not in (7497, 4002):
                raise RuntimeError(
                    "Paper trading requires TWS port 7497 "
                    "or IB Gateway port 4002. "
                    f"Current port={settings.ib_port}"
                )

        if not self.ib.isConnected():

            await self.ib.connectAsync(
                settings.ib_host,
                settings.ib_port,
                clientId=settings.ib_client_id,
                timeout=10,
            )

    # =========================================================
    # DISCONNECT
    # =========================================================

    async def disconnect(self):

        if self.ib and self.ib.isConnected():
            self.ib.disconnect()

    # =========================================================
    # ACCOUNT VALUE
    # =========================================================

    async def account_value(self) -> float:

        await self.connect()

        values = await self.ib.accountSummaryAsync()

        for item in values:

            if item.tag != "NetLiquidation":
                continue

            if settings.account:
                if item.account != settings.account:
                    continue

            return float(item.value)

        raise RuntimeError(
            "NetLiquidation was not available from IBKR"
        )

    # =========================================================
    # HISTORICAL MARKET DATA
    # =========================================================

    async def historical_bars(
        self,
        symbol: str | None = None,
    ):

        await self.connect()

        symbol = symbol or settings.symbol

        contract = Stock(
            symbol.upper(),
            settings.exchange,
            settings.currency,
        )

        qualified = await self.ib.qualifyContractsAsync(
            contract
        )

        if not qualified:
            raise RuntimeError(
                f"Contract not found: {symbol}"
            )

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

        if not bars:
            raise RuntimeError(
                f"IBKR returned no historical bars for {symbol}"
            )

        df = pd.DataFrame(
            [bar.__dict__ for bar in bars]
        )

        if df.empty:
            raise RuntimeError(
                f"Historical data is empty for {symbol}"
            )

        # IBKR يستخدم date
        # النظام الداخلي يستخدم timestamp

        if "date" in df.columns:

            df = df.rename(
                columns={
                    "date": "timestamp"
                }
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        )

        required_columns = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        missing = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing:
            raise RuntimeError(
                f"Missing IBKR columns: {missing}"
            )

        return df[required_columns].copy()

    # =========================================================
    # CURRENT POSITION
    # =========================================================

    async def current_position(
        self,
        symbol: str,
    ) -> float:

        await self.connect()

        positions = self.ib.positions()

        for position in positions:

            contract = getattr(
                position,
                "contract",
                None,
            )

            if not contract:
                continue

            position_symbol = getattr(
                contract,
                "symbol",
                "",
            )

            if position_symbol.upper() == symbol.upper():

                return float(
                    position.position
                )

        return 0.0

    # =========================================================
    # MARKET PRICE
    # =========================================================

    async def market_price(
        self,
        symbol: str,
    ) -> float:

        await self.connect()

        contract = Stock(
            symbol.upper(),
            settings.exchange,
            settings.currency,
        )

        qualified = await self.ib.qualifyContractsAsync(
            contract
        )

        if not qualified:
            raise RuntimeError(
                f"Contract not found: {symbol}"
            )

        ticker = self.ib.reqMktData(
            contract,
            "",
            False,
            False,
        )

        # السماح للـticker بالوصول
        await self.ib.sleep(1)

        price = ticker.marketPrice()

        if price is None or pd.isna(price):

            # محاولة استخدام last
            price = ticker.last

        if price is None or pd.isna(price):

            # محاولة استخدام close
            price = ticker.close

        if price is None or pd.isna(price):

            raise RuntimeError(
                f"No market price available for {symbol}"
            )

        return float(price)

    # =========================================================
    # MARKET ORDER
    # =========================================================

    async def place_market_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
    ):

        # Live trading ممنوع
        if not settings.paper_trading:

            raise RuntimeError(
                "Live trading is disabled by design "
                "in this version."
            )

        if quantity <= 0:
            raise ValueError(
                "Order quantity must be positive"
            )

        await self.connect()

        contract = Stock(
            symbol.upper(),
            settings.exchange,
            settings.currency,
        )

        qualified = await self.ib.qualifyContractsAsync(
            contract
        )

        if not qualified:

            raise RuntimeError(
                f"Contract not found: {symbol}"
            )

        order = MarketOrder(
            action.upper(),
            int(quantity),
            transmit=True,
        )

        return self.ib.placeOrder(
            contract,
            order,
        )

    # =========================================================
    # LIMIT BUY / SELL ORDER
    # =========================================================

    async def place_limit_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
    ):

        # Live trading ممنوع
        if not settings.paper_trading:

            raise RuntimeError(
                "Live trading is disabled by design "
                "in this version."
            )

        if quantity <= 0:

            raise ValueError(
                "Order quantity must be positive"
            )

        if limit_price <= 0:

            raise ValueError(
                "Limit price must be positive"
            )

        await self.connect()

        contract = Stock(
            symbol.upper(),
            settings.exchange,
            settings.currency,
        )

        qualified = await self.ib.qualifyContractsAsync(
            contract
        )

        if not qualified:

            raise RuntimeError(
                f"Contract not found: {symbol}"
            )

        # Limit Order
        order = LimitOrder(
            action.upper(),
            int(quantity),
            float(limit_price),
            transmit=True,
        )

        trade = self.ib.placeOrder(
            contract,
            order,
        )

        return trade

    # =========================================================
    # CANCEL ORDER
    # =========================================================

    async def cancel_order(
        self,
        trade,
    ):

        await self.connect()

        if trade is None:
            return

        order = getattr(
            trade,
            "order",
            None,
        )

        if order is None:
            return

        self.ib.cancelOrder(order)

    # =========================================================
    # OPEN ORDERS
    # =========================================================

    async def open_orders(self):

        await self.connect()

        return self.ib.openOrders()

    # =========================================================
    # ORDER STATUS
    # =========================================================

    def order_status(
        self,
        trade,
    ):

        if trade is None:
            return None

        status = getattr(
            trade,
            "orderStatus",
            None,
        )

        if status is None:
            return None

        return getattr(
            status,
            "status",
            None,
        )

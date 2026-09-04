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

    def __init__(self):

        self.ib = IB() if IB else None

    # =====================================================
    # CONNECTION
    # =====================================================

    async def connect(self):

        if self.ib is None:

            raise RuntimeError(
                "ib_async is not installed. "
                "Run: pip install -r requirements.txt"
            )

        # Paper trading only
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

    # =====================================================
    # DISCONNECT
    # =====================================================

    async def disconnect(self):

        if self.ib and self.ib.isConnected():

            self.ib.disconnect()

    # =====================================================
    # ACCOUNT VALUE
    # =====================================================

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

    # =====================================================
    # HISTORICAL DATA
    # =====================================================

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

        if "date" in df.columns:

            df = df.rename(
                columns={
                    "date": "timestamp"
                }
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"]
        )

        required = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        missing = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing:

            raise RuntimeError(
                f"Missing IBKR columns: {missing}"
            )

        return df[required].copy()

    # =====================================================
    # SINGLE POSITION
    # =====================================================

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

    # =====================================================
    # FULL PORTFOLIO POSITIONS
    # =====================================================

    async def portfolio_positions(self):

        """
        قراءة جديدة للمحفظة من IBKR.

        نرجع فقط الـpositions التي تحتوي على كمية
        غير صفرية.
        """

        await self.connect()

        positions = []

        for position in self.ib.positions():

            quantity = float(
                getattr(
                    position,
                    "position",
                    0,
                )
                or 0
            )

            contract = getattr(
                position,
                "contract",
                None,
            )

            symbol = (
                getattr(
                    contract,
                    "symbol",
                    "",
                )
                if contract
                else ""
            )

            if symbol and quantity != 0:

                positions.append(
                    {
                        "symbol": symbol.upper(),
                        "quantity": quantity,
                    }
                )

        return positions

    # =====================================================
    # ACTIVE TRADE COUNT
    # =====================================================

    async def active_trade_count(self) -> int:

        """
        حساب عدد الـslots المستخدمة.

        Position موجود = slot

        BUY Limit مفتوح = slot

        الهدف منع البوت من إرسال 7 أوامر جديدة
        بينما توجد أوامر قديمة لم تنفذ بعد.
        """

        positions = await self.portfolio_positions()

        open_orders = await self.open_orders()

        position_symbols = {
            position["symbol"]
            for position in positions
        }

        pending_symbols = set()

        for trade in open_orders:

            contract = getattr(
                trade,
                "contract",
                None,
            )

            symbol = (
                getattr(
                    contract,
                    "symbol",
                    "",
                )
                if contract
                else ""
            )

            order = getattr(
                trade,
                "order",
                None,
            )

            action = (
                str(
                    getattr(
                        order,
                        "action",
                        "",
                    )
                )
                if order
                else ""
            )

            status = self.order_status(
                trade
            )

            if (

                symbol

                and action == "BUY"

                and status not in (
                    "Filled",
                    "Cancelled",
                    "Inactive",
                    "ApiCancelled",
                )

            ):

                pending_symbols.add(
                    symbol.upper()
                )

        return len(
            position_symbols
            | pending_symbols
        )

    # =====================================================
    # CURRENT MARKET PRICE
    # =====================================================

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

        await self.ib.sleep(1)

        price = ticker.marketPrice()

        if price is None or pd.isna(price):

            price = ticker.last

        if price is None or pd.isna(price):

            price = ticker.close

        if price is None or pd.isna(price):

            raise RuntimeError(
                f"No market price available for {symbol}"
            )

        return float(price)

    # =====================================================
    # MARKET ORDER
    # =====================================================

    async def place_market_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
    ):

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

    # =====================================================
    # LIMIT ORDER
    # =====================================================

    async def place_limit_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
    ):

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

    # =====================================================
    # CANCEL ORDER
    # =====================================================

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

        if order is not None:

            self.ib.cancelOrder(
                order
            )

    # =====================================================
    # OPEN ORDERS
    # =====================================================

    async def open_orders(self):

        await self.connect()

        # طلب snapshot جديد من IBKR
        return await self.ib.reqAllOpenOrdersAsync()

    # =====================================================
    # ORDER STATUS
    # =====================================================

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

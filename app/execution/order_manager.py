from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.config import settings


@dataclass
class OrderRecord:

    time: str

    symbol: str

    action: str

    quantity: int

    # السعر الحالي
    market_price: float

    # سعر Limit
    entry_limit: float

    # Stop Loss
    stop: float | None

    # Take Profit
    target: float | None

    status: str

    order_id: str = ""


class OrderManager:

    def __init__(self, broker):

        self.broker = broker

        self.records: list[
            OrderRecord
        ] = []

        # آخر إشارة تم تنفيذها
        self.last_signal_key: str | None = None

        # الإشارات الموجودة داخل البوت
        # ولم يسمح لها بعد بالخروج إلى IBKR
        self.pending_signals: dict[
            str,
            object
        ] = {}

    # =====================================================
    # VERIFY BEFORE ORDER
    # =====================================================

    async def can_open_trade(
        self,
        symbol: str,
    ) -> tuple[bool, str]:

        symbol = symbol.upper()

        # -------------------------------------------------
        # قراءة المحفظة
        # -------------------------------------------------

        positions = (
            await self.broker.portfolio_positions()
        )

        # -------------------------------------------------
        # لا نسمح بسهم موجود مسبقًا
        # -------------------------------------------------

        for position in positions:

            if (

                position["symbol"] == symbol

                and position["quantity"] != 0

            ):

                return (
                    False,
                    f"Position already exists: {symbol}"
                )

        # -------------------------------------------------
        # قراءة عدد الصفقات النشطة
        # -------------------------------------------------

        active = (
            await self.broker.active_trade_count()
        )

        if active >= settings.max_active_trades:

            return (
                False,
                (
                    f"Trade limit reached: "
                    f"{active}/"
                    f"{settings.max_active_trades}. "
                    "Order kept inside bot."
                )
            )

        # -------------------------------------------------
        # قراءة المحفظة مرة ثانية
        #
        # هذا الفحص يتم مباشرة قبل الإرسال
        # -------------------------------------------------

        positions_again = (
            await self.broker.portfolio_positions()
        )

        for position in positions_again:

            if (

                position["symbol"] == symbol

                and position["quantity"] != 0

            ):

                return (
                    False,
                    (
                        "Position appeared "
                        f"before send: {symbol}"
                    )
                )

        # -------------------------------------------------
        # فحص العدد مرة ثانية
        # -------------------------------------------------

        active_again = (
            await self.broker.active_trade_count()
        )

        if active_again >= settings.max_active_trades:

            return (
                False,
                (
                    "Trade limit reached "
                    "before send: "
                    f"{active_again}/"
                    f"{settings.max_active_trades}. "
                    "Order kept inside bot."
                )
            )

        return True, "OK"

    # =====================================================
    # SUBMIT SIGNAL
    # =====================================================

    async def submit_signal(
        self,
        symbol,
        signal,
    ):

        # =================================================
        # BUY ONLY
        # =================================================

        if signal.action != "BUY":

            return None

        if not signal.stop:

            return None

        # =================================================
        # SIGNAL KEY
        # =================================================

        key = (

            f"{symbol}:"

            f"{signal.action}:"

            f"{signal.entry:.6f}:"

            f"{signal.stop:.6f}"
        )

        if key == self.last_signal_key:

            return None

        # =================================================
        # وضع الإشارة داخل البوت أولًا
        #
        # لا يتم إرسالها إلى IBKR هنا
        # إلا بعد اجتياز الفحص
        # =================================================

        self.pending_signals[
            symbol.upper()
        ] = signal

        # =================================================
        # VERIFY
        # =================================================

        allowed, reason = (
            await self.can_open_trade(
                symbol
            )
        )

        if not allowed:

            # تبقى الإشارة داخل البوت
            return None

        # =================================================
        # QUANTITY
        # =================================================

        quantity = int(
            settings.fixed_quantity
        )

        if quantity <= 0:

            return None

        # =================================================
        # CURRENT / REFERENCE PRICE
        # =================================================

        market_price = float(
            signal.entry
        )

        # =================================================
        # ENTRY
        #
        # 10 CENT BELOW CURRENT PRICE
        #
        # 18.60 -> 18.50
        # =================================================

        entry_limit = round(
            market_price - 0.10,
            2
        )

        # =================================================
        # TAKE PROFIT
        #
        # Default = 10%
        #
        # 18.50 -> 20.35
        # =================================================

        target = round(

            entry_limit
            *
            (
                1.0
                +
                settings.take_profit_percent
                / 100.0
            ),

            2
        )

        # =================================================
        # SEND TO IBKR
        #
        # THIS IS THE ONLY PLACE WHERE THE ORDER
        # LEAVES THE BOT.
        # =================================================

        trade = (
            await self.broker.place_limit_order(

                symbol,

                "BUY",

                quantity,

                entry_limit,
            )
        )

        # =================================================
        # ORDER ID
        # =================================================

        order_id = str(

            getattr(

                getattr(

                    trade,

                    "order",

                    None,
                ),

                "orderId",

                "",
            )
        )

        # =================================================
        # RECORD
        # =================================================

        record = OrderRecord(

            time=datetime.now().isoformat(
                timespec="seconds"
            ),

            symbol=symbol,

            action="BUY",

            quantity=quantity,

            market_price=market_price,

            entry_limit=entry_limit,

            stop=float(
                signal.stop
            ),

            target=target,

            status="SUBMITTED",

            order_id=order_id,
        )

        self.records.append(
            record
        )

        self.last_signal_key = key

        # تم إرسال الإشارة
        self.pending_signals.pop(
            symbol.upper(),
            None
        )

        return record

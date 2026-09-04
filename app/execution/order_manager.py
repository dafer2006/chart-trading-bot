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

    # السعر الحالي وقت ظهور الإشارة
    market_price: float

    # سعر الدخول المحدد
    entry_limit: float

    # وقف الخسارة
    stop: float | None

    # جني الأرباح
    target: float | None

    status: str

    order_id: str = ""


class OrderManager:

    def __init__(self, broker):

        self.broker = broker

        self.records: list[OrderRecord] = []

        # منع إرسال نفس الإشارة أكثر من مرة
        self.last_signal_key: str | None = None


    async def submit_signal(self, symbol, signal):

        # =====================================================
        # نفتح BUY فقط
        # =====================================================

        if signal.action != "BUY":
            return None

        if not signal.stop:
            return None


        # =====================================================
        # منع تكرار نفس الصفقة
        # =====================================================

        key = (
            f"{symbol}:"
            f"{signal.action}:"
            f"{signal.entry:.6f}:"
            f"{signal.stop:.6f}"
        )

        if key == self.last_signal_key:
            return None


        # =====================================================
        # كمية الأسهم
        #
        # الافتراضي 100
        # ويمكن تغييرها من الواجهة
        # =====================================================

        quantity = int(settings.fixed_quantity)

        if quantity <= 0:
            return None


        # =====================================================
        # السعر الحالي
        # =====================================================

        market_price = float(signal.entry)


        # =====================================================
        # سعر الدخول
        #
        # أقل من السعر الحالي بـ 0.10 دولار
        #
        # مثال:
        #
        # السعر الحالي = 18.60
        # الدخول       = 18.50
        #
        # =====================================================

        entry_limit = round(
            market_price - 0.10,
            2
        )


        # =====================================================
        # Take Profit
        #
        # الافتراضي 10%
        #
        # مثال:
        #
        # Entry = 18.50
        # TP    = 20.35
        #
        # =====================================================

        target = round(
            entry_limit
            * (
                1.0
                + settings.take_profit_percent / 100.0
            ),
            2
        )


        # =====================================================
        # إرسال LIMIT BUY إلى IBKR Paper
        # =====================================================

        trade = await self.broker.place_limit_order(
            symbol,
            "BUY",
            quantity,
            entry_limit
        )


        # =====================================================
        # Order ID
        # =====================================================

        order_id = str(
            getattr(
                getattr(
                    trade,
                    "order",
                    None
                ),
                "orderId",
                ""
            )
        )


        # =====================================================
        # تسجيل الصفقة
        # =====================================================

        record = OrderRecord(

            time=datetime.now().isoformat(
                timespec="seconds"
            ),

            symbol=symbol,

            action="BUY",

            quantity=quantity,

            market_price=market_price,

            entry_limit=entry_limit,

            stop=float(signal.stop),

            target=target,

            status="SUBMITTED",

            order_id=order_id,
        )


        self.records.append(record)

        self.last_signal_key = key

        return record

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
    market_price: float
    entry_limit: float
    stop: float | None
    target: float | None
    status: str
    order_id: str = ""


class OrderManager:
    def __init__(self, broker):
        self.broker = broker
        self.records: list[OrderRecord] = []
        self.last_signal_key: str | None = None

    async def submit_signal(self, symbol, signal):

        # نفتح BUY فقط
        if signal.action != "BUY":
            return None

        if not signal.stop:
            return None

        # منع تكرار نفس الإشارة
        key = (
            f"{symbol}:"
            f"{signal.action}:"
            f"{signal.entry:.6f}:"
            f"{signal.stop:.6f}"
        )

        if key == self.last_signal_key:
            return None

        # كمية الأسهم من إعدادات البرنامج
        qty = int(settings.fixed_quantity)

        if qty <= 0:
            return None

        # السعر الحالي / المرجعي الذي جاء من التحليل
        market_price = float(signal.entry)

        # الدخول أقل من السعر الحالي بـ 0.10 دولار
        entry_limit = round(market_price - 0.10, 2)

        # جني الأرباح الافتراضي 10%
        target = round(
            entry_limit
            * (1.0 + settings.take_profit_percent / 100.0),
            2
        )

        # إرسال Limit Order إلى IBKR Paper
        trade = await self.broker.place_limit_order(
            symbol,
            "BUY",
            qty,
            entry_limit
        )

        order_id = str(
            getattr(
                getattr(trade, "order", None),
                "orderId",
                ""
            )
        )

        record = OrderRecord(
            time=datetime.now().isoformat(timespec="seconds"),
            symbol=symbol,
            action="BUY",
            quantity=qty,
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

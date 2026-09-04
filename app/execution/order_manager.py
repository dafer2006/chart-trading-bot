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
    entry: float
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
        if signal.action != "BUY" or not signal.stop:
            return None
        key = f"{symbol}:{signal.action}:{signal.entry:.6f}:{signal.stop:.6f}"
        if key == self.last_signal_key:
            return None

        # Fixed quantity is the default. The GUI can change it at runtime.
        qty = int(settings.fixed_quantity)
        if qty <= 0:
            return None

        entry = float(signal.entry)
        target = entry * (1.0 + settings.take_profit_percent / 100.0)
        trade = await self.broker.place_market_order(symbol, "BUY", qty)
        order_id = str(getattr(getattr(trade, "order", None), "orderId", ""))
        record = OrderRecord(
            datetime.now().isoformat(timespec="seconds"), symbol, "BUY", qty,
            entry, float(signal.stop), target, "SUBMITTED", order_id
        )
        self.records.append(record)
        self.last_signal_key = key
        return record

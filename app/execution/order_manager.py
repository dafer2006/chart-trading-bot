from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from app.config import settings
from app.risk.manager import position_size

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
        if signal.action not in ("BUY", "SELL") or not signal.stop:
            return None
        key = f"{symbol}:{signal.action}:{signal.entry:.6f}:{signal.stop:.6f}"
        if key == self.last_signal_key:
            return None
        account = await self.broker.account_value()
        qty = position_size(account, signal.entry, signal.stop, settings.risk_per_trade)
        if qty <= 0:
            return None
        trade = await self.broker.place_market_order(symbol, signal.action, qty)
        order_id = str(getattr(getattr(trade, "order", None), "orderId", ""))
        record = OrderRecord(datetime.now().isoformat(timespec="seconds"), symbol, signal.action, qty,
                            signal.entry, signal.stop, signal.target, "SUBMITTED", order_id)
        self.records.append(record)
        self.last_signal_key = key
        return record

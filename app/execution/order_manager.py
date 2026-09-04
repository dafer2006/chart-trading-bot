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
    """Gate every order through a fresh broker-side portfolio check."""

    def __init__(self, broker):
        self.broker = broker
        self.records: list[OrderRecord] = []
        self.last_signal_key: str | None = None
        self.pending_signals: dict[str, object] = {}

    async def can_open_trade(self, symbol: str) -> tuple[bool, str]:
        """Read positions/open orders immediately before sending anything."""
        positions = await self.broker.portfolio_positions()
        symbol = symbol.upper()

        for position in positions:
            if position["symbol"] == symbol and position["quantity"] != 0:
                return False, f"Position already exists: {symbol}"

        active = await self.broker.active_trade_count()
        if active >= settings.max_active_trades:
            return False, (
                f"Trade limit reached: {active}/{settings.max_active_trades}. "
                "Order kept inside bot."
            )

        # A second fresh position check is intentionally performed before the
        # broker call. The worker is single-threaded for order submission, so
        # this closes the gap between the gate and the actual send.
        positions_again = await self.broker.portfolio_positions()
        for position in positions_again:
            if position["symbol"] == symbol and position["quantity"] != 0:
                return False, f"Position appeared before send: {symbol}"

        active_again = await self.broker.active_trade_count()
        if active_again >= settings.max_active_trades:
            return False, (
                f"Trade limit reached before send: "
                f"{active_again}/{settings.max_active_trades}. "
                "Order kept inside bot."
            )

        return True, "OK"

    async def submit_signal(self, symbol, signal):
        if signal.action != "BUY" or not signal.stop:
            return None

        key = f"{symbol}:{signal.action}:{signal.entry:.6f}:{signal.stop:.6f}"
        if key == self.last_signal_key:
            return None

        # Keep the signal internally until the fresh portfolio gate approves it.
        self.pending_signals[symbol.upper()] = signal

        allowed, reason = await self.can_open_trade(symbol)
        if not allowed:
            return None

        quantity = int(settings.fixed_quantity)
        if quantity <= 0:
            return None

        market_price = float(signal.entry)
        entry_limit = round(market_price - 0.10, 2)
        target = round(
            entry_limit * (1.0 + settings.take_profit_percent / 100.0),
            2,
        )

        # Only here, after the fresh portfolio/order checks, is anything sent
        # to IBKR Paper.
        trade = await self.broker.place_limit_order(
            symbol,
            "BUY",
            quantity,
            entry_limit,
        )

        order_id = str(
            getattr(
                getattr(trade, "order", None),
                "orderId",
                "",
            )
        )

        record = OrderRecord(
            time=datetime.now().isoformat(timespec="seconds"),
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
        self.pending_signals.pop(symbol.upper(), None)
        return record

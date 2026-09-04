from __future__ import annotations

import asyncio
import logging
from app.broker.ibkr import IBKRClient
from app.analysis.indicators import add_indicators
from app.analysis.chart_engine import add_chart_indicators, chart_context
from app.strategy.chart_strategy import evaluate_chart
from app.risk.manager import position_size
from app.config import settings

log = logging.getLogger(__name__)


class MarketMonitor:
    def __init__(self, symbol: str, interval_seconds: int = 60):
        self.symbol = symbol.upper()
        self.interval_seconds = interval_seconds
        self.client = IBKRClient()
        self.running = False
        self.last_signal_bar = None

    async def scan_once(self):
        df = await self.client.historical_bars(self.symbol)
        df = add_indicators(df)
        df = add_chart_indicators(df)
        signal = evaluate_chart(df)
        context = chart_context(df)
        log.info(
            "%s | %s | score=%s | entry=%.4f | stop=%s | target=%s",
            self.symbol, signal.action, signal.score, signal.entry, signal.stop, signal.target,
        )
        log.info("%s | chart=%s | reasons=%s", self.symbol, context, " ; ".join(signal.reasons))

        # Paper-account execution: one order at most per signal bar and no stacking.
        bar_time = df.iloc[-1].timestamp
        if signal.action == "BUY" and self.last_signal_bar != bar_time:
            current_position = await self.client.current_position(self.symbol)
            if current_position <= 0 and signal.stop is not None:
                qty = position_size(
                    settings.paper_account_value,
                    signal.entry,
                    signal.stop,
                    settings.risk_per_trade,
                )
                if qty > 0:
                    trade = await self.client.place_market_order(self.symbol, "BUY", qty)
                    self.last_signal_bar = bar_time
                    order_id = getattr(getattr(trade, "order", None), "orderId", "?")
                    log.warning(
                        "PAPER ORDER SUBMITTED | %s BUY %s shares | entry~%.4f | stop=%.4f | target=%.4f | order=%s",
                        self.symbol, qty, signal.entry, signal.stop, signal.target or 0, order_id,
                    )
                else:
                    log.warning("BUY signal rejected by position sizing: quantity=0")
            elif current_position > 0:
                log.info("BUY ignored: existing %s position = %.2f shares", self.symbol, current_position)

        return signal, context

    async def run(self):
        self.running = True
        try:
            while self.running:
                try:
                    await self.scan_once()
                except Exception:
                    log.exception("Market scan failed for %s", self.symbol)
                await asyncio.sleep(self.interval_seconds)
        finally:
            await self.client.disconnect()

    def stop(self):
        self.running = False

from __future__ import annotations
import asyncio
import logging
from app.broker.ibkr import IBKRClient
from app.analysis.indicators import add_indicators
from app.analysis.chart_engine import add_chart_indicators, chart_context
from app.strategy.chart_strategy import evaluate_chart

log = logging.getLogger(__name__)

class MarketMonitor:
    def __init__(self, symbol: str, interval_seconds: int = 60):
        self.symbol = symbol
        self.interval_seconds = interval_seconds
        self.client = IBKRClient()
        self.running = False

    async def scan_once(self):
        df = await self.client.historical_bars(self.symbol)
        df = add_indicators(df)
        df = add_chart_indicators(df)
        signal = evaluate_chart(df)
        context = chart_context(df)
        log.info("%s | %s | score=%s | entry=%.4f | stop=%s | target=%s", self.symbol, signal.action, signal.score, signal.entry, signal.stop, signal.target)
        log.info("%s | chart=%s | reasons=%s", self.symbol, context, " ; ".join(signal.reasons))
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

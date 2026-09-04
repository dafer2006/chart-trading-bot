from __future__ import annotations
import asyncio
import logging
from app.broker.ibkr import IBKRClient
from app.analysis.indicators import add_indicators
from app.analysis.patterns import detect_patterns
from app.strategy.signal import analyze

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
        signal = analyze(df)
        patterns = detect_patterns(df)
        log.info("%s | %s | score=%s | patterns=%s", self.symbol, signal.action, signal.score, patterns)
        return signal, patterns

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

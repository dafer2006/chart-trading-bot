from __future__ import annotations

import asyncio
from PySide6.QtCore import QObject, Signal, Slot
from app.analysis.indicators import add_indicators
from app.analysis.chart_engine import add_chart_indicators, chart_context
from app.strategy.chart_strategy import evaluate_chart
from app.execution.order_manager import OrderManager
from app.broker.ibkr import IBKRClient
from app.scanner import load_watchlist, top_gainers, merge_candidates
from app.config import settings


class ScannerWorker(QObject):
    status = Signal(str)
    scan = Signal(object)
    order = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, interval: int = 60):
        super().__init__()
        self.interval = interval
        self.running = False
        self.client = IBKRClient()
        self.orders = OrderManager(self.client)
        self.semaphore = asyncio.Semaphore(4)

    @Slot()
    def run(self):
        asyncio.run(self._run())

    async def analyze_symbol(self, symbol: str):
        async with self.semaphore:
            try:
                df = await self.client.historical_bars(symbol)
                df = add_indicators(df)
                df = add_chart_indicators(df)
                signal = evaluate_chart(df)
                context = chart_context(df)
                return symbol, signal, context, None
            except Exception as exc:
                return symbol, None, None, str(exc)

    async def _run(self):
        self.running = True
        try:
            await self.client.connect()
            self.status.emit("Connected — background scanner active")
            while self.running:
                try:
                    gainers = await top_gainers(self.client.ib, settings.top_gainers_count)
                    custom = load_watchlist(settings.watchlist_file)
                    symbols = merge_candidates(gainers, custom)
                    self.status.emit(
                        f"Candidates={len(symbols)} | Top gainers={len(gainers)} | Custom={len(custom)} | parallel analysis=4"
                    )

                    # The IBKR scanner already ranks the strongest percentage gainers.
                    # Full chart analysis is done concurrently, with a small limit to avoid flooding the API.
                    results = await asyncio.gather(*(self.analyze_symbol(s) for s in symbols))
                    for symbol, signal, context, error in results:
                        if error:
                            self.error.emit(f"{symbol}: {error}")
                            continue
                        self.scan.emit({"symbol": symbol, "signal": signal, "context": context})

                        # Current live-paper execution is LONG-only: never open a short by accident.
                        if signal.action == "BUY" and signal.stop is not None and self.running:
                            pos = await self.client.current_position(symbol)
                            if pos == 0:
                                record = await self.orders.submit_signal(symbol, signal)
                                if record:
                                    self.order.emit(record)

                    await asyncio.sleep(self.interval)
                except Exception as exc:
                    self.error.emit(f"Scanner: {exc}")
                    await asyncio.sleep(self.interval)
        finally:
            await self.client.disconnect()
            self.status.emit("Disconnected")
            self.finished.emit()

    @Slot()
    def stop(self):
        self.running = False

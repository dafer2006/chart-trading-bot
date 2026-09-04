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

    @Slot()
    def run(self):
        asyncio.run(self._run())

    async def _run(self):
        self.running = True
        try:
            await self.client.connect()
            self.status.emit("Connected — scanning top gainers + TXT watchlist in background")
            while self.running:
                try:
                    gainers = await top_gainers(self.client.ib, settings.top_gainers_count)
                    custom = load_watchlist(settings.watchlist_file)
                    symbols = merge_candidates(gainers, custom)
                    self.status.emit(f"Scanning {len(symbols)} symbols | gainers={len(gainers)} | custom={len(custom)}")
                    for symbol in symbols:
                        if not self.running:
                            break
                        try:
                            df = await self.client.historical_bars(symbol)
                            df = add_indicators(df)
                            df = add_chart_indicators(df)
                            signal = evaluate_chart(df)
                            context = chart_context(df)
                            self.scan.emit({"symbol": symbol, "signal": signal, "context": context})
                            if signal.action in ("BUY", "SELL"):
                                pos = await self.client.current_position(symbol)
                                if pos == 0:
                                    record = await self.orders.submit_signal(symbol, signal)
                                    if record:
                                        self.order.emit(record)
                        except Exception as exc:
                            self.error.emit(f"{symbol}: {exc}")
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

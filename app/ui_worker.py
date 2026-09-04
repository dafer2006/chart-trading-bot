from __future__ import annotations
import asyncio
from PySide6.QtCore import QObject, Signal, Slot
from app.analysis.indicators import add_indicators
from app.analysis.chart_engine import add_chart_indicators, chart_context
from app.strategy.chart_strategy import evaluate_chart
from app.execution.order_manager import OrderManager
from app.broker.ibkr import IBKRClient

class ScannerWorker(QObject):
    status = Signal(str)
    scan = Signal(object)
    order = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, symbol: str, interval: int = 60):
        super().__init__()
        self.symbol = symbol.upper()
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
            self.status.emit("Connected — background scanner running")
            while self.running:
                try:
                    df = await self.client.historical_bars(self.symbol)
                    df = add_indicators(df)
                    df = add_chart_indicators(df)
                    signal = evaluate_chart(df)
                    context = chart_context(df)
                    self.scan.emit({"symbol": self.symbol, "signal": signal, "context": context})
                    if signal.action in ("BUY", "SELL"):
                        pos = await self.client.current_position(self.symbol)
                        if pos == 0:
                            record = await self.orders.submit_signal(self.symbol, signal)
                            if record:
                                self.order.emit(record)
                    await asyncio.sleep(self.interval)
                except Exception as exc:
                    self.error.emit(str(exc))
                    await asyncio.sleep(self.interval)
        finally:
            await self.client.disconnect()
            self.status.emit("Disconnected")
            self.finished.emit()

    @Slot()
    def stop(self):
        self.running = False

from __future__ import annotations

import asyncio

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)

from app.analysis.indicators import (
    add_indicators,
)

from app.analysis.chart_engine import (
    add_chart_indicators,
    chart_context,
)

from app.strategy.chart_strategy import (
    evaluate_chart,
)

from app.execution.order_manager import (
    OrderManager,
)

from app.broker.ibkr import (
    IBKRClient,
)

from app.scanner import (
    load_watchlist,
    top_gainers,
    merge_candidates,
)

from app.config import settings


class ScannerWorker(QObject):

    status = Signal(str)

    scan = Signal(object)

    order = Signal(object)

    error = Signal(str)

    finished = Signal()

    def __init__(
        self,
        interval: int = 60,
    ):

        super().__init__()

        self.interval = interval

        self.running = False

        self.client = IBKRClient()

        self.orders = OrderManager(
            self.client
        )

        self.semaphore = (
            asyncio.Semaphore(4)
        )

    # =====================================================
    # START
    # =====================================================

    @Slot()
    def run(self):

        asyncio.run(
            self._run()
        )

    # =====================================================
    # ANALYZE SYMBOL
    # =====================================================

    async def analyze_symbol(
        self,
        symbol: str,
    ):

        async with self.semaphore:

            try:

                df = (
                    await self.client
                    .historical_bars(
                        symbol
                    )
                )

                df = add_indicators(
                    df
                )

                df = add_chart_indicators(
                    df
                )

                signal = evaluate_chart(
                    df
                )

                context = chart_context(
                    df
                )

                return (
                    symbol,
                    signal,
                    context,
                    None,
                )

            except Exception as exc:

                return (
                    symbol,
                    None,
                    None,
                    str(exc),
                )

    # =====================================================
    # MAIN LOOP
    # =====================================================

    async def _run(self):

        self.running = True

        try:

            await self.client.connect()

            self.status.emit(

                "Connected — "
                f"max active trades="
                f"{settings.max_active_trades}"

            )

            while self.running:

                try:

                    # =================================================
                    # 1. READ PORTFOLIO FIRST
                    # =================================================

                    positions = (
                        await self.client
                        .portfolio_positions()
                    )

                    active_count = (
                        await self.client
                        .active_trade_count()
                    )

                    self.status.emit(

                        "Portfolio verified | "
                        f"active={active_count}/"
                        f"{settings.max_active_trades} | "
                        f"positions={len(positions)}"
                    )

                    # =================================================
                    # 2. GET TOP GAINERS
                    # =================================================

                    gainers = (
                        await top_gainers(
                            self.client.ib,
                            settings.top_gainers_count,
                        )
                    )

                    # =================================================
                    # 3. CUSTOM WATCHLIST
                    # =================================================

                    custom = load_watchlist(
                        settings.watchlist_file
                    )

                    # =================================================
                    # 4. MERGE
                    # =================================================

                    symbols = merge_candidates(
                        gainers,
                        custom,
                    )

                    self.status.emit(

                        f"Candidates={len(symbols)} | "

                        f"Top gainers={len(gainers)} | "

                        f"Custom={len(custom)} | "

                        "parallel analysis=4"
                    )

                    # =================================================
                    # 5. ANALYZE
                    # =================================================

                    results = await asyncio.gather(

                        *(
                            self.analyze_symbol(
                                symbol
                            )

                            for symbol in symbols
                        )
                    )

                    # =================================================
                    # 6. PROCESS RESULTS
                    # =================================================

                    for (

                        symbol,
                        signal,
                        context,
                        error,

                    ) in results:

                        if error:

                            self.error.emit(

                                f"{symbol}: "
                                f"{error}"
                            )

                            continue

                        # =================================================
                        # SEND RESULT TO GUI
                        # =================================================

                        self.scan.emit(

                            {
                                "symbol": symbol,
                                "signal": signal,
                                "context": context,
                            }
                        )

                        if not self.running:

                            break

                        # =================================================
                        # ONLY BUY
                        # =================================================

                        if (
                            signal.action != "BUY"
                            or signal.stop is None
                        ):

                            continue

                        # =================================================
                        # INTERNAL QUEUE
                        # =================================================

                        self.status.emit(

                            f"{symbol} BUY candidate "
                            "queued — "
                            "verifying portfolio..."
                        )

                        # =================================================
                        # ORDER MANAGER
                        #
                        # هنا تتم قراءة الـPositions مرة أخرى
                        # ثم الأوامر المفتوحة
                        # ثم تحديد هل نرسل أم لا
                        # =================================================

                        record = (

                            await self.orders
                            .submit_signal(
                                symbol,
                                signal,
                            )
                        )

                        # =================================================
                        # ORDER SENT
                        # =================================================

                        if record:

                            self.order.emit(
                                record
                            )

                            self.status.emit(

                                f"ORDER SENT | "
                                f"{symbol} | "
                                f"qty={record.quantity} | "
                                f"limit="
                                f"{record.entry_limit:.2f} | "
                                f"target="
                                f"{record.target:.2f} | "
                                f"active limit="
                                f"{settings.max_active_trades}"
                            )

                        # =================================================
                        # ORDER BLOCKED
                        # =================================================

                        else:

                            active_now = (

                                await self.client
                                .active_trade_count()
                            )

                            self.status.emit(

                                f"{symbol} order kept "
                                "inside bot | "
                                f"active={active_now}/"
                                f"{settings.max_active_trades}"
                            )

                    # =================================================
                    # WAIT
                    # =================================================

                    await asyncio.sleep(
                        self.interval
                    )

                except Exception as exc:

                    self.error.emit(
                        f"Scanner: {exc}"
                    )

                    await asyncio.sleep(
                        self.interval
                    )

        finally:

            await self.client.disconnect()

            self.status.emit(
                "Disconnected"
            )

            self.finished.emit()

    # =====================================================
    # STOP
    # =====================================================

    @Slot()
    def stop(self):

        self.running = False

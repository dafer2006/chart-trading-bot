import asyncio
import logging
from app.config import settings
from app.monitor import MarketMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


async def main():
    monitor = MarketMonitor(
        settings.symbol,
        interval_seconds=settings.scan_interval_seconds,
    )
    logging.getLogger(__name__).warning(
        "IBKR PAPER TRADING ONLY | symbol=%s | port=%s | timeframe=%s",
        settings.symbol, settings.ib_port, settings.timeframe,
    )
    await monitor.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

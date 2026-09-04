import asyncio
import logging
from app.broker.ibkr import IBKRClient
from app.analysis.indicators import add_indicators
from app.strategy.signal import analyze

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

async def main():
    client = IBKRClient()
    try:
        df = await client.historical_bars()
        df = add_indicators(df)
        signal = analyze(df)
        print(f"Signal: {signal.action}")
        print(f"Score: {signal.score}")
        print(f"Entry: {signal.entry:.4f}")
        if signal.stop: print(f"Stop: {signal.stop:.4f}")
        if signal.target: print(f"Target: {signal.target:.4f}")
        print("Reasons:", ", ".join(signal.reasons))
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

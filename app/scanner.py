from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from ib_async import ScannerSubscription


@dataclass(frozen=True)
class Candidate:
    symbol: str
    rank: int
    change_percent: float


def load_watchlist(path: str = "watchlist.txt") -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip().upper() for line in f if line.strip() and not line.lstrip().startswith("#")]
    except FileNotFoundError:
        return []


async def top_gainers(ib, number: int = 10) -> list[Candidate]:
    sub = ScannerSubscription(
        instrument="STK", locationCode="STK.US.MAJOR", scanCode="TOP_PERC_GAIN",
        numberOfRows=max(number, 10), abovePrice=1.0, aboveVolume=100000,
    )
    rows = await ib.reqScannerDataAsync(sub)
    candidates: list[Candidate] = []
    for row in rows[:number]:
        contract = row.contractDetails.contract
        candidates.append(Candidate(contract.symbol, int(row.rank) + 1, 0.0))
    return candidates


def merge_candidates(gainers: Iterable[Candidate], custom: Iterable[str]) -> list[str]:
    result: list[str] = []
    for c in gainers:
        if c.symbol not in result:
            result.append(c.symbol)
    for symbol in custom:
        if symbol not in result:
            result.append(symbol)
    return result

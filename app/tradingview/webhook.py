from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.tradingview.store import TradingViewSignalStore

app = FastAPI(title="Chart Trading Bot - TradingView Webhook")
store = TradingViewSignalStore()


class TradingViewSignal(BaseModel):
    symbol: str
    action: str
    price: float | None = None
    stop: float | None = None
    target: float | None = None
    score: int = 0
    message: str | None = None


@app.get("/health")
async def health():
    return {"ok": True, "paper_trading": settings.paper_trading}


@app.post("/webhook/tradingview")
async def tradingview_webhook(
    payload: TradingViewSignal,
    x_webhook_token: str | None = Header(default=None),
):
    if not settings.tradingview_webhook_enabled:
        raise HTTPException(503, "TradingView webhook disabled")
    if settings.tradingview_webhook_token and x_webhook_token != settings.tradingview_webhook_token:
        raise HTTPException(401, "Invalid webhook token")
    action = payload.action.upper()
    if action not in {"BUY", "SELL", "HOLD"}:
        raise HTTPException(400, "Invalid action")
    if action == "BUY" and (payload.stop is None or payload.price is None):
        raise HTTPException(400, "BUY requires price and stop")
    signal_id = store.add(payload)
    return {
        "accepted": True,
        "queued": action in {"BUY", "SELL"},
        "signal_id": signal_id,
        "symbol": payload.symbol.upper(),
        "action": action,
    }

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def root():
    return FileResponse("frontend/index.html")


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.get("/api/headlines")
async def get_headlines(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    category: Optional[str] = None,
    sentiment: Optional[str] = None,
    ticker: Optional[str] = None,
    min_impact: Optional[int] = None,
    source_category: Optional[str] = None,
):
    db = request.app.state.db
    headlines = await db.get_headlines(
        limit=limit,
        offset=offset,
        category=category,
        sentiment=sentiment,
        ticker=ticker,
        min_impact=min_impact,
        source_category=source_category,
    )
    return headlines


@router.get("/api/sources/status")
async def source_status(request: Request):
    db = request.app.state.db
    return await db.get_source_states()


@router.get("/api/stats")
async def stats(request: Request):
    db = request.app.state.db
    return await db.get_today_stats()


@router.get("/api/market-context")
async def get_market_context(request: Request):
    """Return the current market snapshot."""
    mc = getattr(request.app.state, "market_context", None)
    if mc:
        snap = mc.snapshot_to_dict()
        return snap if snap else {"status": "no_data"}
    return {"status": "disabled"}


@router.get("/api/calibration/summary")
async def calibration_summary(request: Request):
    db = request.app.state.db
    return await db.get_calibration_summary()


@router.get("/api/calibration/by-impact")
async def calibration_by_impact(request: Request):
    db = request.app.state.db
    return await db.get_calibration_by_impact()


@router.get("/api/calibration/by-sentiment")
async def calibration_by_sentiment(request: Request):
    db = request.app.state.db
    return await db.get_calibration_by_sentiment()


@router.get("/api/calibration/by-signals")
async def calibration_by_signals(request: Request):
    db = request.app.state.db
    return await db.get_calibration_by_signals()


@router.get("/calibration")
async def calibration_page():
    return FileResponse("frontend/calibration.html")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if "filters" in msg:
                    ws_manager.update_client_filters(websocket, msg["filters"])
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

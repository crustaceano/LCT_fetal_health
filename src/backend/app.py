import io
import os
import csv
import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Deque, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ================== Config ==================

MODEL_API_URL = os.getenv("MODEL_API_URL", "http://localhost:8000/predict")
WINDOW_MINUTES = float(os.getenv("WINDOW_MINUTES", "5"))
THRESHOLD = float(os.getenv("PREDICT_THRESHOLD", "0.5"))
FLUSH_INTERVAL_SECONDS = int(os.getenv("FLUSH_INTERVAL_SECONDS", str(int(WINDOW_MINUTES * 60))))


# ================== Data models ==================

class IngestEvent(BaseModel):
    source: str = Field(..., description="'bpm' or 'uterus'")
    time: float = Field(..., description="seconds since start (float)")
    value: float = Field(..., description="signal value")


@dataclass
class StreamBuffers:
    bpm: Deque[Tuple[float, float]]
    uterus: Deque[Tuple[float, float]]
    window_seconds: float

    def add(self, source: str, t: float, v: float) -> None:
        q = self.bpm if source == "bpm" else self.uterus
        q.append((t, v))
        self._drop_old()

    def _drop_old(self) -> None:
        # Drop by relative t window
        window_start = max(0.0, (self.latest_time() - self.window_seconds))
        while self.bpm and self.bpm[0][0] < window_start:
            self.bpm.popleft()
        while self.uterus and self.uterus[0][0] < window_start:
            self.uterus.popleft()

    def latest_time(self) -> float:
        last_bpm = self.bpm[-1][0] if self.bpm else 0.0
        last_uter = self.uterus[-1][0] if self.uterus else 0.0
        return max(last_bpm, last_uter)

    def snapshot_csv_files(self) -> Tuple[io.BytesIO, io.BytesIO]:
        bpm_buf = io.StringIO()
        uter_buf = io.StringIO()
        bw = csv.writer(bpm_buf)
        uw = csv.writer(uter_buf)
        bw.writerow(["time", "value"])
        uw.writerow(["time", "value"])
        for t, v in self.bpm:
            bw.writerow([t, v])
        for t, v in self.uterus:
            uw.writerow([t, v])
        bpm_bytes = io.BytesIO(bpm_buf.getvalue().encode("utf-8"))
        uter_bytes = io.BytesIO(uter_buf.getvalue().encode("utf-8"))
        bpm_bytes.seek(0); uter_bytes.seek(0)
        return bpm_bytes, uter_bytes


# ================== App ==================

app = FastAPI(title="Streaming Orchestrator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

buffers = StreamBuffers(bpm=deque(), uterus=deque(), window_seconds=WINDOW_MINUTES * 60)
buffers_lock = asyncio.Lock()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(event: IngestEvent):
    if event.source not in {"bpm", "uterus"}:
        raise HTTPException(status_code=400, detail="source must be 'bpm' or 'uterus'")
    async with buffers_lock:
        buffers.add(event.source, float(event.time), float(event.value))
    return {"status": "accepted"}


async def flush_once():
    async with buffers_lock:
        bpm_file, uter_file = buffers.snapshot_csv_files()
    files = {
        "bpm": ("bpm.csv", bpm_file, "text/csv"),
        "uterus": ("uterus.csv", uter_file, "text/csv"),
    }
    params = {"threshold": THRESHOLD}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(MODEL_API_URL, files=files, params=params)
        r.raise_for_status()
        return r.json()


@app.post("/flush")
async def flush_now():
    try:
        data = await flush_once()
        return {"status": "ok", "result": data}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def _startup():
    async def _loop():
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            try:
                await flush_once()
            except Exception:
                # swallow, will try next interval
                pass
    asyncio.create_task(_loop())


@app.get("/stats")
async def stats():
    async with buffers_lock:
        latest = buffers.latest_time()
        return {
            "bpm_len": len(buffers.bpm),
            "uterus_len": len(buffers.uterus),
            "latest_time": latest,
            "window_seconds": buffers.window_seconds,
        }


# Run: uvicorn src.backend.app:app --reload --port 9000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.backend.app:app", host="0.0.0.0", port=9000, reload=True)



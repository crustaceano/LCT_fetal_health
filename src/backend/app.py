import asyncio
import os, shlex, subprocess, sys, threading, time, io, csv
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Tuple, Optional, TypedDict, Dict, List

import serial
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from db.db_hooks import set_session_pipeline, get_session_pipeline, create_session, set_session_status, \
    append_predictions_to_meta
from utils.clear_data import clean_signal
from utils.make_recommend import make_recommendations
from utils.uterus_count import count_contractions

# ==== конфигурация (жёстко, как просили) ====
BPM_PORT = "COM13"
UTR_PORT = "COM15"
BPM_EMU_PORT = "COM12"
UTR_EMU_PORT = "COM14"
BAUDRATE = 115200
EMU_CMD = '{python} emulator.py {dataset} {number} --root .\\data --bpm-port ' + BPM_EMU_PORT + ' --uterus-port ' + UTR_EMU_PORT
WS_TICK_SEC = 0.1         # как часто слать буфер по WS
DB_FLUSH_SEC = 10         # батч в БД
EXTERNAL_FLUSH_SEC = 300.0  # 5 минут

WINDOW_MINUTES = 3
WINDOW_SECONDS = WINDOW_MINUTES * 60

THRESHOLD = 0.5
MODEL_API_URL = "http://localhost:9000/predict"

class LabelInfo(TypedDict):
    proba: float
    pred: int

# ==== буферы окна ====
@dataclass
class StreamBuffers:
    bpm: Deque[Tuple[float, float]]
    uterus: Deque[Tuple[float, float]]
    window_seconds: float
    retain_all: bool = True

    def add(self, source: str, t: float, v: float) -> None:
        q = self.bpm if source == "bpm" else self.uterus
        q.append((t, v))
        if not self.retain_all:  # <— не режем историю, если включен retain_all
            self._drop_old()

    def snapshot(self):
        # копии списков для безопасной отдачи
        return list(self.bpm), list(self.uterus), self.latest_time()

    def _drop_old(self) -> None:
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

# ==== БД-операции (используйте ваши из db_ops.py) ====
# импортируйте готовые функции:

# ==== FastAPI ====
app = FastAPI(title="Fetal Demo Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)



# ==== глобальное состояние «одной» сессии ====
@dataclass
class RuntimeCtx:
    buffers: StreamBuffers = field(default_factory=lambda: StreamBuffers(deque(), deque(), WINDOW_SECONDS))
    buffers_lock = asyncio.Lock()
    new_points_q: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=10000))  # для БД
    ws_clients: set[WebSocket] = field(default_factory=set)
    analytics = []
    # управление
    stop_evt: threading.Event = field(default_factory=threading.Event)
    proc: Optional[subprocess.Popen] = None
    threads: list[threading.Thread] = field(default_factory=list)
    t0: float = 0.0
    loop: Optional[asyncio.AbstractEventLoop] = None

    # фоновые задачи
    tasks: list[asyncio.Task] = field(default_factory=list)

    # идентификаторы
    session_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    user_name: Optional[str] = None
    dataset: Optional[str] = None
    study_number: Optional[int] = None

ctx = RuntimeCtx()

# ========= помощники =========

def spawn_emulator(dataset: str, number: int, *, cwd: Optional[str] = None) -> subprocess.Popen:
    cmd_str = EMU_CMD.format(python=sys.executable, dataset=dataset, number=number)
    argv = shlex.split(cmd_str, posix=False) if os.name == "nt" else shlex.split(cmd_str)
    print(f"[emulator] {cmd_str}")
    proc = subprocess.Popen(argv, cwd=cwd or os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, text=True)

    def _log():
        if not proc.stdout:
            return
        for line in proc.stdout:
            print(f"[emulator] {line.rstrip()}")
    threading.Thread(target=_log, daemon=True).start()
    return proc

def stop_emulator(proc: Optional[subprocess.Popen]):
    if not proc:
        return
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def make_enqueue(loop: asyncio.AbstractEventLoop):
    """
    Возвращает функцию, которую можно дергать из потоков:
    - добавляет точку в буфер
    - кладёт её в очередь для БД
    """
    def enqueue(source: str, t: float, v: float):
        def _do():
            # print(source, t, v)
            ctx.buffers.add(source, t, v)
            try:
                # channel, t, v
                ctx.new_points_q.put_nowait((source, t, v))
            except asyncio.QueueFull:
                # дропаем «хвост» при перегрузе
                pass
        loop.call_soon_threadsafe(_do)
    return enqueue

def serial_reader_thread(port_name: str, baudrate: int, source: str,
                         t0_monotonic: float, stop_evt: threading.Event, enqueue_point):
    try:
        ser = serial.Serial(port_name, baudrate=baudrate, timeout=0.1)
        print(f"[serial] opened {port_name} ({source})")
    except Exception as e:
        print(f"[serial] cannot open {port_name} ({source}): {e}")
        return
    buf = bytearray()
    try:
        while not stop_evt.is_set():
            try:
                chunk = ser.read(1024)
            except serial.SerialException as e:
                print(f"[serial] read error {port_name}: {e}")
                break
            if not chunk:
                continue
            buf.extend(chunk)
            while b"\n" in buf:
                line, _, rest = buf.partition(b"\n")
                buf = bytearray(rest)
                try:
                    val = float(line.strip().decode("utf-8").rstrip("\r"))
                except Exception:
                    continue
                t = time.monotonic() - t0_monotonic
                enqueue_point(source, t, val)
    finally:
        try: ser.close()
        except Exception: pass
        print(f"[serial] closed {port_name} ({source})")


def snapshot_window(self, seconds: float | None = None):
    bpm_list = list(self.bpm)
    utr_list = list(self.uterus)
    latest = self.latest_time()
    if seconds is None:
        return bpm_list, utr_list, latest
    cutoff = max(0.0, latest - seconds)
    # фильтрация по времени
    bpm_win = [p for p in bpm_list if p[0] >= cutoff]
    utr_win = [p for p in utr_list if p[0] >= cutoff]
    return bpm_win, utr_win, latest

def session_elapsed() -> float:
    import time
    return max(0.0, time.monotonic() - (ctx.t0 or 0.0))

# ========= фоновые задачи =========

async def ws_broadcaster():
    print("[WS] broadcaster started")
    tick = 0
    while True:
        try:
            if not ctx.ws_clients:
                await asyncio.sleep(WS_TICK_SEC)
                continue

            bpm, utr, latest = ctx.buffers.snapshot_window(ctx.buffers.window_seconds) \
                if hasattr(ctx.buffers, "snapshot_window") else ctx.buffers.snapshot()

            hr, fm = 0, 0
            if len(bpm):
                hr = bpm[-1][1]
            if len(utr):
                fm = utr[-1][1]

            contractions = count_contractions(utr)

            cleanedUtr = clean_signal(
                utr,
                hampel_win=0.5,  # «иглы» длительностью <~0.5–1 c
                hampel_sigma=3.0,  # чувствительность к выбросам
                ma_win=0.3,  # лёгкое сглаживание
                max_rate=80.0  # ограничение скорости (опционально)
            )

            cleanedBpm = clean_signal(
                bpm,
                hampel_win=0.5,  # «иглы» длительностью <~0.5–1 c
                hampel_sigma=3.0,  # чувствительность к выбросам
                ma_win=0.3,  # лёгкое сглаживание
                max_rate=80.0  # ограничение скорости (опционально)
            )
            analytics = ctx.analytics

            payload = {
                "type": "snapshot",
                "elapsed": session_elapsed(),
                "bpm": cleanedBpm,
                "uterus": cleanedUtr,
                "heartRate": hr,
                "fetalMovement": fm,
                "contractions": contractions,
                "analytics": analytics
            }

            dead = []
            for ws in list(ctx.ws_clients):
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    print("[WS] send failed -> drop client:", e)
                    dead.append(ws)
            for ws in dead:
                ctx.ws_clients.discard(ws)

            # простая диагностика раз в ~5 секунд
            tick += 1
            if tick % int(5 / WS_TICK_SEC) == 0:
                print(f"[WS] sent snapshot to {len(ctx.ws_clients)} client(s); "
                      f"bpm={len(bpm)} uter={len(utr)} latest={latest:.2f}")

        except Exception as e:
            print("[WS] loop error:", e)

        await asyncio.sleep(WS_TICK_SEC)

async def pipeline_writer():

    while not ctx.stop_evt.is_set():
        try:
            if ctx.session_id:
                # ВАЖНО: берём полный срез буфера
                bpm, utr, _ = ctx.buffers.snapshot()   # [[t,v], ...] для обоих каналов
                await set_session_pipeline(
                    ctx.session_id,
                    bpm=bpm,
                    uterus=utr,
                    window_seconds=ctx.buffers.window_seconds,
                )
                analitycs = ctx.analytics
                await append_predictions_to_meta(
                    ctx.session_id, analitycs
                )
        except Exception as e:
            print("[pipeline_writer] error:", e)
        await asyncio.sleep(DB_FLUSH_SEC)

async def external_flusher():
    """Раз в 5 минут дергает внешнее API."""
    while not ctx.stop_evt.is_set():
        try:
            await flush_once()
        except httpx.HTTPError as e:
            print("[external_flusher] http error:", e)
        except NotImplementedError:
            # уберите это, когда реализуете flush_once()
            pass
        except Exception as e:
            print("[external_flusher] error:", e)
        await asyncio.sleep(EXTERNAL_FLUSH_SEC)

# ========= API =========

class StartReq(BaseModel):
    user_id: uuid.UUID
    user_name: str | None = None
    dataset: str           # "hypoxia" | "regular"
    study_number: int



@app.post("/start")
async def start(req: StartReq):
    if ctx.proc and ctx.proc.poll() is None:
        await stop()
        raise HTTPException(409, "session already running")
    print('ok')
    # очистка и инициализация
    ctx.buffers = StreamBuffers(deque(), deque(), WINDOW_SECONDS)
    ctx.buffers_lock = asyncio.Lock()
    ctx.analytics = []
    ctx.new_points_q = asyncio.Queue(maxsize=10000)
    ctx.ws_clients.clear()
    ctx.stop_evt.clear()
    ctx.t0 = time.monotonic()
    ctx.loop = asyncio.get_event_loop()
    ctx.dataset = req.dataset
    ctx.study_number = req.study_number
    ctx.user_id = req.user_id
    ctx.user_name = req.user_name

    # 1) создаём запись о сессии в БД (с user_name в meta)
    meta = {"user_name": req.user_name} if req.user_name else None
    sid = await create_session(req.user_id, req.dataset, req.study_number, meta=meta)
    ctx.session_id = sid

    # 2) запускаем эмулятор
    ctx.proc = spawn_emulator(req.dataset, req.study_number, cwd=os.getcwd())
    # 3) поднимаем два читателя COM → буфер+очередь
    enqueue = make_enqueue(ctx.loop)
    th_bpm = threading.Thread(
        target=serial_reader_thread,
        args=(BPM_PORT, BAUDRATE, "bpm", ctx.t0, ctx.stop_evt, enqueue),
        daemon=True,
    )
    th_utr = threading.Thread(
        target=serial_reader_thread,
        args=(UTR_PORT, BAUDRATE, "uterus", ctx.t0, ctx.stop_evt, enqueue),
        daemon=True,
    )
    th_bpm.start(); th_utr.start()
    ctx.threads = [th_bpm, th_utr]

    # 4) фоновые задачи: WS broadcaster, DB flusher, external flusher
    ctx.tasks = [
        asyncio.create_task(ws_broadcaster()),
        asyncio.create_task(pipeline_writer()),
        asyncio.create_task(external_flusher()),
    ]

    return {"session_id": str(sid), "ok": True}

@app.post("/stop")
async def stop():
    # гасим задачи
    ctx.stop_evt.set()
    for t in ctx.tasks:
        t.cancel()
    await asyncio.gather(*ctx.tasks, return_exceptions=True)
    ctx.tasks.clear()

    # останавливаем потоки и эмулятор
    for th in ctx.threads:
        try: th.join(timeout=2)
        except Exception: pass
    ctx.threads.clear()
    stop_emulator(ctx.proc)
    ctx.proc = None

    if ctx.session_id:
        await set_session_status(ctx.session_id, "stopped")

    return {"ok": True}

@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    ctx.ws_clients.add(ws)
    print(f"[WS] connected; clients={len(ctx.ws_clients)}")

    # отправим начальный снепшот сразу
    try:
        bpm, utr, latest = ctx.buffers.snapshot_window(ctx.buffers.window_seconds) \
            if hasattr(ctx.buffers, "snapshot_window") else ctx.buffers.snapshot()
        await ws.send_json({
            "type": "snapshot",
            "latest_time": latest,
            "bpm": bpm,
            "uterus": utr,
        })
    except Exception as e:
        print("[WS] initial send failed:", e)

    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    finally:
        ctx.ws_clients.discard(ws)
        print(f"[WS] disconnected; clients={len(ctx.ws_clients)}")



async def flush_once():
    print('flush')
    async with ctx.buffers_lock:
        bpm_file, uter_file = ctx.buffers.snapshot_csv_files()
    files = {
        "bpm": ("bpm.csv", bpm_file, "text/csv"),
        "uterus": ("uterus.csv", uter_file, "text/csv"),
    }
    params = {"threshold": THRESHOLD}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(MODEL_API_URL, files=files, params=params)
        r.raise_for_status()
        data = r.json()

    # берём только predictions
    preds = data.get("predictions", {})
    formatted = []
    for pred in preds.keys():
        if int(preds[pred]['pred']):
            formatted.append(make_recommendations(pred, int(preds[pred]['proba']*100)))

    # сохраняем в ctx.analytics (с таймстампом и, при желании, session_id)
    event = {
        "ts": time.time(),                # unix сек
        "predictions": formatted,             # ровно то, что нужно
    }
    async with ctx.buffers_lock:
        ctx.analytics.append(event)
        # (опционально: ограничить длину истории)
        if len(ctx.analytics) > 500:
            ctx.analytics = ctx.analytics[-500:]

    print(preds)
    return preds


@app.post("/flush")
async def flush_now():
    try:
        data = await flush_once()
        return {"status": "ok", "result": data}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
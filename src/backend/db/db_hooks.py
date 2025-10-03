# Высокоуровневые операции БД
import uuid
from typing import Iterable, Sequence, Tuple, List, Any

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

import json
from .db_config import ASYNC_DSN


engine = create_async_engine(ASYNC_DSN, pool_size=5, max_overflow=5)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

# ========== СЕССИИ ==========

async def create_session(user_id: uuid.UUID, dataset: str, study_number: int, meta: dict | None = None) -> uuid.UUID:
    q = (
        text("""
            insert into sessions (user_id, dataset, study_number, status, meta)
            values (:user_id, :dataset, :study_number, 'running', coalesce(:meta, '{}'::jsonb))
            returning id
        """)
        .bindparams(
            bindparam("user_id", type_=PGUUID(as_uuid=True)),
            bindparam("dataset"),
            bindparam("study_number"),
            bindparam("meta", type_=JSONB),   # <<< ВАЖНО
        )
    )
    async with SessionMaker() as s:
        res = await s.execute(q, {
            "user_id": user_id,
            "dataset": dataset,
            "study_number": study_number,
            "meta": meta,  # можно передавать dict
        })
        sid = res.scalar_one()
        await s.commit()
        return sid

async def set_session_status(session_id: uuid.UUID, status: str) -> None:
    q = text("select set_session_status(:sid, :st)")
    async with SessionMaker() as s:
        await s.execute(q, {"sid": session_id, "st": status})
        await s.commit()

async def append_predictions_to_meta(session_id: uuid.UUID, predictions: List[Any]) -> None:
    """
    Добавляет событие в sessions.meta.analytics:
      { "ts": <epoch_seconds>, "predictions": [ ... ] }
    """
    q = (
        text("""
            UPDATE sessions
            SET meta = jsonb_set(
                COALESCE(meta, '{}'::jsonb),
                '{analytics}',
                COALESCE(meta->'analytics','[]'::jsonb) ||
                to_jsonb(
                  jsonb_build_object(
                    'ts', extract(epoch from now()),
                    'predictions', :preds
                  )
                ),
                true
            )
            WHERE id = :sid
        """)
        .bindparams(bindparam("preds", type_=JSONB))
    )
    params = {"sid": session_id, "preds": predictions}
    async with SessionMaker() as s:
        await s.execute(q, params)
        await s.commit()

# ========== ТОЧКИ ==========



async def set_session_pipeline(
    session_id: uuid.UUID,
    bpm: Sequence[tuple[float, float]],
    uterus: Sequence[tuple[float, float]],
    window_seconds: float,
) -> None:
    pipeline = {
        "bpm": list(bpm),
        "uterus": list(uterus),
        "window_seconds": float(window_seconds),
    }

    q = (
        text("""
            update sessions
            set pipeline = :pl
            where id = :sid
        """)
        # Явно указываем типы, чтобы asyncpg корректно сериализовал
        .bindparams(
            bindparam("pl", type_=JSONB),
            bindparam("sid", type_=PGUUID(as_uuid=True)),
        )
    )

    async with SessionMaker() as s:
        await s.execute(q, {"pl": pipeline, "sid": session_id})
        await s.commit()


async def get_session_pipeline(session_id: uuid.UUID) -> dict:
    q = text("select pipeline from sessions where id = :sid")
    async with SessionMaker() as s:
        res = await s.execute(q, {"sid": session_id})
        row = res.first()
        return row[0] if row else {"bpm": [], "uterus": [], "window_seconds": 0.0}


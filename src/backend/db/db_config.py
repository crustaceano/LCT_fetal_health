import os

PG_USER = os.getenv("POSTGRES_USER", "root")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "123456")
PG_DB = os.getenv("POSTGRES_DB", "fetal")
PG_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5433"))

PG_URI = os.getenv("POSTGRES_URI", "").strip()

if PG_URI:
    ASYNC_DSN = PG_URI.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DSN = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

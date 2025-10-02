# Streaming Orchestrator (src/backend)

Сервис принимает поток событий КТГ и каждые N минут отправляет окно значений в `model_api` `/predict` (как два CSV: bpm, uterus).

## Запуск

1) Установите зависимости:
```bash
pip install fastapi uvicorn httpx pydantic
```

2) Запуск сервера:
```bash
uvicorn src.backend.app:app --reload --port 9000
```

## Конфигурация (env)
- `MODEL_API_URL` — URL предсказаний, по умолчанию `http://localhost:8000/predict`
- `WINDOW_MINUTES` — размер окна в минутах (по умолчанию `5`)
- `PREDICT_THRESHOLD` — порог предсказаний (по умолчанию `0.5`)
- `FLUSH_INTERVAL_SECONDS` — периодическая отправка окна (по умолчанию равно окну)

## Эндпоинты

### POST /ingest
Принимает события:
```json
{
  "source": "bpm" | "uterus",
  "time": 12.34,
  "value": 120.0
}
```

### POST /flush
Принудительно отправляет текущее окно в `model_api` `/predict` и возвращает ответ.

### GET /health
Проверка здоровья.



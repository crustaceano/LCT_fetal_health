# LCT Fetal Health

Система анализа КТГ с предсказанием диагнозов на 15 минут вперёд. Извлекает признаки из FHR/uterus сигналов, сглаживает данные и предсказывает вероятности 10 клинических состояний через CatBoost.

**Сайт:** [хакатон.фидли.рф](https://хакатон.фидли.рф)

## Архитектура

```
Поток КТГ → Backend (буфер) → Model API (инференс) → Рекомендации врачу
```

- **Model API** (8000): `/predict` — загрузка CSV, извлечение признаков, инференс CatBoost
- **Backend** (9000): `/ingest` — приём потока, буферизация, периодическая отправка в Model API

## Быстрый старт

```bash
# Docker (рекомендуется)
docker compose up --build

# Или локально
pip install -r requirements.txt
uvicorn src.model_api.model_app:app --reload &
uvicorn src.backend.app:app --reload --port 9000 &
```

**Тест:**
```bash
# Прямой инференс
curl -X POST "http://localhost:8000/predict?threshold=0.5" \
  -F "bpm=@data/hypoxia/10/bpm/20250908-07400001_1.csv" \
  -F "uterus=@data/hypoxia/10/uterus/20250908-07400001_2.csv"

# Поток через backend
python src/backend/send_from_files.py \
  --bpm data/hypoxia/10/bpm/20250908-07400001_1.csv \
  --uterus data/hypoxia/10/uterus/20250908-07400001_2.csv \
  --speed 2.0
curl http://localhost:9000/stats
curl -X POST http://localhost:9000/flush
```

## API

### Model API (8000)
- `POST /predict` — инференс по CSV файлам
- `GET /health` — статус

### Backend (9000)  
- `POST /ingest` — приём событий `{source:"bpm|uterus", time:float, value:float}`
- `GET /stats` — размеры буферов
- `POST /flush` — принудительная отправка окна в Model API
- `GET /health` — статус

## Решение

1. **Обработка данных**: чтение CSV (time,value), нормализация, очистка NaN
2. **Сглаживание**: скользящее среднее/медианный фильтр перед извлечением признаков  
3. **Признаки**: классические КТГ (baseline, ускорения, децелерции, вариабельность) + tsfresh
4. **Обучение**: CatBoost Multi-Output на 10 диагнозов (кесарево, гипоксия, ГСД и др.)
5. **Предсказание**: вероятности на 15 минут вперёд + рекомендации врачу

## Конфигурация

- `WINDOW_MINUTES=5` — размер окна буфера
- `PREDICT_THRESHOLD=0.5` — порог бинарных предсказаний  
- `smooth=true&smooth_method=moving_average&smooth_window_seconds=5` — сглаживание


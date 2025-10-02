from io import BytesIO
from typing import Dict, Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .feature_extraction import extract_features_combined
from .model import load_and_predict
from .evaluate import pretty_print_predictions


app = FastAPI(title="Fetal Health CatBoost API")

# Разрешаем CORS для локальной разработки; настройте origins под ваш фронтенд
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # замените на ["http://localhost:3000", "https://your-frontend"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_signal_from_upload(file: UploadFile) -> np.ndarray:
    """Читает второй столбец (value) из загруженного файла (CSV/XLSX)."""
    content = file.file.read()
    bio = BytesIO(content)

    name_lower = (file.filename or "").lower()
    try:
        if name_lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(bio)
        else:
            # Пытаемся как CSV по умолчанию
            try:
                df = pd.read_csv(bio)
            except Exception:
                bio.seek(0)
                df = pd.read_csv(bio, header=None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла {file.filename}: {e}")

    if df.shape[1] < 2:
        raise HTTPException(status_code=400, detail=f"Ожидалось минимум 2 колонки (time, value) в {file.filename}")

    series = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    arr = series.to_numpy(dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise HTTPException(status_code=400, detail=f"В колонке value нет валидных чисел: {file.filename}")
    return arr


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.post("/predict")
async def predict(
    bpm: UploadFile = File(..., description="CSV/XLSX: time,value"),
    uterus: UploadFile = File(..., description="CSV/XLSX: time,value"),
    threshold: float = 0.5,
):
    try:
        fhr_signal = _read_signal_from_upload(bpm)
        uterine_signal = _read_signal_from_upload(uterus)

        feats = extract_features_combined(fhr_signal, uterine_signal, sampling_rate=4)
        features_df = pd.DataFrame([feats])

        features_df_with_preds, labels = load_and_predict(features_df, threshold=threshold, only_top_categories=True)
        result = pretty_print_predictions(features_df_with_preds, labels)

        return JSONResponse({
            "labels": labels,
            "predictions": result,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Для локального запуска: uvicorn src.model_api.model_app:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.model_api.model_app:app", host="0.0.0.0", port=8000, reload=True)



import os
from typing import Tuple, Dict, Any

import numpy as np
import pandas as pd

from feature_extraction import extract_features_combined
from model import load_and_predict
from utils import smooth_signal


def _read_signal_from_file(path: str) -> np.ndarray:
    """
    Универсальная загрузка сигнала из файла .csv / .xlsx.
    Возвращает np.ndarray (1D) без NaN.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Файл не найден: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext in {".csv", ".txt"}:
        try:
            df = pd.read_csv(path)
        except Exception:
            df = pd.read_csv(path, header=None)
    elif ext in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        # Попробуем csv как дефолтный парсер
        try:
            df = pd.read_csv(path)
        except Exception as e:
            raise ValueError(f"Неподдерживаемый формат файла: {path}. Ошибка: {e}")

    series = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    arr = series.to_numpy(dtype=float)
    arr = arr[np.isfinite(arr)]
    return arr


def run_models_on_files(
    fhr_path: str,
    uterine_path: str,
    sampling_rate: int = 4,
    threshold: float = 0.5,
    smooth: bool = False,
    smooth_method: str = "moving_average",
    smooth_window_seconds: int = 5,
) -> Tuple[pd.DataFrame, Any]:
    """
    Загружает два файла сигналов (FHR и Uterus), извлекает признаки и прогоняет модели CatBoost.

    Возвращает кортеж: (features_df_with_preds, labels_order).
    """
    fhr_signal = _read_signal_from_file(fhr_path)
    uterine_signal = _read_signal_from_file(uterine_path)

    if smooth:
        fhr_signal = smooth_signal(
            fhr_signal,
            method=smooth_method,
            window_seconds=smooth_window_seconds,
            sampling_rate=sampling_rate,
        )
        uterine_signal = smooth_signal(
            uterine_signal,
            method=smooth_method,
            window_seconds=smooth_window_seconds,
            sampling_rate=sampling_rate,
        )

    feats = extract_features_combined(fhr_signal, uterine_signal, sampling_rate=sampling_rate)
    features_df = pd.DataFrame([feats])

    features_df_with_preds, labels = load_and_predict(features_df, threshold=threshold, only_top_categories=True)
    return features_df_with_preds, labels


def pretty_print_predictions(df: pd.DataFrame, labels: Any) -> Dict[str, Dict[str, float]]:
    """
    Возвращает словарь вида {label: {proba: float, pred: int}} для удобного вывода/логирования.
    """
    result: Dict[str, Dict[str, float]] = {}
    row = df.iloc[0]
    for label in labels:
        proba_key = f"proba_{label}"
        pred_key = f"pred_{label}"
        proba = float(row.get(proba_key, np.nan))
        pred = int(row.get(pred_key, 0)) if pd.notna(row.get(pred_key)) else 0
        result[label] = {"proba": proba, "pred": pred}
    return result



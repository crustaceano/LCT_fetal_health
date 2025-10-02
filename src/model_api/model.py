import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier


# Топ категории (используются для порядка столбцов и фильтрации)
TOP_CATEGORIES: List[str] = [
    "кесарево сечение",
    "преждевременное излитие околоплодных вод",
    "гипоксия",
    "гестационный сахарный диабет (диетотерапия)",
    "рубец на матке после кесарева",
    "многоводие",
    "астигматизм",
    "наследственная тромбофилия",
    "миома матки",
    "длительный безводный промежуток",
]


def get_checkpoints_dir() -> str:
    """Возвращает путь к директории с CatBoost чекпойнтами."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "catboost_checkpoints")


def _label_from_filename(filename: str) -> str:
    """Извлекает человеческое название класса из имени файла."""
    name = os.path.splitext(os.path.basename(filename))[0]
    # ожидаемый формат: catboost_model_<label>
    prefix = "catboost_model_"
    if name.startswith(prefix):
        return name[len(prefix):]
    return name


def load_catboost_models(allowed_labels: List[str] | None = None) -> Dict[str, CatBoostClassifier]:
    """
    Загружает все модели CatBoost из папки `catboost_checkpoints`.

    allowed_labels: если задан, загружает только модели с этими метками.
    Возвращает dict: {label: CatBoostClassifier}.
    """
    checkpoints_dir = get_checkpoints_dir()
    if not os.path.isdir(checkpoints_dir):
        raise FileNotFoundError(f"Не найдена папка с чекпойнтами: {checkpoints_dir}")

    models: Dict[str, CatBoostClassifier] = {}
    for fname in os.listdir(checkpoints_dir):
        if not fname.lower().endswith(".cbm"):
            continue
        fpath = os.path.join(checkpoints_dir, fname)
        label = _label_from_filename(fname)
        if allowed_labels is not None and label not in allowed_labels:
            continue
        model = CatBoostClassifier()
        model.load_model(fpath)
        models[label] = model

    if not models:
        raise RuntimeError("Не найдено ни одной модели .cbm для загрузки.")
    return models


def select_feature_columns(features_df: pd.DataFrame) -> List[str]:
    """
    Выбирает колонки с признаками: числовые, исключая мультилейблы/идентификаторы/предыдущие прогнозы.
    """
    drop_cols = {
        "folder_id",
        "folder_type",
        "bpm_file",
        "uterus_file",
        "multilabel",
        "multilabel_top",
        "multilabel_unified",
        "hard_hypoxia",
    }

    feature_cols: List[str] = []
    for col in features_df.columns:
        if col in drop_cols:
            continue
        if str(col).startswith("proba_") or str(col).startswith("pred_"):
            continue
        # оставляем только числовые
        if pd.api.types.is_numeric_dtype(features_df[col]):
            feature_cols.append(col)
    return feature_cols


def predict_with_models(
    features_df: pd.DataFrame,
    models: Dict[str, CatBoostClassifier],
    threshold: float = 0.5,
    ensure_top_order: bool = True,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Считает вероятности и бинарные предсказания для каждого загруженного класса.

    Возвращает (обновлённый DataFrame, список меток в порядке вывода).
    """
    feature_cols = select_feature_columns(features_df)
    if not feature_cols:
        raise ValueError("Не найдены колонки признаков для инференса.")

    X = features_df[feature_cols].values

    labels = list(models.keys())
    if ensure_top_order:
        # Сохраняем порядок TOP_CATEGORIES, но оставляем только те, для которых есть модели
        labels = [lbl for lbl in TOP_CATEGORIES if lbl in models] + [
            lbl for lbl in models.keys() if lbl not in TOP_CATEGORIES
        ]

    for label in labels:
        model = models[label]
        # Предпочтительно predict_proba, но CatBoost в бинарной задаче возвращает столбцы [p(class 0), p(class 1)]
        proba = model.predict_proba(X)
        # Берём вероятность класса 1
        p1 = np.array([p[1] if isinstance(p, (list, tuple, np.ndarray)) else float(p) for p in proba])
        features_df[f"proba_{label}"] = p1
        features_df[f"pred_{label}"] = (p1 >= threshold).astype(int)

    return features_df, labels


def load_and_predict(
    features_df: pd.DataFrame,
    threshold: float = 0.5,
    only_top_categories: bool = True,
) -> Tuple[pd.DataFrame, List[str]]:
    """Упрощённый интерфейс: загрузить модели и получить предсказания."""
    allowed = TOP_CATEGORIES if only_top_categories else None
    models = load_catboost_models(allowed_labels=allowed)
    return predict_with_models(features_df.copy(), models, threshold=threshold, ensure_top_order=True)



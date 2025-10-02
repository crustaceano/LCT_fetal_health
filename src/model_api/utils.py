import numpy as np
import pandas as pd


def smooth_signal(
    signal: np.ndarray,
    method: str = "moving_average",
    window_seconds: int = 5,
    sampling_rate: int = 4,
) -> np.ndarray:
    """
    Простое сглаживание 1D-сигнала перед извлечением признаков.

    method:
      - "moving_average" — скользящее среднее
      - "median" — медианный фильтр
    window_seconds: длина окна в секундах
    sampling_rate: частота дискретизации (Гц)
    """
    if signal is None or len(signal) == 0:
        return signal

    window = max(1, int(window_seconds * sampling_rate))

    if method == "moving_average":
        # Отражённые края для минимизации краевых эффектов
        pad = min(window, len(signal) - 1)
        if pad > 0:
            extended = np.r_[signal[pad:0:-1], signal, signal[-2:-pad-2:-1]]
        else:
            extended = signal
        kernel = np.ones(window, dtype=float) / float(window)
        smoothed = np.convolve(extended, kernel, mode="same")
        # обрезаем обратно к исходной длине
        if pad > 0:
            smoothed = smoothed[pad:-pad]
        return smoothed.astype(float)

    if method == "median":
        s = pd.Series(signal, dtype="float64")
        # center=True, min_periods=1 для корректной обработки краёв
        smoothed = s.rolling(window=window, center=True, min_periods=1).median()
        return smoothed.to_numpy(dtype=float)

    # по умолчанию — без сглаживания
    return np.asarray(signal, dtype=float)



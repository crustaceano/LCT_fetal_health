from typing import List, Tuple, Optional

Pair = Tuple[float, float]  # (t, v)

def _median(xs: List[float]) -> float:
    n = len(xs)
    if n == 0: return 0.0
    s = sorted(xs)
    m = n // 2
    return s[m] if n % 2 else 0.5 * (s[m-1] + s[m])

def despike_hampel_time(
    data: List[Pair],
    window_sec: float = 0.5,     # ширина окна (сек)
    n_sigma: float = 3.0,        # порог в "сигмах" (через MAD)
    replace_with: str = "median" # "median" или "interp"
) -> List[Pair]:
    """
    Убирает кратковременные всплески по Хампелу в скользящем *временном* окне.
    window_sec=0.5 снимает «иглы» длительностью <~0.5–1 с.
    """
    if not data:
        return []
    t_arr = [t for t, _ in data]
    v_arr = [v for _, v in data]
    out: List[Pair] = []

    j0 = 0
    for i, (t, v) in enumerate(data):
        # окно [t - window_sec, t + window_sec]
        while j0 < i and data[j0][0] < t - window_sec:
            j0 += 1
        j1 = i
        while j1 + 1 < len(data) and data[j1 + 1][0] <= t + window_sec:
            j1 += 1

        win_vals = [v_arr[k] for k in range(j0, j1 + 1)]
        med = _median(win_vals)
        abs_dev = [abs(x - med) for x in win_vals]
        mad = _median(abs_dev) or 1e-9  # защита от нуля

        # 1.4826 ~ перевод MAD в σ при нормальном распределении
        sigma = 1.4826 * mad
        is_spike = abs(v - med) > n_sigma * sigma

        if is_spike:
            if replace_with == "median":
                new_v = med
            else:  # "interp": линейная интерполяция между соседями по времени
                # ищем ближайших слева/справа
                # (если нет одного из соседей — откатываемся на медиану)
                left_idx = i - 1 if i - 1 >= 0 else None
                right_idx = i + 1 if i + 1 < len(data) else None
                if left_idx is not None and right_idx is not None:
                    t0, v0 = data[left_idx]
                    t1, v1 = data[right_idx]
                    if t1 != t0:
                        alpha = (t - t0) / (t1 - t0)
                        new_v = v0 + alpha * (v1 - v0)
                    else:
                        new_v = med
                else:
                    new_v = med
            out.append((t, new_v))
        else:
            out.append((t, v))
    return out


def moving_average_time(
    data: List[Pair],
    window_sec: float = 0.3
) -> List[Pair]:
    """
    Скользящее среднее по *временному* окну ±window_sec.
    """
    if not data:
        return []
    out: List[Pair] = []
    j0 = 0
    for i, (t, _) in enumerate(data):
        # окно [t - window_sec, t + window_sec]
        while j0 < i and data[j0][0] < t - window_sec:
            j0 += 1
        j1 = i
        while j1 + 1 < len(data) and data[j1 + 1][0] <= t + window_sec:
            j1 += 1
        s = 0.0
        cnt = 0
        for k in range(j0, j1 + 1):
            s += data[k][1]; cnt += 1
        out.append((t, s / max(1, cnt)))
    return out

def moving_average_time(
    data: List[Pair],
    window_sec: float = 0.3
) -> List[Pair]:
    """
    Скользящее среднее по *временному* окну ±window_sec.
    """
    if not data:
        return []
    out: List[Pair] = []
    j0 = 0
    for i, (t, _) in enumerate(data):
        # окно [t - window_sec, t + window_sec]
        while j0 < i and data[j0][0] < t - window_sec:
            j0 += 1
        j1 = i
        while j1 + 1 < len(data) and data[j1 + 1][0] <= t + window_sec:
            j1 += 1
        s = 0.0
        cnt = 0
        for k in range(j0, j1 + 1):
            s += data[k][1]; cnt += 1
        out.append((t, s / max(1, cnt)))
    return out

def clamp_derivative(
    data: List[Pair],
    max_rate_per_sec: float = 100.0  # максимально допустимое изменение в ед/с
) -> List[Pair]:
    """
    Ограничивает скорость изменения: |v[i]-v[i-1]|/dt <= max_rate_per_sec.
    """
    if not data:
        return []
    out: List[Pair] = [data[0]]
    for i in range(1, len(data)):
        t_prev, v_prev = out[-1]
        t, v = data[i]
        dt = max(1e-6, t - t_prev)
        dv = v - v_prev
        max_dv = max_rate_per_sec * dt
        if abs(dv) > max_dv:
            v = v_prev + (max_dv if dv > 0 else -max_dv)
        out.append((t, v))
    return out


def clean_signal(
    data: List[Pair],
    *,
    hampel_win=0.5,
    hampel_sigma=3.0,
    ma_win=0.3,
    max_rate=None  # например, 80.0
) -> List[Pair]:
    x = despike_hampel_time(data, window_sec=hampel_win, n_sigma=hampel_sigma, replace_with="median")
    x = moving_average_time(x, window_sec=ma_win)
    if max_rate is not None:
        x = clamp_derivative(x, max_rate_per_sec=max_rate)
    return x


def clean_signal(
    data: List[Pair],
    *,
    hampel_win=0.5,
    hampel_sigma=3.0,
    ma_win=0.3,
    max_rate=None  # например, 80.0
) -> List[Pair]:
    x = despike_hampel_time(data, window_sec=hampel_win, n_sigma=hampel_sigma, replace_with="median")
    x = moving_average_time(x, window_sec=ma_win)
    if max_rate is not None:
        x = clamp_derivative(x, max_rate_per_sec=max_rate)
    return x
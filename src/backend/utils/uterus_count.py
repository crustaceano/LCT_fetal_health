from typing import List, Tuple

Pair = Tuple[float, float]  # (t_sec, value)

def ema_time_aware(data: List[Pair], tau_sec: float = 6.0) -> List[Pair]:
    """Экспоненциальное сглаживание с учётом неравномерного шага по времени."""
    if not data:
        return []
    out: List[Pair] = []
    y = data[0][1]
    t_prev = data[0][0]
    out.append((t_prev, y))
    for t, x in data[1:]:
        dt = max(1e-6, t - t_prev)
        alpha = 1.0 - pow(2.718281828, -dt / tau_sec)  # 1 - exp(-dt/tau)
        y = y + alpha * (x - y)
        out.append((t, y))
        t_prev = t
    return out

def rolling_median(data: List[Pair], win_sec: float = 150.0) -> List[Pair]:
    """Скользящая медиана по времени (O(n*w), но просто и надёжно)."""
    n = len(data)
    if n == 0:
        return []
    out: List[Pair] = []
    j0 = 0
    buf: List[float] = []
    for i in range(n):
        t_i = data[i][0]
        while j0 < i and data[j0][0] < t_i - win_sec:
            j0 += 1
        buf.clear()
        for k in range(j0, i + 1):
            buf.append(data[k][1])
        buf.sort()
        m = buf[(len(buf) - 1) // 2] if (len(buf) % 2) else 0.5 * (buf[len(buf)//2 - 1] + buf[len(buf)//2])
        out.append((t_i, m))
    return out

def detect_contractions(
    uterus: List[Pair],
    *,
    tau_sec: float = 6.0,       # EMA сглаживание
    base_win_sec: float = 150.0,# окно базы (медиана)
    th_high: float = 15.0,      # вход: baseline + th_high
    th_low: float = 15.0,       # выход: baseline + th_low  (th_low < th_high)
    min_dur: float = 25.0,      # мин длительность, сек
    min_amp: float = 8.0,      # мин амплитуда (пик - baseline_at_start)
    merge_gap: float = 30.0     # слить эпизоды, если пауза между ними < merge_gap (сек)
) -> List[Tuple[float, float, float, float, float]]:
    """
    Возвращает список схваток в формате:
      (start, end, peak_t, peak_value, amplitude)
    """
    if len(uterus) < 3:
        return []

    # 1) сглаживание и базовая линия
    sm = ema_time_aware(uterus, tau_sec)
    base = rolling_median(sm, base_win_sec)

    # 2) гистерезис
    episodes: List[Tuple[float, float, float, float, float]] = []
    in_evt = False
    start = peak_t = 0.0
    peak = float("-inf")
    base_at_start = 0.0

    for i, (t, y) in enumerate(sm):
        b = base[i][1]
        d = y - b
        if not in_evt:
            if d >= th_high:
                in_evt = True
                start = t
                base_at_start = b
                peak = y
                peak_t = t
        else:
            if y > peak:
                peak = y
                peak_t = t
            if d <= th_low:
                end = t
                dur = end - start
                amp = peak - base_at_start
                if dur >= min_dur and amp >= min_amp:
                    episodes.append((start, end, peak_t, peak, amp))
                in_evt = False

    # закрыть хвост, если ряд закончился внутри эпизода
    if in_evt:
        t_last = sm[-1][0]
        dur = t_last - start
        amp = peak - base_at_start
        if dur >= min_dur and amp >= min_amp:
            episodes.append((start, t_last, peak_t, peak, amp))

    # 3) слияние близких эпизодов
    if not episodes:
        return episodes
    episodes.sort(key=lambda e: e[0])
    merged: List[Tuple[float, float, float, float, float]] = []
    cur = list(episodes[0])
    for nx in episodes[1:]:
        if nx[0] - cur[1] <= merge_gap:
            # слить
            cur[1] = max(cur[1], nx[1])           # end
            if nx[3] > cur[3]:                    # peak_value
                cur[2] = nx[2]                    # peak_t
                cur[3] = nx[3]                    # peak_value
                cur[4] = max(cur[4], nx[4])       # amplitude
        else:
            merged.append(tuple(cur))
            cur = list(nx)
    merged.append(tuple(cur))
    return merged

def count_contractions(uterus: List[Pair], **kwargs) -> int:
    """Просто количество схваток."""
    return len(detect_contractions(uterus, **kwargs))

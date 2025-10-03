#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import time
import re
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd

try:
    import serial  # pyserial
except ImportError as e:
    print("Не найден пакет 'pyserial'. Установите: pip install pyserial", file=sys.stderr)
    raise

# --------- Константы/валидация ---------

LIMITS = {
    "hypoxia": 50,
    "regular": 160,
}

# --------- Утилиты ---------

FILENAME_KEY_RE = re.compile(r"-(\d+)_([12])\.csv$", re.IGNORECASE)

def extract_sort_key(p: Path) -> Tuple[int, int]:
    """
    Извлекает ключ сортировки из имени файла: предпоследнее число и суффикс _1/_2.
    Пример: 20250901-01000012_1.csv -> (1000012, 1)
    """
    m = FILENAME_KEY_RE.search(p.name)
    if not m:
        # если формат неожиданный — ставим в конец, но не падаем
        return (10**12, 9)
    return (int(m.group(1)), int(m.group(2)))

def load_csv_robust(path: Path) -> pd.DataFrame:
    """
    Читает CSV в формате:
      - две колонки с заголовком/без: time_sec,value
      - или одна колонка-строка "time_sec,value"
    Возвращает DataFrame со столбцами: time_sec (float), value (float)
    """
    # пытаемся прямым чтением
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.read_csv(path, engine="python")

    # если одна колонка — сплитим по запятой
    if df.shape[1] == 1:
        col = df.columns[0]
        split = df[col].astype(str).str.split(",", n=1, expand=True)
        if split.shape[1] != 2:
            raise ValueError(f"Не удалось распарсить {path}: ожидался формат 'time_sec,value'.")
        split.columns = ["time_sec", "value"]
        df = split
    else:
        # нормализуем имена
        cols_norm = [c.strip().lower() for c in df.columns]
        mapping = {}
        for i, c in enumerate(cols_norm):
            if "time" in c and "sec" in c:
                mapping[df.columns[i]] = "time_sec"
            elif c in ("value", "val", "signal"):
                mapping[df.columns[i]] = "value"
        df = df.rename(columns=mapping)

    # приведение типов
    for col in ("time_sec", "value"):
        if col not in df.columns:
            raise ValueError(f"{path}: нет обязательного столбца '{col}'. Найдены: {list(df.columns)}")
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .str.replace(r"[^\d\.\-\+eE]", "", regex=True)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["time_sec", "value"]).reset_index(drop=True)
    return df

def concat_sorted_csvs(dir_path: Path, suffix_num: int) -> pd.DataFrame:
    """
    Склеивает CSV из папки, фильтруя по _{suffix_num}.csv и сортируя по предпоследнему числу.
    Возвращает один DataFrame с time_sec,value и накопленным временем (не сбрасывается между файлами).
    Предполагается, что time_sec внутри каждого файла начинается с 0 или монотонно растёт;
    мы нормируем начало КАЖДОГО файла, чтобы общий таймлайн был непрерывный.
    """
    if not dir_path.exists():
        raise FileNotFoundError(f"Папка не найдена: {dir_path}")

    files = [p for p in dir_path.glob("*.csv") if p.name.endswith(f"_{suffix_num}.csv")]
    if not files:
        raise FileNotFoundError(f"В {dir_path} не найдено файлов *_{suffix_num}.csv")

    files.sort(key=extract_sort_key)

    parts = []
    t_offset = 0.0
    for p in files:
        df = load_csv_robust(p)
        # нормируем начало файла к 0, если нужно
        t0 = float(df["time_sec"].iloc[0])
        # гарантируем монотонность времени
        df["time_sec"] = (df["time_sec"] - t0).clip(lower=0.0) + t_offset
        # обновляем смещение: последний time_sec в этом файле
        t_offset = float(df["time_sec"].iloc[-1])
        parts.append(df[["time_sec", "value"]])

    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values("time_sec").reset_index(drop=True)
    return out

# --------- Эмулятор передачи ---------

def stream_two_signals(
    bpm_df: pd.DataFrame,
    uterus_df: pd.DataFrame,
    bpm_port: str,
    uterus_port: str,
    baudrate: int = 115200,
    speed: float = 1.0,
    line_fmt: str = "{value}\n",
    flush: bool = False,
):
    """
    Синхронно воспроизводит два сигнала в два COM-порта по временным меткам.
    speed > 1.0 ускоряет воспроизведение (напр., 2.0 — в два раза быстрее).
    line_fmt — шаблон строки; доступные поля: value, time_sec.
    """
    if speed <= 0:
        raise ValueError("speed должен быть > 0.")

    ser_bpm = serial.Serial(bpm_port, baudrate=baudrate, timeout=0)
    ser_uterus = serial.Serial(uterus_port, baudrate=baudrate, timeout=0)
    try:
        # создаём объединённый список событий (t, stream_id, value)
        # stream_id: 0 -> bpm, 1 -> uterus
        events: List[Tuple[float, int, float]] = []
        time_bpm, last_time_bpm, time_uterus, last_time_uterus = 0, 0, 0, 0
        for _, row in bpm_df.iterrows():
            if float(row["time_sec"]) == 0:
                time_bpm += last_time_bpm + 1/8
            last_time_bpm = float(row["time_sec"])
            events.append((float(row["time_sec"]) + time_bpm, 0, float(row["value"])))

        for _, row in uterus_df.iterrows():
            if float(row["time_sec"]) == 0:
                time_uterus += last_time_uterus + 1/8
            last_time_uterus = float(row["time_sec"])
            events.append((float(row["time_sec"]) + time_uterus, 1, float(row["value"])))
        events.sort(key=lambda x: x[0])
        if not events:
            print("Нет данных для воспроизведения.")
            return

        t0 = events[0][0]
        # "реальное" начало
        wall_start = time.monotonic()
        sent_bpm = sent_uterus = 0

        for t, stream_id, val in events:
            # целевое «реальное» время с учётом ускорения
            target = wall_start + (t - t0) / speed
            # доспим до target (без активного ожидания)
            now = time.monotonic()
            if target > now:
                time.sleep(target - now)

            line = line_fmt.format(value=val, time_sec=t)
            data = line.encode("utf-8", errors="ignore")

            if stream_id == 0:
                ser_bpm.write(data)
                # print('bpm', data, t)
                if flush:
                    ser_bpm.flush()
                sent_bpm += 1
            else:
                ser_uterus.write(data)
                # print('uterus', data, t)
                if flush:
                    ser_uterus.flush()
                sent_uterus += 1

        print(f"Готово. Отправлено: BPM {sent_bpm} строк, Uterus {sent_uterus} строк.")
    finally:
        try:
            ser_bpm.close()
        except Exception:
            pass
        try:
            ser_uterus.close()
        except Exception:
            pass

# --------- CLI ---------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Эмулятор фетального монитора: читает CSV и пишет в два COM-порта синхронно по времени."
    )
    p.add_argument("dataset", choices=["hypoxia", "regular"], help="Выбор набора данных.")
    p.add_argument("number", type=int, help="Номер исследования (hypoxia ≤ 50, regular ≤ 160).")

    p.add_argument("--root", type=Path, default=Path("/data"),
                   help="Корень с данными (по умолчанию: /data).")
    p.add_argument("--bpm-port", default="COM5", help="COM-порт для BPM (по умолчанию: COM5).")
    p.add_argument("--uterus-port", default="COM6", help="COM-порт для Uterus (по умолчанию: COM6).")
    p.add_argument("--baudrate", type=int, default=115200, help="Скорость порта (baud).")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Коэффициент ускорения времени (напр. 2.0 — в 2 раза быстрее).")
    p.add_argument("--line-fmt", default="{value}\n",
                   help="Формат строки для отправки. Доступно: {value}, {time_sec}.")
    p.add_argument("--flush", action="store_true",
                   help="Вызвать flush() после каждой записи (медленнее, но точнее).")
    return p.parse_args(argv)

def main():
    args = parse_args()

    # валидация номера исследования
    limit = LIMITS[args.dataset]
    if not (1 <= args.number <= limit):
        print(f"Номер исследования вне диапазона для {args.dataset}: 1..{limit}", file=sys.stderr)
        sys.exit(2)

    # пути к папкам
    base = args.root / args.dataset / str(args.number)
    bpm_dir = base / "bpm"
    uterus_dir = base / "uterus"

    print(f"Чтение BPM из:    {bpm_dir}")
    print(f"Чтение Uterus из: {uterus_dir}")

    try:
        bpm_df = concat_sorted_csvs(bpm_dir, suffix_num=1)
        uterus_df = concat_sorted_csvs(uterus_dir, suffix_num=2)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}", file=sys.stderr)
        sys.exit(3)

    # Нормируем начало обоих потоков к минимальному времени (синхронный старт)
    t0 = min(float(bpm_df["time_sec"].iloc[0]), float(uterus_df["time_sec"].iloc[0]))
    bpm_df["time_sec"] -= t0
    uterus_df["time_sec"] -= t0

    print(f"Открываем порты: BPM -> {args.bpm_port}, Uterus -> {args.uterus_port} (baud={args.baudrate})")
    print(f"Скорость воспроизведения: x{args.speed:.3f}")
    print("Старт. Нажмите Ctrl+C для остановки.")

    try:
        stream_two_signals(
            bpm_df=bpm_df,
            uterus_df=uterus_df,
            bpm_port=args.bpm_port,
            uterus_port=args.uterus_port,
            baudrate=args.baudrate,
            speed=args.speed,
            line_fmt=args.line_fmt,
            flush=args.flush,
        )
    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")
    except serial.SerialException as e:
        print(f"Ошибка работы с COM-портами: {e}", file=sys.stderr)
        sys.exit(4)

if __name__ == "__main__":
    main()

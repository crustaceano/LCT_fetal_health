import argparse
import time
import requests
import pandas as pd
import numpy as np


def load_tv_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.shape[1] < 2:
        raise ValueError(f"{path}: need at least 2 columns: time, value")
    out = pd.DataFrame({
        "time": df.iloc[:, 0],
        "value": pd.to_numeric(df.iloc[:, 1], errors="coerce"),
    })
    # try numeric time, else datetime
    tnum = pd.to_numeric(out["time"], errors="coerce")
    if tnum.notna().all():
        t = tnum.values.astype(float)
    else:
        tdt = pd.to_datetime(out["time"], errors="coerce")
        if tdt.isna().all():
            raise ValueError(f"{path}: cannot parse time column")
        t = (tdt - tdt.iloc[0]).dt.total_seconds().values.astype(float)
    v = out["value"].to_numpy(dtype=float)
    mask = np.isfinite(t) & np.isfinite(v)
    tv = pd.DataFrame({"time": t[mask], "value": v[mask]}).sort_values("time").reset_index(drop=True)
    # normalize start to 0
    if len(tv) and tv.loc[0, "time"] != 0.0:
        tv["time"] = tv["time"] - tv.loc[0, "time"]
    return tv


def stream_files(bpm_path: str, uter_path: str, base_url: str, speed: float = 1.0):
    bpm_df = load_tv_csv(bpm_path)
    uter_df = load_tv_csv(uter_path)

    i, j = 0, 0
    last_t = None
    sess = requests.Session()
    ingest_url = base_url.rstrip("/") + "/ingest"

    while i < len(bpm_df) or j < len(uter_df):
        tb = bpm_df.iloc[i]["time"] if i < len(bpm_df) else None
        tu = uter_df.iloc[j]["time"] if j < len(uter_df) else None
        candidates = [t for t in [tb, tu] if t is not None]
        if not candidates:
            break
        tnext = min(candidates)
        if last_t is not None and speed > 0:
            dt = max(0.0, (tnext - last_t) / max(speed, 1e-6))
            if dt > 0:
                time.sleep(dt)
        last_t = tnext

        if tb is not None and abs(tb - tnext) < 1e-9:
            payload = {"source": "bpm", "time": float(bpm_df.iloc[i]["time"]), "value": float(bpm_df.iloc[i]["value"])}
            r = sess.post(ingest_url, json=payload, timeout=10)
            r.raise_for_status()
            i += 1
        if tu is not None and abs(tu - tnext) < 1e-9:
            payload = {"source": "uterus", "time": float(uter_df.iloc[j]["time"]), "value": float(uter_df.iloc[j]["value"])}
            r = sess.post(ingest_url, json=payload, timeout=10)
            r.raise_for_status()
            j += 1


def main():
    ap = argparse.ArgumentParser(description="Stream bpm/uterus CSV files to backend /ingest")
    ap.add_argument("--bpm", required=True, help="Path to bpm CSV with time,value")
    ap.add_argument("--uterus", required=True, help="Path to uterus CSV with time,value")
    ap.add_argument("--url", default="http://localhost:9000", help="Backend base URL (default: http://localhost:9000)")
    ap.add_argument("--speed", type=float, default=1.0, help="Playback speed factor (1.0 realtime, 2.0 twice faster, 0 no delays)")
    args = ap.parse_args()

    stream_files(args.bpm, args.uterus, args.url, speed=max(0.0, args.speed))


if __name__ == "__main__":
    main()



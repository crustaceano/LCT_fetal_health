import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
from tqdm import tqdm
import pandas as pd
import numpy as np
import os
from tsfresh.feature_extraction import MinimalFCParameters

# Baseline FHR value
# Measured as the mean of all signal values
def getBaseline(fhr_signal):
    baseline = np.mean(fhr_signal)
    # print(baseline)
    
    return baseline

# Plot the singal
def printWaveform(fhr_signal, sampling_rate, baseline, time):
    time = np.arange(len(fhr_signal)) / sampling_rate
    plt.figure(figsize=(12, 2))
    plt.plot(time, fhr_signal, color='blue')
    plt.xlabel('Time (seconds)')
    plt.ylabel('FHR (bpm)')
    plt.title('Fetal Heart Rate Signal')
    plt.grid(True)
    plt.axhline(y=baseline, color='red', label='Baseline')
    plt.ylim(50, 200)
    plt.xlim(time[0], time[-1])
    plt.show()

# Separate the FHR singal into segments
# Based on the intersections where the FHR meets the Baseline
# Get all segments where the FHR is above the baseline
# Get all segments where the FHR is below the baseline
def getSegments(fhr_signal, baseline):
    current_segment = []
    segments_above_baseline = []
    segments_below_baseline = []
    # Check if first signal is above the baseline
    above_baseline = fhr_signal[0] > baseline

    # Loop through entire FHR signal
    for signal in fhr_signal:
        # Check if current signal is above the baseline
        is_above_baseline = signal > baseline
        # Check if the signal has changed sides of the baseline
        # I.e an intersection has been reached
        if is_above_baseline != above_baseline:
            # If the signal changed and the signal is above the baseline
            # Add segment to segments_above_baseline
            # Otherwise add segment to segments_below_baseline
            if above_baseline:
                segments_above_baseline.append(current_segment)
            else:
                segments_below_baseline.append(current_segment)
            
            current_segment = [signal]
            above_baseline = is_above_baseline
        else:
            # Add signal to current segment
            current_segment.append(signal)

    # Add the last segment to its corresponding list
    if above_baseline:
        segments_above_baseline.append(current_segment)
    else:
        segments_below_baseline.append(current_segment)
        
    return segments_above_baseline, segments_below_baseline

# FHR accelerations
# Defined as an increase in FHR signal between two intersections on the baseline
# such that the highest point in the segment is at least 15 b.p.m above the baseline and the segment is 15 (seconds)
def getAccelerations(segments_above_baseline, window_size, threshold_bpm, baseline, time):
    num_accelerations = 0

    # Iterate through all segments above the baseline
    for segment in segments_above_baseline:
        max_signal = np.max(segment)
        # Check if the segment length is at least 15 and the max signal in the segment is 15 b.p.m above the baseline
        if len(segment) / 4 >= window_size and max_signal >= baseline + threshold_bpm:
            num_accelerations += 1

    AC = num_accelerations / len(time)
    # print(AC)
    
    return AC

# FHR decelerations
# Defined as an decrease in FHR signal between two intersections on the baseline
# such that the lowest point in the segment is at least 15 b.p.m below the baseline and the segment is 15 (seconds)
# If the segment is at lesat 120 seconds / 2 minutes, count as prolongued deceleration
def getDecelerations(segments_below_baseline, window_size, prolongued_window_size, threshold_bpm, baseline, time):
    num_decelerations = 0
    num_prolonged_decelerations = 0
    
    # Iterate through all segments below the baseline
    for segment in segments_below_baseline:
        min_signal = np.min(segment)

        # Check if the segment length is at least 15 and the min signal in the segment is 15 b.p.m below the baseline
        if len(segment) / 4 >= window_size and min_signal <= baseline - threshold_bpm:
            num_decelerations += 1
            # Check if segment length is at least 120
            if len(segment) / 4 >= prolongued_window_size:
                num_prolonged_decelerations += 1

    DC = num_decelerations / len(time)
    DP = num_prolonged_decelerations / len(time)
    # print(DC)
    # print(DP)
    
    return DC, DP

# Variability
# Defined as the difference between the max signal and the min signal within a given time frame
# Short term defined as a 1 minute time frame
# Abnormality defined as the variability being less than 5 and greater than 25
def getShortTermVariability(fhr_signal, sampling_rate, time):
    segment_length = 60 * sampling_rate
    num_abnormal_stv = 0

    stv_values = []
    # Iterate through the FHR signal
    for i in range(0, len(fhr_signal), segment_length):
        # Segment the signal based on the time frame
        segment = fhr_signal[i:i+segment_length]
        max_signal = np.max(segment)
        min_signal = np.min(segment)

        # Add the variability of the time frame to the list
        stv = max_signal - min_signal
        stv_values.append(stv)

        # Check if the variability is abnormal
        if stv < 5 or stv > 25:
            num_abnormal_stv += 1

    MSTV = np.mean(stv_values)
    # print(MSTV)
    ASTV = num_abnormal_stv / len(time)
    # print(ASTV)
    
    return MSTV, ASTV

# Variability
# Defined as the difference between the max signal and the min signal within a given time frame
# Long term defined as a 5 minute time frame
# Abnormality defined as the variability being less than 5 and greater than 25
def getLongTermVariability(fhr_signal, sampling_rate, time):
    segment_length = 300 * sampling_rate
    num_abnormal_ltv = 0

    ltv_values = []
    # Iterate through the FHR signal
    for i in range(0, len(fhr_signal), segment_length):
        # Segment the signal based on the time frame
        segment = fhr_signal[i:i+segment_length]
        max_signal = np.max(segment)
        min_signal = np.min(segment)

        # Add the variability of the time frame to the list
        ltv = max_signal - min_signal
        ltv_values.append(ltv)

        # Check if the variability is abnormal
        if ltv < 5 or ltv > 25:
            num_abnormal_ltv += 1

    MLTV = np.mean(ltv_values)
    # print(MLTV)
    ALTV = num_abnormal_ltv / len(time)
    # print(ALTV)
    return MLTV, ALTV

def extract_features(
    fhr_signal: np.ndarray,
    sampling_rate: int = 4,
    window_size: int = 15,
    prolongued_window_size: int = 120,
    threshold_bpm: int = 15
) -> dict:
    """Извлекает признаки из FHR сигнала."""
    
    # базовая линия
    LB = getBaseline(fhr_signal)
    time = np.arange(len(fhr_signal)) / sampling_rate

    # сегментация
    segments_above_baseline, segments_below_baseline = getSegments(fhr_signal, LB)

    # акселерации
    AC = getAccelerations(segments_above_baseline, window_size, threshold_bpm, LB, time)

    # децелерации (в т.ч. пролонгированные)
    DC, DP = getDecelerations(
        segments_below_baseline,
        window_size,
        prolongued_window_size,
        threshold_bpm,
        LB,
        time
    )

    # коротковременная вариабельность
    MSTV, ASTV = getShortTermVariability(fhr_signal, sampling_rate, time)

    # долговременная вариабельность
    MLTV, ALTV = getLongTermVariability(fhr_signal, sampling_rate, time)

    # собираем всё в словарь
    data = {
        "baseline value": LB,
        "accelerations": AC,
        "prolongued_decelerations": DP,
        "mean_value_of_short_term_variability": MSTV,
        "percentage_of_time_with_abnormal_long_term_variability": ALTV,
        "mean_value_of_long_term_variability": MLTV,
    }
    return data


def extract_features_tsfresh(fhr_signal: np.ndarray, sampling_rate: int = 4) -> dict:
    """
    Извлекает дополнительные признаки FHR через tsfresh.
    Возвращает словарь признаков.
    """
    features = {}
    try:
        fhr_signal = np.array(fhr_signal)
        fhr_signal = fhr_signal[~np.isnan(fhr_signal)]
        
        if len(fhr_signal) < 2:
            return {f"tsfresh_{i}": np.nan for i in range(10)}
        
        df_signal = pd.DataFrame({
            "id": 0,
            "time": np.arange(len(fhr_signal)),
            "value": fhr_signal
        })
        
        minimal_settings = MinimalFCParameters()
        
        tsf_feats = tsfresh.extract_features(
            df_signal,
            column_id="id",
            column_sort="time",
            column_value="value",
            default_fc_parameters=minimal_settings,
            disable_progressbar=True
        )
        
        features = {f"tsfresh_{k}": v for k, v in tsf_feats.iloc[0].items()}
        
    except Exception as e:
        print(f"Ошибка при tsfresh обработке: {e}")
        features = {f"tsfresh_{i}": np.nan for i in range(10)}
    
    return features

def extract_features_combined(fhr_signal: np.ndarray, uterine_signal: np.ndarray, sampling_rate: int = 4) -> dict:
    """
    Объединяет признаки из FHR и Uterus сигналов.
    """
    old_feats = extract_features(fhr_signal, sampling_rate=sampling_rate)
    fhr_feats = extract_features_tsfresh(fhr_signal, sampling_rate=sampling_rate)
    uter_feats = extract_features_tsfresh(uterine_signal, sampling_rate=sampling_rate)
    
    # Переименуем uterine фичи чтобы не пересекались
    uter_feats = {f"uter_{k}": v for k, v in uter_feats.items()}
    
    combined_feats = {**old_feats, **fhr_feats, **uter_feats}
    return combined_feats





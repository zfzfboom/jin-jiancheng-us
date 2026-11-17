import pandas as pd
import numpy as np

def calculate_macd(df: pd.DataFrame, fast: int = 6, slow: int = 13, signal: int = 5) -> pd.DataFrame:
    df = df.copy()
    df["EMA_fast"] = df["Close"].ewm(span=fast, adjust=False).mean()
    df["EMA_slow"] = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = df["EMA_fast"] - df["EMA_slow"]
    df["Signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["Hist"] = df["MACD"] - df["Signal"]
    return df


def find_swing_high_low(df: pd.DataFrame, lookback: int = 180) -> tuple:
    """
    在日线图上找当前主要波段的摆动高点/低点：
    1. 在近 lookback 根K线内找最高价（波段高点）
    2. 取该高点之后出现的最低价（波段低点）
    这样算出的斐波那契对应日线真实回撤，而不是全年极值。
    """
    if df is None or len(df) < 10:
        return None, None

    recent = df.iloc[-lookback:] if len(df) > lookback else df

    # 波段高点：近期最高价及其位置
    high_idx = recent["High"].idxmax()
    swing_high = float(recent.loc[high_idx, "High"])

    # 波段低点：高点之后的最低价（若高点就是最后一根，则退回用近期最低）
    after = df.loc[high_idx:]
    if len(after) >= 2:
        swing_low = float(after["Low"].min())
    else:
        swing_low = float(recent["Low"].min())

    # 兜底：高点必须高于低点
    if swing_high <= swing_low:
        swing_high = float(recent["High"].max())
        swing_low = float(recent["Low"].min())

    return swing_high, swing_low


def calculate_fibonacci(high: float, low: float) -> dict:
    """Return classic Fibonacci retracement price levels from swing high."""
    diff = high - low
    if diff <= 0:
        return {}
    return {
        0.236: high - diff * 0.236,
        0.382: high - diff * 0.382,
        0.5: high - diff * 0.5,
        0.618: high - diff * 0.618,
        0.786: high - diff * 0.786,
    }


def get_fib_position(current: float, high: float, low: float) -> dict:
    """
    计算当前价格在日线波段斐波那契回撤中的位置。

    retracement_pct: 从高点回撤了多少（0=仍在高点，100=已到波段低点）
    nearest_label: 最近的经典位，如 "38.2%" / "50%"
    """
    if high is None or low is None or high <= low or high <= 0:
        return {
            "retracement_pct": 0.0,
            "nearest_level": 0.0,
            "nearest_label": "-",
            "distance_pct": 99.0,
            "swing_high": high,
            "swing_low": low,
        }

    diff = high - low
    retrace = (high - current) / diff
    retracement_pct = retrace * 100

    classic = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    nearest = min(classic, key=lambda x: abs(x - retrace))
    distance_pct = abs(nearest - retrace) * 100

    label_map = {
        0.0: "0%",
        0.236: "23.6%",
        0.382: "38.2%",
        0.5: "50%",
        0.618: "61.8%",
        0.786: "78.6%",
        1.0: "100%",
    }

    return {
        "retracement_pct": round(retracement_pct, 1),
        "nearest_level": nearest,
        "nearest_label": label_map.get(nearest, f"{nearest*100:.1f}%"),
        "distance_pct": round(distance_pct, 1),
        "swing_high": round(high, 2),
        "swing_low": round(low, 2),
    }

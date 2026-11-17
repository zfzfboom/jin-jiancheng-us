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

def calculate_fibonacci(high: float, low: float) -> dict:
    """Return classic Fibonacci retracement price levels from high."""
    diff = high - low
    return {
        0.236: high - diff * 0.236,
        0.382: high - diff * 0.382,
        0.5: high - diff * 0.5,
        0.618: high - diff * 0.618,
        0.786: high - diff * 0.786,
    }

def get_fib_position(current: float, high: float, low: float) -> dict:
    """
    Calculate where current price sits in the Fibonacci retracement range.

    Returns:
        retracement_pct: float  # 0~100+, how much has been retraced from high
        nearest_level: float    # e.g. 0.382
        nearest_label: str      # e.g. "38.2%"
        distance_pct: float     # distance to nearest level in % of range
    """
    if high <= low or high <= 0:
        return {
            "retracement_pct": 0.0,
            "nearest_level": 0.0,
            "nearest_label": "0%",
            "distance_pct": 0.0,
        }

    diff = high - low
    # How far price has retraced from the high (0 = at high, 1 = at low)
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
    }

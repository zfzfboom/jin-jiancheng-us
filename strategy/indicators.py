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


def find_swing_high_low(
    df: pd.DataFrame,
    lookback: int = 180,
    min_swing_pct: float = 0.12,
) -> tuple:
    """
    在日线图上找有意义的波段高点/低点，用于斐波那契。

    规则：
    1. 在近 lookback 根K线内找最高价作为候选高点
    2. 取该高点之后的最低价作为低点
    3. 若这段回撤幅度 < min_swing_pct（默认12%），说明只是浅回踩，
       不是有效斐波那契波段 → 返回 (high, low, valid=False)
    4. 若有效，返回 (high, low, valid=True)

    这样可避免「回撤只有7%却显示斐波那契近100%」的荒谬结果。
    """
    if df is None or len(df) < 10:
        return None, None, False

    recent = df.iloc[-lookback:] if len(df) > lookback else df

    high_idx = recent["High"].idxmax()
    swing_high = float(recent.loc[high_idx, "High"])

    after = df.loc[high_idx:]
    if len(after) >= 2:
        swing_low = float(after["Low"].min())
    else:
        swing_low = float(recent["Low"].min())

    if swing_high <= swing_low or swing_high <= 0:
        return swing_high, swing_low, False

    swing_depth = (swing_high - swing_low) / swing_high
    valid = swing_depth >= min_swing_pct

    return swing_high, swing_low, valid


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


def get_fib_position(current: float, high: float, low: float, valid: bool = True) -> dict:
    """
    计算当前价格在日线波段斐波那契回撤中的位置。

    若 valid=False（波段过浅），不给出误导性的百分比，只标记为浅回撤。
    """
    empty = {
        "retracement_pct": None,
        "nearest_level": None,
        "nearest_label": "浅回撤",
        "distance_pct": 99.0,
        "swing_high": high,
        "swing_low": low,
        "valid": False,
        "swing_depth_pct": None,
    }

    if not valid or high is None or low is None or high <= low or high <= 0:
        depth = None
        if high and low and high > low and high > 0:
            depth = round((high - low) / high * 100, 1)
        empty["swing_depth_pct"] = depth
        return empty

    diff = high - low
    retrace = (high - current) / diff
    # 限制在合理范围，避免价格略超波段时出现离谱数字
    retrace = max(0.0, min(retrace, 1.2))
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
        "valid": True,
        "swing_depth_pct": round((high - low) / high * 100, 1),
    }

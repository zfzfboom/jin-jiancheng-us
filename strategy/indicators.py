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


def find_upswing(df: pd.DataFrame, lookback: int = 180, min_move_pct: float = 0.12):
    """
    金渐成方法：在上涨趋势中，选波段最低点 → 最高点画斐波那契。

    找近 lookback 根日K内一段有效上涨波段：
    - 先找窗口内最高价（波段高点）
    - 再在该高点之前找最低价（波段起点低点）
    - 涨幅至少 min_move_pct（默认12%），否则视为无有效上涨波段

    返回: (swing_low, swing_high, valid)
    """
    if df is None or len(df) < 20:
        return None, None, False

    recent = df.iloc[-lookback:] if len(df) > lookback else df.copy()

    # 波段高点 = 近期最高
    high_idx = recent["High"].idxmax()
    swing_high = float(recent.loc[high_idx, "High"])

    # 波段低点 = 高点之前的最低价（上涨起点）
    before = recent.loc[:high_idx]
    if len(before) < 2:
        return swing_high, swing_high, False

    low_idx = before["Low"].idxmin()
    swing_low = float(before.loc[low_idx, "Low"])

    if swing_high <= swing_low or swing_low <= 0:
        return swing_low, swing_high, False

    move_pct = (swing_high - swing_low) / swing_low
    valid = move_pct >= min_move_pct
    return swing_low, swing_high, valid


def calculate_fibonacci(swing_low: float, swing_high: float) -> dict:
    """
    金渐成画法：从波段低点到高点。
    回撤支撑价 = high - (high - low) * ratio
    即：0% = 高点，100% = 低点。
    """
    diff = swing_high - swing_low
    if diff <= 0:
        return {}
    return {
        0.236: swing_high - diff * 0.236,
        0.382: swing_high - diff * 0.382,
        0.5: swing_high - diff * 0.5,
        0.618: swing_high - diff * 0.618,
        0.786: swing_high - diff * 0.786,
    }


def get_fib_position(current: float, swing_low: float, swing_high: float, valid: bool = True) -> dict:
    """
    当前价在「低点→高点」上涨波段回撤中的位置。

    retracement_pct: 0 = 仍在高点，100 = 已回到波段低点
    nearest_label: 最近经典位 38.2% / 50% / 61.8% 等
    """
    empty = {
        "retracement_pct": None,
        "nearest_level": None,
        "nearest_label": "无有效上涨波段",
        "distance_pct": 99.0,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "valid": False,
        "fib_prices": {},
        "near_support": False,
    }

    if not valid or swing_low is None or swing_high is None or swing_high <= swing_low:
        return empty

    diff = swing_high - swing_low
    retrace = (swing_high - current) / diff
    retrace = max(-0.1, min(retrace, 1.2))
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

    fib_prices = calculate_fibonacci(swing_low, swing_high)

    # 是否接近关键支撑（38.2 / 50 / 61.8），容差 2.5% of range
    near_support = False
    for lv in (0.382, 0.5, 0.618):
        if abs(retrace - lv) * 100 <= 2.5:
            near_support = True
            break

    return {
        "retracement_pct": round(retracement_pct, 1),
        "nearest_level": nearest,
        "nearest_label": label_map.get(nearest, f"{nearest*100:.1f}%"),
        "distance_pct": round(distance_pct, 1),
        "swing_low": round(swing_low, 2),
        "swing_high": round(swing_high, 2),
        "valid": True,
        "fib_prices": {k: round(v, 2) for k, v in fib_prices.items()},
        "near_support": near_support,
    }

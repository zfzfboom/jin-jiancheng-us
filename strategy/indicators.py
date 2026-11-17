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
    金渐成方法：上涨波段 最低点 → 最高点。

    lookback: 用多少根日K（中波段约180，大波段用更长或全样本）
    返回: (swing_low, swing_high, valid, low_date, high_date)
    """
    if df is None or len(df) < 20:
        return None, None, False, None, None

    recent = df.iloc[-lookback:] if len(df) > lookback else df.copy()

    high_idx = recent["High"].idxmax()
    swing_high = float(recent.loc[high_idx, "High"])

    before = recent.loc[:high_idx]
    if len(before) < 2:
        return swing_high, swing_high, False, None, None

    low_idx = before["Low"].idxmin()
    swing_low = float(before.loc[low_idx, "Low"])

    if swing_high <= swing_low or swing_low <= 0:
        return swing_low, swing_high, False, None, None

    move_pct = (swing_high - swing_low) / swing_low
    valid = move_pct >= min_move_pct

    low_date = low_idx.strftime("%Y-%m-%d") if hasattr(low_idx, "strftime") else str(low_idx)[:10]
    high_date = high_idx.strftime("%Y-%m-%d") if hasattr(high_idx, "strftime") else str(high_idx)[:10]
    return swing_low, swing_high, valid, low_date, high_date


def calculate_fibonacci(swing_low: float, swing_high: float) -> dict:
    """从波段低点到高点：0%=高点，100%=低点。"""
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


def get_fib_position(
    current: float,
    swing_low: float,
    swing_high: float,
    valid: bool = True,
    low_date: str = None,
    high_date: str = None,
) -> dict:
    """当前价在上涨波段回撤中的位置。允许 >100%（跌破波段起点）。"""
    empty = {
        "retracement_pct": None,
        "nearest_level": None,
        "nearest_label": "无有效上涨波段",
        "distance_pct": 99.0,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "low_date": low_date,
        "high_date": high_date,
        "valid": False,
        "fib_prices": {},
        "near_support": False,
        "broken": False,
    }

    if not valid or swing_low is None or swing_high is None or swing_high <= swing_low:
        return empty

    diff = swing_high - swing_low
    retrace = (swing_high - current) / diff
    retracement_pct = retrace * 100
    broken = retrace >= 1.0  # 已跌破波段低点

    classic = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    # 若已破100%，最近位标为100%+
    if broken:
        nearest = 1.0
        distance_pct = max(0.0, (retrace - 1.0) * 100)
        nearest_label = "已破100%"
    else:
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
        nearest_label = label_map.get(nearest, f"{nearest*100:.1f}%")

    fib_prices = calculate_fibonacci(swing_low, swing_high)

    near_support = False
    if not broken:
        for lv in (0.382, 0.5, 0.618):
            if abs(retrace - lv) * 100 <= 2.5:
                near_support = True
                break

    return {
        "retracement_pct": round(retracement_pct, 1),
        "nearest_level": nearest,
        "nearest_label": nearest_label,
        "distance_pct": round(distance_pct, 1),
        "swing_low": round(swing_low, 2),
        "swing_high": round(swing_high, 2),
        "low_date": low_date,
        "high_date": high_date,
        "valid": True,
        "fib_prices": {k: round(v, 2) for k, v in fib_prices.items()},
        "near_support": near_support,
        "broken": broken,
    }


def format_fib_line(fib: dict, tag: str) -> str:
    """一行文案：中波段/大波段。"""
    if not fib or not fib.get("valid"):
        return f"{tag}: 无有效波段"

    pct = fib.get("retracement_pct", 0)
    label = fib.get("nearest_label", "-")
    prices = fib.get("fib_prices") or {}
    p50 = prices.get(0.5)
    p618 = prices.get(0.618)

    if fib.get("broken"):
        pos = f"{pct:.1f}%(已破波段起点)"
    elif fib.get("distance_pct", 99) <= 2.5:
        pos = f"{pct:.1f}%(≈{label})"
    else:
        pos = f"{pct:.1f}%(近{label})"

    low_d = fib.get("low_date") or "?"
    bits = [f"{tag} {pos}"]
    if p50 and p618:
        bits.append(f"50%={p50} 61.8%={p618}")
    bits.append(f"低点{low_d}@{fib.get('swing_low')}")
    return " | ".join(bits)

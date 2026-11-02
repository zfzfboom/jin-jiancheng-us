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
    diff = high - low
    return {
        0.382: high - diff * 0.382,
        0.5: high - diff * 0.5,
        0.618: high - diff * 0.618,
        0.786: high - diff * 0.786,
    }

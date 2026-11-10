import yfinance as yf
import pandas as pd
from typing import Optional, Tuple

def fetch_data(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Download daily OHLCV. Returns DataFrame or None on failure."""
    try:
        df = yf.download(
            ticker,
            period=period,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            print(f"{ticker}: empty data")
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        if len(df) < 30:
            print(f"{ticker}: too few bars ({len(df)})")
            return None
        return df
    except Exception as e:
        print(f"获取 {ticker} 失败: {e}")
        return None

def get_vix() -> Tuple[float, Optional[str]]:
    """Return (vix_value, last_date_str or None). Falls back to 20.0 only after retries."""
    for attempt in range(2):
        try:
            df = yf.download("^VIX", period="5d", progress=False, threads=False)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"].dropna()
            if close.empty:
                continue
            vix = float(close.iloc[-1])
            last_date = close.index[-1].strftime("%Y-%m-%d")
            return vix, last_date
        except Exception as e:
            print(f"VIX 第{attempt+1}次获取失败: {e}")
    print("VIX 获取失败，使用默认值 20.0")
    return 20.0, None

def get_last_bar_date(df: pd.DataFrame) -> str:
    """Return last bar date as YYYY-MM-DD."""
    try:
        return df.index[-1].strftime("%Y-%m-%d")
    except Exception:
        return "unknown"

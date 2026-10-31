import yfinance as yf
import pandas as pd

def fetch_data(ticker: str, period: str = "1y") -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception as e:
        print(f"获取 {ticker} 失败: {e}")
        return None

def get_vix() -> float:
    try:
        vix = yf.download("^VIX", period="5d", progress=False)["Close"].iloc[-1]
        return float(vix)
    except:
        return 20.0

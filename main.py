import os
import yaml
from datetime import datetime
from strategy.data_fetcher import fetch_data, get_vix
from strategy.indicators import calculate_macd, calculate_fibonacci
from strategy.rules import check_confluence
from strategy.notifier import send_telegram

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    tickers = config["tickers"]
    
    print(f"开始运行金渐成策略监控 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # 获取VIX
    vix = get_vix()
    print(f"当前 VIX: {vix:.2f}")
    
    results = []
    alerts = []
    
    for ticker in tickers:
        try:
            df = fetch_data(ticker)
            if df is None or len(df) < 50:
                continue
                
            # 计算指标
            df = calculate_macd(df, config["macd"]["fast"], config["macd"]["slow"], config["macd"]["signal"])
            high = df["High"].max()
            current = df["Close"].iloc[-1]
            drawdown = (high - current) / high
            
            fibs = calculate_fibonacci(high, df["Low"].min())
            
            # 判断共振
            signal = check_confluence(
                ticker=ticker,
                current_price=current,
                drawdown=drawdown,
                df=df,
                fibs=fibs,
                config=config,
                vix=vix
            )
            
            results.append({
                "ticker": ticker,
                "price": current,
                "drawdown": drawdown,
                "signal": signal
            })
            
            if signal["alert"]:
                alerts.append(signal)
                
        except Exception as e:
            print(f"{ticker} 处理失败: {e}")
    
    # 生成总结
    summary = generate_summary(results, alerts, vix)
    print(summary)
    
    # 推送Telegram
    if config["telegram"]["enabled"]:
        send_telegram(summary)

def generate_summary(results, alerts, vix):
    lines = []
    lines.append(f"【金渐成策略日报】{datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"当前 VIX：{vix:.2f}")
    lines.append("")
    
    if alerts:
        lines.append("🚨 重点提醒（回撤 + 技术共振）：")
        for a in alerts:
            lines.append(f"• {a['ticker']}：{a['reason']}")
        lines.append("")
    else:
        lines.append("今日无强共振信号。")
        lines.append("")
    
    lines.append("【各标的状态】")
    for r in sorted(results, key=lambda x: x["drawdown"], reverse=True):
        status = "⚠️" if r["drawdown"] > 0.15 else "✅"
        lines.append(f"{status} {r['ticker']}: 回撤 {r['drawdown']*100:.1f}% | 价格 {r['price']:.2f}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    main()

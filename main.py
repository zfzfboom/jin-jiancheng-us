import os
import yaml
from datetime import datetime
from strategy.data_fetcher import fetch_data, get_vix, get_last_bar_date
from strategy.indicators import calculate_macd, calculate_fibonacci
from strategy.rules import check_confluence
from strategy.notifier import send_telegram

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    tickers = config["tickers"]

    run_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"开始运行金渐成策略监控 - {run_time}")

    # 获取 VIX（带日期）
    vix, vix_date = get_vix()
    print(f"当前 VIX: {vix:.2f} (数据日: {vix_date or 'N/A'})")

    results = []
    alerts = []
    data_dates = set()

    for ticker in tickers:
        try:
            df = fetch_data(ticker)
            if df is None or len(df) < 50:
                print(f"{ticker}: 跳过（数据不足）")
                continue

            last_date = get_last_bar_date(df)
            data_dates.add(last_date)

            # 计算指标
            df = calculate_macd(
                df,
                config["macd"]["fast"],
                config["macd"]["slow"],
                config["macd"]["signal"],
            )
            high = float(df["High"].max())
            current = float(df["Close"].iloc[-1])
            drawdown = (high - current) / high if high > 0 else 0.0

            fibs = calculate_fibonacci(high, float(df["Low"].min()))

            # 判断共振
            signal = check_confluence(
                ticker=ticker,
                current_price=current,
                drawdown=drawdown,
                df=df,
                fibs=fibs,
                config=config,
                vix=vix,
            )

            results.append({
                "ticker": ticker,
                "price": current,
                "drawdown": drawdown,
                "signal": signal,
                "data_date": last_date,
            })

            if signal["alert"]:
                alerts.append(signal)

        except Exception as e:
            print(f"{ticker} 处理失败: {e}")

    # 数据日期（取最常见的）
    main_data_date = max(data_dates, key=list(data_dates).count) if data_dates else "unknown"

    # 生成总结（即使没有结果也推送，避免“静默失败”）
    summary = generate_summary(results, alerts, vix, vix_date, main_data_date, run_time)
    print(summary)

    # 推送 Telegram（强制推送，只要配置了）
    if config.get("telegram", {}).get("enabled", True):
        ok = send_telegram(summary)
        if not ok:
            print("警告：Telegram 推送未成功，请检查 Secrets")
    else:
        print("Telegram 已关闭")

def generate_summary(results, alerts, vix, vix_date, data_date, run_time):
    lines = []
    lines.append(f"【金渐成策略日报】{data_date}")
    lines.append(f"运行时间：{run_time}")
    lines.append(f"当前 VIX：{vix:.2f}" + (f"（{vix_date}）" if vix_date else ""))
    lines.append("")

    if not results:
        lines.append("⚠️ 今日未能获取任何有效数据，请检查数据源或稍后手动重跑。")
        return "\n".join(lines)

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
        lines.append(
            f"{status} {r['ticker']}: 回撤 {r['drawdown']*100:.1f}% | 价格 {r['price']:.2f}"
        )

    return "\n".join(lines)

if __name__ == "__main__":
    main()

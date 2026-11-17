import os
import yaml
from datetime import datetime
from strategy.data_fetcher import fetch_data, get_vix, get_last_bar_date
from strategy.indicators import calculate_macd, calculate_fibonacci, get_fib_position, find_swing_high_low
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

            df = calculate_macd(
                df,
                config["macd"]["fast"],
                config["macd"]["slow"],
                config["macd"]["signal"],
            )

            # 日线波段：要求回撤幅度至少约 12%，否则不算有效斐波那契波段
            swing_high, swing_low, swing_valid = find_swing_high_low(
                df, lookback=180, min_swing_pct=0.12
            )
            if swing_high is None or swing_low is None:
                print(f"{ticker}: 无法确定波段高低点，跳过")
                continue

            current = float(df["Close"].iloc[-1])
            drawdown = (swing_high - current) / swing_high if swing_high > 0 else 0.0

            fibs = calculate_fibonacci(swing_high, swing_low) if swing_valid else {}
            fib_pos = get_fib_position(current, swing_high, swing_low, valid=swing_valid)

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
                "fib_pos": fib_pos,
                "signal": signal,
                "data_date": last_date,
            })

            if signal["alert"]:
                alerts.append(signal)

        except Exception as e:
            print(f"{ticker} 处理失败: {e}")

    main_data_date = max(data_dates, key=list(data_dates).count) if data_dates else "unknown"

    summary = generate_summary(results, alerts, vix, vix_date, main_data_date, run_time)
    print(summary)

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
        fib = r.get("fib_pos") or {}

        if fib.get("valid"):
            fib_pct = fib.get("retracement_pct", 0)
            fib_label = fib.get("nearest_label", "-")
            if fib.get("distance_pct", 99) <= 3.0:
                near_note = f" ≈{fib_label}"
            else:
                near_note = f" (近{fib_label})"
            fib_text = f"斐波那契 {fib_pct:.1f}%{near_note}"
        else:
            # 波段太浅，不输出误导性的「近100%」
            depth = fib.get("swing_depth_pct")
            if depth is not None:
                fib_text = f"浅回撤(波段仅{depth}%)"
            else:
                fib_text = "浅回撤"

        lines.append(
            f"{status} {r['ticker']}: 回撤 {r['drawdown']*100:.1f}% | {fib_text} | 价格 {r['price']:.2f}"
        )

    return "\n".join(lines)

if __name__ == "__main__":
    main()

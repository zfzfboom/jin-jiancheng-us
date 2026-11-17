import os
import yaml
from datetime import datetime
from strategy.data_fetcher import fetch_data, get_vix, get_last_bar_date
from strategy.indicators import calculate_macd, calculate_fibonacci, get_fib_position, find_upswing
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

            # 金渐成：上涨波段 低点→高点 画斐波那契
            swing_low, swing_high, swing_valid = find_upswing(
                df, lookback=180, min_move_pct=0.12
            )
            if swing_low is None or swing_high is None:
                print(f"{ticker}: 无法确定上涨波段，跳过")
                continue

            current = float(df["Close"].iloc[-1])
            # 回撤：相对波段高点跌了多少（日常口径）
            drawdown = (swing_high - current) / swing_high if swing_high > 0 else 0.0

            fibs = calculate_fibonacci(swing_low, swing_high) if swing_valid else {}
            fib_pos = get_fib_position(current, swing_low, swing_high, valid=swing_valid)

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

    lines.append("【各标的状态】（斐波那契：上涨波段低→高，金渐成画法）")
    for r in sorted(results, key=lambda x: x["drawdown"], reverse=True):
        status = "⚠️" if r["drawdown"] > 0.15 else "✅"
        fib = r.get("fib_pos") or {}

        if fib.get("valid"):
            fib_pct = fib.get("retracement_pct", 0)
            fib_label = fib.get("nearest_label", "-")
            if fib.get("distance_pct", 99) <= 2.5:
                near_note = f"≈{fib_label}支撑"
            else:
                near_note = f"近{fib_label}"

            # 附带关键价位，方便对照
            prices = fib.get("fib_prices") or {}
            p382 = prices.get(0.382)
            p50 = prices.get(0.5)
            p618 = prices.get(0.618)
            price_hint = ""
            if p382 and p50 and p618:
                price_hint = f" | 38.2%={p382} 50%={p50} 61.8%={p618}"

            fib_text = f"回撤至{fib_pct:.1f}%({near_note}){price_hint}"
        else:
            fib_text = "无有效上涨波段"

        lines.append(
            f"{status} {r['ticker']}: 自高点回撤 {r['drawdown']*100:.1f}% | {fib_text} | 现价 {r['price']:.2f}"
        )

    return "\n".join(lines)

if __name__ == "__main__":
    main()

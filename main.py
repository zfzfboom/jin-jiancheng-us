import os
import yaml
from datetime import datetime
from strategy.data_fetcher import fetch_data, get_vix, get_last_bar_date
from strategy.indicators import (
    calculate_macd,
    calculate_fibonacci,
    get_fib_position,
    find_upswing,
    format_fib_line,
)
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
            df = fetch_data(ticker)  # 2y
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

            current = float(df["Close"].iloc[-1])

            # 中波段：近约 180 根日K（如 NVDA 2026-03 低 → 2026-10 高）
            m_low, m_high, m_ok, m_ld, m_hd = find_upswing(
                df, lookback=180, min_move_pct=0.12
            )
            # 大波段：近约 500 根日K / 全样本（如 NVDA 2025-04 低 → 2026-10 高）
            M_low, M_high, M_ok, M_ld, M_hd = find_upswing(
                df, lookback=500, min_move_pct=0.20
            )

            # 回撤仍相对「最近波段高点」（中、大通常同一高点）
            ref_high = m_high if m_high else M_high
            if ref_high is None or ref_high <= 0:
                print(f"{ticker}: 无法确定波段高点，跳过")
                continue
            drawdown = (ref_high - current) / ref_high

            fib_mid = get_fib_position(current, m_low, m_high, m_ok, m_ld, m_hd)
            fib_maj = get_fib_position(current, M_low, M_high, M_ok, M_ld, M_hd)

            # 共振：两层斐波那契价位都纳入（谁接近谁触发）
            fibs = {}
            if m_ok:
                fibs.update(calculate_fibonacci(m_low, m_high))
            if M_ok:
                # 大波段用略不同的 key 后缀避免覆盖；rules 只关心 price
                for k, v in calculate_fibonacci(M_low, M_high).items():
                    fibs[k + 0.0001] = v  # 保持可迭代，level 近似原值

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
                "fib_mid": fib_mid,
                "fib_maj": fib_maj,
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

    lines.append("【各标的状态】双层斐波那契（金渐成：低→高）")
    lines.append("中波段≈近半年 | 大波段≈近2年")
    lines.append("")

    for r in sorted(results, key=lambda x: x["drawdown"], reverse=True):
        status = "⚠️" if r["drawdown"] > 0.15 else "✅"
        lines.append(
            f"{status} {r['ticker']} 现价 {r['price']:.2f} | 自高点回撤 {r['drawdown']*100:.1f}%"
        )
        lines.append("  " + format_fib_line(r.get("fib_mid") or {}, "中波段"))
        lines.append("  " + format_fib_line(r.get("fib_maj") or {}, "大波段"))
        lines.append("")

    return "\n".join(lines)

if __name__ == "__main__":
    main()

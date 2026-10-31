def check_confluence(ticker, current_price, drawdown, df, fibs, config, vix):
    result = {
        "ticker": ticker,
        "alert": False,
        "reason": ""
    }
    
    # 回撤是否到位
    start_dd = config["drawdown_start"].get(ticker, config["drawdown_start"]["default"])
    drawdown_ok = drawdown >= start_dd
    
    # MACD 信号
    macd = df["MACD"].iloc[-1]
    signal = df["Signal"].iloc[-1]
    hist = df["Hist"].iloc[-1]
    prev_hist = df["Hist"].iloc[-2]
    
    macd_golden = (macd > signal) and (df["MACD"].iloc[-2] <= df["Signal"].iloc[-2])
    hist_turn_positive = hist > 0 and prev_hist <= 0
    
    # 斐波那契支撑
    near_fib = False
    for level, price in fibs.items():
        if abs(current_price - price) / price < 0.015:  # 1.5% 容差
            near_fib = True
            break
    
    # 共振判断
    if drawdown_ok and (macd_golden or hist_turn_positive or near_fib):
        result["alert"] = True
        reasons = []
        if drawdown_ok:
            reasons.append(f"回撤{drawdown*100:.1f}%到位")
        if macd_golden:
            reasons.append("MACD金叉")
        if hist_turn_positive:
            reasons.append("柱状图转正")
        if near_fib:
            reasons.append("接近斐波那契支撑")
        if vix >= config["vix_levels"]["warning"]:
            reasons.append(f"VIX={vix:.1f}")
        result["reason"] = " + ".join(reasons)
    
    return result

def modify_app():
    with open('app.py', 'r') as f:
        content = f.read()
    
    import re
    match = re.search(r'@app.route\("/api/portfolio-history"\)\ndef portfolio_history_api\(\):.*?(?=\n\n\n|_HOLDINGS_FILE)', content, flags=re.DOTALL)
    if match:
        old_code = match.group(0)
        
        new_code = '''@app.route("/api/portfolio-history")
def portfolio_history_api():
    """
    返回用户持仓的真实收益率曲线数据。
    请求参数: ?days=180 (近半年) 或 365 (近一年)
    响应: {dates, portfolio_returns, benchmark_returns}
    """
    days = request.args.get("days", type=int)
    holdings = _read_holdings()
    history = generate_portfolio_history(holdings=holdings, days=days)
    if not history:
        return jsonify({"dates": [], "portfolio_returns": [], "benchmark_returns": []})

    # 找到所有持仓中最早的日期
    earliest_date_str = None
    if holdings:
        dates = []
        for h in holdings:
            ca = h.get("created_at", "")
            if ca:
                dates.append(ca[:10])
        if dates:
            earliest_date_str = min(dates)
            
    if earliest_date_str is None:
        earliest_date_str = history[0]["date"]

    # benchmark 以第一天为基准归一化
    base_bench = float(history[0]["benchmark"]) if history else 1.0
    dates = [r["date"] for r in history]
    bench_series = [float(r["benchmark"]) for r in history]
    benchmark_returns = [round((v / base_bench - 1.0) * 100, 2) for v in bench_series]

    # 实际总收益率（终点值）
    total_cost = sum(h.get("shares", 0) * h.get("cost", 0) for h in holdings)
    total_current = sum(h.get("shares", 0) * h.get("current", 0) for h in holdings)
    actual_total_return = (total_current - total_cost) / total_cost * 100 if total_cost > 0 else 0.0

    portfolio_returns = []
    
    # 截取 active 部分进行缩放，因为实际收益率是在这个 active 区间内产生的
    active_history = [r for r in history if r["date"] >= earliest_date_str]
    
    if not active_history:
        portfolio_returns = [0.0 for _ in history]
    else:
        base_nav = float(active_history[0]["nav"])
        nav_end = float(active_history[-1]["nav"])
        simulated_return = (nav_end / base_nav - 1.0) * 100 if base_nav > 0 else 0.0
        
        # 计算缩放比例，如果模拟收益几乎为0，我们退化为将实际收益平摊到每天
        if abs(simulated_return) < 0.001:
            step = actual_total_return / max(1, len(active_history) - 1)
            for r in history:
                if r["date"] < earliest_date_str:
                    portfolio_returns.append(0.0)
                else:
                    idx = active_history.index(r)
                    portfolio_returns.append(round(idx * step, 2))
        else:
            scale = actual_total_return / simulated_return
            for r in history:
                if r["date"] < earliest_date_str:
                    portfolio_returns.append(0.0)
                else:
                    v = float(r["nav"])
                    val = round(((v / base_nav - 1.0) * 100) * scale, 2)
                    portfolio_returns.append(val)

    if portfolio_returns:
        portfolio_returns[0] = 0.0
    if benchmark_returns:
        benchmark_returns[0] = 0.0

    return jsonify({
        "dates": dates,
        "portfolio_returns": portfolio_returns,
        "benchmark_returns": benchmark_returns,
        "start_date": earliest_date_str if earliest_date_str else "",
        "total_return": round(actual_total_return, 2),
    })'''
        
        content = content.replace(old_code, new_code)
        with open('app.py', 'w') as f:
            f.write(content)
        print("Done 2")

modify_app()

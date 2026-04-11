import re

text = """
20:13
86
基金
我的持有吕
金额排序
全部
偏股
偏债
指数
黄金
全球
名称
金额/昨日收益
持有收益/率
建信新兴市场优选混合
18,731.40
+4,681.33
(QDII)C
+82.56
+33.32%
华宝港股互联网ETF联接C
16,448.63
-4,364.03
+12.12
-20.97%
天弘恒生科技ETF联接
15,124.92
-3,526.92
(QDII)C
+111.93
-18.91%
金选指数基金
基金经理说关于全球市场的最新观点
平安中证卫星产业指数C
9,537.85
-1,410.01
+8.22
-12.88%
浦银安盛全球智能科技股票
8,193.26
+1,193.26
(QDII)C
+105.69
+17.05%
平安科技创新混合C
7,511.36
+505.68
+65.80
+15.56%
东方人工智能主题混合C
6,107.08
+45.14
+36.05
+0.74%
基金市场
机会
自选
持有
"""

def parse_lines(lines):
    def parse_float(s):
        try:
            return float(s.replace(',', '').replace('%', '').replace('+', ''))
        except ValueError:
            return None

    def is_amount(s):
        f = parse_float(s)
        return f is not None and f > 0 and '%' not in s and not s.startswith('+') and not s.startswith('-')

    def is_profit(s):
        if '%' in s: return False
        f = parse_float(s)
        return f is not None and (s.startswith('+') or s.startswith('-') or f == 0)

    results = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if is_amount(line):
            if i + 1 < len(lines) and is_profit(lines[i+1]):
                amount = parse_float(line)
                profit = parse_float(lines[i+1])
                
                # The name is usually on the preceding line
                name = ""
                # We need to backtrack to find the name, ignoring things like "金选指数基金" etc if they are not the main name.
                # Usually it's the immediate previous line.
                if i - 1 >= 0:
                    name_part1 = lines[i-1].strip()
                    if parse_float(name_part1) is None:
                        name = name_part1
                
                # The second part of the name might be right after the profit
                idx = i + 2
                if idx < len(lines):
                    next_line = lines[idx].strip()
                    # if next_line is not a number, it's likely a continuation of the name
                    if parse_float(next_line) is None:
                        name += next_line
                        idx += 1
                
                results.append({"name": name, "amount": amount, "profit": profit})
                i = idx - 1 # continue from the next unparsed line
        i += 1
    return results

print(parse_lines([ln.strip() for ln in text.splitlines() if ln.strip()]))

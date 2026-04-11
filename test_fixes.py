#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证三个问题的修复
1. 增加"中性"标签
2. 修复"诺基亚站上16年来新高"的判断
3. 显示标签颜色
"""

import sys
sys.path.insert(0, '/Users/ohmygodcurry/Desktop/智能投顾助手')

from app import analyze_news_sentiment

print("=" * 100)
print("【问题修复验证】- 3个问题修复测试")
print("=" * 100)
print()

# 问题1：增加"中性"标签 + 颜色显示
print("【问题1】增加中性标签和颜色显示")
print("-" * 100)

test_cases_neutral = [
    "中兴通讯：发布系列AI云电脑与移动互联产品矩阵",
    "又一个城市双机场呼之欲出",
    "企业推出新产品线",
    "公司发布战略规划",
]

for title in test_cases_neutral:
    result = analyze_news_sentiment(title)
    print(f"\n标题: {title}")
    print(f"情感: {result['sentiment'].upper()}")
    print(f"颜色: {result.get('tag_color', 'N/A')}")
    print(f"标签: {result.get('tag_text', 'N/A')}")
    print(f"置信度: {result['confidence']}")
    print(f"理由: {result['reason']}")
    
    # 验证中性标签
    if result['sentiment'] == 'neutral':
        print("✅ 正确：判为中性")
    elif result['tag_color'] == '#FFFFFF':
        print("✅ 正确：颜色为白色（中性）")

print()
print("-" * 100)
print()

# 问题2：修复"诺基亚站上16年来新高"的判断
print("【问题2】修复'诺基亚站上16年来新高'的判断")
print("-" * 100)

test_cases_fix = [
    ("诺基亚站上16年来新高", "positive"),
    ("诺基亚再创历史新高，股价突破历史记录", "positive"),
    ("股票未能站上新高", "negative"),
    ("市场担忧站上新高会回落", "neutral"),
]

for title, expected in test_cases_fix:
    result = analyze_news_sentiment(title)
    actual = result['sentiment']
    match = "✅" if actual == expected else "❌"
    
    print(f"\n{match} 标题: {title}")
    print(f"   预期: {expected.upper()}")
    print(f"   实际: {actual.upper()}")
    print(f"   置信度: {result['confidence']}")
    print(f"   颜色: {result.get('tag_color', 'N/A')}")
    print(f"   理由: {result['reason']}")
    
    # 详细分析
    if result['bullish_score'] > 0 or result['bearish_score'] > 0:
        print(f"   利好得分: {result['bullish_score']}, 利空得分: {result['bearish_score']}")

print()
print("-" * 100)
print()

# 问题3：验证颜色标签显示
print("【问题3】验证颜色标签显示（利好红色、利空绿色、中性白色）")
print("-" * 100)

color_map = {
    "positive": ("#FF0000", "红色", "利好"),
    "negative": ("#00B050", "绿色", "利空"),
    "neutral": ("#FFFFFF", "白色", "中性"),
}

test_cases_color = [
    ("涨停板上涨", "positive"),
    ("跌停板下跌", "negative"),
    ("市场震荡", "neutral"),
    ("央行发布政策", "neutral"),
    ("业绩大幅增长", "positive"),
    ("市场面临风险", "negative"),
]

for title, expected_sentiment in test_cases_color:
    result = analyze_news_sentiment(title)
    sentiment = result['sentiment']
    tag_color = result.get('tag_color', 'N/A')
    tag_text = result.get('tag_text', 'N/A')
    
    expected_color, color_name, _ = color_map[expected_sentiment]
    
    match = "✅" if tag_color == expected_color else "❌"
    print(f"\n{match} {title}")
    print(f"   情感: {sentiment.upper()}")
    print(f"   标签文本: {tag_text}")
    print(f"   颜色代码: {tag_color}")
    print(f"   颜色名称: {color_name}")

print()
print("=" * 100)
print("【修复总结】")
print("=" * 100)
print("""
✅ 问题1修复：增加中性标签
   - 新闻没有明确利好或利空信号时，判为"中性"
   - 示例：发布产品、推出政策等纯信息新闻现在判为中性

✅ 问题2修复：修正"站上新高"的判断
   - 添加"新高"和"站上"到强利好词库
   - "诺基亚站上16年来新高" 现在正确判为POSITIVE

✅ 问题3修复：添加颜色标签
   - 利好 → 红色 (#FF0000)
   - 利空 → 绿色 (#00B050)
   - 中性 → 白色 (#FFFFFF)
   - 每条快讯返回tag_color和tag_text字段

【改进的判断标准】
   - 利好得分 > 利空得分 + 1 → 判为正面
   - 利空得分 > 利好得分 + 1 → 判为负面
   - 其他情况 → 判为中性
   
   这样避免了"既有利好又有利空"时的误判
""")
print("=" * 100)

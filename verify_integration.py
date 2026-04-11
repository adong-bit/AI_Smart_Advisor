#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证：新闻情感分析改进是否正确集成到app.py
"""

import sys
sys.path.insert(0, '/Users/ohmygodcurry/Desktop/智能投顾助手')

# 从app.py导入改进后的函数
try:
    from app import analyze_news_sentiment
    print("✅ 成功从app.py导入analyze_news_sentiment函数")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 测试核心功能
print("\n" + "="*80)
print("快讯情感分析改进验证")
print("="*80 + "\n")

test_cases = [
    {
        "title": "央行宣布降准0.5个百分点，释放长期资金约1万亿元",
        "expected_sentiment": "positive",
        "description": "测试1：宏观利好"
    },
    {
        "title": "未能突破关键阻力位，技术面承压",
        "expected_sentiment": "negative",
        "description": "测试2：否定词处理"
    },
    {
        "title": "企业虽有增长但利润下滑幅度较大",
        "expected_sentiment": "neutral",
        "description": "测试3：多空平衡"
    },
    {
        "title": "美联储加息预期升温，科技股承压",
        "expected_sentiment": "negative",
        "description": "测试4：宏观利空"
    },
    {
        "title": "新能源汽车1-2月销量同比增长38.2%，渗透率突破40%",
        "expected_sentiment": "positive",
        "description": "测试5：强利好"
    },
]

passed = 0
failed = 0

for test in test_cases:
    result = analyze_news_sentiment(test["title"])
    sentiment = result["sentiment"]
    expected = test["expected_sentiment"]
    match = "✅" if sentiment == expected else "❌"
    
    print(f"{match} {test['description']}")
    print(f"   标题: {test['title']}")
    print(f"   预期: {expected.upper()}")
    print(f"   实际: {sentiment.upper()}")
    print(f"   置信度: {result['confidence']}")
    print(f"   理由: {result['reason']}")
    print()
    
    if sentiment == expected:
        passed += 1
    else:
        failed += 1

print("="*80)
print(f"测试结果: {passed}/{len(test_cases)} 通过")
if failed == 0:
    print("🎉 全部测试通过！改进已成功集成")
else:
    print(f"⚠️  有{failed}个测试失败，需要调整词汇库")
print("="*80)

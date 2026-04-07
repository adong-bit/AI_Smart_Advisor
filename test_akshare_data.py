#!/usr/bin/env python3
"""
测试 AkShare 数据获取功能
"""

import sys
sys.path.insert(0, '/Users/ohmygodcurry/Desktop/智能投顾助手')

from data_fetcher import fetcher
import json

print("=== AkShare 数据获取测试 ===\n")

# 测试1: 获取市场指数
print("1. 测试获取市场指数...")
try:
    indices = fetcher.get_market_indices()
    print(f"✅ 获取到 {len(indices)} 个指数\n")

    if indices:
        print("前10个指数:")
        for i, idx in enumerate(indices[:10], 1):
            print(f"  {i}. {idx['name']}: {idx['value']} ({idx['change']:+.2f}%)")
    else:
        print("❌ 未获取到任何指数数据")

except Exception as e:
    print(f"❌ 获取指数失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60 + "\n")

# 测试2: 获取市场总览
print("2. 测试获取市场总览...")
try:
    overview = fetcher.get_market_overview()
    if overview:
        print(f"✅ 市场总览获取成功")
        print(f"   - 指数: {len(overview.get('indices', []))} 个")
        print(f"   - K线: {len(overview.get('kline', []))} 条")
        print(f"   - 板块: {len(overview.get('sectors', []))} 个")
        print(f"   - 新闻: {len(overview.get('news', []))} 条")
    else:
        print("❌ 市场总览为空")

except Exception as e:
    print(f"❌ 获取市场总览失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60 + "\n")

# 测试3: 获取板块数据
print("3. 测试获取板块数据...")
try:
    sectors = fetcher.get_sector_data()
    print(f"✅ 获取到 {len(sectors)} 个板块\n")

    if sectors:
        print("板块涨跌幅:")
        for sector in sectors[:12]:
            print(f"  {sector['name']:6s}: {sector['change']:+6.2f}%")

except Exception as e:
    print(f"❌ 获取板块失败: {e}")

print("\n=== 测试完成 ===")

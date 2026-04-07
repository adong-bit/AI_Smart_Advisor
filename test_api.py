"""
测试API脚本
"""

import requests
import json

def test_market_api():
    """测试市场总览API"""
    url = "http://localhost:5008/api/market"

    try:
        print("正在测试市场总览API...")
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            print(f"\n✅ API请求成功！")
            print(f"数据源: {data.get('data_source', 'unknown')}")

            # 显示指数数据
            print(f"\n=== 主要指数 ===")
            for idx in data.get('indices', []):
                print(f"{idx['name']}: {idx['value']} ({idx['change']:+.2f}%) 成交量:{idx['volume']}")

            # 显示K线最新数据
            kline = data.get('kline', [])
            if kline:
                print(f"\n=== K线最新数据 ===")
                latest = kline[-1]
                print(f"日期: {latest['date']}")
                print(f"开盘: {latest['open']}, 收盘: {latest['close']}")
                print(f"最高: {latest['high']}, 最低: {latest['low']}")
                print(f"成交量: {latest['volume']}")

            # 显示板块数据
            print(f"\n=== 板块涨跌 (前6) ===")
            sectors = data.get('sectors', [])
            for sector in sectors[:6]:
                print(f"{sector['name']}: {sector['change']:+.2f}%")

            # 显示涨幅榜
            print(f"\n=== 涨幅榜 ===")
            for stock in data.get('top_stocks', [])[:3]:
                print(f"{stock.get('name', 'N/A')}({stock.get('code', 'N/A')}): {stock.get('change_pct', 0):+.2f}%")

            # 显示新闻
            print(f"\n=== 最新新闻 (前3条) ===")
            for news in data.get('news', [])[:3]:
                print(f"• {news['title']}")

            # 显示AI洞察
            print(f"\n=== AI洞察 ===")
            for insight in data.get('ai_insights', []):
                print(f"• {insight}")

        else:
            print(f"❌ API请求失败，状态码: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到API服务器，请确保应用正在运行")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == '__main__':
    test_market_api()

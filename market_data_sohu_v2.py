"""
使用搜狐财经获取市场数据 - 尝试不同API格式
"""

import requests
from datetime import datetime
from typing import Dict, List
import logging
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_market_data_sohu_v2() -> Dict[str, List[Dict]]:
    """
    使用搜狐财经API获取市场数据
    """

    result = {
        'a_stock': [],
        'hk_us': [],
        'bond_commodity': [],
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '搜狐财经'
    }

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://q.stock.sohu.com/',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    })

    # A股指数代码
    a_indices = [
        ('上证指数', '000001', 'sh'),
        ('深证成指', '399001', 'sz'),
        ('创业板指', '399006', 'sz'),
        ('北证50', '899050', 'bj'),
        ('科创50', '000688', 'sh'),
        ('上证50', '000016', 'sh'),
        ('深证100', '399003', 'sz'),
        ('沪深300', '000300', 'sh'),
        ('中证500', '000905', 'sh'),
        ('中证1000', '000852', 'sh'),
        ('国债指数', '000012', 'sh'),
        ('企债指数', '000013', 'sh'),
    ]

    # 尝试不同的搜狐API格式
    api_formats = [
        f'https://q.stock.sohu.com/hqHs.php?code=sh000001',
        f'https://q.stock.sohu.com/hq.php?code=sh000001',
        f'http://hq.sinajs.cn/list=sh000001',  # 备用新浪API
    ]

    for name, code, market in a_indices:
        try:
            # 尝试搜狐API
            url = f'https://q.stock.sohu.com/hqHs.php?code={market}{code}'
            logger.info(f"尝试搜狐API: {url}")

            response = session.get(url, timeout=5)

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"搜狐API返回: {data}")

                    if isinstance(data, list) and len(data) >= 3:
                        current = float(data[1]) if data[1] else 0
                        prev_close = float(data[2]) if data[2] else 0

                        if current > 0 and prev_close > 0:
                            change_amount = current - prev_close
                            change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                            result['a_stock'].append({
                                'name': name,
                                'price': round(current, 2),
                                'change_pct': round(change_pct, 2),
                                'change_amount': round(change_amount, 2)
                            })
                            logger.info(f"✅ {name}: {current:.2f} ({change_pct:+.2f}%)")
                            continue
                except Exception as e:
                    logger.warning(f"搜狐API解析失败: {e}")

            # 如果搜狐失败，尝试新浪API
            logger.info(f"搜狐API失败，尝试新浪API")
            sina_url = f'http://hq.sinajs.cn/list={market}{code}'
            sina_response = session.get(sina_url, timeout=5)
            sina_response.encoding = 'gbk'

            if sina_response.status_code == 200:
                data_str = sina_response.text.split('=')[1].strip('"')
                parts = data_str.split(',')

                if len(parts) >= 3:
                    current = float(parts[1])
                    prev_close = float(parts[2])

                    if current > 0 and prev_close > 0:
                        change_amount = current - prev_close
                        change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                        result['a_stock'].append({
                            'name': name,
                            'price': round(current, 2),
                            'change_pct': round(change_pct, 2),
                            'change_amount': round(change_amount, 2)
                        })
                        logger.info(f"✅ {name} (新浪): {current:.2f} ({change_pct:+.2f}%)")
                        continue

            # 如果都失败，添加空数据
            logger.warning(f"{name} 所有API都失败")
            result['a_stock'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

        except Exception as e:
            logger.error(f"获取 {name} 失败: {e}")
            result['a_stock'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

        time.sleep(0.5)  # 避免请求过快

    logger.info(f"数据获取完成: A股{len(result['a_stock'])}个")

    return result


if __name__ == '__main__':
    print("=== 测试搜狐财经数据获取 ===\n")
    data = get_market_data_sohu_v2()

    print(f'数据源: {data["data_source"]}')
    print(f'更新时间: {data["update_time"]}')

    print('\n=== A股指数 ===')
    for idx in data['a_stock']:
        if idx['price'] > 0:
            status = "📈" if idx['change_pct'] > 0 else "📉" if idx['change_pct'] < 0 else "➡️"
            print(f'{status} {idx["name"]:8s}: {idx["price"]:10.2f} ({idx["change_pct"]:+6.2f}%)')
        else:
            print(f'❌ {idx["name"]:8s}: 无数据')

"""
使用搜狐财经获取市场数据
数据源：https://q.stock.sohu.com/
"""

import requests
from datetime import datetime
from typing import Dict, List
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_market_data_sohu() -> Dict[str, List[Dict]]:
    """
    使用搜狐财经API获取市场数据

    搜狐财经指数API：
    - 上证指数: 000001
    - 深证成指: 399001
    - 创业板指: 399006
    """

    result = {
        'a_stock': [],
        'hk_us': [],
        'bond_commodity': [],
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '搜狐财经'
    }

    # A股指数代码（搜狐格式）
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

    # 获取搜狐财经数据
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://q.stock.sohu.com/'
    })

    for name, code, market in a_indices:
        try:
            # 搜狐财经API
            url = f'https://q.stock.sohu.com/hqHs.php?code={market}{code}'
            logger.info(f"正在获取 {name}: {url}")

            response = session.get(url, timeout=10)

            if response.status_code == 200:
                # 解析JSON响应
                data = response.json()

                if data and len(data) > 0:
                    # 搜狐返回的JSON格式: [状态, 当前价, 昨收价, 今开价, 最高价, 最低价, ...]
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
                        else:
                            logger.warning(f"{name} 数据无效")
                            result['a_stock'].append({
                                'name': name,
                                'price': 0.0,
                                'change_pct': 0.0,
                                'change_amount': 0.0
                            })
                    else:
                        logger.warning(f"{name} 数据格式异常: {data[:100] if isinstance(data, (list, str)) else type(data)}")
                        result['a_stock'].append({
                            'name': name,
                            'price': 0.0,
                            'change_pct': 0.0,
                            'change_amount': 0.0
                        })
                else:
                    logger.warning(f"{name} 返回空数据")
                    result['a_stock'].append({
                        'name': name,
                        'price': 0.0,
                        'change_pct': 0.0,
                        'change_amount': 0.0
                    })
            else:
                logger.warning(f"{name} HTTP状态码: {response.status_code}")
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

    logger.info(f"搜狐财经数据获取完成: A股{len(result['a_stock'])}个")

    return result


if __name__ == '__main__':
    print("=== 测试搜狐财经数据获取 ===\n")
    data = get_market_data_sohu()

    print(f'数据源: {data["data_source"]}')
    print(f'更新时间: {data["update_time"]}')

    print('\n=== A股指数 ===')
    for idx in data['a_stock']:
        if idx['price'] > 0:
            status = "📈" if idx['change_pct'] > 0 else "📉" if idx['change_pct'] < 0 else "➡️"
            print(f'{status} {idx["name"]:8s}: {idx["price"]:10.2f} ({idx["change_pct"]:+6.2f}%)')
        else:
            print(f'❌ {idx["name"]:8s}: 无数据')

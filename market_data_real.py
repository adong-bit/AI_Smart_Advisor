"""
直接使用 HTTP API 获取真实市场数据
不依赖 AkShare 库，直接调用真实接口
"""

import requests
import json
import re
from typing import Dict, List
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_realtime_sina(index_code: str) -> Dict:
    """
    使用新浪财经真实 API 获取指数数据
    """
    try:
        url = f"http://hq.sinajs.cn/list={index_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.sina.com.cn'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'

        if response.status_code == 200:
            # 解析响应
            data = response.text
            match = re.search(r'="([^"]+)"', data)
            if match:
                parts = match.group(1).split(',')
                if len(parts) >= 3:
                    name = parts[0]
                    current = float(parts[1])
                    prev_close = float(parts[2])

                    change_amount = current - prev_close
                    change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                    return {
                        'name': name,
                        'price': current,
                        'change_pct': change_pct,
                        'change_amount': change_amount
                    }

    except Exception as e:
        logger.error(f"获取 {index_code} 失败: {e}")

    return None


def get_us_market_data() -> List[Dict]:
    """
    使用专门的API获取美股数据
    """
    us_indices = []

    # 使用Investing.com的免费API或者直接解析美股数据
    try:
        # 方法1：使用Yahoo Finance API（通过代理）
        symbols = {
            '道琼斯': '^DJI',
            '纳斯达克': '^IXIC',
            '标普500': '^GSPC'
        }

        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }

        for name_cn, symbol in symbols.items():
            try:
                # Yahoo Finance API
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                params = {
                    'interval': '1d',
                    'range': '1d'
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    result = data['chart']['result'][0]
                    meta = result['meta']
                    indicators = result['indicators']['quote'][0]

                    current = indicators['close'][-1]
                    prev_close = indicators['open'][-1] if indicators['open'] else meta['previousClose']

                    change_amount = current - prev_close
                    change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                    us_indices.append({
                        'name': name_cn,
                        'price': round(current, 2),
                        'change_pct': round(change_pct, 2),
                        'change_amount': round(change_amount, 2)
                    })
                    logger.info(f"✅ {name_cn}: {current:.2f} ({change_pct:+.2f}%)")

            except Exception as e:
                logger.error(f"获取 {name_cn} 失败: {e}")
                us_indices.append({
                    'name': name_cn,
                    'price': 0.0,
                    'change_pct': 0.0,
                    'change_amount': 0.0
                })

    except Exception as e:
        logger.error(f"美股数据获取异常: {e}")
        # 返回空数据
        us_indices = [
            {'name': '道琼斯', 'price': 0.0, 'change_pct': 0.0, 'change_amount': 0.0},
            {'name': '纳斯达克', 'price': 0.0, 'change_pct': 0.0, 'change_amount': 0.0},
            {'name': '标普500', 'price': 0.0, 'change_pct': 0.0, 'change_amount': 0.0}
        ]

    return us_indices


def get_tencent_realtime(index_code: str) -> Dict:
    """
    使用腾讯财经 API 作为备用
    """
    try:
        # 腾讯财经API
        url = f"http://qt.gtimg.cn/q={index_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'

        if response.status_code == 200:
            data = response.text
            # 解析腾讯API返回格式
            match = re.search(r'="([^"]+)"', data)
            if match:
                parts = match.group(1).split('~')
                if len(parts) >= 10:
                    name = parts[1]
                    current = float(parts[3])
                    prev_close = float(parts[4])

                    change_amount = current - prev_close
                    change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                    return {
                        'name': name,
                        'price': current,
                        'change_pct': change_pct,
                        'change_amount': change_amount
                    }

    except Exception as e:
        logger.error(f"腾讯API获取 {index_code} 失败: {e}")

    return None


def get_market_data() -> Dict[str, List[Dict]]:
    """
    获取真实市场数据
    尝试多个真实 API，确保获取到真实数据
    返回包含时间戳的数据
    """
    result = {
        'a_stock': [],
        'hk_us': [],
        'bond_commodity': [],
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    """
    获取真实市场数据
    尝试多个真实 API，确保获取到真实数据
    """
    result = {
        'a_stock': [],
        'hk_us': [],
        'bond_commodity': []
    }

    # A股指数代码（新浪格式）
    a_indices = [
        ('上证指数', 'sh000001'),
        ('深证成指', 'sz399001'),
        ('创业板指', 'sz399006'),
        ('北证50', 'bj899050'),
        ('科创50', 'sh000688'),
        ('上证50', 'sh000016'),
        ('深证100', 'sz399003'),
        ('沪深300', 'sh000300'),
        ('中证500', 'sh000905'),
        ('中证1000', 'sh000852'),
        ('国债指数', 'sh000012'),
        ('企债指数', 'sh000013'),
    ]

    # 港股（使用腾讯API）
    hk_indices = [
        ('恒生指数', 'rt_hkHSI'),
        ('恒生国企', 'rt_hkHSCEI'),
        ('恒生科技', 'rt_hkHSTECH'),
    ]

    logger.info("开始获取真实市场数据...")

    # 获取A股数据
    for name, code in a_indices:
        # 先尝试新浪，失败则尝试腾讯
        data = get_realtime_sina(code)
        if not data:
            logger.warning(f"新浪API失败，尝试腾讯API: {name}")
            data = get_tencent_realtime(code)

        if data:
            result['a_stock'].append(data)
            logger.info(f"✅ {name}: {data['price']} ({data['change_pct']:+.2f}%)")
        else:
            logger.error(f"❌ {name} 获取失败")
            result['a_stock'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

    # 获取港股数据（使用腾讯API）
    for name, code in hk_indices:
        tencent_code = code.replace('rt_hk', 'hk')
        data = get_tencent_realtime(tencent_code)

        if data:
            result['hk_us'].append(data)
            logger.info(f"✅ {name}: {data['price']} ({data['change_pct']:+.2f}%)")
        else:
            logger.error(f"❌ {name} 获取失败")
            result['hk_us'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

    # 获取美股数据（使用Yahoo Finance API）
    us_data = get_us_market_data()
    result['hk_us'].extend(us_data)

    # COMEX黄金（使用期货代码）
    gold_indices = [
        ('COMEX黄金', 'HF_CL0'),
    ]

    # 获取黄金数据
    for name, code in gold_indices:
        data = get_realtime_sina(code)
        if data:
            result['bond_commodity'].append(data)
            logger.info(f"✅ {name}: {data['price']} ({data['change_pct']:+.2f}%)")
        else:
            logger.error(f"❌ {name} 获取失败")
            result['bond_commodity'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

    # 获取黄金数据
    for name, code in gold_indices:
        data = get_realtime_sina(code)
        if data:
            result['bond_commodity'].append(data)
            logger.info(f"✅ {name}: {data['price']} ({data['change_pct']:+.2f}%)")
        else:
            logger.error(f"❌ {name} 获取失败")
            result['bond_commodity'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

    logger.info(f"数据获取完成: A股{len(result['a_stock'])}个, 港美{len(result['hk_us'])}个, 债商{len(result['bond_commodity'])}个")

    return result


if __name__ == '__main__':
    print("=== 获取真实市场数据 ===\n")
    print("使用新浪财经 + 腾讯财经真实API\n")

    data = get_market_data()

    print("\n" + "="*60)
    print("=== A股指数 ===")
    for idx in data['a_stock']:
        if idx['price'] > 0:
            status = "📈" if idx['change_pct'] > 0 else "📉" if idx['change_pct'] < 0 else "➡️"
            print(f"{status} {idx['name']:8s}: {idx['price']:8.2f} ({idx['change_pct']:+6.2f}%)")
        else:
            print(f"❌ {idx['name']:8s}: 数据获取失败")

    print("\n=== 港股指数 ===")
    for idx in data['hk_us'][:3]:
        if idx['price'] > 0:
            status = "📈" if idx['change_pct'] > 0 else "📉" if idx['change_pct'] < 0 else "➡️"
            print(f"{status} {idx['name']:8s}: {idx['price']:8.2f} ({idx['change_pct']:+6.2f}%)")
        else:
            print(f"❌ {idx['name']:8s}: 数据获取失败")

    print("\n=== 美股指数 ===")
    for idx in data['hk_us'][3:]:
        if idx['price'] > 0:
            status = "📈" if idx['change_pct'] > 0 else "📉" if idx['change_pct'] < 0 else "➡️"
            print(f"{status} {idx['name']:8s}: {idx['price']:8.2f} ({idx['change_pct']:+6.2f}%)")
        else:
            print(f"❌ {idx['name']:8s}: 数据获取失败")

    print("\n=== COMEX黄金 ===")
    if data['bond_commodity']:
        idx = data['bond_commodity'][0]
        if idx['price'] > 0:
            status = "📈" if idx['change_pct'] > 0 else "📉" if idx['change_pct'] < 0 else "➡️"
            print(f"{status} {idx['name']:8s}: {idx['price']:8.2f} ({idx['change_pct']:+6.2f}%)")
        else:
            print(f"❌ {idx['name']:8s}: 数据获取失败")

    print(f"\n⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 数据来源: 新浪财经 + 腾讯财经实时API")

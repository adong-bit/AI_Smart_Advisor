"""
使用多种数据源获取市场数据（包含容错机制）
优先使用 AkShare，失败时使用备用接口
"""

import requests
import akshare as ak
import pandas as pd
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_sina_index_data(sina_code: str) -> Dict:
    """使用新浪财经接口获取指数数据（备用）"""
    try:
        url = f"http://hq.sinajs.cn/list={sina_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'gbk'

        if response.status_code == 200:
            data_str = response.text.split('=')[1].strip('"')
            parts = data_str.split(',')

            if len(parts) > 3:
                current = float(parts[1])
                prev_close = float(parts[2])
                return {
                    'name': parts[0],
                    'price': current,
                    'change_pct': ((current - prev_close) / prev_close * 100) if prev_close > 0 else 0,
                    'change_amount': current - prev_close
                }
    except Exception as e:
        logger.error(f"新浪接口获取 {sina_code} 失败: {e}")

    return None


def get_market_data() -> Dict[str, List[Dict]]:
    """
    获取市场数据，使用多重数据源保证可靠性
    """
    result = {
        'a_stock': [],
        'hk_us': [],
        'bond_commodity': []
    }

    # A股指数代码映射（新浪格式）
    a_indices_codes = [
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

    # 港股/美股代码
    hk_us_codes = [
        ('恒生指数', 'rt_hkHSI'),
        ('恒生国企', 'rt_hkHSCEI'),
        ('恒生科技', 'rt_hkHSTECH'),
        ('道琼斯', 'rt_dji'),
        ('纳斯达克', 'rt_ndx'),
        ('标普500', 'rt_sp500'),
    ]

    # COMEX黄金
    gold_codes = [
        ('COMEX黄金', 'hf_GC0'),
    ]

    # 尝试方法1: AkShare
    akshare_success = False
    try:
        df = ak.stock_zh_index_spot_em()
        if df is not None and not df.empty:
            a_indices_map = {
                '000001': '上证指数', '399001': '深证成指', '399006': '创业板指',
                '899050': '北证50', '000688': '科创50', '000016': '上证50',
                '399003': '深证100', '000300': '沪深300', '000905': '中证500',
                '000852': '中证1000', '000012': '国债指数', '000013': '企债指数',
            }

            for code, name in a_indices_map.items():
                try:
                    idx_data = df[df['代码'] == code]
                    if not idx_data.empty:
                        row = idx_data.iloc[0]
                        result['a_stock'].append({
                            'name': name,
                            'price': float(row['最新价']),
                            'change_pct': float(row['涨跌幅']),
                            'change_amount': float(row['涨跌额'])
                        })
                except Exception:
                    pass

            if len(result['a_stock']) >= 6:
                akshare_success = True
                logger.info(f"AkShare 成功获取 {len(result['a_stock'])} 个A股指数")
    except Exception as e:
        logger.warning(f"AkShare 获取失败: {e}")

    # 如果 AkShare 失败，使用新浪接口
    if not akshare_success or len(result['a_stock']) < 6:
        logger.info("使用新浪备用接口获取A股数据...")
        result['a_stock'] = []
        for name, code in a_indices_codes:
            data = get_sina_index_data(code)
            if data:
                result['a_stock'].append(data)
            else:
                # 添加占位数据
                result['a_stock'].append({
                    'name': name,
                    'price': 0.0,
                    'change_pct': 0.0,
                    'change_amount': 0.0
                })

    # 获取港股/美股（使用新浪接口）
    for name, code in hk_us_codes:
        data = get_sina_index_data(code)
        if data:
            result['hk_us'].append(data)
        else:
            result['hk_us'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

    # 获取黄金（使用新浪接口）
    for name, code in gold_codes:
        data = get_sina_index_data(code)
        if data:
            result['bond_commodity'].append(data)
        else:
            result['bond_commodity'].append({
                'name': name,
                'price': 0.0,
                'change_pct': 0.0,
                'change_amount': 0.0
            })

    logger.info(f"数据获取完成: A股{len(result['a_stock'])}个, 港美{len(result['hk_us'])}个, 债商{len(result['bond_commodity'])}个")

    return result


if __name__ == '__main__':
    print("测试获取市场数据...")
    data = get_market_data()

    print("\n=== A股指数 ===")
    for idx in data['a_stock'][:6]:
        print(f"{idx['name']}: {idx['price']:.2f} ({idx['change_pct']:+.2f}%)")

    print("\n=== 港股指数 ===")
    for idx in data['hk_us'][:3]:
        print(f"{idx['name']}: {idx['price']:.2f} ({idx['change_pct']:+.2f}%)")

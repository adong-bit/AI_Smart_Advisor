"""
使用 Tushare 获取市场数据
Tushare 提供专业、准确的金融数据
"""

import tushare as ts
import pandas as pd
from datetime import datetime
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_market_data_tushare(token: str = None) -> Dict[str, List[Dict]]:
    """
    使用 Tushare 获取市场数据

    Args:
        token: Tushare API token（如果没有提供，尝试使用环境变量）

    Returns:
        Dict: 包含三个分类的字典
            - 'a_stock': A股指数列表
            - 'hk_us': 港股和美股指数列表
            - 'bond_commodity': 债券和商品指数列表
    """

    result = {
        'a_stock': [],
        'hk_us': [],
        'bond_commodity': [],
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': 'Tushare'
    }

    # 设置 token
    if token:
        ts.set_token(token)
    else:
        # 尝试从环境变量获取
        import os
        token = os.environ.get('TUSHARE_TOKEN')
        if token:
            ts.set_token(token)
        else:
            logger.warning("未提供 Tushare token，某些功能可能无法使用")

    # 初始化 pro API
    try:
        pro = ts.pro_api()

        # ==================== 获取A股指数 ====================
        logger.info("正在获取A股指数数据...")

        # 主要指数代码
        a_index_codes = {
            '000001.SH': '上证指数',
            '399001.SZ': '深证成指',
            '399006.SZ': '创业板指',
            '899050.BJ': '北证50',
            '000688.SH': '科创50',
            '000016.SH': '上证50',
            '399003.SZ': '深证100',
            '000300.SH': '沪深300',
            '000905.SH': '中证500',
            '000852.SH': '中证1000',
            '000012.SH': '国债指数',
            '000013.SH': '企债指数'
        }

        try:
            # 获取A股指数实时行情
            # 使用 daily 接口获取最新数据
            for code, name in a_index_codes.items():
                try:
                    # 获取最新交易日数据
                    df = pro.daily(ts_code=code, start_date='20260407', end_date='20260407')

                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        current_price = float(latest['close'])
                        prev_close = float(latest['pre_close'])
                        change_amount = current_price - prev_close
                        change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                        result['a_stock'].append({
                            'name': name,
                            'price': current_price,
                            'change_pct': change_pct,
                            'change_amount': change_amount
                        })
                        logger.info(f"✅ {name}: {current_price} ({change_pct:+.2f}%)")
                    else:
                        logger.warning(f"未获取到 {name} 数据")
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

        except Exception as e:
            logger.error(f"A股数据获取失败: {e}")

        # ==================== 获取港股指数 ====================
        logger.info("正在获取港股指数数据...")

        hk_index_codes = {
            'HSI.HK': '恒生指数',
            'HSCEI.HK': '恒生中国企业指数',
            'HSTECH.HK': '恒生科技指数'
        }

        try:
            for code, name in hk_index_codes.items():
                try:
                    df = pro.daily(ts_code=code, start_date='20260407', end_date='20260407')

                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        current_price = float(latest['close'])
                        prev_close = float(latest['pre_close'])
                        change_amount = current_price - prev_close
                        change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                        result['hk_us'].append({
                            'name': name,
                            'price': current_price,
                            'change_pct': change_pct,
                            'change_amount': change_amount
                        })
                        logger.info(f"✅ {name}: {current_price} ({change_pct:+.2f}%)")
                    else:
                        result['hk_us'].append({
                            'name': name,
                            'price': 0.0,
                            'change_pct': 0.0,
                            'change_amount': 0.0
                        })

                except Exception as e:
                    logger.error(f"获取港股 {name} 失败: {e}")
                    result['hk_us'].append({
                        'name': name,
                        'price': 0.0,
                        'change_pct': 0.0,
                        'change_amount': 0.0
                    })

        except Exception as e:
            logger.error(f"港股数据获取失败: {e}")

        # ==================== 获取美股指数 ====================
        logger.info("正在获取美股指数数据...")

        us_index_codes = {
            '.DJI': '道琼斯',
            '.IXIC': '纳斯达克',
            '.INX': '标普500'
        }

        try:
            for code, name in us_index_codes.items():
                try:
                    df = pro.daily(ts_code=code, start_date='20260407', end_date='20260407')

                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        current_price = float(latest['close'])
                        prev_close = float(latest['pre_close'])
                        change_amount = current_price - prev_close
                        change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                        result['hk_us'].append({
                            'name': name,
                            'price': current_price,
                            'change_pct': change_pct,
                            'change_amount': change_amount
                        })
                        logger.info(f"✅ {name}: {current_price} ({change_pct:+.2f}%)")
                    else:
                        result['hk_us'].append({
                            'name': name,
                            'price': 0.0,
                            'change_pct': 0.0,
                            'change_amount': 0.0
                        })

                except Exception as e:
                    logger.error(f"获取美股 {name} 失败: {e}")
                    result['hk_us'].append({
                        'name': name,
                        'price': 0.0,
                        'change_pct': 0.0,
                        'change_amount': 0.0
                    })

        except Exception as e:
            logger.error(f"美股数据获取失败: {e}")

        # ==================== 获取黄金数据 ====================
        logger.info("正在获取黄金数据...")

        # Tushare 中的黄金期货代码
        gold_codes = {
            'AU0.CFX': '上海金',
            'AU99.CFX': '黄金9999'
        }

        try:
            for code, name in gold_codes.items():
                try:
                    df = pro.daily(ts_code=code, start_date='20260407', end_date='20260407')

                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        current_price = float(latest['close'])
                        prev_close = float(latest['pre_close'])
                        change_amount = current_price - prev_close
                        change_pct = (change_amount / prev_close * 100) if prev_close > 0 else 0

                        result['bond_commodity'].append({
                            'name': f'COMEX黄金',
                            'price': current_price,
                            'change_pct': change_pct,
                            'change_amount': change_amount
                        })
                        logger.info(f"✅ {name}: {current_price} ({change_pct:+.2f}%)")
                        break
                    else:
                        result['bond_commodity'].append({
                            'name': 'COMEX黄金',
                            'price': 0.0,
                            'change_pct': 0.0,
                            'change_amount': 0.0
                        })

                except Exception as e:
                    logger.error(f"获取黄金数据失败: {e}")
                    result['bond_commodity'].append({
                        'name': 'COMEX黄金',
                        'price': 0.0,
                        'change_pct': 0.0,
                        'change_amount': 0.0
                    })

        except Exception as e:
            logger.error(f"黄金数据获取失败: {e}")

        logger.info(f"Tushare 数据获取完成: A股{len(result['a_stock'])}个, 港美{len(result['hk_us'])}个, 债商{len(result['bond_commodity'])}个")

    except Exception as e:
        logger.error(f"Tushare API 连接失败: {e}")
        logger.info("切换到备用数据源...")
        # 返回空数据，让系统使用备用方案
        return {
            'a_stock': [],
            'hk_us': [],
            'bond_commodity': [],
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'Tushare (连接失败)'
        }

    return result


if __name__ == '__main__':
    print("=== 测试 Tushare 数据获取 ===\n")
    print("注意: Tushare 需要 API token")
    print("获取方式: 访问 https://tushare.pro/register 注册")
    print("\n测试连接...")

    try:
        result = get_market_data_tushare()

        print(f"\n数据源: {result['data_source']}")
        print(f"更新时间: {result['update_time']}")
        print(f"A股指数: {len(result['a_stock'])} 个")
        print(f"港美指数: {len(result['hk_us'])} 个")
        print(f"债商指数: {len(result['bond_commodity'])} 个")

        if result['a_stock']:
            print("\nA股指数数据示例:")
            for idx in result['a_stock'][:3]:
                if idx['price'] > 0:
                    print(f"  {idx['name']}: {idx['price']} ({idx['change_pct']:+.2f}%)")

    except Exception as e:
        print(f"测试失败: {e}")

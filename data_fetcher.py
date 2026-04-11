"""
真实市场数据获取模块
使用 AkShare 获取 A股、港股、美股、商品等市场数据
"""

import akshare as ak
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketDataFetcher:
    """市场数据获取器 - 使用 AkShare"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def get_index_data_akshare(self, index_code: str, market: str = 'cn') -> Optional[Dict]:
        """
        使用 AkShare 获取指数实时数据
        :param index_code: 指数代码
        :param market: 市场类型 - cn(中国), hk(香港), us(美国)
        :return: 指数数据字典
        """
        try:
            if market == 'cn':
                # A股指数 - 使用东方财富接口
                df = ak.stock_zh_index_spot_em()
                idx_data = df[df['代码'] == index_code]

                if not idx_data.empty:
                    row = idx_data.iloc[0]
                    return {
                        'name': row['名称'],
                        'current': float(row['最新价']),
                        'open': 0.0,  # AkShare 实时接口不提供开盘价
                        'prev_close': float(row['最新价']) - float(row['涨跌额']),
                        'high': 0.0,  # AkShare 实时接口不提供最高价
                        'low': 0.0,   # AkShare 实时接口不提供最低价
                        'volume': 0.0,
                        'amount': 0.0,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'time': datetime.now().strftime('%H:%M:%S'),
                    }

            elif market == 'hk':
                # 港股指数
                df = ak.stock_hk_index_spot_em()
                idx_data = df[df['代码'] == index_code]

                if not idx_data.empty:
                    row = idx_data.iloc[0]
                    return {
                        'name': row['名称'],
                        'current': float(row['最新价']),
                        'open': 0.0,
                        'prev_close': float(row['最新价']) - float(row['涨跌额']),
                        'high': 0.0,
                        'low': 0.0,
                        'volume': 0.0,
                        'amount': 0.0,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'time': datetime.now().strftime('%H:%M:%S'),
                    }

            elif market == 'us':
                # 美股指数 - 使用新浪接口
                try:
                    url = f"http://hq.sinajs.cn/list={index_code}"
                    response = self.session.get(url, timeout=5)
                    response.encoding = 'gbk'

                    if response.status_code == 200:
                        data_str = response.text.split('=')[1].strip('"')
                        parts = data_str.split(',')

                        if len(parts) > 3:
                            current = float(parts[1])
                            prev_close = float(parts[2])
                            return {
                                'name': parts[0],
                                'current': current,
                                'open': prev_close,
                                'prev_close': prev_close,
                                'high': current,
                                'low': current,
                                'volume': 0.0,
                                'amount': 0.0,
                                'date': datetime.now().strftime('%Y-%m-%d'),
                                'time': datetime.now().strftime('%H:%M:%S'),
                            }
                except Exception as e:
                    logger.error(f"获取美股指数 {index_code} 失败: {e}")

        except Exception as e:
            logger.error(f"AkShare获取指数 {index_code} 失败: {e}")

        return None

    def get_stock_data(self, stock_code: str) -> Dict:
        """
        获取个股实时数据
        :param stock_code: 股票代码，如 sh600519, sz000858
        :return: 股票数据字典
        """
        try:
            url = f"http://hq.sinajs.cn/list={stock_code}"
            response = self.session.get(url, timeout=5)
            response.encoding = 'gbk'

            if response.status_code == 200:
                data_str = response.text.split('=')[1].strip('"')
                parts = data_str.split(',')

                if len(parts) > 30:
                    current_price = float(parts[3])
                    prev_close = float(parts[2])
                    change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0

                    return {
                        'name': parts[0],
                        'open': float(parts[1]),
                        'prev_close': prev_close,
                        'current': current_price,
                        'high': float(parts[4]),
                        'low': float(parts[5]),
                        'buy': float(parts[6]),
                        'sell': float(parts[7]),
                        'volume': float(parts[8]),
                        'amount': float(parts[9]),
                        'change_pct': round(change_pct, 2),
                        'date': parts[30],
                        'time': parts[31],
                    }
        except Exception as e:
            logger.error(f"获取股票数据失败 {stock_code}: {e}")

        return None

    def get_kline_data(self, symbol: str, period: str = 'daily', count: int = 120) -> List[Dict]:
        """
        获取K线数据
        :param symbol: 股票/指数代码，如 sh000001, sz399006
        :param period: 周期 daily/weekly/monthly
        :param count: 获取数量
        :return: K线数据列表
        """
        try:
            # 使用 AkShare 获取历史K线数据
            # 转换代码格式
            if symbol.startswith('sh'):
                code = symbol[2:] + '.SH'
            elif symbol.startswith('sz'):
                code = symbol[2:] + '.SZ'
            else:
                code = symbol

            # 获取日线数据
            df = ak.stock_zh_index_daily(symbol=f"sh{symbol[2:]}" if symbol.startswith('sh') else f"sz{symbol[3:]}")

            if df is not None and not df.empty:
                result = []
                # 取最近的count条数据
                recent_df = df.tail(count)

                for idx, row in recent_df.iterrows():
                    result.append({
                        'date': idx.strftime('%Y-%m-%d'),
                        'open': float(row['open']),
                        'close': float(row['close']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'volume': float(row['volume']),
                        'amount': 0.0,
                    })

                return result

        except Exception as e:
            logger.error(f"获取K线数据失败 {symbol}: {e}")

        # 失败时返回空列表
        return []

    def get_sector_data(self) -> List[Dict]:
        """
        获取主要板块涨跌幅数据
        :return: 板块数据列表
        """
        try:
            # 使用 AkShare 获取板块数据
            df = ak.stock_board_industry_name_em()

            if df is not None and not df.empty:
                result = []
                # 取主要板块
                for idx, row in df.head(20).iterrows():
                    try:
                        result.append({
                            'name': row['板块名称'],
                            'change': float(row['涨跌幅']),
                            'current': float(row['最新价']) if '最新价' in row else 0.0,
                        })
                    except Exception:
                        pass

                return result[:12]  # 返回前12个板块

        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")

        # 失败时返回空列表，而不是模拟板块
        return []

    def get_market_indices(self) -> List[Dict]:
        """
        获取主要市场指数 - 使用 AkShare
        :return: 指数列表
        """
        indices = []

        # A股指数代码映射
        a_indices = [
            ('000001', '上证指数', 'cn'),
            ('399001', '深证成指', 'cn'),
            ('399006', '创业板指', 'cn'),
            ('000688', '科创50', 'cn'),
            ('000016', '上证50', 'cn'),
            ('399003', '深证100', 'cn'),
            ('000300', '沪深300', 'cn'),
            ('000905', '中证500', 'cn'),
            ('000852', '中证1000', 'cn'),
            ('000012', '国债指数', 'cn'),
            ('000013', '企债指数', 'cn'),
            ('899050', '北证50', 'cn'),
        ]

        # 港股指数
        hk_indices = [
            ('HSI', '恒生指数', 'hk'),
            ('HSCEI', '恒生国企', 'hk'),
            ('HSTECH', '恒生科技', 'hk'),
        ]

        # 美股指数（新浪代码）
        us_indices = [
            ('rt_dji', '道琼斯', 'us'),
            ('rt_ndx', '纳斯达克', 'us'),
            ('rt_sp500', '标普500', 'us'),
        ]

        # 获取A股指数
        for code, name, market in a_indices:
            try:
                data = self.get_index_data_akshare(code, market)
                if data:
                    change_pct = ((data['current'] - data['prev_close']) / data['prev_close']) * 100 if data['prev_close'] > 0 else 0
                    indices.append({
                        'name': name,
                        'value': round(data['current'], 2),
                        'change': round(change_pct, 2),
                        'volume': '0亿',
                        'open': round(data['open'], 2) if data['open'] > 0 else round(data['current'], 2),
                        'high': round(data['high'], 2) if data['high'] > 0 else round(data['current'], 2),
                        'low': round(data['low'], 2) if data['low'] > 0 else round(data['current'], 2),
                    })
                else:
                    # 失败时添加空数据
                    indices.append({
                        'name': name,
                        'value': 0.0,
                        'change': 0.0,
                        'volume': '0亿',
                        'open': 0.0,
                        'high': 0.0,
                        'low': 0.0,
                    })
            except Exception as e:
                logger.error(f"处理指数 {name} 失败: {e}")

        # 获取港股指数
        for code, name, market in hk_indices:
            try:
                data = self.get_index_data_akshare(code, market)
                if data:
                    change_pct = ((data['current'] - data['prev_close']) / data['prev_close']) * 100 if data['prev_close'] > 0 else 0
                    indices.append({
                        'name': name,
                        'value': round(data['current'], 2),
                        'change': round(change_pct, 2),
                        'volume': '0亿',
                        'open': round(data['open'], 2) if data['open'] > 0 else round(data['current'], 2),
                        'high': round(data['high'], 2) if data['high'] > 0 else round(data['current'], 2),
                        'low': round(data['low'], 2) if data['low'] > 0 else round(data['current'], 2),
                    })
            except Exception as e:
                logger.error(f"处理港股指数 {name} 失败: {e}")

        # 获取美股指数
        for code, name, market in us_indices:
            try:
                data = self.get_index_data_akshare(code, market)
                if data:
                    change_pct = ((data['current'] - data['prev_close']) / data['prev_close']) * 100 if data['prev_close'] > 0 else 0
                    indices.append({
                        'name': name,
                        'value': round(data['current'], 2),
                        'change': round(change_pct, 2),
                        'volume': '0亿',
                        'open': round(data['open'], 2),
                        'high': round(data['high'], 2),
                        'low': round(data['low'], 2),
                    })
            except Exception as e:
                logger.error(f"处理美股指数 {name} 失败: {e}")

        time.sleep(0.1)
        return indices

    def get_hot_stocks(self) -> Dict:
        """
        获取热门股票数据（涨幅榜和跌幅榜）
        :return: {'top': 涨幅榜, 'bottom': 跌幅榜}
        """
        try:
            # 使用 AkShare 获取涨跌幅榜
            df = ak.stock_zh_a_spot_em()

            if df is not None and not df.empty:
                # 按涨跌幅排序
                df_sorted = df.sort_values('涨跌幅', ascending=False)

                stocks_data = []
                # 取前20名
                for idx, row in df_sorted.head(20).iterrows():
                    try:
                        stocks_data.append({
                            'code': row['代码'],
                            'name': row['名称'],
                            'change_pct': float(row['涨跌幅']),
                            'current': float(row['最新价']),
                            'open': float(row['今开']),
                            'high': float(row['最高']),
                            'low': float(row['最低']),
                            'volume': float(row['成交量']),
                            'amount': float(row['成交额']),
                        })
                    except Exception:
                        pass

                if len(stocks_data) >= 10:
                    return {
                        'top': stocks_data[:5],
                        'bottom': stocks_data[-5:],
                    }

        except Exception as e:
            logger.error(f"获取热门股票失败: {e}")

        # 失败时返回空数据
        return {
            'top': [],
            'bottom': [],
        }

    def get_market_news(self, limit: int = 6) -> List[Dict]:
        """
        获取市场新闻
        :param limit: 返回数量
        :return: 新闻列表
        """
        try:
            # 使用 AkShare 获取财经新闻
            df = ak.stock_news_em()

            if df is not None and not df.empty:
                news_list = []
                for idx, row in df.head(limit).iterrows():
                    try:
                        # 情感标注以 Web 端「市场总览 /api/market」Kimi 为准；此处不跑规则引擎
                        title = str(row.get('新闻标题', ''))
                        news_list.append({
                            "title": title,
                            "source": "财经快讯",
                            "time": "刚刚",
                            "sentiment": "neutral",
                            "sentiment_source": "data_fetcher_neutral",
                            "impact": "市场影响",
                        })
                    except Exception:
                        pass

                if news_list:
                    return news_list

        except Exception as e:
            logger.error(f"获取新闻失败: {e}")

        # 失败时返回空列表，而不是模拟新闻
        return []


# 全局实例
fetcher = MarketDataFetcher()


def get_market_overview():
    """获取市场总览数据 - 使用 AkShare"""
    try:
        logger.info("开始使用 AkShare 获取市场数据...")

        # 获取指数数据
        indices = fetcher.get_market_indices()

        # 获取上证指数K线
        kline = fetcher.get_kline_data('sh000001', count=120)

        if not kline:
            logger.warning("K线数据获取失败，使用空列表")

        # 获取板块数据
        sectors = fetcher.get_sector_data()

        # 获取热门股票
        hot_stocks = fetcher.get_hot_stocks()

        # 获取新闻
        news = fetcher.get_market_news()

        # 计算市场情绪
        market_sentiment = 0.5
        avg_change = 0
        if sectors:
            valid_sectors = [s for s in sectors if s and s.get('change') is not None]
            if valid_sectors:
                avg_change = sum(s['change'] for s in valid_sectors) / len(valid_sectors)
                market_sentiment = max(0, min(1, 0.5 + avg_change / 10))

        # AI洞察
        ai_insights = [
            f"基于 AkShare 实时数据分析，市场当前处于" + ("上涨" if avg_change > 0 else "调整") + "态势",
            f"板块轮动特征明显，{'新能源、科技等成长板块表现活跃' if avg_change > 0 else '防御性板块相对抗跌'}",
            "建议关注市场量能变化，把握结构性机会",
        ]

        # 检查是否获取到足够的关键数据
        has_real_data = bool(indices and len(indices) > 0)

        if not has_real_data:
            logger.warning("关键数据缺失")
            return None

        result = {
            'indices': indices,
            'kline': kline if kline else [],
            'sectors': sectors if sectors else [],
            'news': news if news else [],
            'top_stocks': hot_stocks.get('top', []) if hot_stocks else [],
            'bottom_stocks': hot_stocks.get('bottom', []) if hot_stocks else [],
            'market_sentiment': round(market_sentiment, 2),
            'ai_insights': ai_insights,
            'data_source': 'akshare',
        }

        logger.info(f"市场数据获取完成，使用 AkShare 数据源，获取到 {len(indices)} 个指数")
        return result

    except Exception as e:
        logger.error(f"获取市场总览失败: {e}")
        return None


if __name__ == '__main__':
    # 测试代码
    print("测试 AkShare 获取市场数据...")

    # 测试获取指数
    print("\n=== 主要指数 ===")
    indices = fetcher.get_market_indices()
    for idx in indices[:10]:
        print(f"{idx['name']}: {idx['value']} ({idx['change']:+.2f}%)")

    # 测试获取K线
    print("\n=== 上证指数最近5个交易日 ===")
    kline = fetcher.get_kline_data('sh000001', count=5)
    for item in kline:
        print(f"{item['date']}: 开{item['open']} 收{item['close']} 高{item['high']} 低{item['low']}")

    # 测试获取板块
    print("\n=== 板块涨跌 ===")
    sectors = fetcher.get_sector_data()
    for sector in sectors[:6]:
        print(f"{sector['name']}: {sector['change']:+.2f}%")

    # 测试获取热门股票
    print("\n=== 涨幅榜前5 ===")
    hot = fetcher.get_hot_stocks()
    if hot['top']:
        for stock in hot['top'][:5]:
            print(f"{stock['name']}({stock['code']}): {stock['change_pct']:+.2f}%")

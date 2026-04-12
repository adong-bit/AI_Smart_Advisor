"""
智能选基引擎 - 4层漏斗筛选系统
Layer 1: 板块雷达 (Sector Radar)     - 估值水位 + 动量分析
Layer 2: 基金初筛 (Quant Filter)     - 规模 + 存续期 + 类型过滤
Layer 3: 核心指标排序 (Alpha Ranking) - 夏普 / 最大回撤 / 信息比率 / PS估值关联
Layer 4: AI决策报告 (AI Insights)    - Kimi 大模型生成决策依据和风险提示
数据来源: AkShare（新浪/申万/雪球，不依赖 eastmoney push 接口）
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Dict, List, Optional

import akshare as ak
import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)


def _clean_fund_code_str(raw: Any, fallback: str = "") -> str:
    """从「161725（主代码）」等字符串中提取 6 位基金代码。"""
    d = re.sub(r"\D", "", str(raw or ""))
    if len(d) >= 6:
        return d[:6]
    if d:
        return d.zfill(6)
    fb = re.sub(r"\D", "", str(fallback or ""))
    return fb[:6].zfill(6) if fb else ""


def _parse_overview_net_assets_yi(text: Any) -> float:
    """解析档案中的「净资产规模」文案，得到亿元数值。"""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return 0.0
    t = str(text).strip()
    m = re.search(r"([\d,.]+)\s*亿\s*元", t)
    if m:
        return _to_float(m.group(1).replace(",", ""), 0.0)
    m = re.search(r"([\d,.]+)\s*亿元", t)
    if m:
        return _to_float(m.group(1).replace(",", ""), 0.0)
    return 0.0


def _last_trade_date() -> str:
    """返回最近交易日日期（以当前时间推算，跳过周末）。"""
    today = datetime.now()
    weekday = today.weekday()  # 0=周一, 5=周六, 6=周日
    if weekday == 6:       # 周日 → 取上周五
        offset = 2
    elif weekday == 5:     # 周六 → 取上周五
        offset = 1
    else:
        # 周一~周五：若当前时间 < 9:30，取前一交易日
        if today.hour < 9 or (today.hour == 9 and today.minute < 30):
            offset = 1 if weekday > 0 else 2
        else:
            offset = 0
    last = today - timedelta(days=offset)
    return last.strftime("%Y-%m-%d")


def _safely_call(func, *args, timeout=5, **kwargs):
    """给任意函数包装超时（threading 方式，不干扰 akshare 内部 signal）。"""
    import threading
    result = {"val": None, "exc": None}

    def target():
        try:
            result["val"] = func(*args, **kwargs)
        except Exception as e:
            result["exc"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return None
    if result["exc"] is not None:
        return None
    return result["val"]

# ─────────────────────────── 常量 ───────────────────────────

# 申万一级行业代码（代表性子集，用于 fallback + 标签）
SW_INDUSTRY_MAP = {
    "801010": "农林牧渔", "801020": "采掘", "801030": "化工",
    "801040": "钢铁", "801050": "有色金属", "801060": "电子",
    "801070": "汽车", "801080": "家用电器", "801090": "食品饮料",
    "801110": "轻工制造", "801120": "医药生物",
    "801140": "房地产", "801150": "建筑材料",
    "801160": "电气设备", "801170": "国防军工", "801180": "计算机",
    "801200": "传媒", "801210": "通信", "801220": "机械设备",
}

# 中证主题指数
CSI_INDEX_CODES = {
    "000932": {"name": "中证消费", "risk": "消费", "pe_type": "PE"},
    "000914": {"name": "中证800食品", "risk": "消费", "pe_type": "PE"},
    "000928": {"name": "中证银行", "risk": "金融", "pe_type": "PE"},
    "399976": {"name": "中证新能源汽车", "risk": "成长", "pe_type": "PS"},
    "931643": {"name": "中证人工智能", "risk": "成长", "pe_type": "PS"},
    "931644": {"name": "中证5G", "risk": "成长", "pe_type": "PS"},
    "000688": {"name": "科创50", "risk": "成长", "pe_type": "PS"},
    "399006": {"name": "创业板指", "risk": "成长", "pe_type": "PE"},
    "000001": {"name": "上证指数", "risk": "宽基", "pe_type": "PE"},
    "000300": {"name": "沪深300", "risk": "宽基", "pe_type": "PE"},
    "000905": {"name": "中证500", "risk": "宽基", "pe_type": "PE"},
}

# 东方财富「指数型」基金名称匹配用（与板块/指数联动筛真实基金代码）
CSI_INDEX_FUND_KEYWORDS: Dict[str, List[str]] = {
    "000932": ["中证消费", "主要消费", "全指消费"],
    "000914": ["800食品", "食品饮料", "细分食品", "食品ETF", "饮食"],
    "000928": ["中证银行", "银行ETF", "银行指"],
    "399976": ["新能源汽车", "新能源车", "新能车"],
    "931643": ["人工智能", "AI", "机器人", "智能"],
    "931644": ["5G", "通信设备", "全指通信", "通信ETF"],
    "000688": ["科创50", "科创板50", "科创芯片"],
    "399006": ["创业板指", "创业板ETF", "创业板50", "创业50"],
    "000001": ["上证指数", "上证综合", "上证综指"],
    "000300": ["沪深300", "300ETF"],
    "000905": ["中证500", "500ETF", "中证500ETF"],
}

SW_INDUSTRY_FUND_KEYWORDS: Dict[str, List[str]] = {
    "801010": ["农林牧渔", "农业", "养殖", "畜牧", "种业", "粮食"],
    "801020": ["煤炭", "采掘", "矿业", "能源"],
    "801030": ["化工", "化学", "精细化工", "石化"],
    "801040": ["钢铁", "黑色金属", "冶金"],
    "801050": ["有色金属", "有色", "稀土", "黄金", "铜"],
    "801060": ["电子", "半导体", "芯片", "集成电路"],
    "801070": ["汽车", "新能源车", "零部件", "整车"],
    "801080": ["家用电器", "家电", "白色家电"],
    "801090": ["食品饮料", "食品", "饮料", "白酒", "酿酒", "乳业"],
    "801110": ["轻工制造", "轻工", "造纸", "包装"],
    "801120": ["医药", "医疗", "生物", "创新药", "医疗器械", "中证医疗"],
    "801140": ["房地产", "地产", "物业"],
    "801150": ["建筑材料", "建材", "水泥", "玻璃"],
    "801160": ["电气设备", "电力设备", "电网", "光伏", "风电", "储能", "锂电", "电池"],
    "801170": ["国防军工", "军工", "航天", "航空", "船舶"],
    "801180": ["计算机", "软件", "信创", "云计算"],
    "801200": ["传媒", "游戏", "影视", "广告"],
    "801210": ["通信", "5G", "光通信"],
    "801220": ["机械设备", "机械", "工程机械", "机床", "工业母机"],
}

RISK_FREE_RATE = 0.018
HIST_PERCENTILE_TRADING_DAYS = 600
MOMENTUM_TRADING_DAYS = 20
MAX_DD_TRADING_DAYS = 240


def _to_float(val: Any, default: float = 0.0) -> float:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    try:
        text = str(val).replace(",", "").replace("%", "").strip()
        if text in ("", "-", "--", "None", "nan", "NaN"):
            return default
        return float(text)
    except Exception:
        return default


def _to_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(_to_float(val)))
    except Exception:
        return default


def _normalize_sw_index_code(code: Any) -> str:
    """申万指数代码归一（去掉 .SI 等后缀，兼容 801010.0 等浮点字符串）。"""
    if code is None or (isinstance(code, float) and math.isnan(code)):
        return ""
    num = pd.to_numeric(code, errors="coerce")
    if pd.notna(num) and num != 0:
        try:
            return str(int(round(float(num))))
        except (TypeError, ValueError, OverflowError):
            pass
    t = str(code).strip()
    if not t or t.lower() in ("nan", "none"):
        return ""
    t = t.split(".")[0]
    if t.isdigit():
        return t
    return "".join(ch for ch in t if ch.isdigit()) or t


def _percentile_rank_last_vs_history(values: pd.Series, min_points: int = 15) -> Optional[float]:
    """
    以序列最后一个有效值为「当前」，对其之前全部历史值计算分位：
    百分位 = 历史值中严格小于当前值的比例 × 100（0~99.9）。
    适用于市盈率、市销率或指数收盘价序列。
    """
    s = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    s = s[s > 0]
    if len(s) < min_points:
        return None
    arr = s.astype(float).values
    curr = float(arr[-1])
    past = arr[:-1]
    if len(past) < min_points - 1:
        return None
    rank = 100.0 * float(np.mean(past < curr))
    return round(float(np.clip(rank, 0.0, 99.9)), 1)


# ── 东方财富指数型/增强基金池（多分类合并，供板块关键词匹配）──

_em_index_fund_df: Optional[pd.DataFrame] = None
_em_index_fund_df_at: Optional[datetime] = None
_EM_INDEX_CATALOG_TTL = timedelta(minutes=25)


def _resolve_sector_fund_keywords(sector_code: str, sector_name: str) -> List[str]:
    code = str(sector_code).strip()
    kws: List[str] = []
    if code in CSI_INDEX_FUND_KEYWORDS:
        kws.extend(CSI_INDEX_FUND_KEYWORDS[code])
    if code in SW_INDUSTRY_FUND_KEYWORDS:
        kws.extend(SW_INDUSTRY_FUND_KEYWORDS[code])
    meta = CSI_INDEX_CODES.get(code)
    if meta and meta.get("name"):
        kws.append(str(meta["name"]))
    nm = (sector_name or "").strip()
    if nm:
        kws.append(nm)
        if len(nm) >= 4:
            kws.append(nm[:4])
        if len(nm) >= 2:
            kws.append(nm[:2])
    out: List[str] = []
    seen = set()
    for k in kws:
        k = (k or "").strip()
        if len(k) >= 2 and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _load_em_index_fund_catalog_df() -> pd.DataFrame:
    """合并东方财富「行业主题/沪深指数 × 被动/增强」指数型基金列表。"""
    global _em_index_fund_df, _em_index_fund_df_at
    now = datetime.now()
    if (
        _em_index_fund_df is not None
        and _em_index_fund_df_at is not None
        and (now - _em_index_fund_df_at) < _EM_INDEX_CATALOG_TTL
    ):
        return _em_index_fund_df

    specs = [
        ("行业主题", "被动指数型"),
        ("行业主题", "增强指数型"),
        ("沪深指数", "被动指数型"),
        ("沪深指数", "增强指数型"),
    ]

    def _one(spec: tuple) -> Optional[pd.DataFrame]:
        sym, ind = spec

        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return ak.fund_info_index_em(symbol=sym, indicator=ind)

        return _safely_call(_call, timeout=35)

    chunks: List[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for part in pool.map(_one, specs):
            if part is not None and not part.empty:
                chunks.append(part)

    if not chunks:
        _em_index_fund_df = pd.DataFrame()
        _em_index_fund_df_at = now
        return _em_index_fund_df

    merged = pd.concat(chunks, ignore_index=True)
    if "基金代码" in merged.columns:
        merged = merged.drop_duplicates(subset=["基金代码"], keep="first")
    _em_index_fund_df = merged
    _em_index_fund_df_at = now
    return merged


def _pick_funds_from_catalog(
    df: pd.DataFrame,
    keywords: List[str],
    max_funds: int = 24,
    sector_code: str = "",
    sector_name: str = "",
) -> List[Dict[str, Any]]:
    if df is None or df.empty or not keywords:
        return []
    names = df["基金名称"].astype(str)
    mask = pd.Series(False, index=df.index)
    for kw in keywords:
        mask |= names.str.contains(kw, regex=False, na=False)
    sub = df.loc[mask].copy()
    if sub.empty:
        return []
    ycol = "近1年"
    if ycol in sub.columns:
        sub["_y1"] = pd.to_numeric(sub[ycol], errors="coerce")
    else:
        sub["_y1"] = float("nan")
    if sector_name and len(sector_name.strip()) >= 2:
        sn = sector_name.strip()
        sub["_name_match"] = names.loc[sub.index].str.contains(sn, regex=False, na=False).astype(int)
        sub = sub.sort_values(["_name_match", "_y1"], ascending=[False, False], na_position="last")
    else:
        sub = sub.sort_values("_y1", ascending=False, na_position="last")
    rows: List[Dict[str, Any]] = []
    for _, row in sub.head(max_funds).iterrows():
        code = str(row.get("基金代码", "")).strip().zfill(6)
        if len(code) != 6 or not code.isdigit():
            continue
        rows.append({
            "code": code,
            "name": str(row.get("基金名称", "")).strip(),
            "nav": _to_float(row.get("单位净值")),
            "nav_change_pct": _to_float(row.get("日增长率")),
            "asset_scale": 0.0,
            "establish_date": None,
            "tracking_index": sector_code,
        })
    return rows


# ════════════════════════════════════════════════════════════
# Layer 0: 数据获取基础层
# ════════════════════════════════════════════════════════════

class _DataFetcher:
    """数据获取基础工具类，使用新浪财经、申万、雪球等可用接口。"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "http://finance.sina.com.cn",
        })

    def fetch_sw_realtime(self, level: str = "一级行业") -> Optional[pd.DataFrame]:
        """申万行业实时行情（通过 AkShare，5秒超时）。"""
        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.index_realtime_sw(symbol=level)
            if df is not None and not df.empty:
                df.columns = [c.strip() for c in df.columns]
                return df
            return None
        try:
            return _safely_call(_call, timeout=5)
        except Exception as e:
            logger.warning(f"申万实时行情获取失败: {e}")
        return None

    def fetch_sina_index_history(self, symbol: str, count: int = 300) -> Optional[pd.DataFrame]:
        """
        从新浪获取指数历史 K 线。2秒超时（快速短路）。
        symbol 格式: 'sh000001'（上证）或 'sz399006'（深证）
        """
        def _call():
            url = (
                "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
                "/CN_MarketData.getKLineData"
            )
            params = {"symbol": symbol, "scale": 240, "ma": "no", "datalen": count}
            resp = self.session.get(url, params=params, timeout=2)
            raw = resp.json()
            if not raw:
                return None
            df = pd.DataFrame(raw)
            df["date"] = pd.to_datetime(df["day"])
            df["close"] = df["close"].astype(float)
            df["open"] = df["open"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df.sort_values("date").reset_index(drop=True)
        try:
            return _safely_call(_call, timeout=2)
        except Exception as e:
            logger.warning(f"新浪指数历史获取失败 {symbol}: {e}")
        return None

    def fetch_sina_spot_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        从新浪获取单只指数的实时行情。4秒超时。
        code 格式: 'sh000001' 或 'sz399006'
        """
        def _call():
            url = f"http://hq.sinajs.cn/list={code}"
            resp = self.session.get(url, timeout=4)
            resp.encoding = "gbk"
            text = resp.text
            if "=" not in text:
                return None
            val = text.split("=")[1].strip('" \n\t;')
            parts = val.split(",")
            if len(parts) < 4:
                return None
            price = _to_float(parts[1])
            prev_close = _to_float(parts[2])
            open_ = _to_float(parts[3])
            change_pct = (price - prev_close) / prev_close * 100 if prev_close else 0.0
            high = _to_float(parts[4]) if len(parts) > 4 else price
            low = _to_float(parts[5]) if len(parts) > 5 else price
            return {
                "price": price,
                "prev_close": prev_close,
                "open": open_,
                "high": high,
                "low": low,
                "change_pct": round(change_pct, 2),
                "volume": _to_float(parts[8]) if len(parts) > 8 else 0,
                "amount": _to_float(parts[9]) if len(parts) > 9 else 0,
            }
        try:
            return _safely_call(_call, timeout=4)
        except Exception as e:
            logger.warning(f"新浪实时行情获取失败 {code}: {e}")
        return None

    def fetch_sw_index_history(self, symbol: str, count: int = 300) -> Optional[pd.DataFrame]:
        """申万指数历史 K 线。5秒超时。"""
        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.index_hist_sw(symbol=symbol, period="day")
            if df is not None and not df.empty:
                df.columns = [c.strip() for c in df.columns]
                df["date"] = pd.to_datetime(df["日期"])
                df["close"] = _to_float(df["收盘"], 0)
                df["open"] = _to_float(df["开盘"], 0)
                df["high"] = _to_float(df["最高"], 0)
                df["low"] = _to_float(df["最低"], 0)
                df["volume"] = _to_float(df["成交量"], 0)
                return df.sort_values("date").tail(count).reset_index(drop=True)
            return None
        try:
            return _safely_call(_call, timeout=5)
        except Exception as e:
            logger.warning(f"申万历史数据获取失败 {symbol}: {e}")
        return None

    def fetch_sw_pe_history(self, symbol: str, count: int = 10) -> Optional[pd.DataFrame]:
        """
        申万指数历史 PE（按指数代码过滤日度分析表）。
        symbol: 申万行业代码，如 801010。
        """
        code = _normalize_sw_index_code(symbol)
        if not code:
            return None

        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                end = datetime.now().strftime("%Y%m%d")
                start = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
                df = ak.index_analysis_daily_sw(symbol="一级行业", start_date=start, end_date=end)
            if df is None or df.empty:
                return None
            sub = df[df["指数代码"].map(_normalize_sw_index_code) == code]
            if sub.empty:
                return None
            sub = sub.sort_values("发布日期")
            pe = pd.to_numeric(sub["市盈率"], errors="coerce")
            out = pd.DataFrame({"日期": sub["发布日期"], "pe": pe}).dropna(subset=["pe"])
            return out.tail(count)

        try:
            return _safely_call(_call, timeout=60)
        except Exception as e:
            logger.warning(f"申万PE历史获取失败 {symbol}: {e}")
        return None

    def fetch_fund_nav_history(self, fund_code: str, count: int = 300) -> Optional[pd.DataFrame]:
        """获取开放式基金历史净值；优先 AkShare 单位净值走势（与主站 app 一致），再降级 JSONP / 近1年。"""
        code = str(fund_code).strip().zfill(6)

        def _from_unit_nav_trend() -> Optional[pd.DataFrame]:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")

        try:
            df = _safely_call(_from_unit_nav_trend, timeout=18)
            if df is not None and not df.empty and "单位净值" in df.columns:
                date_col = df.columns[0]
                out = pd.DataFrame({
                    "date": pd.to_datetime(df[date_col], errors="coerce"),
                    "nav": pd.to_numeric(df["单位净值"], errors="coerce"),
                })
                out["acc_nav"] = out["nav"]
                out = out.dropna(subset=["date", "nav"])
                if len(out) >= 20:
                    return out.sort_values("date").tail(count).reset_index(drop=True)
        except Exception as e:
            logger.warning(f"基金净值(AkShare走势)失败 {code}: {e}")

        try:
            url = "https://api.fund.eastmoney.com/f10/lsjz"
            params = {
                "callback": "jjlsjz",
                "fundCode": code,
                "pageIndex": 1,
                "pageSize": min(count, 500),
                "startDate": "", "endDate": "",
            }
            resp = self.session.get(url, params=params, timeout=8)
            text = resp.text
            if text.startswith("jjlsjz"):
                text = text[len("jjlsjz("):-2]
                data = json.loads(text)
                if "Data" in data and "LSJZList" in data["Data"]:
                    rows = data["Data"]["LSJZList"]
                    df = pd.DataFrame(rows)
                    df["date"] = pd.to_datetime(df["FSRQ"])
                    df["nav"] = df["DWJZ"].astype(float)
                    df["acc_nav"] = df["LJJZ"].astype(float)
                    df = df.dropna(subset=["date", "nav"])
                    if len(df) >= 20:
                        return df.sort_values("date").tail(count).reset_index(drop=True)
        except Exception:
            pass

        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.fund_open_fund_info_em(symbol=code, period="近1年")
            if df is not None and not df.empty:
                date_col = next((c for c in df.columns if "日期" in c), df.columns[0])
                nav_col = next((c for c in df.columns if "净值" in c and "累计" not in c), None)
                if nav_col:
                    df2 = df.copy()
                    df2["date"] = pd.to_datetime(df2[date_col])
                    df2["nav"] = df2[nav_col].astype(str).str.replace("--", "0").astype(float)
                    df2["acc_nav"] = df2["nav"]
                    df2 = df2.dropna(subset=["date", "nav"])
                    if len(df2) >= 20:
                        return df2.sort_values("date").tail(count).reset_index(drop=True)
        except Exception as e:
            logger.warning(f"基金净值获取失败 {code}: {e}")

        return None

    def fetch_fund_info_xq(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """从雪球获取基金基本信息。5秒超时。"""
        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.fund_individual_basic_info_xq(symbol=fund_code)
            if df is not None and not df.empty and len(df) >= 2:
                info = {}
                for _, row in df.iterrows():
                    if len(row) >= 2:
                        k = str(row.iloc[0])
                        v = str(row.iloc[1])
                        info[k] = v
                return {
                    "name": info.get("基金简称", ""),
                    "nav": _to_float(info.get("单位净值")),
                    "nav_change_pct": _to_float(info.get("日增长率")),
                    "asset_scale": _to_float(info.get("基金规模")),
                    "establish_date": info.get("成立日期"),
                    "fund_type": info.get("基金类型"),
                }
            return None
        try:
            return _safely_call(_call, timeout=5)
        except Exception as e:
            logger.warning(f"雪球基金信息获取失败 {fund_code}: {e}")
        return None

    def fetch_fund_basic_em(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """
        天天基金「基本概况」档案（HTML 表格），补充基金简称、净资产规模(亿)、成立信息等。
        雪球接口失败或字段不全时作为主力数据源。
        """
        code = str(fund_code).strip().zfill(6)

        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return ak.fund_overview_em(symbol=code)

        try:
            df = _safely_call(_call, timeout=12)
            if df is None or df.empty:
                return None
            row = df.iloc[0]
            name = ""
            if "基金简称" in df.columns:
                name = str(row["基金简称"]).strip()
            raw_code = row["基金代码"] if "基金代码" in df.columns else code
            clean = _clean_fund_code_str(raw_code, code)
            scale = 0.0
            if "净资产规模" in df.columns:
                scale = _parse_overview_net_assets_yi(row["净资产规模"])
            est_raw = ""
            if "成立日期/规模" in df.columns:
                est_raw = str(row["成立日期/规模"] or "").strip()
            establish = ""
            if est_raw and "/" in est_raw:
                establish = est_raw.split("/")[0].strip()
            elif est_raw:
                establish = est_raw
            ftype = ""
            if "基金类型" in df.columns:
                ftype = str(row["基金类型"] or "").strip()
            return {
                "code": clean or code,
                "name": name,
                "asset_scale": scale,
                "establish_date": establish or None,
                "fund_type": ftype or None,
            }
        except Exception as e:
            logger.warning(f"天天基金档案获取失败 {code}: {e}")
        return None

    def fetch_fund_list_for_sector(self, sector_code: str, sector_name: str = "") -> List[Dict[str, Any]]:
        """
        从东方财富指数型/增强基金池中，按板块关键词筛出真实基金代码与名称。
        无匹配或接口失败时回退 mock。
        """
        keywords = _resolve_sector_fund_keywords(sector_code, sector_name)
        catalog = _load_em_index_fund_catalog_df()
        if catalog is None or catalog.empty:
            logger.warning("东方财富指数型基金池为空，使用模拟基金")
            return self._generate_mock_funds(sector_code)
        picked = _pick_funds_from_catalog(
            catalog, keywords, max_funds=24, sector_code=sector_code, sector_name=sector_name
        )
        if not picked and keywords:
            fallback_kw = [keywords[0]] if keywords else []
            picked = _pick_funds_from_catalog(
                catalog, fallback_kw, max_funds=16, sector_code=sector_code, sector_name=sector_name
            )
        if not picked:
            logger.warning("板块关键词未匹配到指数基金，使用模拟基金: %s", sector_code)
            return self._generate_mock_funds(sector_code)
        return picked

    def fetch_fund_list_by_index(self, index_code: str) -> List[Dict[str, Any]]:
        """兼容旧名：无板块中文名时按代码关键词解析。"""
        return self.fetch_fund_list_for_sector(index_code, "")

    def _generate_mock_funds(self, index_code: str) -> List[Dict[str, Any]]:
        """生成代表性基金模拟数据。"""
        meta = CSI_INDEX_CODES.get(index_code, {})
        index_name = meta.get("name", index_code)
        companies = ["易方达", "华夏", "嘉实", "广发", "富国", "博时", "汇添富", "南方", "招商", "工银"]
        types = ["A", "C"]
        funds = []
        for i, comp in enumerate(companies[:6]):
            for t in types:
                code_prefix = str(index_code)[-4:]
                code = f"{code_prefix}{i:02d}{t}"
                nav = round(random.uniform(0.6, 3.5), 4)
                funds.append({
                    "code": code,
                    "name": f"{comp}{index_name}{t}基金",
                    "nav": nav,
                    "acc_nav": round(nav * random.uniform(1.0, 1.8), 4),
                    "nav_change_pct": round(random.uniform(-3, 3), 2),
                    "asset_scale": round(random.uniform(5, 80), 1),
                    "establish_date": (
                        datetime.now() - timedelta(days=random.randint(400, 2000))
                    ).strftime("%Y-%m-%d"),
                    "tracking_index": index_code,
                })
        return funds


_fetcher = _DataFetcher()


# ════════════════════════════════════════════════════════════
# Layer 1: 板块雷达 (Sector Radar)
# ════════════════════════════════════════════════════════════

class SectorRadar:
    """
    板块雷达：评估申万行业 / 中证主题指数的估值水位和动量。
    """

    def __init__(self):
        self.fetcher = _fetcher
        self._cache: Dict[str, List[Dict]] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl_minutes = 30
        # 单次请求内缓存，避免同一 symbol 重复拉取
        self._hist_cache: Dict[str, Optional[pd.DataFrame]] = {}
        # 申万一级行业日度估值面板（多行业共用，单独缓存减轻重复拉取）
        self._sw_pe_panel_df: Optional[pd.DataFrame] = None
        self._sw_pe_panel_time: Optional[datetime] = None
        self._sw_pe_panel_ttl_sec = 45 * 60

    def _is_cache_valid(self, key: str) -> bool:
        t = self._cache_time.get(key)
        if t is None:
            return False
        return (datetime.now() - t).total_seconds() < self._cache_ttl_minutes * 60

    def get_sw_industries(self) -> List[Dict[str, Any]]:
        """获取申万一级行业实时行情。"""
        cache_key = "sw_industries"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        results = []
        sw_df = self.fetcher.fetch_sw_realtime("一级行业")
        if sw_df is not None and not sw_df.empty:
            name_col = next((c for c in sw_df.columns if "名称" in c), None)
            code_col = next((c for c in sw_df.columns if "代码" in c), None)
            price_col = next((c for c in sw_df.columns if "最新价" in c), None)
            prev_col = next((c for c in sw_df.columns if "昨收盘" in c), None)
            chg_col = next((c for c in sw_df.columns if "涨跌幅" in c), None)  # 可能不存在
            for _, row in sw_df.iterrows():
                code = str(row.get(code_col, "")).strip()
                name = str(row.get(name_col, "")).strip()
                if not name or name in ("nan", "None") or not code:
                    continue
                price = _to_float(row.get(price_col))
                prev_close = _to_float(row.get(prev_col)) if prev_col else None
                if chg_col is not None:
                    change_pct = _to_float(row.get(chg_col))
                elif prev_close and prev_close > 0:
                    change_pct = round((price - prev_close) / prev_close * 100, 2)
                else:
                    change_pct = 0.0
                results.append({
                    "code": code,
                    "name": name,
                    "source": "sw",
                    "price": price,
                    "change_pct": change_pct,
                    "volume": 0, "amount": 0,
                    "pe": None, "pb": None, "ps": None,
                    "pe_percentile": None, "ps_percentile": None,
                    "momentum_20d": None, "volume_ratio": None,
                    "signal": "neutral", "signal_reason": "",
                })
        else:
            results = self._get_sw_industries_fallback()

        self._enrich_with_pe_history(results)
        self._compute_momentum(results)
        self._emit_signals(results)

        self._cache[cache_key] = results
        self._cache_time[cache_key] = datetime.now()
        return results

    def _get_sw_industries_fallback(self) -> List[Dict[str, Any]]:
        names = list(SW_INDUSTRY_MAP.values())
        return [
            {
                "code": f"8010{i:02d}0",
                "name": n,
                "source": "sw",
                "price": round(random.uniform(1000, 5000), 2),
                "change_pct": round(random.uniform(-5, 5), 2),
                "volume": 0, "amount": 0,
                "pe": None, "pb": None, "ps": None,
                "pe_percentile": None, "ps_percentile": None,
                "momentum_20d": None, "volume_ratio": None,
                "signal": "neutral", "signal_reason": "",
            }
            for i, n in enumerate(names[:20])
        ]

    def get_csi_indices(self) -> List[Dict[str, Any]]:
        """获取中证主题指数的实时行情与估值。"""
        cache_key = "csi_indices"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        results = []
        for code, meta in CSI_INDEX_CODES.items():
            sina_sym = f"sh{code}"
            spot = self.fetcher.fetch_sina_spot_by_code(sina_sym)
            if spot is None:
                spot = {"price": 0, "change_pct": 0, "volume": 0, "amount": 0, "high": 0, "low": 0}

            row = {
                "code": code,
                "name": meta["name"],
                "source": "csi",
                "risk_type": meta["risk"],
                "pe_type": meta["pe_type"],
                "price": spot.get("price", 0),
                "change_pct": spot.get("change_pct", 0),
                "volume": spot.get("volume", 0),
                "amount": spot.get("amount", 0),
                "high": spot.get("high", 0),
                "low": spot.get("low", 0),
                "pe": None, "pb": None, "ps": None,
                "pe_percentile": None, "ps_percentile": None,
                "momentum_20d": None, "volume_ratio": None,
                "signal": "neutral", "signal_reason": "",
            }
            results.append(row)

        self._enrich_with_pe_history(results)
        self._compute_momentum(results)
        self._emit_signals(results)

        self._cache[cache_key] = results
        self._cache_time[cache_key] = datetime.now()
        return results

    def _load_sw_pe_analysis_panel(self) -> Optional[pd.DataFrame]:
        """拉取申万一级行业日度分析表（含市盈率），带短 TTL 复用。"""
        now = datetime.now()
        if (
            self._sw_pe_panel_df is not None
            and self._sw_pe_panel_time is not None
            and (now - self._sw_pe_panel_time).total_seconds() < self._sw_pe_panel_ttl_sec
        ):
            return self._sw_pe_panel_df

        end = now.strftime("%Y%m%d")
        # 约 12~14 个月交易日：分位可解释性与申万接口分页耗时的折中（分页过慢会被线程超时截断）
        start = (now - timedelta(days=340)).strftime("%Y%m%d")

        def _call():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return ak.index_analysis_daily_sw(symbol="一级行业", start_date=start, end_date=end)

        try:
            # 申万接口需连续翻页，120s 常不够导致返回空；单独放宽上限
            df = _safely_call(_call, timeout=360)
        except Exception as e:
            logger.warning(f"申万行业估值面板获取失败: {e}")
            df = None
        if df is None or getattr(df, "empty", True):
            return None
        self._sw_pe_panel_df = df
        self._sw_pe_panel_time = now
        return df

    def _enrich_sw_pe_percentiles(self, sectors: List[Dict[str, Any]]) -> None:
        panel = self._load_sw_pe_analysis_panel()
        if panel is None or panel.empty:
            return
        if "指数代码" not in panel.columns or "市盈率" not in panel.columns:
            return
        date_col = "发布日期" if "发布日期" in panel.columns else panel.columns[0]
        work = panel.copy()
        work["__code"] = work["指数代码"].map(_normalize_sw_index_code)
        for sec in sectors:
            if sec.get("source") != "sw":
                continue
            code = _normalize_sw_index_code(sec.get("code"))
            if not code:
                continue
            sub = work.loc[work["__code"] == code].sort_values(date_col)
            if len(sub) < 12:
                continue
            pe_series = sub["市盈率"]
            pct = _percentile_rank_last_vs_history(pe_series, min_points=12)
            if pct is None:
                continue
            sec["pe_percentile"] = pct
            last_pe = pd.to_numeric(pe_series, errors="coerce").dropna()
            if len(last_pe) > 0 and float(last_pe.iloc[-1]) > 0:
                sec["pe"] = round(float(last_pe.iloc[-1]), 2)

    @staticmethod
    def _csi_hist_pe_percentile(index_code: str) -> Dict[str, Any]:
        """
        中证官网指数历史 perf：滚动市盈率序列 → 当前分位。
        部分深证指数在中证接口无数据时，回退东财指数收盘价历史分位（近似）。
        """
        out: Dict[str, Any] = {"pe_percentile": None, "pe": None, "proxy": None}
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=800)).strftime("%Y%m%d")
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.stock_zh_index_hist_csindex(symbol=str(index_code), start_date=start, end_date=end)
            if df is not None and not df.empty and "滚动市盈率" in df.columns:
                ser = pd.to_numeric(df["滚动市盈率"], errors="coerce")
                pct = _percentile_rank_last_vs_history(ser, min_points=15)
                if pct is not None:
                    out["pe_percentile"] = pct
                    out["proxy"] = "csindex_pe_ttm"
                last = ser.dropna()
                if len(last) > 0 and float(last.iloc[-1]) > 0:
                    out["pe"] = round(float(last.iloc[-1]), 2)
                if out["pe_percentile"] is not None:
                    return out
        except Exception:
            pass

        # 创业板指等在中证 perf 无数据时，用指数收盘价历史分位作演示级近似
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                hist = ak.index_zh_a_hist(
                    symbol=str(index_code),
                    period="daily",
                    start_date=start,
                    end_date=end,
                )
            if hist is None or hist.empty or "收盘" not in hist.columns:
                return out
            closes = pd.to_numeric(hist["收盘"], errors="coerce")
            pct = _percentile_rank_last_vs_history(closes, min_points=30)
            if pct is not None:
                out["pe_percentile"] = pct
                out["proxy"] = "em_close_proxy"
        except Exception as e:
            logger.debug("CSI 估值分位东财兜底失败 %s: %s", index_code, e)
        return out

    def _enrich_csi_pe_percentiles(self, sectors: List[Dict[str, Any]]) -> None:
        csi = [s for s in sectors if s.get("source") == "csi"]
        if not csi:
            return

        def _task(sec: Dict[str, Any]) -> None:
            code = str(sec.get("code") or "")
            if not code:
                return
            r = self._csi_hist_pe_percentile(code)
            if r.get("pe_percentile") is not None:
                sec["pe_percentile"] = r["pe_percentile"]
            if r.get("pe") is not None:
                sec["pe"] = r["pe"]
            if r.get("proxy"):
                sec["valuation_proxy"] = r["proxy"]

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(_task, s) for s in csi]
            for fut in as_completed(futures, timeout=180):
                try:
                    fut.result()
                except Exception as e:
                    logger.debug("CSI 单指数估值任务异常: %s", e)

    def _enrich_with_pe_history(self, sectors: List[Dict[str, Any]]) -> None:
        """
        估值百分位：
        - 申万一级：申万宏源日度行业分析表中的市盈率历史；
        - 中证主题：中证官网指数 perf 的滚动市盈率，失败时用东财指数收盘价分位近似。
        """
        if not sectors:
            return
        if any(s.get("source") == "sw" for s in sectors):
            self._enrich_sw_pe_percentiles(sectors)
        if any(s.get("source") == "csi" for s in sectors):
            self._enrich_csi_pe_percentiles(sectors)

    def _compute_momentum(self, sectors: List[Dict[str, Any]]) -> None:
        """
        动量计算。Sina 历史K线在国内慢，跳过。
        用实时涨跌率近似短期动量。
        """
        for sec in sectors:
            change = sec.get("change_pct") or 0
            sec["momentum_20d"] = round(change, 2)
            sec["volume_ratio"] = 1.0

    def _emit_signals(self, sectors: List[Dict[str, Any]]) -> None:
        """
        生成板块推荐信号。

        有 PE 百分位时用 PE + 动量综合判断；
        无 PE 数据时（国内网络受限）改用实时涨跌率近似：
          - 涨幅 > 2% 且非高位追涨 → strong_buy（强势启动）
          - 涨幅 0.5~2% → buy（温和上涨）
          - 跌幅 > 2% → sell（弱势）
          - 跌幅 > 4% → strong_sell（破位下行）
          - 涨跌在 ±0.5% → neutral（无明显方向）
        """
        for sec in sectors:
            change = sec.get("change_pct") or 0  # 今日涨跌幅（%）
            pe_pct = sec.get("pe_percentile")   # 可能为 None

            if pe_pct is not None:
                if pe_pct < 20 and change > 0:
                    sec["signal"] = "strong_buy"
                    sec["signal_reason"] = f"估值历史低位({pe_pct:.0f}%百分位)+今日上涨"
                elif pe_pct < 30:
                    sec["signal"] = "buy"
                    sec["signal_reason"] = f"估值偏低({pe_pct:.0f}%百分位)"
                elif pe_pct > 70:
                    sec["signal"] = "strong_sell"
                    sec["signal_reason"] = f"历史估值高位({pe_pct:.0f}%百分位)"
                elif abs(change) > 3:
                    sec["signal"] = "neutral"
                    sec["signal_reason"] = f"估值中位附近，单日异动({change:+.1f}%)，注意风险"
                else:
                    sec["signal"] = "neutral"
                    sec["signal_reason"] = "估值处于历史中位"
            else:
                # 无 PE 数据，用实时涨跌率近似
                if change > 3:
                    sec["signal"] = "strong_buy"
                    sec["signal_reason"] = f"今日强势上涨({change:+.2f}%)，资金持续流入"
                elif change > 1:
                    sec["signal"] = "buy"
                    sec["signal_reason"] = f"今日温和上涨({change:+.2f}%)，动能良好"
                elif change > 0:
                    sec["signal"] = "buy"
                    sec["signal_reason"] = f"今日小幅上涨({change:+.2f}%)"
                elif change < -3:
                    sec["signal"] = "strong_sell"
                    sec["signal_reason"] = f"今日大幅下跌({change:+.2f}%)，注意止损"
                elif change < -1:
                    sec["signal"] = "sell"
                    sec["signal_reason"] = f"今日走弱({change:+.2f}%)，动能不足"
                elif abs(change) <= 0.3:
                    sec["signal"] = "neutral"
                    sec["signal_reason"] = "今日窄幅震荡，观望"
                else:
                    sec["signal"] = "neutral"
                    sec["signal_reason"] = f"今日({change:+.2f}%)方向不明"

    def get_sector_by_code(self, sector_code: str) -> Optional[Dict[str, Any]]:
        all_s = self.get_sw_industries() + self.get_csi_indices()
        for s in all_s:
            if s["code"] == sector_code:
                return s
        return None

    def get_hot_sectors(self, top_n: int = 6) -> List[Dict[str, Any]]:
        """热门板块：直接按 _emit_signals 的信号强度 + 涨跌幅排序。"""
        all_s = self.get_sw_industries() + self.get_csi_indices()
        scored = []
        for s in all_s:
            score = 0
            sig = s.get("signal", "neutral")
            if sig == "strong_buy": score += 5
            elif sig == "buy": score += 3
            elif sig == "sell": score -= 3
            elif sig == "strong_sell": score -= 5
            # 涨幅加成
            score += (s.get("change_pct") or 0) * 0.5
            scored.append((score, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:top_n]]

    def get_undervalued_sectors(self, top_n: int = 6) -> List[Dict[str, Any]]:
        """
        获取低估板块。有 PE 百分位时用 PE；无数据时用跌幅大小近似（跌得多可能价值显现）。
        """
        all_s = self.get_sw_industries() + self.get_csi_indices()
        # 有 PE 百分位时直接用
        with_pe = [s for s in all_s if s.get("pe_percentile") is not None]
        with_pe_sorted = sorted(with_pe, key=lambda x: x.get("pe_percentile") or 99)

        if with_pe_sorted:
            return with_pe_sorted[:top_n]

        # 无 PE 数据：用跌幅近似低估（跌越多相对更"便宜"）
        # 注意：涨幅过大的板块追高风险高，也排除
        without_pe = [s for s in all_s if (s.get("change_pct") or 0) <= 2.0]
        without_pe.sort(key=lambda x: x.get("change_pct") or 0)
        return without_pe[:top_n]


# ════════════════════════════════════════════════════════════
# Layer 2: 基金初筛 (Quant Filter)
# ════════════════════════════════════════════════════════════

class FundQuantFilter:
    """基金量化筛选器。"""

    MIN_SCALE = 2.0
    MAX_SCALE = 100.0
    MIN_AGE_DAYS = 365

    def filter_by_scale_and_age(self, funds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        now = datetime.now()
        for f in funds:
            scale = f.get("asset_scale")
            if scale is not None and float(scale) > 0:
                sc = float(scale)
                if sc < self.MIN_SCALE or sc > self.MAX_SCALE:
                    continue
            est_date = f.get("establish_date")
            if est_date:
                try:
                    est = datetime.strptime(str(est_date)[:10], "%Y-%m-%d")
                    if (now - est).days < self.MIN_AGE_DAYS:
                        continue
                except Exception:
                    pass
            results.append(f)
        return results

    def choose_share_class(self, funds: List[Dict[str, Any]], holding_months: int = 12) -> List[Dict[str, Any]]:
        """持有 >= 18 个月选 A 类，否则选 C 类（模拟数据均为 A 类）。"""
        for f in funds:
            name = f.get("name", "")
            is_c = "C" in name.split()[-1] or name.endswith("C")
            if holding_months >= 18 and is_c:
                f["share_class"] = "A"
            else:
                f["share_class"] = "C" if is_c else "A"
        return funds

    def filter_by_sector(self, sector_code: str, sector_name: str, holding_months: int = 12) -> List[Dict[str, Any]]:
        raw_funds = _fetcher.fetch_fund_list_for_sector(sector_code, sector_name)
        filtered = self.filter_by_scale_and_age(raw_funds)
        return self.choose_share_class(filtered, holding_months)


# ════════════════════════════════════════════════════════════
# Layer 3: 核心指标排序 (Alpha Ranking)
# ════════════════════════════════════════════════════════════

class FundAlphaRanker:
    """多因子打分基金排序器。"""

    def __init__(self):
        self.fetcher = _fetcher

    def rank(self, funds: List[Dict[str, Any]], index_code: str = "") -> List[Dict[str, Any]]:
        if not funds:
            return []

        def _score_one(fund: Dict[str, Any]) -> Dict[str, Any]:
            code = str(fund.get("code", "")).strip().zfill(6)
            merged: Dict[str, Any] = {**fund, "code": code}
            em = self.fetcher.fetch_fund_basic_em(code)
            if em:
                if em.get("name"):
                    merged["name"] = em["name"]
                if em.get("asset_scale"):
                    merged["asset_scale"] = float(em["asset_scale"])
                if em.get("establish_date") and not merged.get("establish_date"):
                    merged["establish_date"] = em["establish_date"]
                if em.get("fund_type") and not merged.get("fund_type"):
                    merged["fund_type"] = em["fund_type"]
            nav_series = self.fetcher.fetch_fund_nav_history(code, count=300)
            nav_val = _to_float(merged.get("nav"), 0.0)
            if (not nav_val or nav_val <= 0) and nav_series is not None and len(nav_series):
                merged["nav"] = float(nav_series.iloc[-1]["nav"])
            scores = self._compute_factors(merged, nav_series, index_code)
            total_score = self._aggregate_score(scores)
            return {
                **merged,
                "factors": scores,
                "total_score": round(total_score, 2),
                "rank_label": self._score_to_label(total_score),
            }

        workers = min(8, max(1, len(funds)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            scored_funds = list(pool.map(_score_one, funds))

        scored_funds.sort(key=lambda x: x["total_score"], reverse=True)
        for i, f in enumerate(scored_funds):
            f["rank"] = i + 1
        return scored_funds

    def _compute_factors(self, fund: Dict, nav_series: Optional[pd.DataFrame], index_code: str) -> Dict[str, float]:
        scores = {
            "sharpe": 50.0, "max_dd": 50.0, "info_ratio": 50.0,
            "ps_valuation": 50.0, "momentum_3m": 50.0,
            "momentum_6m": 50.0, "scale_score": 50.0,
        }
        raw = {}

        if nav_series is not None and len(nav_series) >= 60:
            closes = nav_series["nav"].values
            returns = np.diff(closes) / closes[:-1]

            if returns.std() > 0:
                annual_ret = returns.mean() * 252
                annual_vol = returns.std() * math.sqrt(252)
                sharpe = (annual_ret - RISK_FREE_RATE) / annual_vol if annual_vol > 0 else 0
            else:
                sharpe = 0.0
            raw["sharpe"] = sharpe
            scores["sharpe"] = max(0.0, min(100.0, 50 + sharpe * 10))

            dd = self._max_drawdown(closes)
            raw["max_dd"] = dd
            scores["max_dd"] = max(0.0, min(100.0, 100 + dd * 200))

            ir = self._information_ratio(returns)
            raw["info_ratio"] = ir
            scores["info_ratio"] = max(0.0, min(100.0, 50 + ir * 20))

            mom_3m = self._momentum(closes, 60)
            mom_6m = self._momentum(closes, 120)
            scores["momentum_3m"] = max(0.0, min(100.0, 50 + mom_3m * 50))
            scores["momentum_6m"] = max(0.0, min(100.0, 50 + mom_6m * 50))
            raw["momentum_3m"] = mom_3m
            raw["momentum_6m"] = mom_6m

            if CSI_INDEX_CODES.get(index_code, {}).get("pe_type") == "PS":
                if len(closes) >= 100:
                    curr = closes[-1]
                    pct = (curr < closes).sum() / len(closes) * 100
                    scores["ps_valuation"] = max(0.0, min(100.0, 100 - pct))

        scale = fund.get("asset_scale") or 10
        raw["scale"] = scale
        if 10 <= scale <= 50: scores["scale_score"] = 80.0
        elif 5 <= scale < 10 or 50 < scale <= 80: scores["scale_score"] = 60.0
        else: scores["scale_score"] = 40.0

        fund["_raw_factors"] = raw
        return scores

    @staticmethod
    def _max_drawdown(closes: np.ndarray) -> float:
        peak = np.maximum.accumulate(closes)
        dd = (closes - peak) / peak
        return float(dd.min())

    @staticmethod
    def _information_ratio(returns: np.ndarray) -> float:
        bench = np.full_like(returns, RISK_FREE_RATE / 252)
        excess = returns - bench
        if excess.std() > 0:
            return float(excess.mean() * 252 / (excess.std() * math.sqrt(252)))
        return 0.0

    @staticmethod
    def _momentum(closes: np.ndarray, window: int) -> float:
        if len(closes) <= window:
            return 0.0
        return float((closes[-1] - closes[-window]) / closes[-window])

    def _aggregate_score(self, scores: Dict[str, float]) -> float:
        weights = {
            "sharpe": 0.20, "max_dd": 0.15, "info_ratio": 0.15,
            "ps_valuation": 0.10, "momentum_3m": 0.20,
            "momentum_6m": 0.10, "scale_score": 0.10,
        }
        return sum(scores.get(k, 50) * w for k, w in weights.items())

    @staticmethod
    def _score_to_label(score: float) -> str:
        if score >= 80: return "⭐⭐⭐ 强力推荐"
        elif score >= 65: return "⭐⭐ 推荐"
        elif score >= 50: return "⭐ 可关注"
        else: return "观望"


# ════════════════════════════════════════════════════════════
# Layer 4: AI 决策报告 (AI Insights)
# ════════════════════════════════════════════════════════════

class FundAIInsights:
    """调用 Kimi 大模型生成 AI 决策报告。"""

    def __init__(self):
        self.api_url = os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1/chat/completions").strip()
        self.model = os.getenv("KIMI_MODEL", "moonshot-v1-8k").strip()
        self.api_key = os.getenv("KIMI_API_KEY", "")

    def generate(self, top_funds: List[Dict], sector: Dict, holding_months: int = 12) -> Dict[str, Any]:
        if not top_funds:
            return {"error": "暂无基金数据"}
        if not self.api_key:
            return self._generate_mock_insights(top_funds, sector, holding_months)

        prompt = self._build_prompt(top_funds, sector, holding_months)
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1200,
            }
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.api_url, data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return self._parse_insights(content, top_funds)
        except Exception as e:
            logger.warning(f"Kimi API 调用失败: {e}")
            return self._generate_mock_insights(top_funds, sector, holding_months)

    def _build_prompt(self, top_funds: List[Dict], sector: Dict, holding_months: int) -> str:
        fund_lines = []
        for f in top_funds[:5]:
            raw = f.get("_raw_factors") or {}
            sh = raw.get("sharpe")
            sharpe_s = f"{float(sh):.2f}" if isinstance(sh, (int, float)) else "—"
            scale_s = (
                f"{_to_float(raw.get('scale'), 0.0):.1f}"
                if raw.get("scale") is not None
                else "—"
            )
            dd_pct = _to_float(raw.get("max_dd"), 0.0) * 100
            mom_pct = _to_float(raw.get("momentum_3m"), 0.0) * 100
            fund_lines.append(
                f"- {f.get('code')} | {f.get('name')} | 净值:{f.get('nav','N/A')} | "
                f"规模:{scale_s}亿 | 夏普:{sharpe_s} | "
                f"最大回撤:{dd_pct:.1f}% | 3月动量:{mom_pct:.1f}%"
            )
        return (
            f"## 当前板块\n{sector.get('name','N/A')} | {sector.get('code','N/A')} | "
            f"估值百分位:{sector.get('pe_percentile','N/A')}% | "
            f"20日动量:{sector.get('momentum_20d','N/A')}% | "
            f"信号:{sector.get('signal','N/A')}\n\n"
            f"## 候选基金\n" + "\n".join(fund_lines) + f"\n\n"
            f"## 预期持有 {holding_months} 个月\n\n"
            f"请生成【推荐理由】【风险预警】【操作建议】三部分，每条用项目符号：\n"
            f"1. 推荐理由：结合估值、基金历史表现（数据化）\n"
            f"2. 风险预警：量化风险程度，具体明确\n"
            f"3. 操作建议：基于「份额不变」原理，给出补仓区间和止盈目标"
        )

    @staticmethod
    def _parse_insights(content: str, top_funds: List[Dict]) -> Dict[str, Any]:
        result = {
            "reasons": [], "warnings": [], "actions": [],
            "summary": "", "top_fund_code": top_funds[0].get("code", ""),
            "top_fund_name": top_funds[0].get("name", ""),
        }
        current_section = None
        for line in content.split("\n"):
            line = line.strip()
            if "推荐理由" in line: current_section = "reasons"
            elif "风险预警" in line: current_section = "warnings"
            elif "操作建议" in line: current_section = "actions"
            elif current_section and line.startswith(("-", "•", "*")):
                text = line.lstrip("-•* ").strip()
                if text: result[current_section].append(text)
        if not any(result[k] for k in ("reasons", "warnings", "actions")):
            result["summary"] = content[:500]
        return result

    @staticmethod
    def _generate_mock_insights(top_funds: List[Dict], sector: Dict, holding_months: int) -> Dict[str, Any]:
        top = top_funds[0] if top_funds else {}
        code = top.get("code", "N/A")
        name = top.get("name", "N/A")
        pe_raw = sector.get("pe_percentile")
        pe_pct = 50.0 if pe_raw is None else float(pe_raw)
        raw = top.get("_raw_factors") or {}
        sharpe = _to_float(raw.get("sharpe"), 0.0)
        max_dd = _to_float(raw.get("max_dd"), 0.0)
        mom3m = _to_float(raw.get("momentum_3m"), 0.0)
        nav = _to_float(top.get("nav"), 1.0) or 1.0
        sector_name = sector.get("name", "相关板块")
        signal = sector.get("signal", "neutral")

        buy_zones = [
            f"净值下跌至 {nav * 0.95:.3f} 元（-5%）时加仓 10% 份额",
            f"净值下跌至 {nav * 0.90:.3f} 元（-10%）时加仓 15% 份额",
            f"净值下跌至 {nav * 0.85:.3f} 元（-15%）时加仓 20% 份额",
        ]
        profit_take = [
            f"目标1：净值达到 {nav * 1.15:.3f} 元（+15%）时赎回 30% 利润部分",
            f"目标2：净值达到 {nav * 1.30:.3f} 元（+30%）时赎回 50% 利润部分",
            f"目标3：净值达到 {nav * 1.50:.3f} 元（+50%）时清仓或留10%观察",
            f"定投方式：每次投入总金额的20%，分5次完成建仓",
        ]

        val_text = (
            f"{sector_name}处于历史估值低位（{pe_pct:.0f}%百分位），安全边际较高"
            if pe_pct < 30 else
            f"{sector_name}估值偏高（{pe_pct:.0f}%百分位），需注意回调风险"
            if pe_pct > 60 else
            f"{sector_name}估值中等（{pe_pct:.0f}%百分位），可择机布局"
        )

        return {
            "reasons": [
                f"{code} {name} 夏普比率 {sharpe:.2f}，优于同类平均，配置性价比高",
                f"{val_text}",
                f"近3月动量 {mom3m*100:.1f}%，近期表现优于基准指数",
                f"最大回撤 {max_dd*100:.1f}%，风险控制在同类中表现稳健",
                f"综合评分在同类{len(top_funds)}只候选基金中排名第{top.get('rank', '前')}",
            ],
            "warnings": [
                f"{sector_name}板块近期波动可能较大，建议控制单次买入金额",
                f"当前{sector_name}换手率偏高，板块轮动加快，需关注热点切换风险",
                f"该基金历史最大回撤 {max_dd*100:.1f}%，短期亏损可能超出心理承受范围",
                f"持有时长不足{holding_months}个月时，赎回可能产生较高手续费",
                "市场有风险，投资需谨慎，上述建议不构成保证收益承诺",
            ],
            "actions": buy_zones + profit_take,
            "summary": f"基于{sector_name}板块{signal}信号，综合量化筛选结果，推荐关注{name}（{code}）",
            "top_fund_code": code,
            "top_fund_name": name,
        }


# ════════════════════════════════════════════════════════════
# 顶层 API 函数
# ════════════════════════════════════════════════════════════

_sector_radar = SectorRadar()
_fund_filter = FundQuantFilter()
_fund_ranker = FundAlphaRanker()
_fund_ai = FundAIInsights()


def get_sector_radar_data(sector_type: str = "all", limit: int = 20) -> Dict[str, Any]:
    if sector_type == "hot":
        sectors = _sector_radar.get_hot_sectors(top_n=limit)
    elif sector_type == "undervalued":
        sectors = _sector_radar.get_undervalued_sectors(top_n=limit)
    else:
        sectors = _sector_radar.get_sw_industries() + _sector_radar.get_csi_indices()
        sectors = sorted(
            sectors,
            key=lambda x: (
                0 if x.get("signal") in ("strong_buy", "buy") else 1,
                -(x.get("pe_percentile") or 50),
            ),
        )[:limit]

    today = datetime.now()
    weekday = today.weekday()
    is_weekend = (weekday == 5 or weekday == 6)
    trade_date = _last_trade_date()
    date_note = f"数据截至 {trade_date}（周末休市）" if is_weekend else f"数据截至 {trade_date}"

    return {
        "timestamp": datetime.now().isoformat(),
        "trade_date": trade_date,
        "is_weekend": is_weekend,
        "date_note": date_note,
        "sectors": sectors,
        "total": len(sectors),
    }


def screen_funds(
    sector_code: str,
    holding_months: int = 12,
    top_n: int = 10,
    include_ai: bool = True,
) -> Dict[str, Any]:
    start = time.time()

    sector = _sector_radar.get_sector_by_code(sector_code)
    if sector is None:
        all_s = _sector_radar.get_sw_industries() + _sector_radar.get_csi_indices()
        for s in all_s:
            if s["code"] == sector_code:
                sector = s
                break
    if sector is None:
        sector = {"code": sector_code, "name": sector_code, "signal": "unknown"}

    candidate_funds = _fund_filter.filter_by_sector(
        sector_code, str(sector.get("name") or ""), holding_months
    )
    if not candidate_funds:
        candidate_funds = _fund_filter.filter_by_scale_and_age(
            _fetcher._generate_mock_funds(sector_code)
        )

    ranked_funds = _fund_ranker.rank(candidate_funds, sector_code)
    top_funds = ranked_funds[:top_n]

    result = {
        "sector": sector,
        "candidates_count": len(candidate_funds),
        "ranked_funds": top_funds,
        "ranked_count": len(ranked_funds),
        "elapsed_ms": round((time.time() - start) * 1000, 1),
    }

    if include_ai and top_funds:
        result["ai_report"] = _fund_ai.generate(top_funds, sector, holding_months)

    return result


def get_fund_detail(code: str) -> Dict[str, Any]:
    code = str(code or "").strip().zfill(6)
    info_xq = _fetcher.fetch_fund_info_xq(code) or {}
    info_em = _fetcher.fetch_fund_basic_em(code) or {}

    name = (str(info_xq.get("name") or "").strip() or str(info_em.get("name") or "").strip() or code)
    asset_scale = _to_float(info_xq.get("asset_scale"), 0.0) or _to_float(info_em.get("asset_scale"), 0.0)
    nav = _to_float(info_xq.get("nav"), 0.0)
    raw_nc = info_xq.get("nav_change_pct")
    nav_change_pct: Optional[float] = None
    if raw_nc is not None and str(raw_nc).strip() not in ("", "--", "None", "nan"):
        nav_change_pct = float(_to_float(raw_nc, 0.0))
    establish_date = info_xq.get("establish_date") or info_em.get("establish_date")
    fund_type = info_xq.get("fund_type") or info_em.get("fund_type")

    nav_series = _fetcher.fetch_fund_nav_history(code, count=300)
    if (not nav or nav <= 0) and nav_series is not None and len(nav_series):
        nav = float(nav_series.iloc[-1]["nav"])

    base: Dict[str, Any] = {
        "code": code,
        "name": name,
        "nav": nav if nav > 0 else None,
        "nav_change_pct": nav_change_pct,
        "asset_scale": asset_scale if asset_scale > 0 else None,
        "establish_date": establish_date,
        "fund_type": fund_type,
    }

    ranker = FundAlphaRanker()
    scores = ranker._compute_factors(base, nav_series, "")
    total = ranker._aggregate_score(scores)
    return {
        **base,
        "factors": scores,
        "total_score": round(total, 2),
        "rank_label": FundAlphaRanker._score_to_label(total),
        "nav_history": (
            [
                {"date": str(row["date"].date()), "nav": float(row["nav"]), "acc_nav": float(row["acc_nav"])}
                for _, row in nav_series.iterrows()
            ]
            if nav_series is not None
            else []
        ),
    }


_SYSTEM_PROMPT = """你是一位专业的基金投资顾问，擅长量化分析和资产配置。请：
1. 基于数据说话，引用具体数字和指标
2. 风险提示明确、量化
3. 操作建议可执行，给出净值区间和份额比例
4. 始终强调"投资有风险，入市需谨慎"
5. 语言简洁专业，适合中文用户

输出格式：
【推荐理由】
- 每条理由一句话，引用具体数据

【风险预警】
- 每条风险一句话，量化程度

【操作建议】
- 补仓：净值区间 + 对应操作
- 止盈：目标净值 + 赎回比例
"""

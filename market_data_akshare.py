"""
使用 efinance 获取市场概览数据（东方财富数据源）。
返回每个指数的最新价、涨跌幅、涨跌额。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import efinance as ef
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _to_float(value: object) -> Optional[float]:
    """安全转换为 float，失败返回 None。"""
    if value is None:
        return None
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        if text in ("", "-", "--", "None", "nan"):
            return None
        return float(text)
    except Exception:
        return None


def _extract_from_df(df: pd.DataFrame, target_name: str) -> Optional[Dict]:
    """
    从 efinance 的最新行情 DataFrame 中按名称提取一行，并标准化为:
    {name, price, change_pct, change_amount}
    """
    if df is None or df.empty or "名称" not in df.columns:
        return None

    sub = df[df["名称"] == target_name]
    if sub.empty:
        return None

    row = sub.iloc[0]

    price = _to_float(row.get("最新价"))
    change_pct = _to_float(row.get("涨跌幅"))
    change_amount = _to_float(row.get("涨跌额"))

    if price is None or change_pct is None or change_amount is None:
        return None

    return {
        "name": target_name,
        "price": price,
        "change_pct": change_pct,
        "change_amount": change_amount,
    }


def get_market_data() -> Dict[str, List[Dict]]:
    """
    使用 efinance 一次性拉取全市场最新行情，然后按名称筛选出目标指数。

    返回结构:
        {
            "a_stock": [...],        # A股指数 + 国债/企债
            "hk_us": [...],          # 港股 + 美股指数
            "bond_commodity": [...], # 债券/商品（国债、企债、COMEX黄金）
        }

    健壮性：
        - 整体 try/except，接口异常时返回空结构，不抛出到调用方。
        - 单个指数缺失，不影响其它指数。
    """
    result: Dict[str, List[Dict]] = {
        "a_stock": [],
        "hk_us": [],
        "bond_commodity": [],
    }

    try:
        # 在当前版本中 get_latest_quote 需要显式传入代码列表
        # 这里只传入我们关心、且实测可用的指数代码，避免整体失败
        #
        # 说明：
        # - 399001: 深证成指
        # - 399006: 创业板指
        # - 399330: 深证100
        # - 899050: 北证50
        # - 000300: 沪深300
        #
        # 其他如「上证指数 / 中证500 / 中证1000 / 债券指数 / 企债指数 /
        # 恒生系列 / 美股指数 / COMEX黄金」在 efinance 当前 API 中
        # 无直接行情入口，这些项目会自然留空（不再用模拟数据补齐）。
        codes = ["399001", "399006", "399330", "899050", "000300"]
        df = ef.stock.get_latest_quote(codes)
    except Exception as exc:
        logger.warning("efinance 获取最新行情失败: %s", exc)
        return result

    # ===== 目标指数清单 =====
    a_stock_names = [
        "上证指数",
        "深证成指",
        "创业板指",
        "北证50",
        "科创50",
        "上证50",
        "深证100",
        "沪深300",
        "中证500",
        "中证1000",
    ]

    bond_names = [
        "国债指数",
        "企债指数",
    ]

    hk_us_names = [
        "恒生指数",
        "恒生国企",
        "恒生科技",
        "道琼斯",
        "纳斯达克",
        "标普500",
    ]

    commodity_names = [
        "COMEX黄金",
    ]

    # A股指数
    for name in a_stock_names:
        try:
            item = _extract_from_df(df, name)
            if item:
                result["a_stock"].append(item)
        except Exception:
            continue

    # 债券指数同时计入 A股分组和 债/商 分组，方便前端展示
    for name in bond_names:
        try:
            item = _extract_from_df(df, name)
            if item:
                # A股分组里也放一份
                result["a_stock"].append(item)
                # 债/商分组
                result["bond_commodity"].append(item)
        except Exception:
            continue

    # 港股 + 美股
    for name in hk_us_names:
        try:
            item = _extract_from_df(df, name)
            if item:
                result["hk_us"].append(item)
        except Exception:
            continue

    # COMEX 黄金
    for name in commodity_names:
        try:
            item = _extract_from_df(df, name)
            if item:
                result["bond_commodity"].append(item)
        except Exception:
            continue

    logger.info(
        "efinance 数据获取完成: A股=%s, 港美=%s, 债商=%s",
        len(result["a_stock"]),
        len(result["hk_us"]),
        len(result["bond_commodity"]),
    )
    return result

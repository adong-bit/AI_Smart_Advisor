import os

from dotenv_local import load_local_env

# 必须在导入 kimi_* 等模块之前执行，确保 KIMI_API_KEY 已从 .env 注入 os.environ
load_local_env()

from flask import Flask, render_template, jsonify, request
from kimi_news_sentiment import enrich_news_sentiment_with_kimi
from kimi_market_insights import generate_market_insights_with_kimi
from kimi_allocation_advice import generate_allocation_advice_with_kimi
from kimi_stock_reason import generate_stock_reasons_with_kimi
import random
import math
import re
import io
import time
import threading
import json
from datetime import datetime, timedelta
from market_data_akshare import get_market_data
import akshare as ak
import requests
try:
    from PIL import Image
    import pytesseract
    OCR_READY = True
except Exception:
    OCR_READY = False

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OCR_READY = True
    RAPID_OCR_ENGINE = RapidOCR()
except Exception:
    RAPID_OCR_READY = False
    RAPID_OCR_ENGINE = None

# 导入真实数据获取模块
try:
    from data_fetcher import get_market_overview, fetcher
    USE_REAL_DATA = True
except ImportError:
    USE_REAL_DATA = False
    print("警告: data_fetcher模块未找到，使用模拟数据")

app = Flask(__name__)

KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k")


def _moonshot_api_error_detail(response):
    """解析 Moonshot / Kimi chat 接口错误响应中的可读说明。"""
    try:
        data = response.json()
    except Exception:
        t = (response.text or "").strip()
        return t[:500] if t else ""
    err = data.get("error")
    if isinstance(err, dict):
        msg = (err.get("message") or err.get("type") or "").strip()
        return msg or json.dumps(err, ensure_ascii=False)[:500]
    if isinstance(err, str):
        return err.strip()
    return (str(data)[:500] if data else "").strip()


def _safe_request_json():
    """
    安全解析 JSON POST。避免使用 request.json 在非法 JSON 时触发 Flask HTML 400 页面，
    导致前端 res.json() 报 Unexpected token '<'。
    返回 (dict_or_none, error_message)；成功时 error 为 None。
    """
    raw = (request.get_data(cache=True, as_text=True) or "").strip()
    if not raw:
        return {}, None
    data = request.get_json(silent=True)
    if data is None:
        return None, "POST 无法解析为 JSON（正文格式错误或请求被代理改写）。"
    if not isinstance(data, dict):
        return None, "JSON 根节点必须是对象 {}"
    return data, None

STOCKS = [
    {"code": "600519", "name": "贵州茅台", "industry": "白酒", "price": 1680.50, "pe": 28.5, "pb": 9.2, "roe": 32.1, "revenue_growth": 16.5, "profit_growth": 19.2, "debt_ratio": 22.1, "market_cap": 21120, "dividend_yield": 1.8, "momentum_3m": 5.2, "momentum_6m": 12.8, "analyst_rating": 4.5, "sentiment": 0.82},
    {"code": "601318", "name": "中国平安", "industry": "保险", "price": 48.30, "pe": 8.5, "pb": 1.1, "roe": 13.2, "revenue_growth": 5.8, "profit_growth": 8.1, "debt_ratio": 85.2, "market_cap": 8820, "dividend_yield": 4.2, "momentum_3m": -2.1, "momentum_6m": 3.5, "analyst_rating": 4.2, "sentiment": 0.68},
    {"code": "000858", "name": "五粮液", "industry": "白酒", "price": 158.60, "pe": 22.3, "pb": 6.8, "roe": 28.5, "revenue_growth": 14.2, "profit_growth": 17.8, "debt_ratio": 18.5, "market_cap": 6152, "dividend_yield": 2.1, "momentum_3m": 3.8, "momentum_6m": 8.5, "analyst_rating": 4.3, "sentiment": 0.75},
    {"code": "300750", "name": "宁德时代", "industry": "新能源", "price": 218.90, "pe": 25.6, "pb": 5.2, "roe": 22.8, "revenue_growth": 22.1, "profit_growth": 26.5, "debt_ratio": 65.8, "market_cap": 9580, "dividend_yield": 0.5, "momentum_3m": 8.5, "momentum_6m": 15.2, "analyst_rating": 4.6, "sentiment": 0.85},
    {"code": "000333", "name": "美的集团", "industry": "家电", "price": 68.20, "pe": 12.8, "pb": 3.2, "roe": 24.5, "revenue_growth": 8.5, "profit_growth": 12.1, "debt_ratio": 62.5, "market_cap": 4780, "dividend_yield": 3.5, "momentum_3m": 2.1, "momentum_6m": 6.8, "analyst_rating": 4.1, "sentiment": 0.72},
    {"code": "600036", "name": "招商银行", "industry": "银行", "price": 35.80, "pe": 6.2, "pb": 0.9, "roe": 16.8, "revenue_growth": 3.2, "profit_growth": 6.5, "debt_ratio": 92.1, "market_cap": 9020, "dividend_yield": 5.1, "momentum_3m": 1.5, "momentum_6m": 4.2, "analyst_rating": 4.0, "sentiment": 0.65},
    {"code": "002594", "name": "比亚迪", "industry": "新能源汽车", "price": 285.60, "pe": 22.1, "pb": 4.8, "roe": 18.5, "revenue_growth": 35.2, "profit_growth": 42.1, "debt_ratio": 75.8, "market_cap": 8320, "dividend_yield": 0.3, "momentum_3m": 12.5, "momentum_6m": 28.5, "analyst_rating": 4.7, "sentiment": 0.88},
    {"code": "603259", "name": "药明康德", "industry": "医药", "price": 62.50, "pe": 18.5, "pb": 3.5, "roe": 15.2, "revenue_growth": 12.8, "profit_growth": 15.5, "debt_ratio": 35.2, "market_cap": 1860, "dividend_yield": 1.2, "momentum_3m": -5.2, "momentum_6m": -2.1, "analyst_rating": 3.8, "sentiment": 0.55},
    {"code": "601899", "name": "紫金矿业", "industry": "有色金属", "price": 18.20, "pe": 12.5, "pb": 3.8, "roe": 22.1, "revenue_growth": 18.5, "profit_growth": 25.2, "debt_ratio": 58.5, "market_cap": 4820, "dividend_yield": 2.8, "momentum_3m": 15.2, "momentum_6m": 32.5, "analyst_rating": 4.4, "sentiment": 0.78},
    {"code": "000001", "name": "平安银行", "industry": "银行", "price": 12.50, "pe": 5.8, "pb": 0.6, "roe": 11.2, "revenue_growth": 2.1, "profit_growth": 4.5, "debt_ratio": 93.5, "market_cap": 2420, "dividend_yield": 5.8, "momentum_3m": -1.2, "momentum_6m": 1.5, "analyst_rating": 3.5, "sentiment": 0.52},
    {"code": "600900", "name": "长江电力", "industry": "电力", "price": 28.60, "pe": 20.5, "pb": 3.5, "roe": 16.5, "revenue_growth": 5.2, "profit_growth": 8.8, "debt_ratio": 55.2, "market_cap": 6980, "dividend_yield": 3.2, "momentum_3m": 6.8, "momentum_6m": 15.8, "analyst_rating": 4.2, "sentiment": 0.72},
    {"code": "002475", "name": "立讯精密", "industry": "电子", "price": 38.50, "pe": 28.5, "pb": 5.8, "roe": 18.2, "revenue_growth": 25.5, "profit_growth": 22.8, "debt_ratio": 52.1, "market_cap": 2780, "dividend_yield": 0.8, "momentum_3m": 8.2, "momentum_6m": 18.5, "analyst_rating": 4.3, "sentiment": 0.76},
    {"code": "601688", "name": "华泰证券", "industry": "券商", "price": 18.90, "pe": 15.2, "pb": 1.2, "roe": 8.5, "revenue_growth": 12.1, "profit_growth": 18.5, "debt_ratio": 78.5, "market_cap": 1720, "dividend_yield": 2.5, "momentum_3m": 5.5, "momentum_6m": 12.2, "analyst_rating": 3.9, "sentiment": 0.68},
    {"code": "300059", "name": "东方财富", "industry": "互联网金融", "price": 16.80, "pe": 32.5, "pb": 4.2, "roe": 12.8, "revenue_growth": 15.8, "profit_growth": 12.5, "debt_ratio": 72.1, "market_cap": 2650, "dividend_yield": 0.5, "momentum_3m": 10.2, "momentum_6m": 22.5, "analyst_rating": 4.0, "sentiment": 0.72},
    {"code": "600276", "name": "恒瑞医药", "industry": "医药", "price": 42.80, "pe": 38.5, "pb": 6.2, "roe": 15.8, "revenue_growth": 8.2, "profit_growth": 12.5, "debt_ratio": 15.8, "market_cap": 2720, "dividend_yield": 0.8, "momentum_3m": -3.5, "momentum_6m": 2.8, "analyst_rating": 3.8, "sentiment": 0.58},
    {"code": "601166", "name": "兴业银行", "industry": "银行", "price": 22.50, "pe": 5.5, "pb": 0.7, "roe": 12.5, "revenue_growth": 2.8, "profit_growth": 5.2, "debt_ratio": 92.8, "market_cap": 4680, "dividend_yield": 5.5, "momentum_3m": 2.8, "momentum_6m": 8.5, "analyst_rating": 3.8, "sentiment": 0.62},
    {"code": "000568", "name": "泸州老窖", "industry": "白酒", "price": 185.20, "pe": 24.8, "pb": 8.5, "roe": 30.2, "revenue_growth": 18.5, "profit_growth": 22.1, "debt_ratio": 20.5, "market_cap": 2720, "dividend_yield": 2.5, "momentum_3m": 4.5, "momentum_6m": 10.2, "analyst_rating": 4.2, "sentiment": 0.75},
    {"code": "002415", "name": "海康威视", "industry": "安防", "price": 32.50, "pe": 18.2, "pb": 4.5, "roe": 22.5, "revenue_growth": 10.5, "profit_growth": 8.2, "debt_ratio": 38.5, "market_cap": 3050, "dividend_yield": 2.2, "momentum_3m": -2.8, "momentum_6m": 5.5, "analyst_rating": 3.9, "sentiment": 0.62},
    {"code": "600809", "name": "山西汾酒", "industry": "白酒", "price": 228.50, "pe": 35.2, "pb": 12.5, "roe": 35.8, "revenue_growth": 25.8, "profit_growth": 30.2, "debt_ratio": 28.5, "market_cap": 2780, "dividend_yield": 1.2, "momentum_3m": 6.2, "momentum_6m": 14.5, "analyst_rating": 4.5, "sentiment": 0.82},
    {"code": "601012", "name": "隆基绿能", "industry": "光伏", "price": 22.80, "pe": 12.8, "pb": 2.1, "roe": 18.5, "revenue_growth": -5.2, "profit_growth": -12.5, "debt_ratio": 55.8, "market_cap": 1720, "dividend_yield": 1.5, "momentum_3m": -8.5, "momentum_6m": -15.2, "analyst_rating": 3.5, "sentiment": 0.42},
]


def _median(values, default=0.0):
    nums = sorted([float(v) for v in values if v is not None])
    if not nums:
        return float(default)
    mid = len(nums) // 2
    if len(nums) % 2 == 1:
        return float(nums[mid])
    return float((nums[mid - 1] + nums[mid]) / 2.0)


def _build_industry_pe_roe_reference():
    """
    为智能选股构建行业 PE / ROE 参考值：
    - 优先用于实时接口未返回时的稳定兜底
    - 统一返回行业中位数，避免极端值影响
    """
    by_industry = {}
    all_pe = []
    all_roe = []
    for item in STOCKS:
        ind = str(item.get("industry", "")).strip() or "未知"
        pe = item.get("pe")
        roe = item.get("roe")
        bucket = by_industry.setdefault(ind, {"pe": [], "roe": []})
        if pe is not None:
            bucket["pe"].append(float(pe))
            all_pe.append(float(pe))
        if roe is not None:
            bucket["roe"].append(float(roe))
            all_roe.append(float(roe))

    ref = {
        "industry": {},
        "global": {
            "pe": round(_median(all_pe, default=18.0), 2),
            "roe": round(_median(all_roe, default=12.0), 2),
        },
    }
    for ind, vals in by_industry.items():
        ref["industry"][ind] = {
            "pe": round(_median(vals["pe"], default=ref["global"]["pe"]), 2),
            "roe": round(_median(vals["roe"], default=ref["global"]["roe"]), 2),
        }
    return ref


PE_ROE_REFERENCE = _build_industry_pe_roe_reference()


def _resolve_pe_roe(row, base_item, industry):
    """
    统一补全 PE / ROE：
    1) 优先实时行情字段（若存在）
    2) 其次使用基础样本值
    3) 最后使用行业中位数兜底，保证“每只股票都展示”
    """
    # 兼容可能的不同字段命名
    pe_keys = ["市盈率-动态", "市盈率", "PE", "pe"]
    pb_keys = ["市净率", "PB", "pb"]
    roe_keys = ["ROE", "roe", "净资产收益率", "ROEJQ"]

    pe_val = None
    pb_val = None
    roe_val = None

    for k in pe_keys:
        if k in row:
            pe_tmp = row.get(k)
            try:
                pe_tmp = float(str(pe_tmp).replace(",", "").strip())
                if pe_tmp > 0:
                    pe_val = pe_tmp
                    break
            except Exception:
                continue

    for k in pb_keys:
        if k in row:
            pb_tmp = row.get(k)
            try:
                pb_tmp = float(str(pb_tmp).replace(",", "").strip())
                if pb_tmp > 0:
                    pb_val = pb_tmp
                    break
            except Exception:
                continue

    for k in roe_keys:
        if k in row:
            roe_tmp = row.get(k)
            try:
                roe_tmp = float(str(roe_tmp).replace(",", "").strip().replace("%", ""))
                if abs(roe_tmp) > 0:
                    roe_val = roe_tmp
                    break
            except Exception:
                continue

    # 优先基础样本值（本地样本更稳定）
    if pe_val is None and base_item and base_item.get("pe") is not None:
        pe_val = float(base_item.get("pe"))
    if roe_val is None and base_item and base_item.get("roe") is not None:
        roe_val = float(base_item.get("roe"))

    # 若有 PE+PB，可估算 ROE（ROE ~= PB / PE）
    if roe_val is None and pe_val and pb_val and pe_val > 0:
        roe_val = (pb_val / pe_val) * 100

    # 行业兜底，确保每只都有值
    industry_key = industry if industry in PE_ROE_REFERENCE["industry"] else "未知"
    ind_ref = PE_ROE_REFERENCE["industry"].get(industry_key, {})
    global_ref = PE_ROE_REFERENCE["global"]
    if pe_val is None:
        pe_val = ind_ref.get("pe", global_ref["pe"])
    if roe_val is None:
        roe_val = ind_ref.get("roe", global_ref["roe"])

    return round(float(pe_val), 2), round(float(roe_val), 2)


RISK_QUESTIONS = [
    {
        "id": 1,
        "question": "您的年龄段是？",
        "options": [
            {"label": "60岁以上", "score": 1},
            {"label": "50-59岁", "score": 2},
            {"label": "40-49岁", "score": 3},
            {"label": "30-39岁", "score": 4},
            {"label": "18-29岁", "score": 5},
        ]
    },
    {
        "id": 2,
        "question": "您的投资经验有多长时间？",
        "options": [
            {"label": "没有任何投资经验", "score": 1},
            {"label": "少于1年", "score": 2},
            {"label": "1-3年", "score": 3},
            {"label": "3-5年", "score": 4},
            {"label": "5年以上", "score": 5},
        ]
    },
    {
        "id": 3,
        "question": "您的主要收入来源是？",
        "options": [
            {"label": "退休金/社会福利", "score": 1},
            {"label": "固定工资", "score": 2},
            {"label": "工资+奖金", "score": 3},
            {"label": "经营性收入", "score": 4},
            {"label": "投资收益为主", "score": 5},
        ]
    },
    {
        "id": 4,
        "question": "您计划的投资期限是？",
        "options": [
            {"label": "1年以内", "score": 1},
            {"label": "1-3年", "score": 2},
            {"label": "3-5年", "score": 3},
            {"label": "5-10年", "score": 4},
            {"label": "10年以上", "score": 5},
        ]
    },
    {
        "id": 5,
        "question": "您可以接受的最大投资亏损比例是？",
        "options": [
            {"label": "不能接受任何亏损", "score": 1},
            {"label": "5%以内", "score": 2},
            {"label": "10%-20%", "score": 3},
            {"label": "20%-40%", "score": 4},
            {"label": "40%以上也能接受", "score": 5},
        ]
    },
    {
        "id": 6,
        "question": "当您的投资出现10%亏损时，您会？",
        "options": [
            {"label": "立即全部卖出止损", "score": 1},
            {"label": "卖出大部分，保留小部分观望", "score": 2},
            {"label": "持有不动，等待回本", "score": 3},
            {"label": "适当加仓摊低成本", "score": 4},
            {"label": "大幅加仓，逆势抄底", "score": 5},
        ]
    },
    {
        "id": 7,
        "question": "您投资的主要目的是？",
        "options": [
            {"label": "资产保值，跑赢通胀即可", "score": 1},
            {"label": "获取稳定收益，如固定利息", "score": 2},
            {"label": "兼顾收益与风险的平衡", "score": 3},
            {"label": "追求较高收益，可以承受波动", "score": 4},
            {"label": "追求最大化收益，不惧高风险", "score": 5},
        ]
    },
    {
        "id": 8,
        "question": "您可用于投资的资金占家庭总资产比例？",
        "options": [
            {"label": "10%以下", "score": 1},
            {"label": "10%-30%", "score": 2},
            {"label": "30%-50%", "score": 3},
            {"label": "50%-70%", "score": 4},
            {"label": "70%以上", "score": 5},
        ]
    },
    {
        "id": 9,
        "question": "您对以下哪类投资品种最为熟悉？",
        "options": [
            {"label": "银行存款/国债", "score": 1},
            {"label": "银行理财/货币基金", "score": 2},
            {"label": "债券基金/混合基金", "score": 3},
            {"label": "股票/股票基金", "score": 4},
            {"label": "期货/期权/衍生品", "score": 5},
        ]
    },
    {
        "id": 10,
        "question": "以下两种投资方案，您更偏向哪个？",
        "options": [
            {"label": "稳赚2%的年化收益", "score": 1},
            {"label": "90%概率赚5%，10%概率亏2%", "score": 2},
            {"label": "70%概率赚15%，30%概率亏8%", "score": 3},
            {"label": "50%概率赚30%，50%概率亏15%", "score": 4},
            {"label": "30%概率赚80%，70%概率亏30%", "score": 5},
        ]
    },
]

ALLOCATION_PROFILES = {
    "保守型": {
        "label": "保守型",
        "description": "您属于保守型投资者，追求资产安全与稳定收益，建议以固定收益类资产为主。",
        "color": "#3b82f6",
        "allocation": [
            {"name": "货币基金", "value": 20, "color": "#60a5fa"},
            {"name": "债券基金", "value": 50, "color": "#3b82f6"},
            {"name": "混合基金", "value": 15, "color": "#818cf8"},
            {"name": "股票基金", "value": 10, "color": "#f59e0b"},
            {"name": "另类投资", "value": 5, "color": "#8b5cf6"},
        ],
        "expected_return": "3%-5%",
        "max_drawdown": "3%",
        "volatility": "低",
        "sharpe": 1.2,
    },
    "稳健型": {
        "label": "稳健型",
        "description": "您属于稳健型投资者，在追求稳定的同时兼顾一定收益，建议债券为主、权益为辅。",
        "color": "#10b981",
        "allocation": [
            {"name": "货币基金", "value": 15, "color": "#60a5fa"},
            {"name": "债券基金", "value": 40, "color": "#3b82f6"},
            {"name": "混合基金", "value": 20, "color": "#818cf8"},
            {"name": "股票基金", "value": 18, "color": "#f59e0b"},
            {"name": "另类投资", "value": 7, "color": "#8b5cf6"},
        ],
        "expected_return": "5%-8%",
        "max_drawdown": "8%",
        "volatility": "中低",
        "sharpe": 1.5,
    },
    "平衡型": {
        "label": "平衡型",
        "description": "您属于平衡型投资者，能够在风险与收益之间寻求平衡，建议均衡配置各类资产。",
        "color": "#f59e0b",
        "allocation": [
            {"name": "货币基金", "value": 10, "color": "#60a5fa"},
            {"name": "债券基金", "value": 25, "color": "#3b82f6"},
            {"name": "混合基金", "value": 25, "color": "#818cf8"},
            {"name": "股票基金", "value": 30, "color": "#f59e0b"},
            {"name": "另类投资", "value": 10, "color": "#8b5cf6"},
        ],
        "expected_return": "8%-12%",
        "max_drawdown": "15%",
        "volatility": "中",
        "sharpe": 1.3,
    },
    "进取型": {
        "label": "进取型",
        "description": "您属于进取型投资者，愿意承受较大波动以追求更高收益，建议以权益类资产为主。",
        "color": "#f97316",
        "allocation": [
            {"name": "货币基金", "value": 5, "color": "#60a5fa"},
            {"name": "债券基金", "value": 15, "color": "#3b82f6"},
            {"name": "混合基金", "value": 20, "color": "#818cf8"},
            {"name": "股票基金", "value": 45, "color": "#f59e0b"},
            {"name": "另类投资", "value": 15, "color": "#8b5cf6"},
        ],
        "expected_return": "12%-18%",
        "max_drawdown": "25%",
        "volatility": "中高",
        "sharpe": 1.1,
    },
    "激进型": {
        "label": "激进型",
        "description": "您属于激进型投资者，追求收益最大化，能够承受较大幅度的资产波动。",
        "color": "#ef4444",
        "allocation": [
            {"name": "货币基金", "value": 3, "color": "#60a5fa"},
            {"name": "债券基金", "value": 7, "color": "#3b82f6"},
            {"name": "混合基金", "value": 15, "color": "#818cf8"},
            {"name": "股票基金", "value": 55, "color": "#f59e0b"},
            {"name": "另类投资", "value": 20, "color": "#8b5cf6"},
        ],
        "expected_return": "18%-30%",
        "max_drawdown": "40%",
        "volatility": "高",
        "sharpe": 0.9,
    },
}

CHAT_RESPONSES = {
    "market": [
        "根据AI模型分析，当前A股市场整体估值处于历史中位数偏下水平，具有一定的安全边际。建议关注以下几个方向：\n\n1. **新能源板块**：受政策驱动和全球能源转型推动，宁德时代、比亚迪等龙头仍具长期价值\n2. **消费复苏**：白酒、家电等消费板块估值回归合理区间，可逢低布局\n3. **高股息策略**：银行、电力等高分红板块在低利率环境下配置价值凸显\n\n⚠️ 风险提示：以上为AI模型分析结果，仅供参考，不构成投资建议。",
    ],
    "stock": [
        "基于多因子选股模型，为您推荐以下关注标的：\n\n🔹 **贵州茅台(600519)** - 综合评分92分\n- 价值因子：PE 28.5倍，处于历史中位数\n- 质量因子：ROE 32.1%，盈利能力卓越\n- 成长因子：净利润增速19.2%，稳健增长\n\n🔹 **比亚迪(002594)** - 综合评分88分\n- 成长因子：营收增速35.2%，高速成长\n- 动量因子：6个月涨幅28.5%，趋势强劲\n- 情绪因子：分析师一致看好，市场情绪积极\n\n⚠️ 以上为AI模型筛选结果，投资需结合个人风险承受能力。",
    ],
    "allocation": [
        "关于资产配置，我的建议基于现代投资组合理论(MPT)：\n\n📊 **核心原则**：\n1. **分散化投资**：不要把鸡蛋放在一个篮子里，跨资产类别、跨行业配置\n2. **风险匹配**：配置比例应与您的风险承受能力相匹配\n3. **定期再平衡**：每季度检视组合，偏离目标配置超过5%时进行调整\n\n💡 **当前市场环境下的建议**：\n- 适当增配高股息策略（银行、电力）作为防御性配置\n- 保持一定比例的成长股仓位（新能源、科技）\n- 债券配置以短久期为主，降低利率风险\n\n您可以先完成「风险测评」，我会为您生成个性化的配置方案。",
    ],
    "risk": [
        "关于投资风险管理，这里有几个重要原则：\n\n🛡️ **风险管理三要素**：\n1. **事前控制**：设定投资纪律，明确止损线和目标收益\n2. **事中监控**：利用AI实时监控组合风险指标，如波动率、最大回撤、VaR值\n3. **事后复盘**：定期回顾投资决策，总结经验教训\n\n📏 **关键风险指标**：\n- **夏普比率**：衡量风险调整后收益，>1为良好，>2为优秀\n- **最大回撤**：历史最大亏损幅度，直观反映极端风险\n- **波动率**：收益率的标准差，反映价格波动程度\n- **VaR(在险价值)**：在一定置信水平下的最大可能亏损\n\n建议您根据自身情况，设置合理的风险预警线。",
    ],
    "education": [
        "很高兴您关注投资知识学习！以下是一些核心概念：\n\n📚 **基础概念**：\n- **PE (市盈率)**：股价÷每股收益，反映市场对公司盈利的估值\n- **PB (市净率)**：股价÷每股净资产，反映市场对公司资产的估值\n- **ROE (净资产收益率)**：净利润÷净资产，衡量公司盈利能力\n\n🎯 **投资策略**：\n- **价值投资**：寻找市场低估的优质公司，长期持有\n- **成长投资**：投资高增长公司，分享企业成长红利\n- **指数投资**：通过ETF投资指数，获取市场平均收益\n\n💡 **AI在投资中的应用**：\n- 多因子选股模型\n- 自然语言处理分析研报和新闻\n- 量化交易策略\n- 智能风控系统\n\n有任何问题，随时问我！",
    ],
    "default": [
        "您好！我是您的AI投顾助手，可以为您提供以下服务：\n\n🔹 **市场分析** - 输入「市场」了解当前市场观点\n🔹 **选股建议** - 输入「选股」获取AI选股推荐\n🔹 **资产配置** - 输入「配置」了解资产配置建议\n🔹 **风险管理** - 输入「风险」学习风控知识\n🔹 **投资教育** - 输入「学习」获取投资知识\n\n您也可以直接提问任何投资相关问题，我会尽力为您解答。\n\n⚠️ 温馨提示：AI投顾仅提供参考建议，不构成投资决策依据。投资有风险，入市需谨慎。",
    ],
}

NEWS_DATA = [
    {"title": "央行宣布降准0.5个百分点，释放长期资金约1万亿元", "source": "新华社", "time": "2小时前", "sentiment": "positive", "impact": "利好银行、地产板块"},
    {"title": "新能源汽车1-2月销量同比增长38.2%，渗透率突破40%", "source": "中汽协", "time": "3小时前", "sentiment": "positive", "impact": "利好新能源产业链"},
    {"title": "多家白酒企业发布提价公告，行业景气度持续回升", "source": "证券时报", "time": "5小时前", "sentiment": "positive", "impact": "利好白酒板块"},
    {"title": "美联储暗示年内降息预期增强，全球市场情绪回暖", "source": "路透社", "time": "6小时前", "sentiment": "positive", "impact": "利好全球权益资产"},
    {"title": "某光伏龙头企业发布业绩预警，产能过剩压力加大", "source": "财联社", "time": "8小时前", "sentiment": "negative", "impact": "利空光伏板块"},
    {"title": "AI大模型应用加速落地，科技板块获资金持续流入", "source": "第一财经", "time": "10小时前", "sentiment": "positive", "impact": "利好科技板块"},
]

FUND_SEARCH_POOL = [
    {"code": "000001", "name": "华夏成长混合", "category": "混合型"},
    {"code": "000011", "name": "华夏大盘精选混合", "category": "混合型"},
    {"code": "000013", "name": "易方达科翔混合", "category": "混合型"},
    {"code": "001714", "name": "工银瑞信文体产业股票", "category": "股票型"},
    {"code": "002190", "name": "农银新能源主题混合", "category": "混合型"},
    {"code": "003095", "name": "中欧医疗健康混合A", "category": "混合型"},
    {"code": "004851", "name": "广发医疗保健股票A", "category": "股票型"},
    {"code": "005827", "name": "易方达蓝筹精选混合", "category": "混合型"},
    {"code": "006113", "name": "汇添富创新医药混合", "category": "混合型"},
    {"code": "008888", "name": "华夏中证5G通信主题ETF联接A", "category": "ETF联接"},
    {"code": "009865", "name": "招商中证白酒指数A", "category": "指数型"},
    {"code": "010363", "name": "易方达竞争优势企业混合A", "category": "混合型"},
    {"code": "012348", "name": "富国中证新能源汽车指数A", "category": "指数型"},
    {"code": "015790", "name": "华夏上证50ETF联接A", "category": "ETF联接"},
    {"code": "017810", "name": "东方人工智能主题混合A", "category": "混合型"},
    {"code": "017811", "name": "东方人工智能主题混合C", "category": "混合型"},
    {"code": "110011", "name": "易方达中小盘混合", "category": "混合型"},
    {"code": "161725", "name": "招商中证白酒指数(LOF)", "category": "LOF"},
    {"code": "161903", "name": "万家行业优选混合(LOF)", "category": "LOF"},
    {"code": "162605", "name": "景顺长城鼎益混合(LOF)", "category": "LOF"},
    {"code": "159915", "name": "创业板ETF", "category": "ETF"},
    {"code": "510300", "name": "沪深300ETF", "category": "ETF"},
]

FUND_SEARCH_CACHE = {
    "loaded_at": None,
    "items": [],
    "loading": False,
    "failed_at": None,
}
FUND_SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".fund_search_cache.json")
STOCK_SEARCH_CACHE = {
    "loaded_at": None,
    "items": [],
}
STOCK_SCREEN_RESULT_CACHE = {
    "loaded_at": None,
    "items": [],
}
REALTIME_NEWS_CACHE = {
    "loaded_at": None,
    "items": [],
}
FUND_RANK_CACHE = {
    "loaded_at": None,
    "items": [],
}

OCR_TEXT_ALIASES = {
    "新易盛": ["新易盛", "300502"],
    "宁德时代": ["宁德时代", "300750"],
    "贵州茅台": ["贵州茅台", "600519"],
    "比亚迪": ["比亚迪", "002594"],
    "中国平安": ["中国平安", "601318"],
    "沪深300ETF": ["沪深300ETF", "510300"],
    "创业板ETF": ["创业板ETF", "159915"],
    "招商中证白酒指数(LOF)": ["招商中证白酒", "161725"],
}


def _call_with_timeout(fn, timeout_sec=8):
    """
    执行可能阻塞的函数并设置超时。
    超时后立即返回 None，不等待底层任务结束。
    """
    state = {"done": False, "value": None}

    def runner():
        try:
            state["value"] = fn()
        except Exception:
            state["value"] = None
        finally:
            state["done"] = True

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        return None
    return state["value"]


def _load_fund_search_cache_from_disk():
    try:
        if not os.path.exists(FUND_SEARCH_CACHE_FILE):
            return []
        with open(FUND_SEARCH_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return []
        clean_items = []
        for x in items:
            code = str((x or {}).get("code", "")).strip()
            name = str((x or {}).get("name", "")).strip()
            if not code or not name:
                continue
            clean_items.append({
                "code": code,
                "name": name,
                "category": str((x or {}).get("category", "基金")).strip() or "基金",
                "pinyin_short": str((x or {}).get("pinyin_short", "")).strip(),
                "pinyin_full": str((x or {}).get("pinyin_full", "")).strip(),
            })
        return clean_items
    except Exception:
        return []


def _save_fund_search_cache_to_disk(items):
    try:
        with open(FUND_SEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "saved_at": datetime.now().isoformat(),
                    "items": items,
                },
                f,
                ensure_ascii=False,
            )
    except Exception:
        pass


def _fund_name_em_df_to_items(df):
    """东财 fund_name_em 转与 /api/fund-search 一致的条目列表。"""
    items = []
    if df is None or df.empty:
        return items
    for _, row in df.iterrows():
        code = str(row.get("基金代码", "")).strip()
        name = str(row.get("基金简称", "")).strip()
        category = str(row.get("基金类型", "")).strip()
        pinyin_short = str(row.get("拼音缩写", "")).strip()
        pinyin_full = str(row.get("拼音全称", "")).strip()
        if not code or not name:
            continue
        items.append({
            "code": code,
            "name": name,
            "category": category or "基金",
            "pinyin_short": pinyin_short,
            "pinyin_full": pinyin_full,
        })
    return items


def _ensure_fund_search_pool_sync_for_ocr(min_items=200, timeout_sec=28):
    """
    截图 OCR 解析前尽量载入与「手动添加基金」相同的数据源（AkShare fund_name_em 官方代码）。
    冷启动时若仅命中内置小样例池，名称无法对齐会误生成 P+hash 占位码（非真实基金代码）。
    """
    pool = FUND_SEARCH_CACHE.get("items") or []
    if len(pool) >= min_items:
        return pool
    disk = _load_fund_search_cache_from_disk()
    if disk and len(disk) >= min_items:
        FUND_SEARCH_CACHE["items"] = disk
        FUND_SEARCH_CACHE["loaded_at"] = datetime.now()
        FUND_SEARCH_CACHE["failed_at"] = None
        return disk
    try:
        df = _call_with_timeout(ak.fund_name_em, timeout_sec=timeout_sec)
        items = _fund_name_em_df_to_items(df)
        if items:
            FUND_SEARCH_CACHE["loaded_at"] = datetime.now()
            FUND_SEARCH_CACHE["items"] = items
            FUND_SEARCH_CACHE["failed_at"] = None
            _save_fund_search_cache_to_disk(items)
            return items
    except Exception:
        pass
    return _get_fund_search_pool()


def _ocr_text_looks_like_fund(text):
    """避免把股票类 OCR 行误套到基金宽松匹配上。"""
    t = (text or "").lower()
    keys = (
        "基金", "联接", "etf", "lof", "混合", "债券", "货币", "指数", "qdii",
        "中证", "上证", "深证", "创业板", "科创板", "msci", "fof",
    )
    return any(k in t for k in keys)


def _ocr_line_strip_numbers_for_name_match(line):
    """
    行级 OCR 常把金额/收益与名称写在同一行；数字参与模糊匹配会误命中短关键词（如 etf）。
    去掉数值片段后再做名称解析，与手动搜索「只输入基金名」一致。
    """
    s = re.sub(r"-?\d+(?:\.\d+)?%?", " ", str(line or ""))
    return s.strip()


def _ocr_loose_fund_match(name_str, fund_pool):
    """
    OCR 名称与官方简称不完全一致时，用多长度子串命中打分，在全量基金池里选最优。
    """
    ln = _normalize_asset_name_for_ocr(name_str)
    if len(ln) < 2 or not fund_pool:
        return "", ""
    grams = []
    max_n = min(5, len(ln))
    for n in range(max_n, 1, -1):
        for i in range(0, len(ln) - n + 1):
            grams.append(ln[i : i + n])
    seen = set()
    grams_u = []
    for g in grams:
        if g not in seen:
            seen.add(g)
            grams_u.append(g)
    head = ln[:2]
    narrowed = [f for f in fund_pool if head in (f.get("name") or "")]
    scan = narrowed if len(narrowed) >= 8 else fund_pool
    wants_link = "联接" in ln

    def _score_scan(require_link):
        bc, bn, bs = "", "", -1.0
        for f in scan:
            fname = str(f.get("name", "") or "")
            fn = _normalize_asset_name_for_ocr(fname)
            if len(fn) < 3:
                continue
            if require_link and "联接" not in fn:
                continue
            score = 0.0
            for g in grams_u:
                lg = len(g)
                if lg < 2:
                    continue
                if g in fn:
                    score += float(lg * lg)
            if require_link and "联接" in fn:
                score += 25.0
            if score > bs:
                bs, bc, bn = score, str(f.get("code", "") or "").strip(), fname
        return bc, bn, bs

    best_code, best_name, best_s = _score_scan(wants_link)
    if best_s < 14.0 and wants_link:
        best_code, best_name, best_s = _score_scan(False)
    if best_s >= 14.0 and best_code:
        return best_code, best_name
    return "", ""


def _refresh_fund_search_cache_async():
    """
    异步刷新基金全量搜索池：
    - 避免请求线程阻塞
    - 成功后更新缓存，失败则记录失败时间用于短期退避
    """
    if FUND_SEARCH_CACHE.get("loading"):
        return

    def runner():
        FUND_SEARCH_CACHE["loading"] = True
        try:
            df = _call_with_timeout(ak.fund_name_em, timeout_sec=25)
            items = _fund_name_em_df_to_items(df)
            if items:
                FUND_SEARCH_CACHE["loaded_at"] = datetime.now()
                FUND_SEARCH_CACHE["items"] = items
                FUND_SEARCH_CACHE["failed_at"] = None
                _save_fund_search_cache_to_disk(items)
            else:
                FUND_SEARCH_CACHE["failed_at"] = datetime.now()
        except Exception:
            FUND_SEARCH_CACHE["failed_at"] = datetime.now()
        finally:
            FUND_SEARCH_CACHE["loading"] = False

    threading.Thread(target=runner, daemon=True).start()


def _get_fund_search_pool():
    """
    基金搜索池：
    1) 优先 AkShare 全量基金清单（fund_name_em）
    2) 失败时回退内置样例池，确保功能可用
    """
    now = datetime.now()
    loaded_at = FUND_SEARCH_CACHE.get("loaded_at")
    cached_items = FUND_SEARCH_CACHE.get("items") or []
    failed_at = FUND_SEARCH_CACHE.get("failed_at")
    # 缓存30分钟，降低接口压力
    if loaded_at and cached_items and (now - loaded_at) < timedelta(minutes=30):
        return cached_items
    # 即便缓存过期，仍优先使用已有缓存，后台异步刷新
    if cached_items:
        if not failed_at or (now - failed_at) > timedelta(minutes=2):
            _refresh_fund_search_cache_async()
        return cached_items

    # 进程冷启动优先读取磁盘缓存（上次成功结果）
    disk_items = _load_fund_search_cache_from_disk()
    if disk_items:
        FUND_SEARCH_CACHE["loaded_at"] = now
        FUND_SEARCH_CACHE["items"] = disk_items
        if not failed_at or (now - failed_at) > timedelta(minutes=2):
            _refresh_fund_search_cache_async()
        return disk_items

    # 异步预热：不阻塞当前请求
    # 失败后 2 分钟内不重复发起，避免持续抖动
    if not failed_at or (now - failed_at) > timedelta(minutes=2):
        _refresh_fund_search_cache_async()

    # 回退
    return FUND_SEARCH_POOL


def _get_stock_search_pool():
    """
    股票搜索池：
    1) 优先 AkShare A股代码名称全量清单（stock_info_a_code_name）
    2) 再尝试 AkShare 全市场快照（stock_zh_a_spot）
    3) 失败时回退内置 STOCKS，确保功能可用
    """
    now = datetime.now()
    loaded_at = STOCK_SEARCH_CACHE.get("loaded_at")
    cached_items = STOCK_SEARCH_CACHE.get("items") or []
    if loaded_at and cached_items and (now - loaded_at) < timedelta(minutes=10):
        return cached_items

    # 1) A股全量代码名称清单（覆盖最全）
    try:
        df = _call_with_timeout(ak.stock_info_a_code_name, timeout_sec=5)
        items = []
        if df is not None and not df.empty:
            code_col = (
                "code" if "code" in df.columns else
                ("证券代码" if "证券代码" in df.columns else
                 ("代码" if "代码" in df.columns else ""))
            )
            name_col = (
                "name" if "name" in df.columns else
                ("证券简称" if "证券简称" in df.columns else
                 ("名称" if "名称" in df.columns else ""))
            )
            if code_col and name_col:
                for _, row in df.iterrows():
                    code = str(row.get(code_col, "")).strip()
                    name = str(row.get(name_col, "")).strip()
                    if not code or not name:
                        continue
                    items.append({
                        "code": code,
                        "name": name,
                        "category": "股票",
                    })
        if items:
            STOCK_SEARCH_CACHE["loaded_at"] = now
            STOCK_SEARCH_CACHE["items"] = items
            return items
    except Exception:
        pass

    # 2) 快照接口（字段更丰富，但个别环境可能失败）
    try:
        df = _call_with_timeout(ak.stock_zh_a_spot, timeout_sec=5)
        items = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                raw_code = str(row.get("代码", "")).strip()
                name = str(row.get("名称", "")).strip()
                if not raw_code or not name:
                    continue
                code = raw_code[2:] if raw_code.startswith(("sh", "sz", "bj")) else raw_code
                if not code:
                    continue
                items.append({
                    "code": code,
                    "name": name,
                    "category": "股票",
                })
        if items:
            STOCK_SEARCH_CACHE["loaded_at"] = now
            STOCK_SEARCH_CACHE["items"] = items
            return items
    except Exception:
        pass

    return [
        {"code": s["code"], "name": s["name"], "category": "股票"}
        for s in STOCKS
    ]


def _extract_amount_and_profit(line):
    """
    适配截图字段:
    - 基金名称
    - 金额/昨日收益
    - 持有收益/率
    优先读取两个“x/y”字段中的前半部分:
      amount = (金额/昨日收益) 的金额
      profit = (持有收益/率) 的持有收益
    """
    clean = line.replace(",", "").replace("，", "").replace("：", ":")

    # 提取带斜杠的数字对，例如 12345.67/12.34  或 -230.00/1.25%
    pair_matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?%?)", clean)
    if len(pair_matches) >= 2:
        try:
            amount = float(pair_matches[0][0])
            profit = float(pair_matches[1][0])
            return amount, profit
        except Exception:
            pass

    # 弱匹配：存在“金额”与“持有收益”关键词
    amount_m = re.search(r"(?:金额|持有金额|持仓金额|市值)\s*[: ]?\s*(-?\d+(?:\.\d+)?)", clean)
    profit_m = re.search(r"(?:持有收益|累计收益|浮动盈亏|收益)\s*[: ]?\s*(-?\d+(?:\.\d+)?)", clean)
    if amount_m and profit_m:
        try:
            return float(amount_m.group(1)), float(profit_m.group(1))
        except Exception:
            pass

    # 最后兜底：取前两个数
    nums = re.findall(r"-?\d+(?:\.\d+)?", clean)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return None, None


def _normalize_asset_name_for_ocr(text):
    """
    OCR 名称归一化：
    - 小写
    - 去除空格/标点
    - 仅保留中文、字母、数字
    """
    if not text:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[\s\-\._·•:：,，;；\(\)\[\]（）【】]+", "", s)
    s = re.sub(r"[^0-9a-z\u4e00-\u9fa5]+", "", s)
    return s


def _build_name_variants(name, asset_type):
    """
    构造名称变体，提升 OCR 错字/漏字下的命中概率。
    """
    raw = str(name or "").strip()
    if not raw:
        return set()

    variants = set()
    norm = _normalize_asset_name_for_ocr(raw)
    if norm:
        variants.add(norm)

    # 去除括号内容，例如 "(LOF)"、"（ETF）"
    no_bracket = re.sub(r"\(.*?\)|（.*?）|\[.*?\]|【.*?】", "", raw).strip()
    norm_no_bracket = _normalize_asset_name_for_ocr(no_bracket)
    if norm_no_bracket:
        variants.add(norm_no_bracket)

    # 基金常见后缀弱化：A/C/E 等份额尾缀；若去掉后仍有足够长度则加入
    tail_stripped = re.sub(r"[a-zA-Z]$", "", norm_no_bracket or norm)
    if tail_stripped and len(tail_stripped) >= 3:
        variants.add(tail_stripped)

    # 行业词后缀弱化，适配 OCR 截断（如“招商中证白酒指数A” -> “招商中证白酒”）
    if asset_type == "基金":
        core = norm_no_bracket or norm
        core = re.sub(r"(基金|混合|股票|指数|联接|lof|etf)+$", "", core)
        if core and len(core) >= 3:
            variants.add(core)

    return {v for v in variants if v}


def _build_name_candidates(asset_pool, asset_type):
    candidates = []
    for x in asset_pool:
        code = str(x.get("code", "")).strip()
        name = str(x.get("name", "")).strip()
        if not code or not name:
            continue
        variants = _build_name_variants(name, asset_type)
        if not variants:
            continue
        candidates.append({
            "code": code,
            "name": name,
            "variants": variants,
        })
    return candidates


def _fuzzy_match_asset_by_name(line, candidates):
    """
    在候选集中做名称模糊匹配，返回最佳候选 (code, name) 或 ("","")。
    规则：
    - 优先完整名称命中
    - 其次变体命中，按命中长度评分，避免短词误匹配
    """
    line_norm = _normalize_asset_name_for_ocr(line)
    if not line_norm:
        return "", ""

    best = ("", "", 0)  # code, name, score
    for item in candidates:
        code = item["code"]
        name = item["name"]
        name_norm = _normalize_asset_name_for_ocr(name)
        if name_norm and name_norm in line_norm:
            score = 1000 + len(name_norm)
            if score > best[2]:
                best = (code, name, score)
            continue

        for v in item["variants"]:
            if len(v) < 3:
                continue
            if v in line_norm:
                score = len(v)
                if score > best[2]:
                    best = (code, name, score)

    return best[0], best[1]


def _resolve_asset_by_name_or_code(line, code, stock_map, fund_map, stock_candidates=None, fund_candidates=None):
    """
    优先按代码匹配；若无代码则按名称匹配（基金优先）
    """
    if code:
        if code in stock_map:
            return code, stock_map[code], "股票"
        if code in fund_map:
            return code, fund_map[code], "基金"

    # 名称匹配：基金优先（用户给的截图格式以基金为主）
    for f_code, f_name in fund_map.items():
        if f_name and f_name in line:
            return f_code, f_name, "基金"
    for s_code, s_name in stock_map.items():
        if s_name and s_name in line:
            return s_code, s_name, "股票"

    # 名称模糊匹配：基金优先
    if fund_candidates:
        c, n = _fuzzy_match_asset_by_name(line, fund_candidates)
        if c and n:
            return c, n, "基金"
    if stock_candidates:
        c, n = _fuzzy_match_asset_by_name(line, stock_candidates)
        if c and n:
            return c, n, "股票"

    # 别名兜底
    for n, aliases in OCR_TEXT_ALIASES.items():
        if any(a in line for a in aliases):
            for c, nn in fund_map.items():
                if nn == n:
                    return c, n, "基金"
            for c, nn in stock_map.items():
                if nn == n:
                    return c, n, "股票"
    return "", "", "基金"


def _ocr_parse_holdings_text(text):
    lines = [ln.strip() for ln in text.splitlines() if ln and ln.strip()]
    parsed = []
    stock_pool = _get_stock_search_pool()
    fund_pool = _ensure_fund_search_pool_sync_for_ocr()
    stock_map = {x["code"]: x["name"] for x in stock_pool if x.get("code") and x.get("name")}
    fund_map = {x["code"]: x["name"] for x in fund_pool if x.get("code") and x.get("name")}
    stock_candidates = _build_name_candidates(stock_pool, "股票")
    fund_candidates = _build_name_candidates(fund_pool, "基金")

    def parse_float_val(s):
        try:
            return float(s.replace(',', '').replace('%', '').replace('+', ''))
        except ValueError:
            return None

    def is_amount_val(s):
        f = parse_float_val(s)
        return f is not None and f > 0 and '%' not in s and not s.startswith('+') and not s.startswith('-')

    def is_profit_val(s):
        if '%' in s: return False
        f = parse_float_val(s)
        return f is not None and (s.startswith('+') or s.startswith('-') or f == 0)

    # 1. Block-based parsing (for vertical layout from RapidOCR)
    i = 0
    used_lines = set()
    while i < len(lines):
        line = lines[i].strip()
        if is_amount_val(line):
            if i + 1 < len(lines) and is_profit_val(lines[i+1]):
                amount = parse_float_val(line)
                profit = parse_float_val(lines[i+1])
                
                name_str = ""
                if i - 1 >= 0:
                    name_part1 = lines[i-1].strip()
                    if parse_float_val(name_part1) is None:
                        name_str = name_part1
                
                idx = i + 2
                if idx < len(lines):
                    next_line = lines[idx].strip()
                    if parse_float_val(next_line) is None:
                        name_str += next_line
                        idx += 1
                
                if name_str:
                    name_for_match = _ocr_line_strip_numbers_for_name_match(name_str) or name_str
                    code, resolved_name, asset_type = _resolve_asset_by_name_or_code(
                        name_for_match,
                        "",
                        stock_map,
                        fund_map,
                        stock_candidates=stock_candidates,
                        fund_candidates=fund_candidates,
                    )
                    
                    if not code and _ocr_text_looks_like_fund(name_str):
                        c2, n2 = _ocr_loose_fund_match(name_for_match, fund_pool)
                        if c2:
                            code, resolved_name, asset_type = c2, n2, "基金"
                    if not code:
                        for j in (i - 1, i, i + 1, i + 2):
                            if j >= 0:
                                used_lines.add(j)
                        if idx > i + 2:
                            used_lines.add(idx - 1)
                        i = idx - 1
                        i += 1
                        continue

                    used_lines.update([i-1, i, i+1, i+2])
                    current_value = amount
                    cost_value = amount - profit
                    shares = cost_value if cost_value > 0 else amount
                    cost_price = 1.0
                    current_price = current_value / shares if shares > 0 else 1.0
                    unit = "股" if asset_type == "股票" else "份"
                    parsed.append({
                        "code": code,
                        "name": resolved_name or name_str,
                        "asset_type": asset_type,
                        "shares": float(shares),
                        "unit": unit,
                        "cost": float(cost_price),
                        "current": float(current_price),
                        "amount": float(amount),
                        "profit": float(profit),
                        "input_amount": float(amount),
                        "input_profit": float(profit),
                        "needs_share_calc": True
                    })
                i = idx - 1
        i += 1

    # 2. Line-based parsing (fallback for single-line text formats)
    for i, line in enumerate(lines):
        if i in used_lines:
            continue
        code_match = re.search(r"\b(\d{6})\b", line)
        code = code_match.group(1) if code_match else ""
        amount, profit = _extract_amount_and_profit(line)
        if amount is None or profit is None:
            continue
        if amount <= 0 or (amount + profit) <= 0:
            continue

        name_only_line = _ocr_line_strip_numbers_for_name_match(line)
        code, name, asset_type = _resolve_asset_by_name_or_code(
            name_only_line,
            code,
            stock_map,
            fund_map,
            stock_candidates=stock_candidates,
            fund_candidates=fund_candidates,
        )

        if not code and _ocr_text_looks_like_fund(line):
            c2, n2 = _ocr_loose_fund_match(name_only_line or line, fund_pool)
            if c2:
                code, name, asset_type = c2, n2, "基金"
        if not code:
            continue

        if not name:
            name = stock_map.get(code) or fund_map.get(code) or f"资产{code}"

        current_value = amount
        cost_value = amount - profit
        shares = cost_value if cost_value > 0 else amount
        cost_price = 1.0
        current_price = current_value / shares if shares > 0 else 1.0
        unit = "股" if asset_type == "股票" else "份"
        parsed.append({
            "code": code,
            "name": name,
            "asset_type": asset_type,
            "shares": float(shares),
            "unit": unit,
            "cost": float(cost_price),
            "current": float(current_price),
            "amount": float(amount),
            "profit": float(profit),
            "input_amount": float(amount),
            "input_profit": float(profit),
            "needs_share_calc": True
        })

    dedup = []
    seen = set()
    for x in parsed:
        key = (x["asset_type"], x["code"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(x)
    return dedup


def generate_kline_data(days=120):
    """生成模拟K线数据（仅用于组合历史曲线等，不再用于市场概览造数）"""
    data = []
    base_price = 3200
    for i in range(days):
        date = (datetime.now() - timedelta(days=days - i)).strftime("%m-%d")
        change = random.gauss(0.0005, 0.015)
        base_price *= (1 + change)
        open_p = base_price * (1 + random.uniform(-0.005, 0.005))
        close_p = base_price
        high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.01))
        low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.01))
        volume = random.randint(2000, 5000)
        data.append({
            "date": date,
            "open": round(open_p, 2),
            "close": round(close_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "volume": volume,
        })
    return data


def _format_index_date(val):
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    return s[:10] if len(s) >= 10 else s


def _fetch_hs300_normalized_series(days=180):
    """
    拉取沪深300（sh000300）最近若干交易日收盘价，归一化为以首日为 1.0 的净值曲线。
    失败返回 None。
    """
    try:
        df = ak.stock_zh_index_daily(symbol="sh000300")
        if df is None or df.empty or len(df) < 2:
            return None
        tail = df.tail(int(days))
        if tail.empty:
            return None
        closes = tail["close"].astype(float)
        first = float(closes.iloc[0])
        if first <= 0:
            return None
        out = []
        for _, row in tail.iterrows():
            d = _format_index_date(row.get("date"))
            close_p = float(row["close"])
            out.append({
                "date": d,
                "benchmark": round(close_p / first, 4),
            })
        return out
    except Exception:
        return None


def generate_portfolio_history(holdings=None, days=None):
    """
    根据用户真实持仓生成收益率曲线：
    - 若传入了 days，则强制使用最近 days 天作为起始
    - 否则：起始日期 = 所有持仓中最早的 created_at（买入日期）
    - 组合净值 = 按各标的持仓金额加权，用真实 HS300 日收益率 × beta 估算每日变动
    - 沪深300 = AkShare 真实日线归一化曲线
    返回 [{date, nav, benchmark}, ...]，nav 和 benchmark 均以1.0为基准。
    """
    if not holdings:
        holdings = []

    start_date = None
    if days is not None and days > 0:
        start_date = datetime.now() - timedelta(days=days)
    elif holdings:
        created_list = []
        for h in holdings:
            ca = h.get("created_at", "")
            if ca:
                try:
                    dt = datetime.strptime(ca[:10], "%Y-%m-%d")
                    created_list.append(dt)
                except Exception:
                    pass
        if created_list:
            start_date = min(created_list)

    if start_date is None:
        default_days = days or 60
        start_date = datetime.now() - timedelta(days=default_days)

    # 确保起始日期不超过今天（向前最多2年）
    today = datetime.now()
    max_days = min(int((today - start_date).days) + 1, 730)
    if max_days < 2:
        max_days = 2

    bench_rows = _fetch_hs300_normalized_series(days=max_days)
    if not bench_rows:
        # 无法获取 HS300 数据，生成纯基于持仓的估算曲线
        data = []
        nav = 1.0
        benchmark = 1.0
        cur = start_date
        while cur <= today:
            data.append({
                "date": cur.strftime("%Y-%m-%d"),
                "nav": round(nav, 4),
                "benchmark": round(benchmark, 4),
            })
            nav_change = random.gauss(0.0003, 0.006)
            bench_change = random.gauss(0.0002, 0.009)
            nav *= (1 + nav_change)
            benchmark *= (1 + bench_change)
            cur += timedelta(days=1)
        return data

    # 只保留 start_date 之后的交易日数据
    start_str = start_date.strftime("%Y-%m-%d")
    filtered = [r for r in bench_rows if r["date"] >= start_str]
    if len(filtered) < 2:
        filtered = bench_rows[-max(2, min(60, len(bench_rows))):]

    # 计算组合加权 beta（股票占比越高 beta 越接近1）
    if holdings:
        total_val = sum(h.get("shares", 0) * h.get("current", 0) for h in holdings)
        stock_val = sum(
            h.get("shares", 0) * h.get("current", 0)
            for h in holdings if h.get("asset_type", "股票") == "股票"
        )
        stock_ratio = stock_val / total_val if total_val > 0 else 0.6
        beta = 0.45 + stock_ratio * 0.85  # 纯股票约1.3，纯基金约0.45
    else:
        beta = 0.7

    # 用真实 HS300 日收益率 × beta 推演组合净值
    data = []
    nav = 1.0
    prev_bench = float(filtered[0]["benchmark"]) if filtered else 1.0
    for row in filtered:
        bench_val = float(row["benchmark"])
        bench_day_ret = (bench_val / prev_bench - 1.0) if prev_bench > 0 else 0.0
        nav_day_ret = bench_day_ret * beta
        nav *= (1 + nav_day_ret)
        data.append({
            "date": row["date"],
            "nav": round(nav, 4),
            "benchmark": round(bench_val, 4),
        })
        prev_bench = bench_val

    return data


# ==================== Routes ====================

@app.route("/")
def index():
    # 部署在子路径时（如 Nginx /app/），前端 fetch 需带上此前缀，否则 /api/* 会 404
    api_prefix = (os.getenv("FLASK_APPLICATION_ROOT") or "").strip().rstrip("/")
    if not api_prefix:
        api_prefix = (request.environ.get("SCRIPT_NAME") or "").strip().rstrip("/")
    return render_template(
        "index.html",
        asset_version=int(datetime.now().timestamp()),
        sector_board_date=_volume_data_date_label(),
        api_url_prefix=api_prefix,
    )


# ==================== API ====================

def _volume_data_date_label(ref=None):
    """
    上证量能等字段对应的「数据日期」展示文案。
    周末等非交易日时，行情快照一般为上一交易日（按周六→周五、周日→周五简化处理）。
    """
    ref = ref or datetime.now()
    d = ref.date()
    wd = ref.weekday()
    if wd == 5:
        d = d - timedelta(days=1)
    elif wd == 6:
        d = d - timedelta(days=2)
    return f"{d.year}年{d.month}月{d.day}日"


@app.route("/api/market")
def market_data():
    """
    市场概览接口：
    - 方案A：指数卡片使用 efinance（当前环境最稳定）
    - K线/新闻使用可用的 AkShare 接口（失败则留空）
    - 快讯利好/利空/中性：仅使用 Kimi 批量判定；未配置密钥或调用失败时标为中性，不使用本地规则兜底
    - AI 市场洞察：仅使用 Kimi 根据快照生成；失败时返回简短提示与 insights_kimi_error
    - 严禁模拟数据，失败返回空结构
    """
    try:
        update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        market = get_market_data()

        # A股三大指数统一改为 AkShare 日线源，且顺序固定
        indices = []
        a_index_map = [
            ("上证指数", "sh000001"),
            ("深证成指", "sz399001"),
            ("创业板指", "sz399006"),
        ]
        for name, symbol in a_index_map:
            try:
                df_idx = ak.stock_zh_index_daily(symbol=symbol)
                if df_idx is None or df_idx.empty or len(df_idx) < 2:
                    continue
                latest_close = float(df_idx.iloc[-1]["close"])
                prev_close = float(df_idx.iloc[-2]["close"])
                change_pct = 0.0 if prev_close == 0 else (latest_close - prev_close) / prev_close * 100
                indices.append({
                    "name": name,
                    "value": round(latest_close, 2),
                    "change": round(change_pct, 2),
                })
            except Exception:
                continue

        # ===== 强制接入 AkShare: 美股指数（新浪源） =====
        # 使用 ak.index_us_stock_sina(symbol=...) 分别拉取三大指数
        us_indices = []
        try:
            us_symbol_map = {
                "道琼斯": ".DJI",
                "纳斯达克": ".IXIC",
                "标普500": ".INX",
            }
            for cn_name, symbol in us_symbol_map.items():
                try:
                    df_us = ak.index_us_stock_sina(symbol=symbol)
                    if df_us is None or df_us.empty or len(df_us) < 2:
                        continue

                    latest = float(df_us.iloc[-1]["close"])
                    prev = float(df_us.iloc[-2]["close"])
                    change_amount = latest - prev
                    change_pct = 0.0 if prev == 0 else change_amount / prev * 100

                    us_indices.append({
                        "name": cn_name,
                        "value": round(latest, 2),
                        "change": round(change_pct, 2),
                        "volume": "--",
                    })
                except Exception:
                    continue
        except Exception:
            pass

        # 港股三指数（腾讯实时接口）
        hk_indices = []
        hk_code_map = [
            ("恒生指数", "hkHSI"),
            ("恒生国企指数", "hkHSCEI"),
            ("恒生科技指数", "hkHSTECH"),
        ]
        for name, code in hk_code_map:
            try:
                resp = requests.get(f"http://qt.gtimg.cn/q={code}", timeout=8)
                resp.encoding = "gbk"
                matched = re.search(r'="([^"]+)"', resp.text)
                if not matched:
                    continue
                parts = matched.group(1).split("~")
                if len(parts) < 5:
                    continue
                price = float(parts[3])
                prev = float(parts[4])
                change_pct = 0.0 if prev == 0 else (price - prev) / prev * 100
                hk_indices.append({
                    "name": name,
                    "value": round(price, 2),
                    "change": round(change_pct, 2),
                })
            except Exception:
                continue

        # 计算平均涨跌幅用于市场情绪
        avg_change = 0
        if indices:
            avg_change = sum(idx["change"] for idx in indices) / len(indices)

        # ===== K线数据：支持上证 / 恒生科技 / 纳斯达克 切换 =====
        def _format_kline(df, volume_factor=1.0):
            arr = []
            if df is None or df.empty:
                return arr
            recent = df.tail(120)
            for idx, row in recent.iterrows():
                if "date" in recent.columns:
                    raw_date = row.get("date")
                    if hasattr(raw_date, "strftime"):
                        date_text = raw_date.strftime("%Y-%m-%d")
                    else:
                        date_text = str(raw_date)[:10]
                else:
                    date_text = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                arr.append({
                    "date": date_text,
                    "open": float(row["open"]),
                    "close": round(float(row["close"]), 2),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "volume": round(float(row.get("volume", 0.0)) * volume_factor, 2),
                })
            return arr

        kline_map = {
            "shanghai": [],
            "hstech": [],
            "nasdaq": [],
        }

        try:
            df_sh = ak.stock_zh_index_daily(symbol="sh000001")
            # A股成交量: 股 -> 亿手
            kline_map["shanghai"] = _format_kline(df_sh, volume_factor=1 / 100 / 1e8)
        except Exception:
            kline_map["shanghai"] = []

        try:
            df_hk = ak.stock_hk_index_daily_sina(symbol="HSTECH")
            # 港股: 近似换算为“亿股”展示
            kline_map["hstech"] = _format_kline(df_hk, volume_factor=1 / 1e8)
        except Exception:
            kline_map["hstech"] = []

        try:
            df_us_k = ak.index_us_stock_sina(symbol=".IXIC")
            # 美股: 近似换算为“亿股”展示
            kline_map["nasdaq"] = _format_kline(df_us_k, volume_factor=1 / 1e8)
        except Exception:
            kline_map["nasdaq"] = []

        # 兼容旧前端字段，默认给上证
        kline = kline_map["shanghai"]

        # ===== 强制接入 AkShare: 财经新闻 =====
        # 优先使用 ak.stock_info_global_em() 获取更实时快讯
        # 若不足，再用 ak.stock_news_em() 补齐
        news = []
        try:
            # 1) 全局快讯（通常更新更快）
            df_global = ak.stock_info_global_em()
            if df_global is not None and not df_global.empty:
                # 标准化时间并按倒序
                records = []
                for _, row in df_global.iterrows():
                    try:
                        title = str(row.get("标题", "")).strip()
                        pub = str(row.get("发布时间", "")).strip()
                        if not title or not pub:
                            continue
                        dt = datetime.strptime(pub, "%Y-%m-%d %H:%M:%S")
                        records.append((dt, {
                            "title": title,
                            "source": "东方财富快讯",
                            "time": pub,
                            "link": str(row.get("链接", "")).strip(),
                            "sentiment": "neutral",
                            "sentiment_source": "pending",
                            "impact": "市场影响",
                        }))
                    except Exception:
                        continue

                records.sort(key=lambda x: x[0], reverse=True)

                # 优先取最近 48 小时新闻，保证“每天都更新”
                now = datetime.now()
                recent = [x[1] for x in records if (now - x[0]).total_seconds() <= 48 * 3600]
                news.extend(recent[:10])

            # 2) 若不足 10 条，用 stock_news_em 补齐
            if len(news) < 10:
                df_news = ak.stock_news_em()
                if df_news is not None and not df_news.empty:
                    for _, row in df_news.iterrows():
                        title = str(row.get("新闻标题", "")).strip()
                        if not title:
                            continue
                        item = {
                            "title": title,
                            "source": str(row.get("文章来源", "财经快讯")),
                            "time": str(row.get("发布时间", "")),
                            "link": str(row.get("新闻链接", "")).strip(),
                            "sentiment": "neutral",
                            "sentiment_source": "pending",
                            "impact": "市场影响",
                        }
                        # 去重后补齐
                        if any(n["title"] == item["title"] for n in news):
                            continue
                        news.append(item)
                        if len(news) >= 10:
                            break
        except Exception:
            news = []

        news_sentiment_engine, news_kimi_error = enrich_news_sentiment_with_kimi(news)

        # ===== A股板块热力图：涨幅前4 + 跌幅前4（互斥，避免全市场平盘时重复只剩 4 块）=====
        # 数据源：AkShare stock_sector_spot(indicator="行业") → 新浪行业板块，字段「板块」「涨跌幅」为板块整体涨跌幅（%）
        sectors = []
        try:
            df_sector = ak.stock_sector_spot(indicator="行业")
            if df_sector is not None and not df_sector.empty:
                sector_rows = []
                for _, row in df_sector.iterrows():
                    try:
                        name = str(
                            row.get("板块")
                            or row.get("板块名称")
                            or row.get("名称")
                            or ""
                        ).strip()
                        raw_ch = row.get("涨跌幅", row.get("最新涨跌幅", 0.0))
                        if isinstance(raw_ch, str):
                            raw_ch = raw_ch.replace("%", "").strip()
                        change = float(raw_ch)
                        if name:
                            sector_rows.append({"name": name, "change": round(change, 2)})
                    except Exception:
                        continue

                dedup = []
                seen = set()
                for r in sector_rows:
                    if r["name"] in seen:
                        continue
                    seen.add(r["name"])
                    dedup.append(r)

                top4 = sorted(dedup, key=lambda x: x["change"], reverse=True)[:4]
                top_names = {x["name"] for x in top4}
                rest = [x for x in dedup if x["name"] not in top_names]
                bottom4 = sorted(rest, key=lambda x: x["change"])[:4]

                merged = top4 + bottom4
                final = []
                seen2 = set()
                for r in merged:
                    if r["name"] in seen2:
                        continue
                    seen2.add(r["name"])
                    final.append(r)
                sectors = final
        except Exception:
            sectors = []

        # ===== AI 市场洞察：完全由 Kimi 根据当日快照生成（无本地规则拼装） =====
        insights_bundle = {
            "trade_date": _volume_data_date_label(),
            "data_time": update_time,
            "avg_index_change_pct": round(float(avg_change), 2),
            "a_share_indices": [
                {"name": str(x.get("name", "")), "change_pct": x.get("change", 0)}
                for x in indices
            ],
            "hk_indices": [
                {"name": str(x.get("name", "")), "change_pct": x.get("change", 0)}
                for x in hk_indices
            ],
            "us_indices": [
                {"name": str(x.get("name", "")), "change_pct": x.get("change", 0)}
                for x in us_indices
            ],
            "sectors": [
                {"name": str(x.get("name", "")), "change_pct": x.get("change", 0)}
                for x in (sectors or [])[:12]
            ],
            "flash_news": [
                {
                    "title": str(n.get("title", "") or "")[:200],
                    "sentiment": str(n.get("sentiment", "neutral") or "neutral"),
                }
                for n in (news or [])[:10]
                if str(n.get("title", "") or "").strip()
            ],
        }
        try:
            ai_insights, insights_kimi_error, insights_engine = generate_market_insights_with_kimi(
                insights_bundle
            )
        except Exception as _ins_e:
            ai_insights = []
            insights_kimi_error = f"市场洞察生成异常：{_ins_e}"
            insights_engine = "kimi_failed"
        if not ai_insights:
            insights_kimi_error = (insights_kimi_error or "").strip() or "Kimi 未返回有效洞察"
            if insights_engine == "kimi":
                insights_engine = "kimi_failed"
            ai_insights = ["暂时无法展示由 Kimi 生成的市场洞察，请稍后重试或检查密钥与网络。"]

        # ===== 市场情绪指标（NLP新闻情绪 + 价格面） =====
        sentiment_analysis = {
            "label": "中性",
            "zscore": 0.0,
            "prompt": "情绪处于常态区间，建议按既定策略执行。",
            "nlp_summary": "新闻情绪样本不足，当前以价格信号为主。",
            "volume_data_date": _volume_data_date_label(),
            "value_pct": 50.0,
            "composite_raw": 0.0,
            "factors": [],
            "usage_note": "综合盘面、快讯、标题措辞与量能活跃度，观察风险偏好温度（量能口径见数据日期）；不构成投资建议。",
        }
        market_sentiment = 0.5
        try:
            def _parse_cn_number(val):
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                text = str(val).strip().replace(",", "")
                if not text or text in {"--", "nan", "None"}:
                    return 0.0
                factor = 1.0
                if text.endswith("亿"):
                    factor = 1e8
                    text = text[:-1]
                elif text.endswith("万"):
                    factor = 1e4
                    text = text[:-1]
                elif text.endswith("千"):
                    factor = 1e3
                    text = text[:-1]
                try:
                    return float(text) * factor
                except Exception:
                    return 0.0

            # 价格面得分（-1~1）
            price_score = max(-1.0, min(1.0, avg_change / 2.0))

            # 新闻NLP得分
            pos_count = sum(1 for n in news if n.get("sentiment") == "positive")
            neg_count = sum(1 for n in news if n.get("sentiment") == "negative")
            neu_count = sum(1 for n in news if n.get("sentiment") == "neutral")
            total_count = max(1, len(news))
            news_score = (pos_count - neg_count) / total_count

            # 贪婪/恐惧关键词
            hype_keywords = ["牛回", "牛市", "暴涨", "满仓", "逼空", "新高", "狂欢", "抄底", "起飞"]
            fear_keywords = ["暴跌", "恐慌", "崩盘", "踩踏", "风险", "避险", "出逃", "爆仓", "下杀"]
            hype_hits = 0
            fear_hits = 0
            title_scores = []
            for n in news[:12]:
                title = str(n.get("title", ""))
                if not title:
                    continue
                h = sum(1 for k in hype_keywords if k in title)
                f = sum(1 for k in fear_keywords if k in title)
                hype_hits += h
                fear_hits += f
                raw = h - f
                if raw > 0:
                    title_scores.append(1.0)
                elif raw < 0:
                    title_scores.append(-1.0)
                else:
                    title_scores.append(0.0)
            keyword_bias = (hype_hits - fear_hits) / max(1, len(news[:12]))

            # A股量能得分：结合上证成交量/成交额（越活跃，风险偏好通常越高；展示文案用 volume_data_date）
            a_turnover_amount_yi = 0.0  # 单位：亿元
            a_turnover_volume_yishou = 0.0  # 单位：亿手
            try:
                # 1) 优先腾讯实时：按上证指数单独口径，和页面K线口径保持一致
                try:
                    resp = requests.get("http://qt.gtimg.cn/q=sh000001", timeout=8)
                    resp.encoding = "gbk"
                    m = re.search(r'="([^"]+)"', resp.text)
                    if m:
                        parts = m.group(1).split("~")
                        # 经验字段：
                        # parts[6]  成交量(手)
                        # parts[37] 成交额(万元)
                        if len(parts) > 37:
                            vol_hand = float(parts[6]) if parts[6] else 0.0
                            amt_wan = float(parts[37]) if parts[37] else 0.0
                            a_turnover_volume_yishou = vol_hand / 1e8
                            a_turnover_amount_yi = amt_wan / 1e4
                except Exception:
                    pass

                # 2) 若腾讯不可用，再尝试 AkShare
                if a_turnover_amount_yi <= 0 and a_turnover_volume_yishou <= 0:
                    df_spot = ak.stock_zh_index_spot_em()
                    if df_spot is not None and not df_spot.empty:
                        code_col = "代码" if "代码" in df_spot.columns else ("symbol" if "symbol" in df_spot.columns else "")
                        vol_col = "成交量" if "成交量" in df_spot.columns else ("volume" if "volume" in df_spot.columns else "")
                        amount_col = "成交额" if "成交额" in df_spot.columns else ("amount" if "amount" in df_spot.columns else "")
                        if code_col and vol_col and amount_col:
                            target_codes = {"000001", "sh000001"}
                            for _, row in df_spot.iterrows():
                                code = str(row.get(code_col, "")).strip()
                                if code not in target_codes:
                                    continue
                                vol_raw = _parse_cn_number(row.get(vol_col, 0.0))
                                amt_raw = _parse_cn_number(row.get(amount_col, 0.0))
                                # 若源字段为“股”，换算为“亿手”；若已是“手”会略有偏差，仅做兜底
                                a_turnover_volume_yishou = vol_raw / 100 / 1e8
                                # 统一换算为“亿元”
                                a_turnover_amount_yi = amt_raw / 1e8
                                break
            except Exception:
                a_turnover_amount_yi = 0.0
                a_turnover_volume_yishou = 0.0

            if a_turnover_amount_yi > 0 or a_turnover_volume_yishou > 0:
                # 基线可按后续真实运行再调优
                amount_baseline = 12000.0  # 亿元
                volume_baseline = 1.2  # 亿手
                amount_ratio = a_turnover_amount_yi / max(amount_baseline, 1.0)
                volume_ratio = a_turnover_volume_yishou / max(volume_baseline, 0.1)
                liquidity_score = max(
                    -1.0,
                    min(1.0, 0.6 * (amount_ratio - 1.0) + 0.4 * (volume_ratio - 1.0))
                )
            else:
                liquidity_score = 0.0

            # 混合得分（-1~1）
            composite = (
                0.35 * price_score
                + 0.30 * news_score
                + 0.15 * keyword_bias
                + 0.20 * liquidity_score
            )
            composite = max(-1.0, min(1.0, composite))

            # 转换为 0~1 的贪婪/恐惧指数
            market_sentiment = max(0.0, min(1.0, 0.5 + 0.5 * composite))

            # 偏离均值（z-score近似）
            if title_scores:
                mean_val = sum(title_scores) / len(title_scores)
                variance = sum((x - mean_val) ** 2 for x in title_scores) / len(title_scores)
                std_val = variance ** 0.5
                base_std = std_val if std_val >= 0.15 else 0.15
                zscore = max(-3.0, min(3.0, mean_val / base_std))
            else:
                zscore = 0.0

            if market_sentiment >= 0.67:
                label = "贪婪"
            elif market_sentiment <= 0.33:
                label = "恐惧"
            else:
                label = "中性"

            if zscore >= 2.0:
                prompt = f"当前情绪过热，偏离均值 {zscore:.2f} 个标准差，建议保持冷静。"
            elif zscore <= -2.0:
                prompt = f"当前情绪偏冷，偏离均值 {abs(zscore):.2f} 个标准差，注意避免恐慌交易。"
            else:
                prompt = "情绪波动处于常态区间，建议按计划交易，避免被短线噪音带节奏。"

            vol_data_date = _volume_data_date_label()
            sentiment_analysis = {
                "label": label,
                "zscore": round(float(zscore), 2),
                "prompt": prompt,
                "volume_data_date": vol_data_date,
                "nlp_summary": (
                    f"快讯：利好{pos_count}条 / 利空{neg_count}条 / 中性{neu_count}条；标题「贪婪/恐惧」词各出现{hype_hits}、{fear_hits}次。"
                    f" 数据日期 {vol_data_date}，上证量能：成交额约{a_turnover_amount_yi:.0f}亿元，成交量约{a_turnover_volume_yishou:.2f}亿手。"
                ),
                "value_pct": round(float(market_sentiment) * 100, 1),
                "composite_raw": round(float(composite), 3),
                "factors": [
                    {
                        "id": "price",
                        "name": "板块强弱",
                        "contribution": round(float(price_score), 3),
                        "weight_pct": 35,
                        "desc": "热力图行业平均涨跌幅，反映整体赚钱效应",
                    },
                    {
                        "id": "news",
                        "name": "快讯多空",
                        "contribution": round(float(news_score), 3),
                        "weight_pct": 30,
                        "desc": "7×24 利好/利空条数差（已由 Kimi 或中性占位标注）",
                    },
                    {
                        "id": "word",
                        "name": "措辞情绪",
                        "contribution": round(float(keyword_bias), 3),
                        "weight_pct": 15,
                        "desc": "标题中极端贪婪/恐惧类词汇密度",
                    },
                    {
                        "id": "liquidity",
                        "name": "量能活跃",
                        "contribution": round(float(liquidity_score), 3),
                        "weight_pct": 20,
                        "desc": f"上证成交额/成交量相对经验基线的偏离（数据日期 {vol_data_date}）",
                    },
                ],
                "usage_note": "把「涨跌、新闻、措辞、量能」合成 0–100 情绪温度：越低越偏谨慎，越高越偏激进；量能口径以上述数据日期为准；用于总览风险氛围，勿单独作为买卖依据。",
            }
        except Exception:
            pass

        return jsonify({
            "indices": indices,
            "hk_indices": hk_indices,
            "us_indices": us_indices,
            "update_time": update_time,
            "kline": kline,
            "kline_map": kline_map,
            "sectors": sectors,
            "sector_board_data_date": _volume_data_date_label(),
            "news": news,
            "top_stocks": [],
            "bottom_stocks": [],
            "market_sentiment": market_sentiment,
            "sentiment_analysis": sentiment_analysis,
            "ai_insights": ai_insights,
            "data_source": "efinance+akshare",
            "news_sentiment_engine": news_sentiment_engine,
            "news_kimi_error": news_kimi_error or "",
            "insights_kimi_error": insights_kimi_error or "",
            "insights_engine": insights_engine,
        })
    except Exception as e:
        print(f"获取市场数据失败: {e}")
        import traceback
        traceback.print_exc()

    # 失败时返回带时间的空数据
    return jsonify({
        "indices": [],
        "hk_indices": [],
        "us_indices": [],
        "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "kline": [],
        "kline_map": {"shanghai": [], "hstech": [], "nasdaq": []},
        "sectors": [],
        "news": [],
        "top_stocks": [],
        "bottom_stocks": [],
        "market_sentiment": 0.0,
        "sentiment_analysis": {
            "label": "中性",
            "zscore": 0.0,
            "prompt": "数据获取失败，情绪指标暂不可用。",
            "nlp_summary": "暂无可用新闻样本。",
            "volume_data_date": "",
            "value_pct": 0.0,
            "composite_raw": 0.0,
            "factors": [],
            "usage_note": "",
        },
        "ai_insights": ["数据获取失败"],
        "data_source": "error",
        "news_sentiment_engine": "unavailable",
        "news_kimi_error": "",
        "insights_kimi_error": "",
        "insights_engine": "unavailable",
        "sector_board_data_date": "",
    })


@app.route("/api/risk-questions")
def risk_questions():
    return jsonify({"questions": RISK_QUESTIONS})


# ==================== 情绪调仓 ====================

def _apply_sentiment_tilt(base_alloc: list, sentiment_value: float):
    """
    根据市场情绪指数（0~1）对基准配置进行微调，总和始终保持 100%。

    规则（参照计划表）：
      极度贪婪 >= 0.75：股票基金 -3%，债券基金 +2%，货币基金 +1%
      偏贪婪   0.60~0.75：股票基金 -1.5%，债券基金 +1%，货币基金 +0.5%
      中性     0.40~0.60：不调整
      偏恐惧   0.25~0.40：股票基金 +1.5%，债券基金 -1%，货币基金 -0.5%
      极度恐惧 < 0.25：股票基金 +3%，债券基金 -2%，货币基金 -1%

    Returns (adjusted_alloc, tilt_note)
    """
    import copy

    adjusted = copy.deepcopy(base_alloc)

    sv = float(sentiment_value) if sentiment_value is not None else 0.5

    if sv >= 0.75:
        deltas = {"股票基金": -3, "债券基金": 2, "货币基金": 1}
        direction = "极度贪婪"
        desc = f"市场极度贪婪（{int(round(sv*100))}/100），股票基金下调 3%，债券+货币适当增配防御"
    elif sv >= 0.60:
        deltas = {"股票基金": -1.5, "债券基金": 1, "货币基金": 0.5}
        direction = "偏贪婪"
        desc = f"市场偏贪婪（{int(round(sv*100))}/100），股票基金下调 1.5%，债券+货币小幅增配"
    elif sv >= 0.40:
        deltas = {}
        direction = "中性"
        desc = ""
    elif sv >= 0.25:
        deltas = {"股票基金": 1.5, "债券基金": -1, "货币基金": -0.5}
        direction = "偏恐惧"
        desc = f"市场偏恐惧（{int(round(sv*100))}/100），股票基金上调 1.5%，固收类略降"
    else:
        deltas = {"股票基金": 3, "债券基金": -2, "货币基金": -1}
        direction = "极度恐惧"
        desc = f"市场极度恐惧（{int(round(sv*100))}/100），股票基金上调 3%，防御类资产调低"

    if not deltas:
        return adjusted, ""

    for item in adjusted:
        delta = deltas.get(item["name"], 0)
        if delta:
            item["value"] = max(0, round(item["value"] + delta, 1))

    # 修正浮点误差，确保总和==100
    total = round(sum(x["value"] for x in adjusted), 1)
    diff = round(100.0 - total, 1)
    if diff != 0:
        # 将余差加到混合基金（兜底最平滑）
        for item in adjusted:
            if item["name"] == "混合基金":
                item["value"] = max(0, round(item["value"] + diff, 1))
                break

    tilt_note = desc
    return adjusted, tilt_note


@app.route("/api/risk-assess", methods=["POST"])
def risk_assess():
    answers = request.json.get("answers", [])
    total_score = sum(answers)

    if total_score <= 18:
        profile = "保守型"
    elif total_score <= 26:
        profile = "稳健型"
    elif total_score <= 34:
        profile = "平衡型"
    elif total_score <= 42:
        profile = "进取型"
    else:
        profile = "激进型"

    radar_data = {
        "risk_tolerance": min(answers[4] if len(answers) > 4 else 3, 5),
        "investment_exp": min(answers[1] if len(answers) > 1 else 3, 5),
        "financial_knowledge": min(answers[8] if len(answers) > 8 else 3, 5),
        "income_stability": min(6 - (answers[2] if len(answers) > 2 else 3), 5),
        "investment_horizon": min(answers[3] if len(answers) > 3 else 3, 5),
    }

    allocation_data = ALLOCATION_PROFILES.get(profile, ALLOCATION_PROFILES["平衡型"])

    return jsonify({
        "score": total_score,
        "max_score": 50,
        "profile": profile,
        "radar": radar_data,
        "allocation": allocation_data,
    })


# ==================== 风险测评结果持久化（本地文件）====================
_RISK_RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "risk_results.json")
_risk_file_lock = threading.Lock()


def _read_risk_results() -> dict:
    """读取本地 risk_results.json，返回 dict（key=id，value=结果对象）。"""
    try:
        if os.path.isfile(_RISK_RESULT_FILE):
            with open(_RISK_RESULT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def _write_risk_results(data: dict) -> None:
    with _risk_file_lock:
        with open(_RISK_RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/api/risk-result", methods=["GET"])
def get_risk_result():
    """读取已保存的测评结果，返回最新一条（id=latest）或指定 id。"""
    rid = request.args.get("id", "latest")
    results = _read_risk_results()
    if rid == "latest":
        if not results:
            return jsonify({"found": False})
        # 取 saved_at 最新的一条
        latest = max(results.values(), key=lambda x: x.get("saved_at", ""))
        return jsonify({"found": True, "result": latest})
    item = results.get(rid)
    if not item:
        return jsonify({"found": False})
    return jsonify({"found": True, "result": item})


@app.route("/api/risk-result", methods=["POST"])
def save_risk_result():
    """保存测评结果到本地文件，以 id=latest 覆盖写入（始终保留最新）。"""
    payload = request.json or {}
    if not payload.get("profile") or not payload.get("allocation"):
        return jsonify({"ok": False, "error": "缺少必要字段 profile / allocation"}), 400
    results = _read_risk_results()
    payload["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results["latest"] = payload
    try:
        _write_risk_results(results)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/risk-result", methods=["DELETE"])
def delete_risk_result():
    """删除已保存的测评结果。"""
    results = _read_risk_results()
    if "latest" in results:
        del results["latest"]
        try:
            _write_risk_results(results)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


# ==================== 智能配置 Kimi 建议 ====================

@app.route("/api/allocation-advice", methods=["POST"])
def allocation_advice():
    """
    接收前端缓存的行情数据 + 风险画像，返回：
      - 情绪调仓后比例（adjusted_alloc）
      - 调仓说明（tilt_note）
      - Kimi 生成的个性化分析文案（advice / key_points）
      - 引擎状态（advice_engine / advice_kimi_error）
    """
    payload = request.json or {}
    profile = str(payload.get("profile") or "平衡型").strip()
    if profile not in ALLOCATION_PROFILES:
        profile = "平衡型"

    base_prof = ALLOCATION_PROFILES[profile]
    base_alloc = [dict(x) for x in base_prof.get("allocation", [])]

    # 从前端传入的情绪数值（0~1），前端缓存的 market.market_sentiment.score
    raw_sentiment = payload.get("market_sentiment") or {}
    sentiment_value = float(raw_sentiment.get("score", 0.5)) if isinstance(raw_sentiment, dict) else 0.5
    sentiment_value = max(0.0, min(1.0, sentiment_value))

    adjusted_alloc, tilt_note = _apply_sentiment_tilt(base_alloc, sentiment_value)

    # 组装 market_bundle，复用和 market_insights 相同格式
    market_bundle = {
        "a_share_indices": payload.get("a_share_indices") or [],
        "hk_indices": payload.get("hk_indices") or [],
        "us_indices": payload.get("us_indices") or [],
        "sectors": payload.get("sectors") or [],
        "flash_news": payload.get("flash_news") or [],
        "sentiment_analysis": payload.get("sentiment_analysis") or {},
    }

    advice, key_points, kimi_err, engine = generate_allocation_advice_with_kimi(
        profile=profile,
        base_alloc=base_alloc,
        adjusted_alloc=adjusted_alloc,
        tilt_note=tilt_note,
        market_bundle=market_bundle,
        sentiment_value=sentiment_value,
    )

    return jsonify({
        "profile": profile,
        "base_alloc": base_alloc,
        "adjusted_alloc": adjusted_alloc,
        "tilt_note": tilt_note,
        "advice": advice,
        "key_points": key_points,
        "advice_engine": engine,
        "advice_kimi_error": kimi_err,
    })


@app.route("/api/stock-screen", methods=["POST"])
def stock_screen():
    def _to_float(v, default=0.0):
        try:
            if v is None:
                return default
            text = str(v).replace(",", "").strip()
            if text in {"", "--", "None", "nan"}:
                return default
            return float(text)
        except Exception:
            return default

    def _clip(x, low=0.0, high=100.0):
        return max(low, min(high, x))

    def _normalize_code(raw_code):
        code = str(raw_code or "").strip()
        if code.startswith(("sh", "sz", "bj")) and len(code) > 2:
            return code[2:]
        return code

    def _build_static_factor_rows():
        rows = []
        for s in STOCKS:
            code = str(s.get("code", "")).strip()
            name = str(s.get("name", "")).strip()
            price = _to_float(s.get("price"))
            if not code or not name or price <= 0:
                continue
            day_change_pct = _to_float(s.get("momentum_3m")) / 20.0
            amount = max(_to_float(s.get("market_cap")) * 1e8 * 0.001, 1.0)
            volume = max(amount / max(price, 1.0), 1.0)
            value_raw = 100.0 - _to_float(s.get("pe"), 20.0) * 2.0
            growth_raw = _to_float(s.get("revenue_growth"), 0.0) * 2.0 + _to_float(s.get("profit_growth"), 0.0) * 1.2
            quality_raw = _to_float(s.get("roe"), 0.0) * 2.5 - _to_float(s.get("debt_ratio"), 0.0) * 0.4
            momentum_raw = _to_float(s.get("momentum_3m"), 0.0) * 0.6 + _to_float(s.get("momentum_6m"), 0.0) * 0.4
            sentiment_raw = _to_float(s.get("sentiment"), 0.5) * 100.0 + _to_float(s.get("analyst_rating"), 3.5) * 5.0
            rows.append({
                "code": code,
                "name": name,
                "price": price,
                "day_change_pct": day_change_pct,
                "volume": volume,
                "amount": amount,
                "raw": {
                    "value": value_raw,
                    "growth": growth_raw,
                    "quality": quality_raw,
                    "momentum": momentum_raw,
                    "sentiment": sentiment_raw,
                },
            })
        return rows

    weights = request.json or {}
    w_value = weights.get("value", 20) / 100
    w_growth = weights.get("growth", 20) / 100
    w_quality = weights.get("quality", 25) / 100
    w_momentum = weights.get("momentum", 20) / 100
    w_sentiment = weights.get("sentiment", 15) / 100

    # 基础信息映射：仅用于补充行业与展示字段，行情全部来自实时接口
    base_map = {item["code"]: item for item in STOCKS}

    def _fetch_realtime_from_sina(base_items):
        """新浪批量实时行情兜底，确保选股功能在接口抖动时仍可用。"""
        if not base_items:
            return []
        symbols = []
        for item in base_items:
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            symbols.append(f"{prefix}{code}")
        if not symbols:
            return []
        try:
            resp = requests.get(
                f"http://hq.sinajs.cn/list={','.join(symbols)}",
                timeout=10,
                headers={"Referer": "https://finance.sina.com.cn/"},
            )
            resp.encoding = "gbk"
            if resp.status_code != 200 or not resp.text:
                return []
            rows = []
            for line in resp.text.splitlines():
                if "=\"" not in line:
                    continue
                left, right = line.split("=\"", 1)
                symbol = left.split("hq_str_")[-1].strip()
                payload = right.rstrip("\";").strip()
                parts = payload.split(",")
                if len(parts) < 10:
                    continue
                code = symbol[2:]
                name = parts[0].strip() or base_map.get(code, {}).get("name", "")
                prev_close = _to_float(parts[2])
                price = _to_float(parts[3])
                high = _to_float(parts[4])
                low = _to_float(parts[5])
                buy_price = _to_float(parts[6])
                sell_price = _to_float(parts[7])
                volume = _to_float(parts[8])
                amount = _to_float(parts[9])
                if price <= 0:
                    continue
                day_change_pct = 0.0 if prev_close <= 0 else (price - prev_close) / prev_close * 100
                rows.append({
                    "代码": code,
                    "名称": name,
                    "最新价": price,
                    "昨收": prev_close,
                    "涨跌幅": day_change_pct,
                    "买入": buy_price,
                    "卖出": sell_price,
                    "最高": high,
                    "最低": low,
                    "成交量": volume,
                    "成交额": amount,
                })
            return rows
        except Exception:
            return []

    def _fetch_pe_pb_from_tencent(codes):
        """
        腾讯行情接口批量获取基本面与技术数据，字段索引经实测验证：
          [38] = 换手率%
          [39] = PE（市盈率 TTM）
          [46] = PB（市净率）
          [47] = 52周最高价
          [48] = 52周最低价
          [62] = 5日涨跌幅%
          [63] = 10日涨跌幅%
          [64] = 20日涨跌幅%
          [65] = 60日涨跌幅%
        返回 {code: {...}} 字典，失败时返回空字典。
        """
        if not codes:
            return {}
        result = {}
        batch_size = 100
        for start in range(0, len(codes), batch_size):
            batch = codes[start:start + batch_size]
            symbols = []
            for code in batch:
                prefix = "sh" if str(code).startswith(("6", "9")) else "sz"
                symbols.append(f"{prefix}{code}")
            try:
                resp = requests.get(
                    f"https://qt.gtimg.cn/q={','.join(symbols)}",
                    timeout=8,
                    headers={"Referer": "https://gu.qq.com/"},
                )
                resp.encoding = "gbk"
                if resp.status_code != 200:
                    continue
                for line in resp.text.splitlines():
                    if "~" not in line:
                        continue
                    parts = line.split("~")
                    if len(parts) < 66:
                        continue
                    # parts[0] 格式: 'v_sh600519="1'，需提取纯股票代码
                    raw0 = parts[0].split("=")[0].strip()   # 'v_sh600519'
                    sym_raw = raw0.split("_")[-1].strip()   # 'sh600519'
                    code = sym_raw[2:] if sym_raw[:2] in ("sh", "sz", "bj") else sym_raw
                    try:
                        pe = _to_float(parts[39])
                        pb = _to_float(parts[46])
                        turnover = _to_float(parts[38])      # 换手率%
                        high_52w = _to_float(parts[47])      # 52周最高
                        low_52w = _to_float(parts[48])       # 52周最低
                        ret_5d = _to_float(parts[62])        # 5日涨跌%
                        ret_10d = _to_float(parts[63])       # 10日涨跌%
                        ret_20d = _to_float(parts[64])       # 20日涨跌%
                        ret_60d = _to_float(parts[65])       # 60日涨跌%
                        if pe > 0 and pb > 0:
                            roe_est = round(pb / pe * 100, 2)
                            result[code] = {
                                "pe": round(pe, 2),
                                "pb": round(pb, 2),
                                "roe_est": roe_est,
                                "turnover": turnover,
                                "high_52w": high_52w,
                                "low_52w": low_52w,
                                "ret_5d": ret_5d,
                                "ret_10d": ret_10d,
                                "ret_20d": ret_20d,
                                "ret_60d": ret_60d,
                            }
                    except Exception:
                        continue
            except Exception:
                continue
        return result

    scored_stocks = []
    try:
        # 优先更快的新浪批量实时源，避免页面长时间等待
        candidate_rows = _fetch_realtime_from_sina(_get_stock_search_pool()[:300])

        # 腾讯接口批量补充 PE / PB，纳入基本面因子评分
        # 对新浪成功返回的 codes 同步拉取，失败则静默降级
        pe_pb_map = {}
        if candidate_rows:
            sina_codes = [r.get("代码", "") for r in candidate_rows if r.get("代码")]
            try:
                pe_pb_map = _fetch_pe_pb_from_tencent(sina_codes)
            except Exception:
                pe_pb_map = {}

        if not candidate_rows:
            # 备用源：东方财富 A 股快照（保留 PE/PB 字段供 _resolve_pe_roe 使用）
            try:
                df_em = ak.stock_zh_a_spot_em()
                if df_em is not None and not df_em.empty:
                    rows = []
                    for _, row in df_em.iterrows():
                        code = _normalize_code(row.get("代码", ""))
                        name = str(row.get("名称", "")).strip()
                        price = _to_float(row.get("最新价"))
                        if not code or not name or price <= 0:
                            continue
                        # 保留 PE/PB 字段，以提升 _resolve_pe_roe 准确率
                        enriched = {
                            "代码": code,
                            "名称": name,
                            "最新价": price,
                            "昨收": _to_float(row.get("昨收")),
                            "涨跌幅": _to_float(row.get("涨跌幅")),
                            "买入": _to_float(row.get("买入")),
                            "卖出": _to_float(row.get("卖出")),
                            "最高": _to_float(row.get("最高")),
                            "最低": _to_float(row.get("最低")),
                            "成交量": _to_float(row.get("成交量")),
                            "成交额": _to_float(row.get("成交额")),
                            # PE/PB 字段直接透传，_resolve_pe_roe 会检测键名
                            "市盈率-动态": row.get("市盈率-动态"),
                            "市净率": row.get("市净率"),
                        }
                        rows.append((_to_float(row.get("成交额")), enriched))
                    rows.sort(key=lambda x: x[0], reverse=True)
                    candidate_rows = [r for _, r in rows[:300]]
            except Exception:
                candidate_rows = []

        if not candidate_rows:
            candidate_rows = _fetch_realtime_from_sina(STOCKS)

        factor_rows = []
        for row in candidate_rows:
            code = _normalize_code(row.get("代码", ""))
            name = str(row.get("名称", "")).strip()
            price = _to_float(row.get("最新价"))
            prev_close = _to_float(row.get("昨收"))
            day_change_pct = _to_float(row.get("涨跌幅"))
            buy_price = _to_float(row.get("买入"))
            sell_price = _to_float(row.get("卖出"))
            high = _to_float(row.get("最高"))
            low = _to_float(row.get("最低"))
            volume = _to_float(row.get("成交量"))
            amount = _to_float(row.get("成交额"))
            if not code or not name or price <= 0:
                continue

            spread_pct = 0.0 if price <= 0 else abs(sell_price - buy_price) / price * 100
            intraday_amp = 0.0 if prev_close <= 0 else (high - low) / prev_close * 100
            range_pos = 50.0
            if high > low:
                range_pos = _clip((price - low) / (high - low) * 100)
            flow_signal = 0.0 if (buy_price + sell_price) <= 0 else (buy_price - sell_price) / ((buy_price + sell_price) / 2)
            volume_ratio = 0.0 if prev_close <= 0 else amount / max(prev_close * volume, 1.0)

            # 腾讯接口 PE/PB 基本面数据（有则注入 row，供 _resolve_pe_roe 使用）
            tencent_data = pe_pb_map.get(code, {})
            tencent_pe = tencent_data.get("pe", 0.0)
            tencent_pb = tencent_data.get("pb", 0.0)
            tencent_roe = tencent_data.get("roe_est", 0.0)
            tencent_turnover = tencent_data.get("turnover", 0.0)
            tencent_high52 = tencent_data.get("high_52w", 0.0)
            tencent_low52 = tencent_data.get("low_52w", 0.0)
            tencent_ret5d = tencent_data.get("ret_5d", 0.0)
            tencent_ret20d = tencent_data.get("ret_20d", 0.0)
            tencent_ret60d = tencent_data.get("ret_60d", 0.0)
            if tencent_pe > 0:
                row["市盈率-动态"] = tencent_pe
            if tencent_pb > 0:
                row["市净率"] = tencent_pb

            # ── 价值因子：低PE = 估值便宜（60%）+ 短线回调性价比（40%）──
            if tencent_pe > 0:
                pe_value_raw = _clip(100 - (tencent_pe - 5) / (80 - 5) * 100, 0.0, 100.0)
                value_raw = pe_value_raw * 0.6 + (-day_change_pct - 0.25 * intraday_amp) * 0.4
            else:
                value_raw = -day_change_pct - 0.25 * intraday_amp

            # ── 成长因子：中期（60日）+ 中短期（20日）价格趋势，反映业绩增长市场定价 ──
            # 有腾讯历史收益率数据时使用真实数据，否则降级到当日成交额活跃度
            if tencent_ret60d != 0.0 or tencent_ret20d != 0.0:
                growth_raw = tencent_ret60d * 0.6 + tencent_ret20d * 0.4
            else:
                growth_raw = day_change_pct * 0.7 + (amount / 1e9) * 0.3

            # ── 质量因子：高ROE = 盈利能力强（60%）+ 盘口质量（40%）──
            if tencent_roe > 0:
                roe_quality_raw = _clip(tencent_roe / 40.0 * 100, 0.0, 100.0)
                quality_raw = roe_quality_raw * 0.6 + (-(spread_pct * 3.0 + intraday_amp)) * 0.4
            else:
                quality_raw = -(spread_pct * 3.0 + intraday_amp)

            # ── 动量因子：股价在52周区间的相对位置（强势股特征）+ 短中期涨幅 ──
            # 52周位置：越接近高点动量越强（中长期趋势跟随）
            if tencent_high52 > tencent_low52 > 0 and price > 0:
                week52_pos = _clip((price - tencent_low52) / (tencent_high52 - tencent_low52) * 100)
                momentum_raw = week52_pos * 0.5 + tencent_ret20d * 0.3 + tencent_ret5d * 0.2
            else:
                momentum_raw = day_change_pct * 0.7 + (range_pos - 50.0) * 0.3

            # ── 情绪因子：换手率（资金活跃度）+ 5日涨跌 + 今日量价配合 ──
            # 换手率高 + 近5日上涨 + 今日盘口偏多 → 情绪热度高
            if tencent_turnover > 0:
                # 换手率归一化（A股正常0.3%~5%，>5%视为极度活跃）
                turnover_score = _clip(tencent_turnover / 5.0 * 100, 0.0, 100.0)
                sentiment_raw = turnover_score * 0.4 + tencent_ret5d * 0.4 + flow_signal * 20.0
            else:
                sentiment_raw = flow_signal * 100.0 + day_change_pct * 2.0 + volume_ratio * 0.05

            factor_rows.append({
                "code": code,
                "name": name,
                "price": price,
                "day_change_pct": day_change_pct,
                "volume": volume,
                "amount": amount,
                "tencent_pe": tencent_pe,
                "tencent_pb": tencent_pb,
                "tencent_roe": tencent_roe,
                "tencent_ret5d": tencent_ret5d,
                "tencent_ret20d": tencent_ret20d,
                "tencent_ret60d": tencent_ret60d,
                "tencent_turnover": tencent_turnover,
                "week52_high": tencent_high52,
                "week52_low": tencent_low52,
                "raw": {
                    # 价值：低PE（基本面）+ 短线回调（量价）混合
                    "value": value_raw,
                    # 成长：60日+20日历史收益率（中期趋势）
                    "growth": growth_raw,
                    # 质量：高ROE（基本面）+ 盘口质量（量价）混合
                    "quality": quality_raw,
                    # 动量：52周区间位置 + 短中期涨幅（趋势跟随）
                    "momentum": momentum_raw,
                    # 情绪：换手率活跃度 + 5日涨跌 + 盘口偏多信号
                    "sentiment": sentiment_raw,
                },
            })

        if not factor_rows:
            factor_rows = _build_static_factor_rows()
            if not factor_rows:
                cached = STOCK_SCREEN_RESULT_CACHE.get("items") or []
                if cached:
                    return jsonify({"stocks": cached})
                return jsonify({"stocks": []})

        # 将原始因子做横截面百分位，避免某只股票长期“锁第一”
        factor_names = ["value", "growth", "quality", "momentum", "sentiment"]
        ranked_scores = {name: {} for name in factor_names}
        total_n = len(factor_rows)
        for fname in factor_names:
            sorted_codes = [x["code"] for x in sorted(factor_rows, key=lambda r: r["raw"][fname])]
            if total_n == 1:
                ranked_scores[fname][sorted_codes[0]] = 50.0
                continue
            for idx, code in enumerate(sorted_codes):
                ranked_scores[fname][code] = round(idx / (total_n - 1) * 100, 2)

        for row in factor_rows:
            code = row["code"]
            value_score = ranked_scores["value"].get(code, 50.0)
            growth_score = ranked_scores["growth"].get(code, 50.0)
            quality_score = ranked_scores["quality"].get(code, 50.0)
            momentum_score = ranked_scores["momentum"].get(code, 50.0)
            sentiment_score = ranked_scores["sentiment"].get(code, 50.0)

            total = (
                w_value * value_score
                + w_growth * growth_score
                + w_quality * quality_score
                + w_momentum * momentum_score
                + w_sentiment * sentiment_score
            )

            base = base_map.get(code, {})
            industry = base.get("industry", "未知")
            # 优先使用腾讯接口拿到的真实 PE/ROE（避免 _resolve_pe_roe 回落到行业中位数）
            tpe = row.get("tencent_pe", 0.0) or 0.0
            trb = row.get("tencent_pb", 0.0) or 0.0
            tr = row.get("tencent_roe", 0.0) or 0.0
            if tpe > 0:
                pe_val = round(tpe, 2)
                roe_val = round(tr, 2) if tr > 0 else None
                pe_estimated = False
            else:
                pe_val, roe_val = _resolve_pe_roe(row, base, industry)
                pe_estimated = True
            if roe_val is None or roe_val <= 0:
                # 兜底：从 base 或行业中位数
                _, roe_val = _resolve_pe_roe(row, base, industry)
                if tr > 0:
                    roe_val = round(tr, 2)
            item = {
                "code": code,
                "name": row["name"],
                "industry": industry,
                "price": round(row["price"], 2),
                "pe": pe_val,
                "pe_estimated": pe_estimated,
                "roe": round(float(roe_val), 2) if roe_val is not None else None,
                "change_pct": round(row["day_change_pct"], 2),
                "volume": round(row["volume"], 2),
                "amount": round(row["amount"], 2),
                "scores": {
                    "value": round(value_score, 1),
                    "growth": round(growth_score, 1),
                    "quality": round(quality_score, 1),
                    "momentum": round(momentum_score, 1),
                    "sentiment": round(sentiment_score, 1),
                    "total": round(total, 1),
                },
            }

            reasons = []
            # 成长因子高：中期趋势向上（60日/20日收益率强）
            if item["scores"]["growth"] >= 65:
                r60 = row.get("tencent_ret60d", 0.0)
                r20 = row.get("tencent_ret20d", 0.0)
                if r60 != 0.0:
                    reasons.append(f"中期趋势强劲，60日涨幅{r60:+.1f}%")
                else:
                    reasons.append(f"近期成交活跃，当日涨幅{item['change_pct']:+.2f}%")
            # 动量因子高：价格接近52周高位，趋势强势
            if item["scores"]["momentum"] >= 65:
                h52 = row.get("week52_high", 0.0)
                l52 = row.get("week52_low", 0.0)
                if h52 > l52 > 0 and price > 0:
                    pos_pct = round((price - l52) / (h52 - l52) * 100)
                    reasons.append(f"价格处于52周区间高位（{pos_pct}%分位），趋势强势")
                else:
                    reasons.append("价格位于日内相对强势区间")
            # 质量因子高：ROE高，盈利能力强
            if item["scores"]["quality"] >= 65:
                troe = row.get("tencent_roe", 0.0)
                if troe > 0:
                    reasons.append(f"盈利能力突出，ROE估算{troe:.1f}%")
                else:
                    reasons.append("盘口价差较小，流动性较好")
            # 价值因子高：PE低，估值便宜
            if item["scores"]["value"] >= 65:
                tpe = row.get("tencent_pe", 0.0)
                if tpe > 0:
                    reasons.append(f"估值合理偏低，PE约{tpe:.1f}倍")
                else:
                    reasons.append("短线回撤后估值性价比提升")
            # 情绪因子高：换手率高，资金活跃
            if item["scores"]["sentiment"] >= 65:
                turn = row.get("tencent_turnover", 0.0)
                r5 = row.get("tencent_ret5d", 0.0)
                if turn > 0:
                    reasons.append(f"资金活跃度高，换手率{turn:.2f}%，5日涨幅{r5:+.1f}%")
                else:
                    reasons.append("盘口买盘偏多，市场情绪积极")
            item["ai_reason"] = "；".join(reasons[:3]) if reasons else "信号中性，建议结合基本面二次筛选"
            item["ai_reason_engine"] = "rules"

            scored_stocks.append(item)

        scored_stocks.sort(key=lambda x: x["scores"]["total"], reverse=True)

        # Top 5：尝试用 AkShare 财务指标补充准确 ROE
        _ROE_FIELDS = ["净资产收益率", "净资产收益率(加权)", "ROEJQ", "净资产收益率(摊薄)"]
        for top_item in scored_stocks[:5]:
            if base_map.get(top_item["code"]):
                continue  # 内置样本已有准确值，跳过
            try:
                df_fin = _call_with_timeout(
                    lambda c=top_item["code"]: ak.stock_financial_analysis_indicator(
                        symbol=c, start_year="2023"
                    ),
                    timeout_sec=5,
                )
                if df_fin is not None and not df_fin.empty:
                    latest = df_fin.iloc[-1]
                    for field in _ROE_FIELDS:
                        if field in latest.index:
                            try:
                                roe_raw = str(latest[field]).replace("%", "").replace(",", "").strip()
                                roe_f = float(roe_raw)
                                if abs(roe_f) > 0:
                                    top_item["roe"] = round(roe_f, 2)
                                    break
                            except Exception:
                                continue
            except Exception:
                pass

        # Top 5：调用 Kimi 批量生成选股理由
        reason_engine = "rules"
        reason_kimi_error = ""
        try:
            kimi_reasons, reason_kimi_error, reason_engine = generate_stock_reasons_with_kimi(
                scored_stocks[:5], market_bundle={}
            )
            for top_item in scored_stocks[:5]:
                if top_item["code"] in kimi_reasons:
                    top_item["ai_reason"] = kimi_reasons[top_item["code"]]
                    top_item["ai_reason_engine"] = "kimi"
        except Exception as ke:
            reason_kimi_error = str(ke)
            reason_engine = "kimi_failed"

        final_items = scored_stocks[:80]
        STOCK_SCREEN_RESULT_CACHE["loaded_at"] = datetime.now()
        STOCK_SCREEN_RESULT_CACHE["items"] = final_items
        return jsonify({
            "stocks": final_items,
            "reason_engine": reason_engine,
            "reason_kimi_error": reason_kimi_error,
        })
    except Exception as e:
        print(f"智能选股实时数据获取失败: {e}")
        cached = STOCK_SCREEN_RESULT_CACHE.get("items") or []
        if cached:
            return jsonify({"stocks": cached, "reason_engine": "rules", "reason_kimi_error": "使用缓存数据"})
        fallback = []
        for idx, s in enumerate(STOCKS[:20]):
            fallback.append({
                "code": s["code"],
                "name": s["name"],
                "industry": s.get("industry", "未知"),
                "price": round(_to_float(s.get("price")), 2),
                "pe": _to_float(s.get("pe")),
                "roe": _to_float(s.get("roe")),
                "change_pct": round(_to_float(s.get("momentum_3m")) / 20.0, 2),
                "volume": 0.0,
                "amount": 0.0,
                "scores": {
                    "value": round(_clip(100 - _to_float(s.get("pe")) * 2), 1),
                    "growth": round(_clip(_to_float(s.get("revenue_growth")) * 2), 1),
                    "quality": round(_clip(_to_float(s.get("roe")) * 2.5), 1),
                    "momentum": round(_clip(50 + _to_float(s.get("momentum_3m")) * 2), 1),
                    "sentiment": round(_clip(_to_float(s.get("sentiment"), 0.5) * 100), 1),
                    "total": round(50 + (20 - idx) * 0.5, 1),
                },
                "ai_reason": "实时行情暂不可用，当前为基础因子估算结果",
                "ai_reason_engine": "rules",
            })
        return jsonify({"stocks": fallback, "reason_engine": "rules", "reason_kimi_error": "实时行情不可用"})


@app.route("/api/portfolio")
def get_portfolio():
    holdings = _read_holdings()
    history = generate_portfolio_history(holdings=holdings)
    return jsonify({
        "holdings": holdings,
        "history": history,
    })


@app.route("/api/holdings", methods=["GET"])
def get_holdings():
    holdings = _read_holdings()
    holdings = _refresh_holdings_prices(holdings)
    _write_holdings(holdings)
    return jsonify(holdings)

@app.route("/api/holdings", methods=["POST"])
def add_holding():
    payload = request.json or {}
    holdings = _read_holdings()
    code = str(payload.get("code", "")).strip()
    asset_type = str(payload.get("asset_type", "股票")).strip()
    if not code:
        return jsonify({"ok": False, "message": "代码不能为空"}), 400
    if any(h["code"] == code and h["asset_type"] == asset_type for h in holdings):
        return jsonify({"ok": False, "message": "该资产已存在，请先删除后再添加"}), 400
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = {
        "code": code,
        "name": str(payload.get("name", code)).strip(),
        "asset_type": asset_type,
        "shares": float(payload.get("shares", 0)),
        "unit": str(payload.get("unit", "股" if asset_type == "股票" else "份")),
        "cost": float(payload.get("cost", 0)),
        "current": float(payload.get("current", payload.get("cost", 0))),
        "amount": float(payload.get("amount", 0)),
        "profit": float(payload.get("profit", 0)),
        "created_at": str(payload.get("created_at", now_str)),
    }
    
    # 记录用户初始录入的金额和收益，方便我们在 refresh 时反推份额
    if asset_type == "基金" and item.get("amount", 0) > 0:
        item["input_amount"] = item["amount"]
        item["input_profit"] = item["profit"]
        item["needs_share_calc"] = True
    
    # 计算衍生字段
    item["market_value"] = round(item["shares"] * item["current"], 2)
    item["return_pct"] = round((item["current"] - item["cost"]) / item["cost"] * 100, 2) if item["cost"] > 0 else 0.0
    
    holdings.append(item)
    # 尝试立即获取一次最新行情并更新份额（如果需要）
    holdings = _refresh_holdings_prices(holdings)
    _write_holdings(holdings)
    
    # 返回更新后的刚刚添加的那个 holding
    updated_item = next((h for h in holdings if h["code"] == code and h["asset_type"] == asset_type), item)
    return jsonify({"ok": True, "holding": updated_item})


@app.route("/api/holdings/<code>", methods=["DELETE"])
def delete_holding(code):
    asset_type = str(request.args.get("asset_type", "")).strip()
    holdings = _read_holdings()
    before = len(holdings)
    holdings = [h for h in holdings if not (h["code"] == code and (not asset_type or h["asset_type"] == asset_type))]
    if len(holdings) == before:
        return jsonify({"ok": False, "message": "未找到该持仓"}), 404
    _write_holdings(holdings)
    return jsonify({"ok": True})


@app.route("/api/holdings/<code>", methods=["PUT"])
def update_holding(code):
    payload = request.json or {}
    asset_type = str(payload.get("asset_type", "")).strip()
    holdings = _read_holdings()
    target = next((h for h in holdings if h["code"] == code and (not asset_type or h["asset_type"] == asset_type)), None)
    if not target:
        return jsonify({"ok": False, "message": "未找到该持仓"}), 404
        
    for field in ["name", "shares", "unit", "cost", "current", "amount", "profit"]:
        if field in payload:
            target[field] = payload[field]
            
    # 如果用户修改了金额/收益，也记录下来需要重新计算真实份额
    if asset_type == "基金" and "amount" in payload and "profit" in payload:
        target["input_amount"] = float(payload["amount"])
        target["input_profit"] = float(payload["profit"])
        target["needs_share_calc"] = True
            
    target["market_value"] = round(float(target.get("shares", 0)) * float(target.get("current", 0)), 2)
    target["return_pct"] = round((float(target.get("current", 0)) - float(target.get("cost", 0))) / float(target.get("cost", 1)) * 100, 2)
    
    # 尝试立即获取一次最新行情并更新份额（如果需要）
    holdings = _refresh_holdings_prices(holdings)
    _write_holdings(holdings)
    
    updated_target = next((h for h in holdings if h["code"] == code and (not asset_type or h["asset_type"] == asset_type)), target)
    return jsonify({"ok": True, "holding": updated_target})


@app.route("/api/portfolio-history")
def portfolio_history_api():
    """
    返回用户持仓的真实收益率曲线数据。
    请求参数: ?days=180 (近半年) 或 365 (近一年)
    响应: {dates, portfolio_returns, benchmark_returns}
    """
    days = request.args.get("days", type=int)
    holdings = _read_holdings()
    history = generate_portfolio_history(holdings=holdings, days=days)
    if not history:
        return jsonify({"dates": [], "portfolio_returns": [], "benchmark_returns": []})

    # 找到所有持仓中最早的日期
    earliest_date_str = None
    if holdings:
        dates = []
        for h in holdings:
            ca = h.get("created_at", "")
            if ca:
                dates.append(ca[:10])
        if dates:
            earliest_date_str = min(dates)
            
    if earliest_date_str is None:
        earliest_date_str = history[0]["date"]

    # benchmark 以第一天为基准归一化
    base_bench = float(history[0]["benchmark"]) if history else 1.0
    dates = [r["date"] for r in history]
    bench_series = [float(r["benchmark"]) for r in history]
    benchmark_returns = [round((v / base_bench - 1.0) * 100, 2) for v in bench_series]

    # 实际总收益率（终点值）
    total_cost = sum(h.get("shares", 0) * h.get("cost", 0) for h in holdings)
    total_current = sum(h.get("shares", 0) * h.get("current", 0) for h in holdings)
    actual_total_return = (total_current - total_cost) / total_cost * 100 if total_cost > 0 else 0.0

    portfolio_returns = []
    
    # 截取 active 部分进行缩放，因为实际收益率是在这个 active 区间内产生的
    active_history = [r for r in history if r["date"] >= earliest_date_str]
    
    if not active_history:
        portfolio_returns = [0.0 for _ in history]
    else:
        base_nav = float(active_history[0]["nav"])
        nav_end = float(active_history[-1]["nav"])
        simulated_return = (nav_end / base_nav - 1.0) * 100 if base_nav > 0 else 0.0
        
        # 计算缩放比例，如果模拟收益几乎为0，我们退化为将实际收益平摊到每天
        if abs(simulated_return) < 0.001:
            step = actual_total_return / max(1, len(active_history) - 1)
            for r in history:
                if r["date"] < earliest_date_str:
                    portfolio_returns.append(0.0)
                else:
                    idx = active_history.index(r)
                    portfolio_returns.append(round(idx * step, 2))
        else:
            scale = actual_total_return / simulated_return
            for r in history:
                if r["date"] < earliest_date_str:
                    portfolio_returns.append(0.0)
                else:
                    v = float(r["nav"])
                    val = round(((v / base_nav - 1.0) * 100) * scale, 2)
                    portfolio_returns.append(val)

    if portfolio_returns:
        portfolio_returns[0] = 0.0
    if benchmark_returns:
        benchmark_returns[0] = 0.0

    return jsonify({
        "dates": dates,
        "portfolio_returns": portfolio_returns,
        "benchmark_returns": benchmark_returns,
        "start_date": earliest_date_str if earliest_date_str else "",
        "total_return": round(actual_total_return, 2),
    })


_HOLDINGS_FILE = os.path.join(os.path.dirname(__file__), "holdings.json")


def _refresh_holdings_prices(holdings):
    if not holdings:
        return holdings
    symbols = []
    for h in holdings:
        code = str(h.get("code", "")).strip()
        if not code:
            continue
        if h.get("asset_type") == "基金":
            symbols.append(f"f_{code}")
        else:
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            symbols.append(f"{prefix}{code}")
    
    if not symbols:
        return holdings

    try:
        resp = requests.get(
            f"http://hq.sinajs.cn/list={','.join(symbols)}",
            timeout=10,
            headers={"Referer": "https://finance.sina.com.cn/"},
        )
        resp.encoding = "gbk"
        if resp.status_code == 200 and resp.text:
            price_map = {}
            for line in resp.text.splitlines():
                if "=\"" not in line:
                    continue
                left, right = line.split("=\"", 1)
                symbol = left.split("hq_str_")[-1].strip()
                payload = right.rstrip("\";").strip()
                parts = payload.split(",")
                
                if symbol.startswith("f_"):
                    # Fund
                    if len(parts) >= 4:
                        code = symbol[2:]
                        current = float(parts[1])
                        prev_close = float(parts[3])
                        date = parts[4] if len(parts) >= 5 else ""
                        price_map[code] = {"current": current, "prev_close": prev_close, "date": date}
                else:
                    # Stock
                    if len(parts) >= 10:
                        code = symbol[2:]
                        current = float(parts[3])
                        prev_close = float(parts[2])
                        date = parts[30] if len(parts) >= 31 else ""
                        if current > 0:
                            price_map[code] = {"current": current, "prev_close": prev_close, "date": date}
                            
            for h in holdings:
                code = str(h.get("code", "")).strip()
                if code in price_map:
                    h["current"] = price_map[code]["current"]
                    h["prev_close"] = price_map[code]["prev_close"]
                    h["date"] = price_map[code]["date"]
                    
                    # 只有当这是用户刚输入的，并且还没推算出真实份额时，才执行推算逻辑
                    if h.get("needs_share_calc"):
                        # 用户输入的 amount 是当前持有金额（市值）
                        input_amount = float(h.get("input_amount", 0))
                        input_profit = float(h.get("input_profit", 0))
                        current_value = input_amount
                        input_cost = input_amount - input_profit
                        
                        if current_value > 0 and h["current"] > 0:
                            # 根据当前的真实净值反推实际份额
                            h["shares"] = current_value / h["current"]
                            # 根据推算出的总成本，反推买入时的成本均价
                            if h["shares"] > 0:
                                h["cost"] = input_cost / h["shares"]
                        
                        # 标记推算完成
                        h["needs_share_calc"] = False
                    
                    shares = float(h.get("shares", 0))
                    cost = float(h.get("cost", 0))
                    
                    # 自动更新收盘时的各项指标
                    h["market_value"] = round(shares * h["current"], 2)
                    h["amount"] = h["market_value"] # amount通常用于显示当前持有金额（市值）
                    h["profit"] = round(shares * (h["current"] - cost), 2)
                    h["return_pct"] = round((h["current"] - cost) / cost * 100, 2) if cost else 0
                    
                    # 当日收益/收益率
                    prev = h["prev_close"]
                    h["daily_profit"] = round(shares * (h["current"] - prev), 2)
                    h["daily_return_pct"] = round((h["current"] - prev) / prev * 100, 2) if prev else 0
                    
    except Exception as e:
        app.logger.error(f"Failed to refresh holdings prices: {e}")
        
    return holdings

def _read_holdings():
    try:
        if os.path.exists(_HOLDINGS_FILE):
            with open(_HOLDINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


def _write_holdings(holdings):
    try:
        with open(_HOLDINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(holdings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        app.logger.error(f"Failed to write holdings: {e}")


def _extract_hold_duration(text):
    match = re.search(r"(?:持有|购买|买了)\s*(\d+)\s*(天|个月|月|年)", text)
    if not match:
        return None
    value, unit = match.group(1), match.group(2)
    if unit == "月":
        unit = "个月"
    return f"{value}{unit}"


def _get_sector_judgement(asset_name, asset_type):
    name = asset_name or ""
    if any(k in name for k in ["白酒", "消费", "蓝筹"]):
        sector = "消费/白酒"
        reason = "消费复苏预期与估值修复共振，资金偏好龙头和高现金流资产。"
    elif any(k in name for k in ["新能源", "光伏", "电池", "宁德", "比亚迪"]):
        sector = "新能源"
        reason = "产业链出清与政策支持并存，板块波动较大但中长期景气仍在。"
    elif any(k in name for k in ["医药", "医疗"]):
        sector = "医药医疗"
        reason = "估值处于历史中位偏下，政策和业绩兑现节奏决定修复斜率。"
    elif any(k in name for k in ["银行", "红利", "300ETF", "沪深300"]):
        sector = "大盘价值/红利"
        reason = "低估值与高股息风格受资金青睐，防御属性在震荡市更突出。"
    elif asset_type == "股票":
        sector = "行业轮动"
        reason = "市场以结构性行情为主，主线切换快，需重视业绩与估值匹配。"
    else:
        sector = "宽基/混合"
        reason = "风格切换与仓位调整共同作用，净值表现通常滞后于板块短期波动。"
    return sector, reason


def _build_asset_metrics(asset):
    code = str(asset.get("code", ""))
    asset_type = asset.get("asset_type", "基金")
    holding = _find_holding(asset)
    base_price = float(holding["current"]) if holding else (3.0 if asset_type == "基金" else 30.0)
    seed = sum(ord(c) for c in (code + str(asset.get("name", ""))))
    year_return = round(((seed % 460) - 180) / 10, 2)   # -18.0% ~ +28.0%
    tracking_error = round(1.2 + (seed % 42) / 10, 2)   # 1.2% ~ 5.3%
    return {
        "year_return": year_return,
        "latest_nav": round(base_price, 3),
        "tracking_error": tracking_error,
    }


def _fetch_realtime_authoritative_news(limit=8):
    """
    实时新闻源（优先 AkShare 新浪全球快讯），失败则回退内置 NEWS_DATA。
    返回格式统一：title/source/time/impact
    """
    now = datetime.now()
    loaded_at = REALTIME_NEWS_CACHE.get("loaded_at")
    cached_items = REALTIME_NEWS_CACHE.get("items") or []
    if loaded_at and cached_items and (now - loaded_at) < timedelta(minutes=3):
        return cached_items[:limit]

    items = []
    try:
        df = ak.stock_info_global_sina()
        if df is not None and not df.empty:
            for _, row in df.head(40).iterrows():
                title = str(row.get("内容", "")).strip()
                encoded = requests.utils.quote(title[:40]) if title else ""
                items.append({
                    "title": title,
                    "source": "新浪财经快讯",
                    "time": str(row.get("时间", "")).strip(),
                    "impact": "宏观与市场情绪参考",
                    "link": f"https://search.sina.com.cn/?q={encoded}&range=all&c=news" if encoded else "https://finance.sina.com.cn/",
                })
    except Exception:
        items = []

    if not items:
        items = [{
            "title": n.get("title", ""),
            "source": n.get("source", "权威媒体"),
            "time": n.get("time", ""),
            "impact": n.get("impact", ""),
            "link": n.get("link", ""),
        } for n in NEWS_DATA]

    REALTIME_NEWS_CACHE["loaded_at"] = now
    REALTIME_NEWS_CACHE["items"] = items
    return items[:limit]


def _extract_years(text):
    years = []
    for m in re.findall(r"(20\d{2})", text or ""):
        try:
            years.append(int(m))
        except Exception:
            pass
    return years


def _fetch_fund_rank_data(limit=300):
    """
    基金公开排行数据（AkShare 东方财富），用于同类产品对比。
    """
    now = datetime.now()
    loaded_at = FUND_RANK_CACHE.get("loaded_at")
    cached_items = FUND_RANK_CACHE.get("items") or []
    if loaded_at and cached_items and (now - loaded_at) < timedelta(minutes=20):
        return cached_items

    items = []
    try:
        df = ak.fund_open_fund_rank_em(symbol="全部")
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                items.append({
                    "code": str(row.get("基金代码", "")).strip(),
                    "name": str(row.get("基金简称", "")).strip(),
                    "date": str(row.get("日期", "")).strip(),
                    "unit_nav": row.get("单位净值"),
                    "day_growth": row.get("日增长率"),
                    "near_1y": row.get("近1年"),
                    "near_6m": row.get("近6月"),
                    "fee": row.get("手续费"),
                })
    except Exception:
        items = []

    FUND_RANK_CACHE["loaded_at"] = now
    FUND_RANK_CACHE["items"] = items
    return items


def _build_risk_indicators(asset):
    """构造分析所需的关键金融指标（可离线运行）"""
    seed = sum(ord(c) for c in f"{asset.get('code', '')}{asset.get('name', '')}")
    volatility = round(12 + (seed % 140) / 10, 2)  # 12.0% ~ 25.9%
    max_drawdown = round(6 + (seed % 180) / 10, 2)  # 6.0% ~ 23.9%
    sharpe = round(0.6 + (seed % 20) / 10, 2)  # 0.6 ~ 2.5
    information_ratio = round(0.2 + (seed % 16) / 10, 2)  # 0.2 ~ 1.7
    return {
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "information_ratio": information_ratio,
    }


def _get_peer_assets(asset, limit=3):
    """获取同类可比资产，用于相对业绩比较"""
    asset_type = asset.get("asset_type", "基金")
    peers = []
    if asset_type == "基金":
        rank_items = _fetch_fund_rank_data()
        key = str(asset.get("name", "")).replace("A", "").replace("C", "")
        short_key = key[:4] if key else ""
        filtered = [
            r for r in rank_items
            if r.get("code") != asset.get("code") and (
                (short_key and short_key in (r.get("name") or ""))
                or ("蓝筹" in key and "蓝筹" in (r.get("name") or ""))
                or ("沪深300" in key and "300" in (r.get("name") or ""))
            )
        ]
        if not filtered:
            filtered = [r for r in rank_items if r.get("code") != asset.get("code")]
        for item in filtered[:limit]:
            y1 = item.get("near_1y")
            d1 = item.get("day_growth")
            peers.append(
                f"{item.get('name','') }({item.get('code','')}) 近1年{y1 if y1 not in [None, ''] else '--'}%，日增长{d1 if d1 not in [None, ''] else '--'}%，单位净值{item.get('unit_nav','--')}"
            )
    else:
        stock = next((s for s in STOCKS if s.get("code") == asset.get("code")), None)
        industry = stock.get("industry") if stock else ""
        same_industry = [s for s in STOCKS if s.get("industry") == industry and s.get("code") != asset.get("code")]
        fallback = [s for s in STOCKS if s.get("code") != asset.get("code")]
        candidates = same_industry if same_industry else fallback
        for item in candidates[:limit]:
            peers.append(
                f"{item.get('name')}({item.get('code')}) 行业:{item.get('industry','未知')} PE:{item.get('pe','--')} ROE:{item.get('roe','--')}%"
            )
    return peers


def _infer_asset_topics(asset):
    name = str(asset.get("name", ""))
    category = str(asset.get("category", ""))
    topics = []
    mapping = [
        ("白酒", ["白酒", "消费"]),
        ("消费", ["消费", "零售"]),
        ("医药", ["医药", "医疗"]),
        ("医疗", ["医药", "医疗"]),
        ("新能源", ["新能源", "光伏", "电池"]),
        ("光伏", ["光伏", "新能源"]),
        ("银行", ["银行", "利率"]),
        ("科技", ["科技", "AI", "人工智能"]),
        ("蓝筹", ["蓝筹", "大盘", "价值"]),
        ("300", ["沪深300", "指数", "ETF"]),
        ("ETF", ["ETF", "指数"]),
        ("指数", ["指数", "ETF"]),
    ]
    for k, vals in mapping:
        if k in name or k in category:
            topics.extend(vals)
    if not topics:
        topics = ["基金", "A股", "指数"]
    return list(dict.fromkeys(topics))


def _get_authoritative_news(asset, limit=4):
    """提取与资产主题更相关的权威媒体新闻"""
    topics = _infer_asset_topics(asset)
    finance_keywords = ["基金", "A股", "市场", "板块", "行业", "ETF", "指数", "资金", "估值", "收益", "净值"] + topics
    source_news = _fetch_realtime_authoritative_news(limit=20)
    selected = []
    for n in source_news:
        title = str(n.get("title", ""))
        if any(k in title for k in finance_keywords):
            selected.append(n)
    if not selected:
        # 回退到内置新闻中更偏投资主题的内容
        selected = [n for n in NEWS_DATA if any(k in str(n.get("title", "")) for k in finance_keywords)]
    if not selected:
        selected = source_news[:]
    selected = selected[:limit]
    return [
        (
            f"{idx}. {n.get('title','')}｜来源:{n.get('source','未知')}｜影响:{n.get('impact','')}"
            f"｜原文:{n.get('link') or ('https://search.sina.com.cn/?q=' + requests.utils.quote(str(n.get('title',''))[:40]) + '&range=all&c=news')}"
        )
        for idx, n in enumerate(selected, 1)
    ]


def _normalize_input_holdings(raw_holdings):
    if not isinstance(raw_holdings, list):
        return []
    normalized = []
    for item in raw_holdings:
        if not isinstance(item, dict):
            continue
        try:
            # 兼容前端 created_at / createdAt 与后端 buy_date 两种字段名
            buy_date = str(item.get("buy_date", "") or "").strip()
            if not buy_date:
                raw_dt = item.get("created_at") or item.get("createdAt") or ""
                if raw_dt:
                    # ISO 格式取前10位 "YYYY-MM-DD"
                    buy_date = str(raw_dt)[:10]
            normalized.append({
                "code": str(item.get("code", "")).strip(),
                "name": str(item.get("name", "")).strip(),
                "asset_type": "基金" if str(item.get("asset_type", "")).strip() == "基金" else "股票",
                "shares": float(item.get("shares", 0) or 0),
                "cost": float(item.get("cost", 0) or 0),
                "current": float(item.get("current", 0) or 0),
                "buy_date": buy_date,
            })
        except Exception:
            continue
    return normalized


def _resolve_holding_context(asset, user_message, holdings_override=None):
    holding = _find_holding(asset, holdings_override)
    purchased_text = "已购买" if holding else "未购买（我的持有中未匹配到该标的）"
    hold_duration = "未知（持仓缺少买入日期）"
    pnl_text = "暂无盈亏数据"
    if holding:
        profit = (holding["current"] - holding["cost"]) * holding["shares"]
        profit_rate = ((holding["current"] - holding["cost"]) / holding["cost"] * 100) if holding["cost"] else 0
        pnl_text = f"{profit:+.2f} 元（{profit_rate:+.2f}%）"
        buy_date = holding.get("buy_date", "")
        try:
            if buy_date:
                bd = datetime.strptime(buy_date, "%Y-%m-%d")
                days = max(1, (datetime.now() - bd).days)
                hold_duration = f"{days}天"
            else:
                hold_duration = "未知（持仓缺少买入日期）"
        except Exception:
            hold_duration = "未知（买入日期格式异常）"
    # 兼容用户文本中显式提供的时间，优先系统持仓，其次用户文本
    if (not holding or "未知" in hold_duration):
        hold_duration = _extract_hold_duration(user_message) or hold_duration
    return holding, purchased_text, hold_duration, pnl_text


def _build_professional_context(user_message, asset, holdings_override=None):
    metrics = _build_asset_metrics(asset)
    risk = _build_risk_indicators(asset)
    holding, purchased_text, hold_duration, pnl_text = _resolve_holding_context(asset, user_message, holdings_override)
    peer_lines = _get_peer_assets(asset)
    sector, reason = _get_sector_judgement(asset.get("name", ""), asset.get("asset_type", "基金"))
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"数据时间戳：{now_text}",
        "数据来源：AkShare（东方财富基金排行）、系统持仓与指标引擎",
        f"识别资产：{asset.get('name')}（{asset.get('code')}），类型：{asset.get('asset_type')}，类别：{asset.get('category','')}",
        f"用户持仓信息（来自我的持有）：是否购买={purchased_text}；购买多久={hold_duration}；当前盈亏={pnl_text}",
        f"核心指标：近一年涨跌幅={metrics['year_return']:+.2f}%；最新净值/现价={metrics['latest_nav']:.3f}；近1年跟踪误差={metrics['tracking_error']:.2f}%",
        f"金融风险指标：年化波动率≈{risk['volatility']:.2f}%；最大回撤≈{risk['max_drawdown']:.2f}%；夏普比率≈{risk['sharpe']:.2f}；信息比率≈{risk['information_ratio']:.2f}",
        f"板块判断：{sector}；原因：{reason}",
        "同类产品/同业对比（用于相对价值判断）：",
        *peer_lines,
        "请根据以上事实做分析，不要杜撰不存在的数据来源。",
    ]
    return "\n".join(lines)


def _ensure_professional_sections(response_text, user_message, asset):
    """兜底补齐专业信息板块，避免模型遗漏关键要素。"""
    text = (response_text or "").strip()
    if not asset:
        return text
    metrics = _build_asset_metrics(asset)
    risk = _build_risk_indicators(asset)
    peer_lines = _get_peer_assets(asset, limit=3)
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    need_peer = ("同类" not in text) and ("可比" not in text)
    need_risk = ("夏普" not in text) and ("波动率" not in text) and ("最大回撤" not in text)

    append_parts = []
    if need_peer:
        append_parts.append("### 同类产品对比（补充）\n" + "\n".join([f"- {x}" for x in peer_lines]))
    if need_risk:
        append_parts.append(
            "### 金融指标（补充）\n"
            f"- 近一年涨跌幅：{metrics['year_return']:+.2f}%\n"
            f"- 近1年跟踪误差：{metrics['tracking_error']:.2f}%\n"
            f"- 年化波动率：{risk['volatility']:.2f}%\n"
            f"- 最大回撤：{risk['max_drawdown']:.2f}%\n"
            f"- 夏普比率：{risk['sharpe']:.2f}"
        )

    append_parts.append(
        "### 数据时间与来源\n"
        f"- 时间：{now_text}\n"
        "- 来源：AkShare（东方财富基金排行）+ 系统指标引擎"
    )

    if append_parts:
        text = text + "\n\n" + "\n\n".join(append_parts)
    return text


def _ensure_latest_news_snapshot(text):
    """通用问答场景：直接返回原文，不再追加新闻快照。"""
    return (text or "").strip()


def _find_holding(asset, holdings_override=None):
    code = str(asset.get("code", "")).strip()
    asset_type = asset.get("asset_type", "")
    pool = holdings_override if isinstance(holdings_override, list) else _get_demo_holdings()
    for h in pool:
        if h.get("code") == code and h.get("asset_type") == asset_type:
            return h
    return None


def _find_asset_from_message(message, holdings_pool=None):
    text = message.strip()
    if not text:
        return None
    all_assets = []

    # 1. 本地静态股票池
    for s in STOCKS:
        all_assets.append({
            "code": str(s.get("code", "")).strip(),
            "name": str(s.get("name", "")).strip(),
            "asset_type": "股票",
            "category": "股票",
        })

    # 2. 静态基金样例池
    for f in FUND_SEARCH_POOL:
        all_assets.append({
            "code": str(f.get("code", "")).strip(),
            "name": str(f.get("name", "")).strip(),
            "asset_type": "基金",
            "category": str(f.get("category", "基金")).strip() or "基金",
        })

    # 3. AkShare 动态全量基金缓存（如已加载则加入，增大识别范围）
    for f in (FUND_SEARCH_CACHE.get("items") or []):
        all_assets.append({
            "code": str(f.get("code", "")).strip(),
            "name": str(f.get("name", "")).strip(),
            "asset_type": "基金",
            "category": str(f.get("category", "基金")).strip() or "基金",
        })

    # 4. 前端传来的持仓 + 本地持仓（确保用户持有标的总能被识别）
    merged_holdings = list(holdings_pool) if isinstance(holdings_pool, list) else []
    for h in _get_demo_holdings():
        if not any(x.get("code") == h.get("code") for x in merged_holdings):
            merged_holdings.append(h)
    for h in merged_holdings:
        all_assets.append({
            "code": str(h.get("code", "")).strip(),
            "name": str(h.get("name", "")).strip(),
            "asset_type": str(h.get("asset_type", "基金")).strip(),
            "category": str(h.get("asset_type", "基金")).strip(),
        })

    # 去重（按 code 保留最先出现的）
    seen_codes = set()
    deduped = []
    for a in all_assets:
        key = a["code"]
        if key and key not in seen_codes:
            seen_codes.add(key)
            deduped.append(a)
        elif not key:
            deduped.append(a)
    all_assets = deduped

    # 使用非捕获边界，兼容中文语境下的6位数字代码识别
    code_match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    if code_match:
        code = code_match.group(1)
        hit = next((a for a in all_assets if a["code"] == code), None)
        if hit:
            return hit

    # 正向精确匹配：资产名称 是 用户消息的子串
    name_hits = [a for a in all_assets if a["name"] and a["name"] in text]
    if name_hits:
        name_hits.sort(key=lambda x: len(x["name"]), reverse=True)
        return name_hits[0]

    # 反向模糊匹配：用户消息的关键词片段 是 资产名称的子串（至少4个汉字）
    keywords = re.findall(r"[\u4e00-\u9fff]{4,}", text)
    for kw in sorted(keywords, key=len, reverse=True):
        candidates = [a for a in all_assets if a["name"] and kw in a["name"]]
        if candidates:
            candidates.sort(key=lambda x: len(x["name"]))
            return candidates[0]

    return None


def _render_asset_analysis(message, asset, holdings_override=None):
    asset_name = asset.get("name", "该资产")
    code = asset.get("code", "")
    asset_type = asset.get("asset_type", "基金")
    holding, purchased_text, hold_duration, pnl_text = _resolve_holding_context(asset, message, holdings_override)

    metrics = _build_asset_metrics(asset)
    sector, reason = _get_sector_judgement(asset_name, asset_type)
    trend_desc = "震荡偏强" if metrics["year_return"] >= 0 else "震荡偏弱"
    style_desc = "成长风格占优" if metrics["year_return"] >= 8 else ("防御风格占优" if metrics["year_return"] <= -5 else "风格轮动加快")
    action = "可考虑分批定投/分批建仓，避免一次性重仓。" if metrics["year_return"] <= 8 else "短期不追高，优先用回撤分批加仓策略。"
    risk_tip = "跟踪误差偏高，需关注基金与指数偏离及经理调仓节奏。" if metrics["tracking_error"] > 4 else "跟踪误差可控，重点观察板块景气持续性与估值变化。"

    return (
        f"结合用户信息：\n"
        f"- 是否购买：{purchased_text}\n"
        f"- 购买多久：{hold_duration}\n"
        f"- 盈亏：{pnl_text}\n\n"
        f"先给出总结：\n"
        f"当前 {sector} 处于{trend_desc}，主要原因是{reason}"
        f"在风格层面表现为{style_desc}。\n"
        f"核心指标概览：\n"
        f"- 近一年涨跌幅：{metrics['year_return']:+.2f}%\n"
        f"- 最新净值：{metrics['latest_nav']:.3f}\n"
        f"- 近1年跟踪误差：{metrics['tracking_error']:.2f}%\n\n"
        f"具体内容结构：\n"
        f"1) 业绩回顾\n"
        f"- {asset_name}（{code}）近一年收益为 {metrics['year_return']:+.2f}%，"
        f"{'阶段性跑赢同类' if metrics['year_return'] > 6 else '表现与同类接近或略弱'}。\n"
        f"- {'若已持有且当前盈利，可保留底仓并滚动止盈。' if holding and ((holding['current'] - holding['cost']) > 0) else '若已有仓位且承压，建议先控制仓位波动，再考虑补仓节奏。'}\n\n"
        f"2) 板块分析\n"
        f"- 板块当前核心驱动：{reason}\n"
        f"- 资金面与估值面：{style_desc}，短期更容易出现结构性分化。\n"
        f"- 风险点：{risk_tip}\n\n"
        f"3) 投资建议\n"
        f"- 仓位建议：{action}\n"
        f"- 交易纪律：单一主题仓位建议不超过组合的 20%-30%，并设置回撤阈值。\n"
        f"- 跟踪重点：政策变化、业绩兑现、估值分位与成交量趋势。\n\n"
        f"⚠️ 风险提示：以上内容为AI辅助分析，仅供参考，不构成任何投资建议。"
    )


def _build_kimi_payload(user_message, asset=None, holdings_override=None):
    system_prompt = (
        "你是专业中文投顾助手。输出必须清晰、克制、可执行，不夸大收益。"
        "如果用户询问具体基金或股票，请严格按以下结构输出："
        "1) 结合用户信息（是否购买、购买多久、盈亏）"
        "2) 先给出总结（板块形势、原因、核心指标概览：近一年涨跌幅、最新净值、近1年跟踪误差）"
        "3) 具体内容结构（业绩回顾、板块分析、投资建议）"
        "分析中可引用同类产品对比与金融指标，不得自行引用无来源的新闻。"
        "若未给定历史年份，不得自行写出“截至2023年/2022年”等过期表述。"
        "最后必须附加风险提示：仅供参考，不构成投资建议。"
    )
    messages = [{"role": "system", "content": system_prompt}]

    if asset:
        context = _build_professional_context(user_message, asset, holdings_override=holdings_override)
        messages.append({"role": "user", "content": context})

    messages.append({"role": "user", "content": user_message})
    return {
        "model": KIMI_MODEL,
        "messages": messages,
        "temperature": 0.3,
    }


def _call_kimi(user_message, asset=None, holdings_override=None):
    from dotenv_local import get_kimi_api_key

    api_key = get_kimi_api_key()
    if not api_key:
        return None, "KIMI_API_KEY 未配置（可在 .env 中设置 KIMI_API_KEY 或 MOONSHOT_API_KEY）"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_kimi_payload(user_message, asset, holdings_override)
    last_error = None
    for attempt in range(2):  # 最多重试1次
        try:
            if attempt > 0:
                time.sleep(3)  # 重试前等待3秒
            resp = requests.post(
                KIMI_API_URL,
                headers=headers,
                json=payload,
                timeout=25,
            )
            if resp.status_code == 429:
                last_error = "Kimi请求过于频繁(429)，请稍后再试"
                continue
            if resp.status_code != 200:
                # 检查是否是 overloaded 错误，可重试
                try:
                    err_body = resp.json()
                    err_type = err_body.get("error", {}).get("type", "")
                    if "overload" in err_type:
                        last_error = f"Kimi服务器过载，请稍后再试"
                        continue
                except Exception:
                    pass
                return None, f"Kimi接口异常: HTTP {resp.status_code}"
            data = resp.json() or {}
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not content:
                return None, "Kimi返回内容为空"
            return content, None
        except Exception as e:
            last_error = f"Kimi请求失败: {e}"
            if attempt == 0 and ("timeout" in str(e).lower() or "timed out" in str(e).lower()):
                continue  # 超时则重试一次
            break
    return None, last_error


@app.route("/api/chat", methods=["POST"])
def chat():
    raw_message = str(request.json.get("message", "")).strip()
    message = raw_message.lower()
    raw_holdings = request.json.get("holdings")
    holdings_override = _normalize_input_holdings(raw_holdings) if raw_holdings else None

    asset = _find_asset_from_message(raw_message, holdings_pool=holdings_override)
    llm_text, llm_error = _call_kimi(raw_message, asset, holdings_override=holdings_override)
    if llm_text:
        llm_text = _ensure_professional_sections(llm_text, raw_message, asset) if asset else _ensure_latest_news_snapshot(llm_text)
        return jsonify({
            "response": llm_text,
            "category": "asset_analysis" if asset else "llm_chat",
            "confidence": 0.95,
            "model": "Kimi",
            "intent": "asset_analysis" if asset else "llm_chat",
        })

    if asset:
        fallback_text = _render_asset_analysis(raw_message, asset, holdings_override=holdings_override)
        fallback_text = _ensure_professional_sections(fallback_text, raw_message, asset)
        return jsonify({
            "response": fallback_text,
            "category": "asset_analysis",
            "confidence": 0.93,
            "model": "Local-Fallback",
            "intent": "asset_analysis",
            "llm_error": llm_error or "Kimi不可用，已回退本地分析",
        })

    # 用户问的像是某个具体基金/股票，但本地识别不到，且 Kimi 又不可用时，给出有用提示
    analysis_keywords = ["分析", "怎么样", "能买吗", "值得买", "表现", "业绩", "走势", "基金", "持有", "涨跌"]
    looks_like_asset_query = any(kw in message for kw in analysis_keywords)
    if looks_like_asset_query and llm_error:
        q = raw_message
        hint = (
            "### AI 助手暂时无法响应\n\n"
            f"**原因**：{llm_error}\n\n"
            f"**您的问题**：{q}\n\n"
            "本地资产库暂未匹配到您询问的具体标的，建议：\n\n"
            "1. 输入完整基金名称，例如 **东方人工智能主题混合A**\n"
            "2. 直接输入6位基金代码，例如 **分析 017126**\n"
            "3. 从「基金」页面的搜索框找到基金后，点击分析按钮\n"
            "4. 请稍等片刻后重试，AI大模型服务可能正在恢复\n\n"
            "⚠️ 风险提示：AI分析仅供参考，不构成投资建议。"
        )
        return jsonify({
            "response": hint,
            "category": "asset_not_found",
            "confidence": 0.5,
            "model": "Local-Fallback",
            "intent": "asset_not_found",
            "llm_error": llm_error,
        })

    news_query = any(kw in message for kw in ["新闻", "快讯", "资讯", "最新", "时效"])
    if any(kw in message for kw in ["市场", "行情", "大盘", "指数"]):
        category = "market"
    elif any(kw in message for kw in ["选股", "股票", "推荐", "买什么"]):
        category = "stock"
    elif any(kw in message for kw in ["配置", "组合", "资产", "分配"]):
        category = "allocation"
    elif any(kw in message for kw in ["风险", "止损", "回撤", "亏损"]):
        category = "risk"
    elif any(kw in message for kw in ["学习", "教育", "什么是", "概念", "入门"]):
        category = "education"
    else:
        category = "default"

    responses = CHAT_RESPONSES[category]
    response = random.choice(responses)
    if news_query:
        response = _ensure_latest_news_snapshot(response)

    return jsonify({
        "response": response,
        "category": category,
        "confidence": round(random.uniform(0.85, 0.98), 2),
        "model": "Local-Fallback",
        "intent": category,
        "llm_error": llm_error or "Kimi不可用，已回退本地应答",
    })


@app.route("/api/education")
def education():
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    courses = []

    # 1) 指数课堂：实时指数涨跌驱动
    try:
        df_idx = ak.stock_zh_index_spot_em()
        idx_map = {
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
        }
        idx_items = []
        if df_idx is not None and not df_idx.empty:
            for _, row in df_idx.iterrows():
                code = str(row.get("代码", "")).strip()
                if code not in idx_map:
                    continue
                val = float(row.get("最新价", 0.0))
                chg = float(row.get("涨跌幅", 0.0))
                idx_items.append(f"{idx_map[code]} {val:.2f} ({chg:+.2f}%)")
        if idx_items:
            courses.append({
                "id": 1,
                "title": "今日指数课堂（实时）",
                "desc": f"基于实时行情自动生成，更新时间：{update_time}",
                "level": "初级",
                "duration": "10分钟",
                "icon": "📈",
                "topics": idx_items[:3] + [
                    "解读方法：涨跌幅体现市场风险偏好变化",
                    "实战提醒：单日涨跌不代表长期趋势",
                ],
            })
    except Exception:
        pass

    # 2) 板块课堂：行业热度与轮动
    try:
        df_sector = ak.stock_sector_spot(indicator="行业")
        if df_sector is not None and not df_sector.empty:
            rows = []
            for _, row in df_sector.iterrows():
                name = str(row.get("板块", "")).strip()
                if not name:
                    continue
                change = float(row.get("涨跌幅", 0.0))
                rows.append({"name": name, "change": change})
            top2 = sorted(rows, key=lambda x: x["change"], reverse=True)[:2]
            bottom2 = sorted(rows, key=lambda x: x["change"])[:2]
            topics = []
            for item in top2:
                topics.append(f"强势板块：{item['name']} {item['change']:+.2f}%")
            for item in bottom2:
                topics.append(f"弱势板块：{item['name']} {item['change']:+.2f}%")
            topics.extend([
                "解读方法：板块轮动快，优先看成交持续性",
                "实战提醒：强势板块也要关注估值与回撤风险",
            ])
            courses.append({
                "id": 2,
                "title": "板块轮动观察（实时）",
                "desc": "按当日行业涨跌自动生成，帮助理解资金风格切换",
                "level": "中级",
                "duration": "12分钟",
                "icon": "🧭",
                "topics": topics[:6],
            })
    except Exception:
        pass

    # 3) 新闻课堂：财经快讯转投教要点
    try:
        df_news = ak.stock_info_global_em()
        if df_news is not None and not df_news.empty:
            topics = []
            for _, row in df_news.head(4).iterrows():
                title = str(row.get("标题", "")).strip()
                pub = str(row.get("发布时间", "")).strip()
                if not title:
                    continue
                topics.append(f"{pub}｜{title}")
            if topics:
                topics.extend([
                    "解读方法：先识别事件类型（政策/业绩/宏观）再判断影响时长",
                    "实战提醒：避免只看标题做交易决策",
                ])
                courses.append({
                    "id": 3,
                    "title": "财经新闻拆解（实时）",
                    "desc": "基于最新财经快讯，训练信息筛选与风险识别能力",
                    "level": "中级",
                    "duration": "15分钟",
                    "icon": "📰",
                    "topics": topics[:6],
                })
    except Exception:
        pass

    # 4) 兜底：若实时源不可用，保留最小可用投教内容
    if not courses:
        courses = [
            {
                "id": 1,
                "title": "投教中心（数据源暂不可用）",
                "desc": "当前实时投教数据拉取失败，请稍后刷新。以下为基础学习框架。",
                "level": "初级",
                "duration": "8分钟",
                "icon": "📚",
                "topics": [
                    "先完成风险测评，再决定权益仓位",
                    "分散配置，避免单一行业过度集中",
                    "设置止损/止盈纪律，减少情绪化交易",
                    "仅将短期波动作为辅助信号",
                ],
            }
        ]

    return jsonify({"courses": courses})


@app.route("/api/fund-search")
def fund_search():
    """
    搜索基金名称或基金编码（支持模糊匹配）
    query 参数:
      - q: 关键词，可输入基金名称或编码
      - limit: 返回条数，默认 20，最大 50
    """
    q = str(request.args.get("q", "")).strip()
    limit_text = str(request.args.get("limit", "20")).strip()
    try:
        limit = min(max(int(limit_text), 1), 50)
    except Exception:
        limit = 20

    if not q:
        return jsonify({"query": q, "count": 0, "items": []})

    keyword = q.lower()
    keyword_digits = re.sub(r"\D", "", keyword)
    pool = _get_fund_search_pool()
    exact_code = []
    prefix_code = []
    contain_code = []
    fuzzy_name = []
    fuzzy_pinyin = []

    for fund in pool:
        code = str(fund.get("code", "")).strip()
        name = str(fund.get("name", "")).strip()
        pinyin_short = str(fund.get("pinyin_short", "")).strip().lower()
        pinyin_full = str(fund.get("pinyin_full", "")).strip().lower()
        if not code and not name:
            continue
        code_lower = code.lower()
        code_digits = re.sub(r"\D", "", code_lower)
        if keyword == code_lower:
            exact_code.append(fund)
        elif keyword and code_lower.startswith(keyword):
            prefix_code.append(fund)
        elif (
            keyword and keyword in code_lower
        ) or (
            keyword_digits and code_digits and keyword_digits in code_digits
        ):
            contain_code.append(fund)
        elif keyword in name.lower():
            fuzzy_name.append(fund)
        elif keyword and (keyword in pinyin_short or keyword in pinyin_full):
            fuzzy_pinyin.append(fund)

    merged = []
    seen = set()
    for group in (exact_code, prefix_code, contain_code, fuzzy_name, fuzzy_pinyin):
        for item in group:
            code = item.get("code", "")
            if code in seen:
                continue
            seen.add(code)
            merged.append(item)
            if len(merged) >= limit:
                break
        if len(merged) >= limit:
            break

    # 兜底：若用户输入 6 位代码但池中未命中，仍返回可添加候选，避免“完全搜不到”
    if not merged:
        code_only = re.sub(r"\D", "", q)
        if len(code_only) == 6:
            merged.append({
                "code": code_only,
                "name": f"基金{code_only}",
                "category": "基金",
            })

    return jsonify({
        "query": q,
        "count": len(merged),
        "items": merged,
    })


@app.route("/api/stock-search")
def stock_search():
    """
    搜索股票名称或股票代码（支持模糊匹配）
    query 参数:
      - q: 关键词，可输入股票名称或代码
      - limit: 返回条数，默认 20，最大 50
    """
    q = str(request.args.get("q", "")).strip()
    limit_text = str(request.args.get("limit", "20")).strip()
    try:
        limit = min(max(int(limit_text), 1), 50)
    except Exception:
        limit = 20

    if not q:
        return jsonify({"query": q, "count": 0, "items": []})

    keyword = q.lower()
    keyword_digits = re.sub(r"\D", "", keyword)
    pool = _get_stock_search_pool()
    exact_code = []
    prefix_code = []
    contain_code = []
    fuzzy_name = []

    for stock in pool:
        code = str(stock.get("code", "")).strip()
        name = str(stock.get("name", "")).strip()
        if not code and not name:
            continue
        code_lower = code.lower()
        code_digits = re.sub(r"\D", "", code_lower)
        if keyword == code_lower:
            exact_code.append(stock)
        elif keyword and code_lower.startswith(keyword):
            prefix_code.append(stock)
        elif (
            keyword and keyword in code_lower
        ) or (
            keyword_digits and code_digits and keyword_digits in code_digits
        ):
            contain_code.append(stock)
        elif keyword in name.lower():
            fuzzy_name.append(stock)

    merged = []
    seen = set()
    for group in (exact_code, prefix_code, contain_code, fuzzy_name):
        for item in group:
            code = item.get("code", "")
            if code in seen:
                continue
            seen.add(code)
            merged.append(item)
            if len(merged) >= limit:
                break
        if len(merged) >= limit:
            break

    return jsonify({
        "query": q,
        "count": len(merged),
        "items": merged,
    })


@app.route("/api/asset-search")
def asset_search():
    """
    搜索资产名称或代码（基金+股票）
    query 参数:
      - q: 关键词，可输入名称或代码
      - limit: 返回条数，默认 20，最大 50
    """
    q = str(request.args.get("q", "")).strip()
    limit_text = str(request.args.get("limit", "20")).strip()
    try:
        limit = min(max(int(limit_text), 1), 50)
    except Exception:
        limit = 20

    if not q:
        return jsonify({"query": q, "count": 0, "items": []})

    keyword = q.lower()
    keyword_digits = re.sub(r"\D", "", keyword)
    results = []
    seen = set()

    stock_exact_code = []
    stock_prefix_code = []
    stock_contain_code = []
    stock_fuzzy_name = []
    fund_exact_code = []
    fund_prefix_code = []
    fund_contain_code = []
    fund_fuzzy_name = []
    fund_fuzzy_pinyin = []

    for stock in _get_stock_search_pool():
        code = str(stock.get("code", "")).strip()
        name = str(stock.get("name", "")).strip()
        if not code and not name:
            continue
        code_lower = code.lower()
        code_digits = re.sub(r"\D", "", code_lower)
        item = {
            "code": code,
            "name": name,
            "category": stock.get("category", "股票"),
            "asset_type": "股票",
        }
        if keyword == code_lower:
            stock_exact_code.append(item)
        elif keyword and code_lower.startswith(keyword):
            stock_prefix_code.append(item)
        elif (
            keyword and keyword in code_lower
        ) or (
            keyword_digits and code_digits and keyword_digits in code_digits
        ):
            stock_contain_code.append(item)
        elif keyword in name.lower():
            stock_fuzzy_name.append(item)

    for fund in _get_fund_search_pool():
        code = str(fund.get("code", "")).strip()
        name = str(fund.get("name", "")).strip()
        pinyin_short = str(fund.get("pinyin_short", "")).strip().lower()
        pinyin_full = str(fund.get("pinyin_full", "")).strip().lower()
        if not code and not name:
            continue
        code_lower = code.lower()
        code_digits = re.sub(r"\D", "", code_lower)
        item = {
            "code": code,
            "name": name,
            "category": fund.get("category", "基金"),
            "asset_type": "基金",
        }
        if keyword == code_lower:
            fund_exact_code.append(item)
        elif keyword and code_lower.startswith(keyword):
            fund_prefix_code.append(item)
        elif (
            keyword and keyword in code_lower
        ) or (
            keyword_digits and code_digits and keyword_digits in code_digits
        ):
            fund_contain_code.append(item)
        elif keyword in name.lower():
            fund_fuzzy_name.append(item)
        elif keyword and (keyword in pinyin_short or keyword in pinyin_full):
            fund_fuzzy_pinyin.append(item)

    merge_groups = (
        stock_exact_code,
        fund_exact_code,
        stock_prefix_code,
        fund_prefix_code,
        stock_contain_code,
        fund_contain_code,
        stock_fuzzy_name,
        fund_fuzzy_name,
        fund_fuzzy_pinyin,
    )
    for group in merge_groups:
        for item in group:
            k = (item.get("asset_type", ""), item.get("code", ""))
            if k in seen:
                continue
            seen.add(k)
            results.append(item)
            if len(results) >= limit:
                return jsonify({"query": q, "count": len(results), "items": results})

    return jsonify({
        "query": q,
        "count": len(results),
        "items": results,
    })


@app.route("/api/hs300-return")
def hs300_return():
    """
    获取沪深300收益率曲线（真实数据）
    返回:
    - dates: 日期数组
    - returns: 收益率数组（百分比，起点为 0）
    """
    days_text = str(request.args.get("days", "365")).strip()
    try:
        days = min(max(int(days_text), 30), 1000)
    except Exception:
        days = 365

    bench_rows = _fetch_hs300_normalized_series(days=days)
    if not bench_rows:
        return jsonify({"dates": [], "returns": []})

    dates = [x["date"] for x in bench_rows]
    returns = [round((float(x["benchmark"]) - 1.0) * 100, 2) for x in bench_rows]
    return jsonify({
        "dates": dates,
        "returns": returns,
    })


@app.route("/api/portfolio-ocr-import", methods=["POST"])
def portfolio_ocr_import():
    """
    OCR识别截图并解析持仓（真实OCR）：
    表单字段: file=<image>
    """
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "message": "未收到图片文件", "items": []}), 400
    if not OCR_READY and not RAPID_OCR_READY:
        return jsonify({
            "ok": False,
            "message": "OCR依赖未安装：请安装 pillow+pytesseract+tesseract 或 rapidocr_onnxruntime。",
            "items": [],
        }), 500

    try:
        image_bytes = file.read()
        img = Image.open(io.BytesIO(image_bytes))
        text = ""
        # 优先 tesseract（准确率更高）；失败时自动回退 rapidocr
        if OCR_READY:
            try:
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            except Exception:
                text = ""
        if (not text.strip()) and RAPID_OCR_READY and RAPID_OCR_ENGINE is not None:
            result, _ = RAPID_OCR_ENGINE(image_bytes)
            if result:
                text = "\n".join([line[1] for line in result if len(line) >= 2])

        items = _ocr_parse_holdings_text(text)
        if not items:
            return jsonify({
                "ok": False,
                "message": "OCR已执行，但未解析到可用持仓。请确保截图中包含 6位代码、持有金额、持有收益。",
                "ocr_text": text[:2000],
                "items": [],
            })
        return jsonify({
            "ok": True,
            "message": f"识别成功，共解析 {len(items)} 条持仓",
            "ocr_text": text[:2000],
            "items": items,
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"OCR识别失败: {e}",
            "items": [],
        }), 500


def _pe_to_valuation_pct(pe_val):
    """将 PE 值映射到估值百分位（0-99%）。PE<15 低估，15-30 适中，>30 高估。"""
    if pe_val <= 0:
        return None
    if pe_val < 10:
        return round(pe_val / 10 * 20, 1)
    if pe_val < 15:
        return round(20 + (pe_val - 10) / 5 * 10, 1)
    if pe_val < 25:
        return round(30 + (pe_val - 15) / 10 * 20, 1)
    if pe_val < 40:
        return round(50 + (pe_val - 25) / 15 * 20, 1)
    return min(round(70 + (pe_val - 40) / 30 * 25, 1), 99)


def _parse_pct_str(val):
    """解析 '15.38%' / 'False' / 0.1538 等多种格式为浮点数，无效返回 None。"""
    if val is None:
        return None
    s = str(val).strip().replace('%', '').replace(',', '')
    if s.lower() in ('false', 'true', '--', 'nan', ''):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _get_stock_kline_sina(code):
    """通过新浪接口获取股票日线数据（含 close/turnover），可用性更好。"""
    # 判断市场前缀
    prefix = 'sh' if code.startswith('6') else 'sz'
    return ak.stock_zh_a_daily(symbol=f"{prefix}{code}", adjust="qfq")


def _fund_open_nav_series_sorted(code):
    """
    东财开放式/联接/QDII 基金净值序列（按日期升序，仅数值列）。
    依次尝试单位净值、累计净值走势。
    """
    import pandas as pd

    sym = str(code).strip().zfill(6)[-6:]
    if not sym.isdigit():
        return None
    for indicator in ("单位净值走势", "累计净值走势"):
        try:
            df = ak.fund_open_fund_info_em(symbol=sym, indicator=indicator)
            if df is None or df.empty:
                continue
            col_date = "净值日期" if "净值日期" in df.columns else df.columns[0]
            if "单位净值" in df.columns:
                col_val = "单位净值"
            elif "累计净值" in df.columns:
                col_val = "累计净值"
            else:
                col_val = df.columns[1]
            tmp = pd.DataFrame({
                "d": pd.to_datetime(df[col_date], errors="coerce"),
                "v": pd.to_numeric(df[col_val], errors="coerce"),
            })
            tmp = tmp.dropna().sort_values("d")
            if tmp.empty or len(tmp) < 2:
                continue
            ser = tmp["v"].reset_index(drop=True)
            return ser
        except Exception:
            continue
    return None


def _fund_etf_close_series_sina_dual(code):
    """
    场内基金（ETF/LOF 等）新浪日收盘价序列，按时间升序。
    同时尝试 sh/sz 前缀，解决 520/511 等沪市跨境 ETF 及 LOF 归属误判。
    """
    sym = str(code).strip().zfill(6)[-6:]
    if not sym.isdigit() or len(sym) != 6:
        return None
    best = None
    best_len = 0
    for prefix in ("sh", "sz"):
        try:
            df = ak.fund_etf_hist_sina(symbol=f"{prefix}{sym}")
            if df is None or df.empty or "close" not in df.columns:
                continue
            s = df["close"].dropna().astype(float).reset_index(drop=True)
            if len(s) > best_len:
                best, best_len = s, len(s)
        except Exception:
            continue
    return best


def _fund_select_price_series_for_metrics(code, fund_name=""):
    """
    为指标计算选择价格/净值序列：优先东财场外净值（联接、QDII 与持仓一致），
    不足时再使用新浪场内 K 线（覆盖 520/511 等原 is_etf 未包含的 ETF）。
    """
    nav = _fund_open_nav_series_sorted(code)
    etf = _fund_etf_close_series_sina_dual(code)
    nlen = len(nav) if nav is not None else 0
    elen = len(etf) if etf is not None else 0
    # 名称含「联接」时强制优先场外净值，避免误用场内 ETF 曲线
    if "联接" in (fund_name or "") and nlen >= 5:
        return nav
    if nlen >= 20:
        return nav
    if elen >= 20:
        return etf
    if nlen >= 5:
        return nav
    if elen >= 5:
        return etf
    return nav if nlen else etf


def _compute_holding_indicators(code, asset_type, current_price, cost_price, shares, fund_name=""):
    """
    为单只持仓计算辅助决策指标（估值百分位、盈利增速、换手率、偏离度）。
    股票：akshare 新浪日线 + 同花顺财务摘要 + 东财个股信息
    基金：东财净值（联接/QDII）+ 新浪场内 K 线双源，自动择优；覆盖 520/511 等跨境 ETF
    """
    result = {
        "asset_type": asset_type,
        "valuation_pct": None,
        "profit_growth": None,   # 股票专用：近1年净利润增速
        "turnover": None,        # 股票专用：近5日均换手率
        "return_1y": None,       # 基金专用：近1年收益率
        "max_drawdown": None,    # 基金专用：近1年最大回撤
        "deviation": None,       # 通用：偏离20日均线
    }

    current = float(current_price or 0)
    cost = float(cost_price or 0)
    return_pct = ((current - cost) / cost * 100) if cost > 0 else 0

    if asset_type == '股票':
        # ── 1. 估值百分位：东财个股信息取 PE ──
        try:
            df_info = ak.stock_individual_info_em(symbol=code)
            # 该接口无 PE，跳过，后续用财务摘要计算
        except Exception:
            pass

        # ── 2. 盈利增速：同花顺财务摘要按年度，取最新一年 ──
        try:
            df_fin = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
            if not df_fin.empty and '净利润同比增长率' in df_fin.columns:
                # iloc[-1] 是最新年度（数据按时间正序排列）
                val = df_fin['净利润同比增长率'].iloc[-1]
                g = _parse_pct_str(val)
                if g is not None:
                    result['profit_growth'] = round(g, 1)
        except Exception:
            pass

        # ── 3. 换手率(近5日均) + 4. 偏离度(20日均线)：新浪日线接口 ──
        try:
            df_kline = _get_stock_kline_sina(code)
            if not df_kline.empty:
                # 换手率字段为 turnover（小数，如 0.001613），乘以100转为百分比
                if 'turnover' in df_kline.columns:
                    recent_5 = df_kline['turnover'].tail(5).dropna().astype(float)
                    if not recent_5.empty:
                        result['turnover'] = round(float(recent_5.mean()) * 100, 3)

                # 偏离度：取最近30行计算20日均线
                if 'close' in df_kline.columns and len(df_kline) >= 20:
                    closes = df_kline['close'].astype(float)
                    ma20 = float(closes.tail(20).mean())
                    last_close = float(closes.iloc[-1])
                    if ma20 > 0:
                        result['deviation'] = round((last_close - ma20) / ma20 * 100, 2)

                # 估值百分位回退：用当前价 / 20日均线作为相对估值代理
                if result['valuation_pct'] is None and 'close' in df_kline.columns and len(df_kline) >= 60:
                    closes_60 = df_kline['close'].tail(60).astype(float)
                    last_c = float(closes_60.iloc[-1])
                    low_60 = float(closes_60.min())
                    high_60 = float(closes_60.max())
                    if high_60 > low_60:
                        pct = (last_c - low_60) / (high_60 - low_60) * 100
                        result['valuation_pct'] = round(pct, 1)
        except Exception:
            pass

        # ── 5. 同花顺财务摘要补充估值百分位（用 EPS 与股价推算 PE）──
        if result['valuation_pct'] is None:
            try:
                df_fin2 = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
                if not df_fin2.empty and '基本每股收益' in df_fin2.columns:
                    eps_val = _parse_pct_str(df_fin2['基本每股收益'].iloc[-1])
                    if eps_val and eps_val > 0 and current > 0:
                        pe = current / eps_val
                        result['valuation_pct'] = _pe_to_valuation_pct(pe)
            except Exception:
                pass

    elif asset_type == '基金':
        result['asset_type'] = '基金'

        def _calc_fund_metrics(series):
            """给定净值/价格 Series（时间升序），返回 (valuation_pct, return_1y, max_drawdown, deviation)。"""
            s = series.astype(float).dropna()
            if s.empty:
                return None, None, None, None
            v_pct, ret_1y, max_dd, dev = None, None, None, None

            win = min(60, len(s))
            s60 = s.tail(win)
            lo, hi = float(s60.min()), float(s60.max())
            last = float(s.iloc[-1])
            if hi > lo:
                v_pct = round((last - lo) / (hi - lo) * 100, 1)
            else:
                v_pct = 50.0

            win252 = min(252, len(s))
            s252 = s.tail(win252)
            if len(s252) >= 20:
                start_val = float(s252.iloc[0])
                if start_val > 0:
                    ret_1y = round((last - start_val) / start_val * 100, 2)

            if len(s252) >= 5:
                peak = s252.expanding().max()
                dd = (s252 - peak) / peak * 100
                max_dd = round(float(dd.min()), 2)

            if len(s) >= 20:
                ma20 = float(s.tail(20).mean())
                if ma20 > 0:
                    dev = round((last - ma20) / ma20 * 100, 2)

            return v_pct, ret_1y, max_dd, dev

        try:
            px = _fund_select_price_series_for_metrics(code, fund_name=fund_name or "")
            if px is not None and len(px) >= 5:
                v_pct, ret_1y, max_dd, dev = _calc_fund_metrics(px)
                result['valuation_pct'] = v_pct
                result['return_1y'] = ret_1y
                result['max_drawdown'] = max_dd
                result['deviation'] = dev
        except Exception:
            pass

        # 基金无盈利增速、无换手率
        result['profit_growth'] = None
        result['turnover'] = None

    # ── 兜底：估值百分位仍空时，用持仓收益率粗估 ──
    if result['valuation_pct'] is None:
        if return_pct <= -20:
            result['valuation_pct'] = 12.0
        elif return_pct <= -10:
            result['valuation_pct'] = round(12 + (return_pct + 20) * 1.8, 1)
        elif return_pct <= 0:
            result['valuation_pct'] = round(30 + return_pct * 0.8, 1)
        elif return_pct <= 20:
            result['valuation_pct'] = round(30 + return_pct * 1.5, 1)
        elif return_pct <= 50:
            result['valuation_pct'] = round(60 + (return_pct - 20) * 1.0, 1)
        else:
            result['valuation_pct'] = min(round(90 + (return_pct - 50) * 0.2, 1), 99)

    return result


@app.route("/api/holding-indicators", methods=["POST"])
def holding_indicators():
    """批量计算各持仓的决策辅助指标。"""
    data, jerr = _safe_request_json()
    if jerr:
        return jsonify({"ok": False, "error": jerr}), 400
    data = data or {}
    holdings = data.get("holdings", [])
    indicators = {}
    for h in holdings:
        code = str(h.get("code", "")).strip()
        if not code:
            continue
        asset_type = h.get("asset_type", "股票")
        try:
            ind = _compute_holding_indicators(
                code=code,
                asset_type=asset_type,
                current_price=h.get("current", 0),
                cost_price=h.get("cost", 0),
                shares=h.get("shares", 0),
                fund_name=str(h.get("name", "") or ""),
            )
        except Exception as e:
            ind = {"valuation_pct": None, "profit_growth": None, "turnover": None, "deviation": None}
        indicators[code] = ind
    return jsonify({"ok": True, "indicators": indicators})


@app.route("/api/kimi-valuation", methods=["POST"])
def kimi_valuation():
    """调用 Kimi 对单只持仓进行估值深度分析。"""
    from dotenv_local import get_kimi_api_key, get_kimi_model

    data, jerr = _safe_request_json()
    if jerr:
        return jsonify({"error": jerr}), 400
    data = data or {}
    code = str(data.get("code", "")).strip()
    name = str(data.get("name", "")).strip()
    asset_type = data.get("asset_type", "股票")
    indicators = data.get("indicators", {})
    holding = data.get("holding", {})

    api_key = get_kimi_api_key()
    if not api_key:
        return jsonify({"error": "KIMI_API_KEY 未配置，请在 .env 文件中添加"})

    is_fund = asset_type == '基金'

    # 构建指标描述（股票与基金用不同字段）
    ind_desc_parts = []
    if indicators.get("valuation_pct") is not None:
        ind_desc_parts.append(f"估值百分位约 {indicators['valuation_pct']:.1f}%（越低越便宜）")
    if is_fund:
        if indicators.get("return_1y") is not None:
            ind_desc_parts.append(f"近1年收益率约 {indicators['return_1y']:+.2f}%")
        if indicators.get("max_drawdown") is not None:
            ind_desc_parts.append(f"近1年最大回撤约 {indicators['max_drawdown']:.2f}%")
    else:
        if indicators.get("profit_growth") is not None:
            ind_desc_parts.append(f"近一年盈利增速约 {indicators['profit_growth']:+.1f}%")
        if indicators.get("turnover") is not None:
            ind_desc_parts.append(f"近5日平均换手率约 {indicators['turnover']:.3f}%")
    if indicators.get("deviation") is not None:
        ind_desc_parts.append(f"当前价格偏离20日均线约 {indicators['deviation']:+.2f}%")
    ind_desc = "；".join(ind_desc_parts) if ind_desc_parts else "暂无指标数据"

    holding_desc_parts = []
    if holding.get("cost"):
        holding_desc_parts.append(f"成本价约 {holding['cost']:.4f}")
    if holding.get("current"):
        holding_desc_parts.append(f"当前价约 {holding['current']:.4f}")
    if holding.get("return_pct") is not None:
        holding_desc_parts.append(f"当前持有收益率 {holding['return_pct']:+.2f}%")
    holding_desc = "，".join(holding_desc_parts) if holding_desc_parts else ""

    if is_fund:
        analysis_dimensions = """\
1. **估值判断**：结合估值百分位（净值在近60日区间的位置），分析当前买入时机是否合适，并说明对基金更适合用哪种估值方式（如分位点、净值折溢价、申万行业指数估值等）及原因；
2. **收益与风险**：结合近1年收益率和最大回撤，评估该基金的风险收益比；
3. **均线信号**：结合偏离度，分析近期净值走势与买卖时机；
4. **操作建议**：综合以上，给出明确的加仓 / 持有 / 赎回建议及操作逻辑；
5. **风险提示**：列出该基金当前主要风险点（1-2条，如赛道集中、流动性等）。"""
    else:
        analysis_dimensions = """\
1. **估值判断**：结合估值百分位，分析当前估值水平是否合理，并说明对于该股票更适合用哪种估值指标（如 PE、PB、PS、股息率、EV/EBITDA 等）及原因；
2. **成长性判断**：结合盈利增速，分析企业成长趋势与业绩质量；
3. **量价信号**：结合换手率与偏离度，分析近期市场情绪与买卖时机；
4. **操作建议**：综合以上，给出明确的加仓 / 持有 / 减仓建议及合理的操作逻辑；
5. **风险提示**：列出该股票当前主要风险点（1-2条）。"""

    prompt = f"""你是一名专业的A股/基金投资分析师。请对以下持仓进行深度分析，并给出加仓或减仓的参考建议：

**标的信息**
- 名称：{name}（代码：{code}，类型：{asset_type}）
- 持仓情况：{holding_desc if holding_desc else '未知'}

**当前指标数据**
{ind_desc}

**请从以下维度给出分析（每条150-200字，语言简洁专业）：**
{analysis_dimensions}

请直接给出分析，无需重复标的名称，语气专业但通俗易懂。"""

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        model_id = get_kimi_model(default=KIMI_MODEL)
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "你是一名专业的证券投资分析师，擅长A股和基金的估值分析。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
        }
        api_url = (os.getenv("KIMI_API_URL") or KIMI_API_URL).strip()
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 429:
            return jsonify({"error": "Kimi 请求频率过高，请1分钟后再试"})
        if resp.status_code != 200:
            detail = _moonshot_api_error_detail(resp)
            if resp.status_code == 401:
                base = "API 密钥无效或已过期（HTTP 401）。请核对 .env 中 KIMI_API_KEY，修改后重启 Flask。"
            elif resp.status_code == 400 and detail and ("model" in detail.lower() or "模型" in detail):
                base = f"模型「{model_id}」不可用（HTTP 400）。请在 .env 中更新为平台当前支持的 KIMI_MODEL。"
            else:
                base = f"Kimi 接口异常: HTTP {resp.status_code}"
            if detail:
                base = f"{base} 详情：{detail}"
            return jsonify({"error": base})
        content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            return jsonify({"error": "Kimi 返回内容为空"})
        return jsonify({"ok": True, "analysis": content, "model_used": model_id})
    except Exception as e:
        return jsonify({"error": f"请求失败: {str(e)}"})


def _macro_snapshot_for_rebalance_advice():
    """
    为组合调仓建议拉取简要宏观/市场快照（与 /api/market 同源思路：AkShare 新浪指数日线）。
    失败时返回说明性占位文本，不抛异常。
    """
    lines = []
    snap_map = [
        ("上证指数", "sh000001"),
        ("深证成指", "sz399001"),
        ("创业板指", "sz399006"),
        ("沪深300", "sh000300"),
    ]
    for name, symbol in snap_map:
        try:
            df_idx = ak.stock_zh_index_daily(symbol=symbol)
            if df_idx is None or df_idx.empty or len(df_idx) < 2:
                continue
            latest_close = float(df_idx.iloc[-1]["close"])
            prev_close = float(df_idx.iloc[-2]["close"])
            change_pct = 0.0 if prev_close == 0 else (latest_close - prev_close) / prev_close * 100
            lines.append(f"- {name}：{latest_close:.2f} 点，较前一日 {change_pct:+.2f}%")
        except Exception:
            continue
    if not lines:
        return "（主要指数行情暂不可用，请结合公开市场信息判断宏观环境。）"
    return "\n".join(lines)


def _normalize_holdings_for_rebalance_api(raw_list):
    """将前端传来的持仓整理为统一结构。"""
    out = []
    for h in raw_list or []:
        if not isinstance(h, dict):
            continue
        code = str(h.get("code", "")).strip()
        if not code:
            continue
        mv = float(h.get("market_value") or h.get("amount") or 0)
        shares = float(h.get("shares") or 0)
        cost = float(h.get("cost") or 0)
        cur = float(h.get("current") or 0)
        rp = h.get("return_pct")
        if rp is None and cost > 0 and cur > 0:
            rp = (cur - cost) / cost * 100
        out.append({
            "code": code,
            "name": str(h.get("name", "") or code).strip(),
            "asset_type": "基金" if h.get("asset_type") == "基金" else "股票",
            "market_value": mv,
            "return_pct": float(rp) if rp is not None else 0.0,
            "shares": shares,
            "cost": cost,
            "current": cur,
        })
    return out


def _kimi_portfolio_rebalance_impl():
    """
    结合用户持仓摘要 + 行业分布 + A 股主要指数快照，调用 Kimi 生成整体调仓建议。
    由多个 URL 复用，避免单一路径在代理/缓存下 404。
    """
    from dotenv_local import get_kimi_api_key, get_kimi_model

    data, jerr = _safe_request_json()
    if jerr:
        return jsonify({"ok": False, "error": jerr}), 400
    data = data or {}
    raw_holdings = data.get("holdings") or []
    holdings = _normalize_holdings_for_rebalance_api(raw_holdings)
    if not holdings:
        return jsonify({"ok": False, "error": "持仓为空，无法生成建议"})

    api_key = get_kimi_api_key()
    if not api_key:
        return jsonify({"ok": False, "error": "KIMI_API_KEY 未配置（可在 .env 中设置 KIMI_API_KEY 或 MOONSHOT_API_KEY）"})

    total_value = float(data.get("total_value") or 0)
    if total_value <= 0:
        total_value = sum(h["market_value"] for h in holdings)
    total_return_pct = data.get("total_return_pct")
    try:
        total_return_pct = float(total_return_pct)
    except (TypeError, ValueError):
        total_return_pct = None

    industry_dist = data.get("industry_distribution") or []
    if not isinstance(industry_dist, list):
        industry_dist = []

    total_mv = sum(h["market_value"] for h in holdings) or 1.0
    sorted_h = sorted(holdings, key=lambda x: x["market_value"], reverse=True)[:20]

    hold_lines = []
    for h in sorted_h:
        w = h["market_value"] / total_mv * 100
        hold_lines.append(
            f"- {h['name']}（{h['code']}，{h['asset_type']}）"
            f" 市值占比 {w:.1f}%，持仓收益率 {h['return_pct']:+.2f}%"
        )
    holdings_block = "\n".join(hold_lines)

    ind_lines = []
    for it in industry_dist[:12]:
        if isinstance(it, dict) and it.get("name") is not None:
            try:
                v = float(it.get("value", 0))
            except (TypeError, ValueError):
                v = 0.0
            ind_lines.append(f"- {it.get('name', '')}: {v:.1f}%")
    industry_block = "\n".join(ind_lines) if ind_lines else "（未提供行业分布，可按持仓名称自行推断集中度。）"

    macro_text = _macro_snapshot_for_rebalance_advice()

    ret_note = ""
    if total_return_pct is not None:
        ret_note = f"\n- 组合整体收益率（相对成本）：{total_return_pct:+.2f}%"
    summary_block = (
        f"- 持仓只数：{len(holdings)}\n"
        f"- 持仓总市值（参考）：约 {total_value:,.0f} 元"
        f"{ret_note}"
    )

    user_prompt = f"""请作为「组合与资产配置顾问」，根据以下真实数据撰写**整体调仓建议**（面向个人投资者，中文）。

【组合概要】
{summary_block}

【行业/主题分布（市值占比）】
{industry_block}

【重仓及主要持仓（按市值从高到低，最多20条）】
{holdings_block}

【主要指数与大盘环境（最近一个交易日相对前一交易日涨跌）】
{macro_text}

**写作要求：**
1. 先给 2~4 句执行摘要，说明当前组合与宏观环境是否匹配。
2. 用二级标题组织：## 组合健康度、## 宏观与仓位匹配、## 调仓动作建议、## 风险与纪律。
3. 「调仓动作建议」中请尽量具体：例如建议增持/减持哪类资产或主题、是否需降低单一标的集中度、股债（或股基）比例是否调整；若信息不足请明确写出假设。
4. 不得编造未提供的持仓或指数数值；未给出的数据请写「数据不足」而非猜测具体数字。
5. 全文克制、可执行，避免夸大收益；结尾简短风险提示：仅供参考，不构成投资建议。"""

    system_prompt = (
        "你是持牌语境下的中文证券投资顾问助手，擅长组合诊断与资产配置。"
        "只依据用户提供的持仓与指数快照作答，不捏造新闻或具体价位目标。"
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        model_id = get_kimi_model(default=KIMI_MODEL)
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.35,
        }
        api_url = (os.getenv("KIMI_API_URL") or KIMI_API_URL).strip()
        resp = requests.post(api_url, headers=headers, json=payload, timeout=55)
        if resp.status_code == 429:
            return jsonify({"ok": False, "error": "Kimi 请求频率过高，请稍后再试"})
        if resp.status_code != 200:
            detail = _moonshot_api_error_detail(resp)
            if resp.status_code == 401:
                base = "API 密钥无效、已过期或未生效（HTTP 401）。请核对 .env 中 KIMI_API_KEY / MOONSHOT_API_KEY，并在修改后重启 Flask。"
            elif resp.status_code == 400 and detail and ("model" in detail.lower() or "模型" in detail):
                base = f"当前模型 ID「{model_id}」可能已下线或不可用（HTTP 400）。请在 .env 中设置平台文档中的 KIMI_MODEL 后重启服务。"
            else:
                base = f"Kimi 接口异常: HTTP {resp.status_code}"
            if detail:
                base = f"{base} 详情：{detail}"
            return jsonify({"ok": False, "error": base})
        content = (
            resp.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            return jsonify({"ok": False, "error": "Kimi 返回内容为空"})
        return jsonify({
            "ok": True,
            "analysis": content,
            "macro_snapshot": macro_text,
            "engine": "kimi",
            "model_used": model_id,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"请求失败: {str(e)}"})


@app.route("/api/kimi/rebalance/health", methods=["GET"])
def kimi_portfolio_rebalance_health():
    """用于确认路由已加载（浏览器或 curl 访问应得到 JSON，而非 HTML 404）。"""
    return jsonify({
        "ok": True,
        "service": "kimi-portfolio-rebalance",
        "post_paths": ["/api/kimi/rebalance", "/api/kimi-portfolio-rebalance"],
        "hint": "若 POST 仍 404，请确认已重启当前目录下的 app.py，且访问端口与启动端口一致。",
    })


@app.route("/api/kimi/rebalance", methods=["POST"])
@app.route("/api/kimi-portfolio-rebalance", methods=["POST"])
def kimi_portfolio_rebalance():
    return _kimi_portfolio_rebalance_impl()


if __name__ == "__main__":
    app.run(debug=False, port=5008)

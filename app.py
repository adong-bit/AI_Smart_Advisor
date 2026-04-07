from flask import Flask, render_template, jsonify, request
import random
import math
import re
from datetime import datetime, timedelta
from market_data_akshare import get_market_data
import akshare as ak
import requests

# 导入真实数据获取模块
try:
    from data_fetcher import get_market_overview, fetcher
    USE_REAL_DATA = True
except ImportError:
    USE_REAL_DATA = False
    print("警告: data_fetcher模块未找到，使用模拟数据")

app = Flask(__name__)

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
}


def _get_fund_search_pool():
    """
    基金搜索池：
    1) 优先 AkShare 全量基金清单（fund_name_em）
    2) 失败时回退内置样例池，确保功能可用
    """
    now = datetime.now()
    loaded_at = FUND_SEARCH_CACHE.get("loaded_at")
    cached_items = FUND_SEARCH_CACHE.get("items") or []
    # 缓存30分钟，降低接口压力
    if loaded_at and cached_items and (now - loaded_at) < timedelta(minutes=30):
        return cached_items

    try:
        df = ak.fund_name_em()
        items = []
        if df is not None and not df.empty:
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
        if items:
            FUND_SEARCH_CACHE["loaded_at"] = now
            FUND_SEARCH_CACHE["items"] = items
            return items
    except Exception:
        pass

    # 回退
    return FUND_SEARCH_POOL


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


def generate_portfolio_history(days=180):
    """生成组合历史净值曲线"""
    data = []
    nav = 1.0
    benchmark = 1.0
    for i in range(days):
        date = (datetime.now() - timedelta(days=days - i)).strftime("%Y-%m-%d")
        nav_change = random.gauss(0.0004, 0.008)
        bench_change = random.gauss(0.0002, 0.012)
        nav *= (1 + nav_change)
        benchmark *= (1 + bench_change)
        data.append({
            "date": date,
            "nav": round(nav, 4),
            "benchmark": round(benchmark, 4),
        })
    return data


# ==================== Routes ====================

@app.route("/")
def index():
    return render_template("index.html", asset_version=int(datetime.now().timestamp()))


# ==================== API ====================

@app.route("/api/market")
def market_data():
    """
    市场概览接口：
    - 方案A：指数卡片使用 efinance（当前环境最稳定）
    - K线/新闻使用可用的 AkShare 接口（失败则留空）
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
                            "sentiment": "positive" if any(x in title for x in ["涨", "利好", "增长", "突破"]) else "negative",
                            "impact": "市场影响",
                        }))
                    except Exception:
                        continue

                records.sort(key=lambda x: x[0], reverse=True)

                # 优先取最近 48 小时新闻，保证“每天都更新”
                now = datetime.now()
                recent = [x[1] for x in records if (now - x[0]).total_seconds() <= 48 * 3600]
                news.extend(recent[:6])

            # 2) 若不足 6 条，用 stock_news_em 补齐
            if len(news) < 6:
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
                            "sentiment": "positive" if any(x in title for x in ["涨", "利好", "增长", "突破"]) else "negative",
                            "impact": "市场影响",
                        }
                        # 去重后补齐
                        if any(n["title"] == item["title"] for n in news):
                            continue
                        news.append(item)
                        if len(news) >= 6:
                            break
        except Exception:
            news = []

        # ===== A股板块热力图：涨幅前4 + 跌幅前4 =====
        sectors = []
        try:
            df_sector = ak.stock_sector_spot(indicator="行业")
            if df_sector is not None and not df_sector.empty:
                # 标准化涨跌幅
                sector_rows = []
                for _, row in df_sector.iterrows():
                    try:
                        name = str(row.get("板块", "")).strip()
                        change = float(row.get("涨跌幅", 0.0))
                        if name:
                            sector_rows.append({"name": name, "change": round(change, 2)})
                    except Exception:
                        continue

                # 去重（同名板块保留首条）
                dedup = []
                seen = set()
                for r in sector_rows:
                    if r["name"] in seen:
                        continue
                    seen.add(r["name"])
                    dedup.append(r)

                # 取涨幅前4和跌幅前4
                top4 = sorted(dedup, key=lambda x: x["change"], reverse=True)[:4]
                bottom4 = sorted(dedup, key=lambda x: x["change"])[:4]

                # 合并并再次去重，保持“涨在前、跌在后”
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

        # ===== AI 市场洞察（新闻驱动 + 结构解释，不展示指数数值） =====
        ai_insights = []
        try:
            market_down = avg_change < 0
            has_sector_data = bool(sectors)
            has_hk_us = bool(hk_indices or us_indices)
            has_news = bool(news)

            # 新闻关键词统计（当天/近几日快讯）
            bearish_keywords = [
                "下跌", "回落", "走弱", "承压", "收紧", "加息", "风险", "担忧", "波动",
                "冲突", "关税", "制裁", "裁员", "违约", "缩表", "降级", "暴跌", "跳水",
            ]
            bullish_keywords = [
                "上涨", "走强", "反弹", "修复", "宽松", "降息", "利好", "回暖", "突破",
                "增持", "回购", "增长", "新高", "提振", "扩张", "改善", "稳定",
            ]
            macro_keywords = ["油价", "美元", "美债", "通胀", "就业", "PMI", "央行", "政策"]

            bear_hits = 0
            bull_hits = 0
            macro_hits = 0
            news_focus = []
            if has_news:
                for item in news[:10]:
                    title = str(item.get("title", ""))
                    if not title:
                        continue
                    if any(k in title for k in bearish_keywords):
                        bear_hits += 1
                    if any(k in title for k in bullish_keywords):
                        bull_hits += 1
                    if any(k in title for k in macro_keywords):
                        macro_hits += 1
                    if len(news_focus) < 2:
                        news_focus.append(title[:26] + ("..." if len(title) > 26 else ""))

            # 1) 核心结论：解释涨跌而不是报数
            if market_down:
                ai_insights.append("AI判断：指数回落更可能由风险偏好下降与资金防御化共同驱动，而非单一事件。")
            else:
                ai_insights.append("AI判断：市场走强主要由风险偏好回升与资金回流驱动，情绪面有边际改善。")

            # 2) 新闻驱动解释（新增）
            if has_news:
                if market_down:
                    if bear_hits > bull_hits:
                        ai_insights.append("新闻面偏谨慎，负面事件密度高于正面事件，短线资金更倾向先降风险再配置。")
                    elif macro_hits >= 2:
                        ai_insights.append("宏观类新闻占比上升，市场对流动性与外部变量更敏感，导致指数表现承压。")
                    else:
                        ai_insights.append("新闻面多空交织但确定性不足，资金交易重心转向防守，放大了盘面回撤。")
                else:
                    if bull_hits >= bear_hits:
                        ai_insights.append("新闻面总体偏积极，利好线索提升了资金风险偏好，对指数形成情绪支撑。")
                    else:
                        ai_insights.append("尽管新闻面仍有扰动，但市场对负面信息钝化，修复动能来自内部资金回流。")
                if news_focus:
                    ai_insights.append(f"近期关注：{news_focus[0]}；{news_focus[1] if len(news_focus) > 1 else news_focus[0]}。")
            else:
                ai_insights.append("新闻面数据暂不可用，当前判断主要基于板块结构与港美联动信号。")

            # 3) 板块结构原因
            if has_sector_data:
                top2 = sorted(sectors, key=lambda x: x["change"], reverse=True)[:2]
                bottom2 = sorted(sectors, key=lambda x: x["change"])[:2]
                top_names = "、".join([x["name"] for x in top2]) if top2 else "少数主题"
                bottom_names = "、".join([x["name"] for x in bottom2]) if bottom2 else "部分权重行业"
                if market_down:
                    ai_insights.append(f"结构上看，承压板块集中在{bottom_names}，而{top_names}的对冲力度不足，导致指数修复受限。")
                else:
                    ai_insights.append(f"结构上看，{top_names}形成了明显带动效应，抵消了{bottom_names}的拖累。")
            else:
                ai_insights.append("板块数据暂不完整，当前判断以价格趋势和成交量变化为主，建议谨慎放大仓位。")

            # 4) 外盘传导原因
            if has_hk_us:
                hk_down = any(x.get("change", 0) < 0 for x in hk_indices)
                us_down = any(x.get("change", 0) < 0 for x in us_indices)
                if market_down and (hk_down or us_down):
                    ai_insights.append("外盘端的波动与避险情绪可能通过风险偏好传导至A股，放大了短线回撤压力。")
                elif (not market_down) and (not hk_down and not us_down):
                    ai_insights.append("港美市场情绪相对稳定，对A股形成了边际支撑，资金更愿意参与高弹性方向。")
                else:
                    ai_insights.append("外盘信号分化，A股更偏向内部结构性定价，板块轮动速度加快。")
            else:
                ai_insights.append("港美数据暂不可用，短线可重点关注A股内部风格切换与成交持续性。")

            # 5) 操作建议（原因导向）
            if market_down:
                ai_insights.append("应对建议：优先控制回撤，避免追跌补仓，等待成交量止跌与主线板块企稳后再逐步提高仓位。")
            else:
                ai_insights.append("应对建议：在不追高前提下分批布局强势主线，同时保留部分防御仓位应对波动反复。")

            # 前端展示控制在 5 条以内
            ai_insights = ai_insights[:5]
        except Exception:
            ai_insights = [
                "市场洞察生成异常，建议先观察市场情绪与板块轮动方向。",
                f"数据更新时间: {update_time}",
            ]

        # ===== 市场情绪指标（NLP新闻情绪 + 价格面） =====
        sentiment_analysis = {
            "label": "中性",
            "zscore": 0.0,
            "prompt": "情绪处于常态区间，建议按既定策略执行。",
            "nlp_summary": "新闻情绪样本不足，当前以价格信号为主。",
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

            # A股量能得分：结合三大指数当日成交量/成交额（越活跃，风险偏好通常越高）
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

            sentiment_analysis = {
                "label": label,
                "zscore": round(float(zscore), 2),
                "prompt": prompt,
                "nlp_summary": (
                    f"NLP情绪统计：利好{pos_count}条，利空{neg_count}条，贪婪词{hype_hits}次，恐惧词{fear_hits}次。"
                    f" A股当日量能：成交额约{a_turnover_amount_yi:.0f}亿元，成交量约{a_turnover_volume_yishou:.2f}亿手。"
                ),
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
            "news": news,
            "top_stocks": [],
            "bottom_stocks": [],
            "market_sentiment": market_sentiment,
            "sentiment_analysis": sentiment_analysis,
            "ai_insights": ai_insights,
            "data_source": "efinance+akshare",
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
        },
        "ai_insights": ["数据获取失败"],
        "data_source": "error",
    })


@app.route("/api/risk-questions")
def risk_questions():
    return jsonify({"questions": RISK_QUESTIONS})


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


@app.route("/api/stock-screen", methods=["POST"])
def stock_screen():
    weights = request.json or {}
    w_value = weights.get("value", 20) / 100
    w_growth = weights.get("growth", 20) / 100
    w_quality = weights.get("quality", 25) / 100
    w_momentum = weights.get("momentum", 20) / 100
    w_sentiment = weights.get("sentiment", 15) / 100

    scored_stocks = []
    for s in STOCKS:
        pe_norm = max(0, min(100, 100 - s["pe"] * 2))
        pb_norm = max(0, min(100, 100 - s["pb"] * 8))
        div_norm = min(100, s["dividend_yield"] * 18)
        value_score = (pe_norm + pb_norm + div_norm) / 3

        rev_norm = min(100, max(0, s["revenue_growth"] * 3))
        profit_norm = min(100, max(0, s["profit_growth"] * 2.5))
        growth_score = (rev_norm + profit_norm) / 2

        roe_norm = min(100, s["roe"] * 3)
        debt_norm = max(0, 100 - s["debt_ratio"])
        quality_score = (roe_norm + debt_norm) / 2

        mom3_norm = min(100, max(0, 50 + s["momentum_3m"] * 3))
        mom6_norm = min(100, max(0, 50 + s["momentum_6m"] * 2))
        momentum_score = (mom3_norm + mom6_norm) / 2

        sentiment_score = s["sentiment"] * 100

        total = (
            w_value * value_score
            + w_growth * growth_score
            + w_quality * quality_score
            + w_momentum * momentum_score
            + w_sentiment * sentiment_score
        )

        stock_copy = dict(s)
        stock_copy["scores"] = {
            "value": round(value_score, 1),
            "growth": round(growth_score, 1),
            "quality": round(quality_score, 1),
            "momentum": round(momentum_score, 1),
            "sentiment": round(sentiment_score, 1),
            "total": round(total, 1),
        }
        scored_stocks.append(stock_copy)

    scored_stocks.sort(key=lambda x: x["scores"]["total"], reverse=True)

    for i, s in enumerate(scored_stocks):
        reasons = []
        scores = s["scores"]
        if scores["value"] > 65:
            reasons.append(f"估值合理(PE:{s['pe']})")
        if scores["growth"] > 60:
            reasons.append(f"成长性强(营收增速:{s['revenue_growth']}%)")
        if scores["quality"] > 65:
            reasons.append(f"盈利质量高(ROE:{s['roe']}%)")
        if scores["momentum"] > 60:
            reasons.append(f"趋势向好(近3月:{s['momentum_3m']}%)")
        if scores["sentiment"] > 70:
            reasons.append(f"市场情绪积极(评级:{s['analyst_rating']})")
        s["ai_reason"] = "、".join(reasons[:3]) if reasons else "综合评分一般，建议谨慎关注"

    return jsonify({"stocks": scored_stocks})


@app.route("/api/portfolio")
def get_portfolio():
    holdings = [
        {"code": "600519", "name": "贵州茅台", "asset_type": "股票", "shares": 100, "unit": "股", "cost": 1620.00, "current": 1680.50, "weight": 18},
        {"code": "002594", "name": "比亚迪", "asset_type": "股票", "shares": 500, "unit": "股", "cost": 268.00, "current": 285.60, "weight": 14},
        {"code": "600036", "name": "招商银行", "asset_type": "股票", "shares": 2000, "unit": "股", "cost": 33.50, "current": 35.80, "weight": 10},
        {"code": "300750", "name": "宁德时代", "asset_type": "股票", "shares": 300, "unit": "股", "cost": 205.00, "current": 218.90, "weight": 10},
        {"code": "000333", "name": "美的集团", "asset_type": "股票", "shares": 800, "unit": "股", "cost": 65.00, "current": 68.20, "weight": 8},
        {"code": "601899", "name": "紫金矿业", "asset_type": "股票", "shares": 3000, "unit": "股", "cost": 16.80, "current": 18.20, "weight": 8},
        {"code": "005827", "name": "易方达蓝筹精选混合", "asset_type": "基金", "shares": 20000, "unit": "份", "cost": 1.61, "current": 1.74, "weight": 17},
        {"code": "510300", "name": "沪深300ETF", "asset_type": "基金", "shares": 15000, "unit": "份", "cost": 3.92, "current": 4.03, "weight": 15},
    ]

    total_cost = sum(h["shares"] * h["cost"] for h in holdings)
    total_current = sum(h["shares"] * h["current"] for h in holdings)
    total_profit = total_current - total_cost
    total_return = (total_profit / total_cost) * 100

    for h in holdings:
        h["profit"] = round((h["current"] - h["cost"]) * h["shares"], 2)
        h["return_pct"] = round((h["current"] - h["cost"]) / h["cost"] * 100, 2)
        h["market_value"] = round(h["current"] * h["shares"], 2)

    history = generate_portfolio_history()

    industry_dist = {}
    for h in holdings:
        stock = next((s for s in STOCKS if s["code"] == h["code"]), None)
        if stock:
            ind = stock["industry"]
            industry_dist[ind] = industry_dist.get(ind, 0) + h["weight"]

    return jsonify({
        "holdings": holdings,
        "total_value": round(total_current, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_profit, 2),
        "total_return": round(total_return, 2),
        "history": history,
        "risk_metrics": {
            "sharpe_ratio": 1.35,
            "max_drawdown": -12.5,
            "volatility": 15.8,
            "beta": 0.85,
            "alpha": 3.2,
            "var_95": -2.8,
            "tracking_error": 5.2,
        },
        "industry_distribution": [{"name": k, "value": v} for k, v in industry_dist.items()],
        "rebalance_alerts": [
            {"type": "warning", "message": "贵州茅台持仓占比25%，超过单一标的建议上限20%，建议适当减仓"},
            {"type": "info", "message": "组合整体Beta为0.85，低于基准，防御性较强"},
            {"type": "success", "message": "组合夏普比率1.35，风险调整后收益表现良好"},
        ],
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    message = request.json.get("message", "").lower()

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

    return jsonify({
        "response": response,
        "category": category,
        "confidence": round(random.uniform(0.85, 0.98), 2),
        "model": "FinGPT-v3",
        "intent": category,
    })


@app.route("/api/education")
def education():
    courses = [
        {
            "id": 1, "title": "投资入门：从零开始",
            "desc": "了解股票、债券、基金等基础投资品种，建立正确的投资观念",
            "level": "初级", "duration": "30分钟", "icon": "📖",
            "topics": ["什么是股票？", "什么是基金？", "什么是债券？", "投资与投机的区别"]
        },
        {
            "id": 2, "title": "价值投资方法论",
            "desc": "学习巴菲特的价值投资理念，掌握基本面分析的核心方法",
            "level": "中级", "duration": "45分钟", "icon": "💎",
            "topics": ["护城河理论", "安全边际", "财务报表分析", "内在价值估算"]
        },
        {
            "id": 3, "title": "技术分析基础",
            "desc": "了解K线图、均线系统、技术指标等技术分析工具",
            "level": "中级", "duration": "40分钟", "icon": "📊",
            "topics": ["K线形态", "均线系统", "MACD指标", "量价关系"]
        },
        {
            "id": 4, "title": "资产配置与组合管理",
            "desc": "学习现代投资组合理论，掌握科学的资产配置方法",
            "level": "高级", "duration": "50分钟", "icon": "🎯",
            "topics": ["马科维茨模型", "有效前沿", "夏普比率", "再平衡策略"]
        },
        {
            "id": 5, "title": "AI量化投资揭秘",
            "desc": "了解人工智能在投资中的应用，包括多因子模型、NLP分析等",
            "level": "高级", "duration": "60分钟", "icon": "🤖",
            "topics": ["多因子模型", "机器学习选股", "NLP情绪分析", "强化学习交易"]
        },
        {
            "id": 6, "title": "风险管理实战",
            "desc": "学习专业的风险管理方法，保护投资组合免受极端风险",
            "level": "高级", "duration": "45分钟", "icon": "🛡️",
            "topics": ["VaR模型", "压力测试", "止损策略", "对冲方法"]
        },
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
    pool = _get_fund_search_pool()
    exact_code = []
    prefix_code = []
    fuzzy_name = []
    fuzzy_pinyin = []

    for fund in pool:
        code = str(fund.get("code", "")).strip()
        name = str(fund.get("name", "")).strip()
        pinyin_short = str(fund.get("pinyin_short", "")).strip().lower()
        pinyin_full = str(fund.get("pinyin_full", "")).strip().lower()
        if not code and not name:
            continue
        if keyword == code.lower():
            exact_code.append(fund)
        elif code.lower().startswith(keyword):
            prefix_code.append(fund)
        elif keyword in name.lower():
            fuzzy_name.append(fund)
        elif keyword and (keyword in pinyin_short or keyword in pinyin_full):
            fuzzy_pinyin.append(fund)

    merged = []
    seen = set()
    for group in (exact_code, prefix_code, fuzzy_name, fuzzy_pinyin):
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


if __name__ == "__main__":
    app.run(debug=True, port=5008)

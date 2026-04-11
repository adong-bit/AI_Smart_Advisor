# -*- coding: utf-8 -*-
"""
7×24 财经快讯标题情感：利好 / 利空 / 中性

设计目标（相对「零散关键词」）：
1) 用「正则模式」覆盖财报常用句式（同比…增、营收…增、净利…亏 等），避免必须出现固定词组。
2) 用「加权计分」区分强/弱信号，再合成净分。
3) 用「否定 / 乏力 / 收窄方向」等规则做方向修正。
4) 用「多空同时显著」判定为中性，避免标题里好坏参半仍判单边。

说明：仍为规则引擎，非大模型；极端修辞、反讽、跨句转折可能误判。
"""

from __future__ import annotations

import re
from typing import List, Tuple

# ---------- 正则：强信号（每条匹配 +WEIGHT_STRONG 分，单模式最多计 MAX_HITS_PER_RX 次）----------
WEIGHT_STRONG = 2.0
WEIGHT_MID = 1.0
MAX_HITS_PER_RX = 2

# 偏多：业绩、景气、政策、资金面、供需、市场表现
_BULL_STRONG_PATTERNS = [
    ("财报增速", r"同比[^|，。；;、\n]{0,18}?(?:增|涨|升|转[好正]|(?:大|劲|暴)?超|逾|提速|好转|改善)"),
    ("环比改善", r"环比[^|，。；;、\n]{0,14}?(?:增|涨|升|改善|转正)"),
    ("营收向好", r"(?:营收|营业收入|销售额|收入)[^|，。；;、\n]{0,22}?(?:增|涨|升|破|新(?:高|纪录)|创新(?:纪)?录)"),
    ("利润向好", r"(?:净利|净利润|归母净利润)[^|，。；;、\n]{0,22}?(?:增|涨|升|扭亏|扭亏为盈|超预期|(?:大|暴)?增)"),
    ("预告偏好", r"(?:业绩|利润|净利)[^|，。；;、\n]{0,14}?(?:预增|略增|续盈|扭亏)"),
    ("增速描述", r"(?:增幅|增速|增长率)[^|，。；;、\n]{0,10}?(?:扩大|走高|回升|为正|上行)"),
    ("供需紧", r"供不应求|一货难求|紧俏|(?:订单|排产)(?:饱满|火爆|已排至)|满(?:产|负荷)|销量(?:大)?增"),
    ("货币财政偏松", r"降准|降息|(?:货币|流动性)?宽松|(?:政策|监管)(?:呵护|边际宽松)"),
    ("回购增持", r"(?:回购|增持)[^|，。；;、\n]{0,14}?(?:亿|万|元|计划|方案|实施|完成|进展)"),
    (
        "景气",
        r"景气度(?:回升|向好|改善|提升|高企|高位|持续向好|维持高位|持续(?!低迷|下滑|走弱|承压|恶化|降温))",
    ),
    ("行情偏强", r"(?:放量)?(?:大涨|飙升|涨停|连板|创新高|新高)(?![小少低])"),
    ("修复", r"(?:股价|指数|板块)?(?:反弹|修复|走强|上攻|攀升)"),
    ("亏损收敛", r"亏损(?:大幅)?收窄|降幅收窄|由亏转盈|扭亏"),
]

_BEAR_STRONG_PATTERNS: List[Tuple[str, str]] = [
    ("财报走弱", r"同比[^|，。；;、\n]{0,18}?(?:降|减|跌|亏|滑坡|萎缩|回落|转负|下滑)"),
    ("营收走弱", r"(?:营收|营业收入|销售额|收入)[^|，。；;、\n]{0,22}?(?:降|减|跌|亏|下滑|萎缩)"),
    ("利润走弱", r"(?:净利|净利润|归母净利润)[^|，。；;、\n]{0,22}?(?:亏损|暴亏|预亏|首亏|大降|锐减|转亏|盈转亏|由盈转亏)"),
    ("预期落空", r"不及预期|远低于预期|低于预期|业绩(?:变)?脸|(?:大幅)?预减|续亏|预亏"),
    ("风险事件", r"(?:被)?立案|退市风险|ST风险|暴雷|(?:债务)?违约|爆仓|调查|处罚|罚款"),
    ("市场表现弱", r"(?:大幅)?(?:暴跌|重挫|跳水|跌停|破发)(?![口小])"),
    ("经营恶化", r"裁员|(?:大幅)?减员|砍单|滞销|积压|产能过剩|不景气"),
    ("宏观地缘", r"(?:地缘)?冲突|制裁|关税|(?:风险|担忧)(?:升温|加剧)|收紧|加息|缩表"),
    (
        "地缘军事",
        r"(?:增兵|屯兵|派兵|军(?:事)?部署|战备(?:升级|动员)?|交火|开火|空袭|导弹(?:袭击|试射)?)",
    ),
    (
        "热点紧张",
        r"(?:中东|俄乌|海湾|以[色巴]|伊朗|乌克兰|加沙)[^|，。；;、\n]{0,16}?(?:增兵|冲突|开火|空袭|紧张(?:升级)?|局势(?:恶化|升温)|动荡|交火)|"
        r"向[^|，。；;、\n]{0,8}(?:中东|海湾)[^|，。；;、\n]{0,12}?(?:增兵|屯兵|派兵|部署)|"
        r"(?:美军|美军方|五角大楼|北约)[^|，。；;、\n]{0,16}?(?:增兵|屯兵|派兵|调动|部署)",
    ),
    ("下行", r"(?:股价|指数|板块)?(?:大跌|下挫|走低|走弱|承压)"),
]

# 中等关键词（补充正则未覆盖的常见词）
# 注意：不用单独「突破」——易与「未能突破」等否定句冲突，强多由正则「创新高/走强」等覆盖
_BULL_MID = (
    "利好", "回暖", "增持", "扩张", "改善", "稳定", "齐涨", "收涨", "抬升",
    "优化", "提振", "放量", "净流入", "净流入额", "外资流入", "北向资金净流入",
)
_BEAR_MID = (
    "利空", "担忧", "波动加剧", "避险情绪", "避险升温", "净流出", "外资流出", "北向资金净流出",
    "恶化", "预警", "下滑", "萎缩", "收跌", "回落", "地缘紧张", "局势紧张", "军事冲突",
)

# 否定 / 落空 / 乏力：对净分做额外偏空修正（避免「未能突破」仍算强多）
_NEGATION_TILT_PATTERNS: List[str] = [
    r"未(?:能)?[^|，。；;、\n]{0,10}?(?:突破|增长|兑现|完成|达到|回升)",
    r"难(?:以)?[^|，。；;、\n]{0,8}?(?:回暖|增长|改善|盈利)",
    r"(?:并未|远没有|谈不上|无从)[^|，。；;、\n]{0,10}?(?:改善|增长|盈利|突破)",
    r"(?:上涨|反弹|涨势|增长)[^|，。；;、\n]{0,6}?(?:乏力|趋弱|放缓|遇阻|终结|结束)",
    r"涨幅收窄(?!.*(?:仍|依然|继续)(?:大|飙))",
]

# 偏空但常被误判为「涨」的短语
_BEAR_EXTRA = (
    "涨幅收窄", "上涨乏力", "反弹乏力", "冲高回落", "高开低走", "利多出尽",
)

# 明显偏陈述、无方向的弱中性（不单独判中性，仅用于压低极端分；主要靠净分阈值）
# 若全文几乎只有此类且无多空信号，则净分接近 0

_COMPILED_BULL_S = [(n, re.compile(p)) for n, p in _BULL_STRONG_PATTERNS]
_COMPILED_BEAR_S = [(n, re.compile(p)) for n, p in _BEAR_STRONG_PATTERNS]
_COMPILED_NEG = [re.compile(p) for p in _NEGATION_TILT_PATTERNS]


def _rx_total_weight(text: str, compiled: List[Tuple[str, re.Pattern]], w: float) -> float:
    s = 0.0
    for name, rx in compiled:
        hits = len(rx.findall(text))
        if not hits:
            continue
        s += w * min(hits, MAX_HITS_PER_RX)
    return s


def _keyword_weight(text: str, kws: Tuple[str, ...], w_per: float) -> float:
    s = 0.0
    for kw in kws:
        if kw in text:
            s += w_per
    return s


def _negation_penalty(text: str) -> float:
    """否定/乏力类：加到 bear 侧的分值（正数），权重大于普通中词，确保「未能突破」等能落到利空。"""
    p = 0.0
    for rx in _COMPILED_NEG:
        hits = len(rx.findall(text))
        if hits:
            p += (WEIGHT_STRONG * 0.62) * min(hits, MAX_HITS_PER_RX)
    return p


def classify_flash_news_title(title: str) -> str:
    """
    返回 'positive' | 'negative' | 'neutral'
    """
    t = (title or "").strip()
    if not t:
        return "neutral"

    bull = _rx_total_weight(t, _COMPILED_BULL_S, WEIGHT_STRONG)
    bear = _rx_total_weight(t, _COMPILED_BEAR_S, WEIGHT_STRONG)

    bull += _keyword_weight(t, _BULL_MID, WEIGHT_MID)
    bear += _keyword_weight(t, _BEAR_MID, WEIGHT_MID)

    bear += _keyword_weight(t, _BEAR_EXTRA, WEIGHT_MID)

    # 否定 / 乏力：加重偏空
    bear += _negation_penalty(t)

    # 「或」引导的供不应求仍能被供需正则命中；「但」「然而」后若跟强空，略加重（简化：整句扫描已够用）

    net = bull - bear

    # 多空均出现「强正则级」信号：典型为业绩喜忧参半、多空交织，不判单边
    if bull >= WEIGHT_STRONG and bear >= WEIGHT_STRONG:
        return "neutral"

    # 净分阈值：需一定置信度才标单边
    POS_TH = 1.15
    NEG_TH = -1.15
    if net >= POS_TH:
        return "positive"
    if net <= NEG_TH:
        return "negative"
    return "neutral"


# 兼容旧名
analyze_flash_news_sentiment = classify_flash_news_title


def _self_check() -> None:
    samples = [
        ("行业景气度持续 浪潮信息去年营收同比增超四成 AI服务器产品或供不应求 |财报解读", "positive"),
        ("央行宣布全面降准0.5个百分点", "positive"),
        ("沪指放量大涨2% 创阶段新高", "positive"),
        ("未能突破前高 资金获利了结", "negative"),
        ("归母净利润同比大降六成 不及预期", "negative"),
        ("营收大增但净利润亏损扩大 多空交织", "neutral"),
        ("美联储维持利率不变 市场观望", "neutral"),
        ("行业不景气 营收同比下滑", "negative"),
        ("A股涨跌互现 结构性行情延续", "neutral"),
        ("光伏产能过剩 价格承压", "negative"),
        ("公司发布三季度财报解读", "neutral"),
        ("美媒称谈判在即美军继续向中东增兵", "negative"),
    ]
    for text, want in samples:
        got = classify_flash_news_title(text)
        mark = "OK" if got == want else f"FAIL want={want}"
        print(f"[{mark}] {got} <- {text[:40]}...")


if __name__ == "__main__":
    _self_check()

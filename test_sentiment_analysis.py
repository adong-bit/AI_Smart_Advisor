#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻情感分析改进对比测试
展示改进前后的判断差异
"""

def analyze_news_sentiment_OLD(title):
    """改进前的简单判断"""
    sentiment = "positive" if any(x in title for x in ["涨", "利好", "增长", "突破"]) else "negative"
    return {"sentiment": sentiment, "reason": "仅基于4个关键词的简单匹配"}


def analyze_news_sentiment_NEW(title):
    """改进后的多层次判断"""
    if not title or not isinstance(title, str):
        return {"sentiment": "neutral", "confidence": 0.5, "reason": "标题为空"}
    
    title_lower = title.lower()
    
    # 定义词汇库
    negation_words = ["未", "没有", "不会", "不能", "缺乏", "无法", "难以", "风险", "担忧"]
    strong_bullish = ["涨停", "暴涨", "大幅上升", "创新高", "突破", "利好", "回购", "增持", "利润增长", "收益增长"]
    moderate_bullish = ["上涨", "反弹", "修复", "改善", "增长", "回暖", "扩张", "提振", "稳定", "确认"]
    
    strong_bearish = ["跌停", "暴跌", "大幅下跌", "创新低", "风险", "警告", "停产", "破产", "违约", "裁员", "大幅下降"]
    moderate_bearish = ["下跌", "回落", "走弱", "承压", "衰退", "下滑", "萎缩", "削减", "延迟", "困难"]
    
    # 宏观相关词汇
    macro_keywords = {
        "降息": ("positive", 0.7),
        "加息": ("negative", 0.7),
        "降准": ("positive", 0.8),
        "收紧": ("negative", 0.7),
    }
    
    # 检查否定词
    has_negation = any(neg in title for neg in negation_words)
    
    # 计数各类词汇
    strong_bull_count = sum(1 for word in strong_bullish if word in title)
    moderate_bull_count = sum(1 for word in moderate_bullish if word in title)
    strong_bear_count = sum(1 for word in strong_bearish if word in title)
    moderate_bear_count = sum(1 for word in moderate_bearish if word in title)
    
    # 宏观指标处理
    macro_sentiment = None
    for macro_word, (sentiment, strength) in macro_keywords.items():
        if macro_word in title:
            macro_sentiment = (sentiment, strength)
            break
    
    # 计算总体得分（加权）
    bullish_score = strong_bull_count * 3 + moderate_bull_count * 1
    bearish_score = strong_bear_count * 3 + moderate_bear_count * 1
    
    # 如果有否定词，反转情感
    if has_negation:
        if bullish_score > 0:
            bearish_score += bullish_score * 2
            bullish_score = 0
        elif bearish_score > 0:
            bullish_score += bearish_score * 2
            bearish_score = 0
    
    # 确定最终情感
    if bullish_score > bearish_score:
        sentiment = "positive"
        confidence = min(0.95, 0.5 + bullish_score * 0.15)
        reason = f"检测到{strong_bull_count}个强利好词、{moderate_bull_count}个温和利好词"
    elif bearish_score > bullish_score:
        sentiment = "negative"
        confidence = min(0.95, 0.5 + bearish_score * 0.15)
        reason = f"检测到{strong_bear_count}个强利空词、{moderate_bear_count}个温和利空词"
    elif macro_sentiment:
        sentiment, strength = macro_sentiment
        confidence = strength
        reason = "基于宏观因素判断"
    else:
        sentiment = "neutral"
        confidence = 0.5
        reason = "无明确利好/利空信号"
    
    return {
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "reason": reason,
        "has_negation": has_negation,
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
    }


# 测试用例（包含问题场景）
test_cases = [
    "央行宣布降准0.5个百分点，释放长期资金约1万亿元",
    "某光伏龙头企业发布业绩预警，产能过剩压力加大",
    "美联储暗示年内降息预期增强，全球市场情绪回暖",
    "新能源汽车1-2月销量同比增长38.2%，渗透率突破40%",
    "多家白酒企业发布提价公告，行业景气度持续回升",
    "未能突破关键阻力位，技术面承压",  # 问题1: 含"突破"但实际是利空
    "企业虽有增长但利润下滑幅度较大",  # 问题2: 含"增长"但整体利空
    "央行释放流动性但市场担忧后续政策收紧",  # 问题3: 利好词后跟利空词
    "降息政策推出，银行股上涨",  # 问题4: 降息+上涨，应该是利好
    "美联储加息预期升温，科技股承压",  # 问题5: 加息，应该利空
]

print("=" * 80)
print("新闻情感分析改进对比测试")
print("=" * 80)
print()

for i, title in enumerate(test_cases, 1):
    print(f"测试用例 {i}: {title}")
    print("-" * 80)
    
    old_result = analyze_news_sentiment_OLD(title)
    new_result = analyze_news_sentiment_NEW(title)
    
    old_sentiment = old_result["sentiment"]
    new_sentiment = new_result["sentiment"]
    
    print(f"改进前判断: {old_sentiment.upper()}")
    print(f"改进后判断: {new_sentiment.upper()}  (置信度: {new_result['confidence']})")
    print(f"判断理由: {new_result['reason']}")
    
    if old_sentiment != new_sentiment:
        print(f"⚠️  判断改变！")
        if new_result.get("has_negation"):
            print(f"   理由: 检测到否定词，反转了情感")
        if new_result.get("bullish_score") and new_result.get("bearish_score"):
            print(f"   利好得分: {new_result['bullish_score']}, 利空得分: {new_result['bearish_score']}")
    
    print()

print("=" * 80)
print("改进要点总结:")
print("=" * 80)
print("""
1. ✅ 关键词库扩充
   - 利好词: 涨停、暴涨、大幅上升、创新高、利好、回购、增持、利润增长等
   - 利空词: 跌停、暴跌、大幅下跌、创新低、风险、警告、停产、破产等

2. ✅ 检测否定词反转
   - "未能突破" -> 正确判为利空（而不是利好）
   - "没有增长" -> 正确判为利空

3. ✅ 加权评分机制
   - 强信号(3分): 涨停、跌停等极端词汇
   - 弱信号(1分): 上涨、下跌等常见词汇
   - 综合评分后判断

4. ✅ 宏观因素支持
   - 识别降息/加息等宏观关键词
   - 降息通常利好，加息通常利空

5. ✅ 置信度量化
   - 不再是简单的二分法
   - 返回0-1的置信度，标识判断的可信程度

6. ⚠️  局限性（下一步可优化）
   - 行业特异性（降息对银行利好但对存款类利空）
   - 上下文联系（多句综合分析）
   - 时间效应（市场预期vs实际影响）
""")

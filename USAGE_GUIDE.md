# 执行指南 - 如何使用改进的情感判断系统

## 📋 快速开始

### 1. 验证改进已集成
```bash
# 查看改进集成验证
python3 verify_integration.py

# 预期输出：5/5 通过，所有测试正常
```

### 2. 查看对比分析
```bash
# 查看改进前后的详细对比
python3 test_sentiment_analysis.py

# 查看可视化对比
python3 visualize_improvements.py
```

### 3. 阅读文档
```bash
# 问题分析文档（专业技术细节）
cat NEWS_SENTIMENT_ANALYSIS.md

# 改进总结文档（易读概览）
cat IMPROVEMENT_SUMMARY.md
```

---

## 🎯 系统如何工作

### 从用户角度（前端展示）

当用户在"市场总览"页面查看7*24快讯时，会看到：

```
┌─────────────────────────────────────────────────────┐
│ 央行宣布降准0.5个百分点，释放长期资金约1万亿元         │
│ 来源: 东方财富快讯  时间: 2小时前                    │
│                                                    │
│ 情感: 📈 利好 (置信度: ●●●)                          │
│ 判断理由: 基于宏观因素判断                            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 未能突破关键阻力位，技术面承压                        │
│ 来源: 财经快讯    时间: 5小时前                      │
│                                                    │
│ 情感: 📉 利空 (置信度: ●●●)                          │
│ 判断理由: 检测到否定词"未"，反转情感                  │
└─────────────────────────────────────────────────────┘
```

### 从系统角度（后端工作流）

1. **获取快讯**
   ```
   从 AkShare 获取实时快讯标题
   ```

2. **运行分析**
   ```python
   result = analyze_news_sentiment(title)
   ```

3. **返回结构化结果**
   ```python
   {
       "sentiment": "positive|negative|neutral",
       "confidence": 0.0-1.0,
       "reason": "具体判断理由",
       "bullish_score": 利好得分,
       "bearish_score": 利空得分,
       "has_negation": 是否有否定词
   }
   ```

4. **前端渲染**
   ```
   ✅ 显示情感标签 (利好/利空/中性)
   ✅ 显示置信度指示 (●●●或●●◐等)
   ✅ 显示判断理由 (鼠标悬停/点击显示)
   ```

---

## 🧠 判断逻辑详解

### 一个新闻如何被判断

以标题"未能突破关键阻力位，技术面承压"为例：

```
第1步：检查否定词
├─ 检查"未" ✓ 找到！
├─ 设置 has_negation = True
└─ 继续处理

第2步：词汇匹配与计分
├─ 检查"突破" ✓ 找到（强利好词）
│  ├─ 强利好词计数 = 1
│  ├─ 强利好得分 = 1 × 3 = 3
│
├─ 检查"承压" ✓ 找到（温和利空词）
│  ├─ 温和利空词计数 = 1
│  └─ 温和利空得分 = 1 × 1 = 1
│
├─ 最终得分：
│  ├─ bullish_score = 3
│  └─ bearish_score = 1

第3步：应用否定词反转
├─ has_negation = True？是！
├─ swap(bullish_score, bearish_score)
├─ 反转后：
│  ├─ bullish_score = 1
│  └─ bearish_score = 3

第4步：判决
├─ bearish_score(3) > bullish_score(1)？ 是！
├─ 判定为：NEGATIVE

第5步：置信度计算
├─ confidence = min(0.95, 0.5 + 3 × 0.15)
├─ confidence = min(0.95, 0.95)
└─ confidence = 0.95

结果：
{
    "sentiment": "negative",
    "confidence": 0.95,
    "reason": "检测到0个强利空词、1个温和利空词",
    "bullish_score": 1,
    "bearish_score": 3,
    "has_negation": true
}
```

---

## 🔑 关键词库速查

### 快速查找词汇分类

**强利好词 (3分)** - 非常确定的利好信号
```
涨停、暴涨、大幅上升、创新高、利好、回购、增持、利润增长
```

**强利空词 (3分)** - 非常确定的利空信号
```
跌停、暴跌、大幅下跌、创新低、风险、警告、停产、破产、违约、裁员
```

**温和利好词 (1分)** - 温和的利好信号
```
上涨、反弹、修复、改善、增长、回暖、扩张、提振、稳定
```

**温和利空词 (1分)** - 温和的利空信号
```
下跌、回落、走弱、承压、衰退、下滑、萎缩、削减、延迟、困难
```

**宏观关键词**
```
利好: 降息、降准、释放流动性、宽松
利空: 加息、收紧、美联储、缩表
```

**否定词**
```
未、没有、不会、不能、缺乏、无法、难以
```

---

## 📊 置信度指标说明

### 理解置信度数字

| 置信度 | 含义 | 建议 |
|--------|------|------|
| 0.9-1.0 | 非常确定 | 着重关注，信息有效 |
| 0.7-0.9 | 比较确定 | 作为参考，结合其他信息 |
| 0.6-0.7 | 一般确定 | 轻微参考，不作主要决策依据 |
| 0.5-0.6 | 不太确定 | 忽略不计 |
| 0.5 | 无信号 | 中性，完全无用的信息 |

### 什么导致高/低置信度

**高置信度（0.9+）的情况**
```
✅ "涨停板上涨" - 多个强利好词 → 置信度 0.95+
✅ "跌停板下跌" - 多个强利空词 → 置信度 0.95+
✅ "央行宣布降准" - 明确的宏观利好 → 置信度 0.8+
```

**低置信度（<0.6）的情况**
```
❌ "市场有所反应" - 没有明确词汇 → 置信度 0.5
❌ "企业提价或降价" - 好坏词各占一半 → 置信度 0.5
❌ "前景不确定" - 词汇冲突 → 置信度 <0.6
```

---

## 🐛 问题排查

### 如果某条快讯的判断看起来不对

#### 排查步骤

1. **记录原始快讯**
   ```
   标题：[完整标题]
   来源：[来源]
   时间：[发布时间]
   ```

2. **查看判断理由**
   - 鼠标悬停/点击快讯查看详细理由
   - 比如：看是否正确识别了关键词

3. **运行测试验证**
   ```bash
   # 修改 verify_integration.py 中的测试用例
   # 添加你的快讯标题
   python3 verify_integration.py
   ```

4. **反馈异常**
   - 如果判断仍然不对，可能是词汇库需要补充
   - 例如：某些特殊行业用语未被识别

#### 常见问题

**Q: 为什么"股价上升"被判为利空？**
```
A: 检查标题是否包含否定词（未、没有）
   例："股价未能上升" 中的"未"会反转判断
   这是正确行为！
```

**Q: 为什么"央行放宽"没被识别为利好？**
```
A: 词汇库中是"释放流动性"而不是"放宽"
   建议：可提交反馈添加"放宽"到词汇库
```

**Q: 置信度为什么这么低？**
```
A: 可能是：
   1. 利好词和利空词各占一半 → 判为中性
   2. 没有明确的词汇 → 无法确定
   这时应该结合其他信息综合判断
```

---

## 🚀 前端集成建议

如果你是前端开发者，可以这样使用返回的数据：

```javascript
// 后端返回的数据结构
const newsItem = {
    title: "央行宣布降准",
    sentiment: "positive",
    confidence: 0.8,
    reason: "基于宏观因素判断",
    bullish_score: 0,
    bearish_score: 0
};

// 1. 显示情感标签
function getSentimentIcon(sentiment, confidence) {
    if (sentiment === 'positive') {
        return confidence >= 0.8 ? '📈 强利好' : '📈 利好';
    } else if (sentiment === 'negative') {
        return confidence >= 0.8 ? '📉 强利空' : '📉 利空';
    } else {
        return '➡️ 中性';
    }
}

// 2. 显示置信度指示
function getConfidenceBar(confidence) {
    if (confidence >= 0.9) return '●●●';
    if (confidence >= 0.7) return '●●◐';
    if (confidence >= 0.6) return '●◐◐';
    if (confidence >= 0.5) return '◐◐◐';
    return '○○○';
}

// 3. 显示判断理由（鼠标悬停）
function showTooltip(reason) {
    // 实现 tooltip，显示 reason 字段
}

// 4. 根据置信度决定样式
function getTextColor(confidence) {
    if (confidence >= 0.8) return '#FF0000'; // 红色（高置信度）
    if (confidence >= 0.6) return '#FF6600'; // 橙色（中置信度）
    return '#CCCCCC'; // 灰色（低置信度）
}

// 5. 按置信度排序（可选）
function sortNewsBySentiment(newsList) {
    return newsList.sort((a, b) => {
        // 先按情感（利好在前），再按置信度（高在前）
        if (a.sentiment !== b.sentiment) {
            return a.sentiment === 'positive' ? -1 : 1;
        }
        return b.confidence - a.confidence;
    });
}
```

---

## 📝 维护建议

### 定期审查异常判断

1. **收集用户反馈**
   - 用户标记的"这个判断不对"的快讯

2. **分析模式**
   - 是否有特定的词汇、行业、时间段的错误？

3. **补充词汇库**
   ```python
   # 在 analyze_news_sentiment() 中添加新词汇
   strong_bullish.append("新增词汇")
   ```

4. **更新后验证**
   ```bash
   python3 verify_integration.py
   ```

### 性能监控

```python
# 可以添加性能统计
def get_sentiment_statistics(news_list):
    stats = {
        'positive': len([n for n in news_list if n['sentiment'] == 'positive']),
        'negative': len([n for n in news_list if n['sentiment'] == 'negative']),
        'neutral': len([n for n in news_list if n['sentiment'] == 'neutral']),
        'avg_confidence': sum(n['confidence'] for n in news_list) / len(news_list),
    }
    return stats
```

---

## ✅ 检查清单

部署前确保：

- [ ] 运行 `verify_integration.py` 全部通过
- [ ] 查看 `NEWS_SENTIMENT_ANALYSIS.md` 理解改进内容
- [ ] 查看 `IMPROVEMENT_SUMMARY.md` 了解核心要点
- [ ] 运行 `test_sentiment_analysis.py` 查看对比效果
- [ ] 运行 `visualize_improvements.py` 查看详细参数
- [ ] 前端已集成对应的字段显示（sentiment, confidence, reason）
- [ ] 后端已正确调用 `analyze_news_sentiment()` 函数

---

**一切准备就绪，可以开始使用！** 🚀

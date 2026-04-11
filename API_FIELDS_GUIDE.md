# 快讯返回字段完整说明

## 📋 返回的完整字段列表

### 基础信息字段
```python
{
    # 情感判断结果
    "sentiment": "positive|negative|neutral",
    
    # 显示字段
    "title": "新闻标题",
    "source": "新闻来源",
    "time": "发布时间",
    "link": "新闻链接",
    
    # 情感分析结果
    "impact": "市场影响",
    "reason": "判断理由（可显示为tooltip）",
    "confidence": 0.65,  # 置信度 0.0-1.0
    
    # 新增：颜色标签字段 ✨
    "tag_color": "#FF0000",  # 颜色代码
    "tag_text": "利好",       # 标签文本
    
    # 调试字段（可选）
    "bullish_score": 3,      # 利好得分
    "bearish_score": 1,      # 利空得分
    "has_negation": False,   # 是否检测到否定词
    "analysis_reason": "检测到1个强利好词、1个温和利好词"
}
```

---

## 🎨 颜色和标签映射

### 情感 → 颜色 → 标签

| 情感 | 颜色代码 | 颜色名 | 标签文本 | RGB | 使用场景 |
|------|---------|--------|---------|-----|---------|
| positive | #FF0000 | 红色 | 利好 | rgb(255,0,0) | 利好消息 |
| negative | #00B050 | 绿色 | 利空 | rgb(0,176,80) | 利空消息 |
| neutral | #FFFFFF | 白色 | 中性 | rgb(255,255,255) | 中性信息 |

---

## 📊 完整示例

### 示例1：利好新闻
```python
{
    "title": "诺基亚站上16年来新高",
    "source": "财经快讯",
    "time": "2小时前",
    "sentiment": "positive",
    "tag_color": "#FF0000",      # 红色
    "tag_text": "利好",
    "confidence": 0.95,
    "reason": "检测到2个强利好词、0个温和利好词",
    "bullish_score": 6,
    "bearish_score": 0,
    "has_negation": False
}
```

### 示例2：利空新闻
```python
{
    "title": "某光伏龙头企业发布业绩预警，产能过剩压力加大",
    "source": "财联社",
    "time": "8小时前",
    "sentiment": "negative",
    "tag_color": "#00B050",      # 绿色
    "tag_text": "利空",
    "confidence": 0.75,
    "reason": "检测到1个强利空词、1个温和利空词",
    "bullish_score": 0,
    "bearish_score": 4,
    "has_negation": False
}
```

### 示例3：中性新闻
```python
{
    "title": "中兴通讯：发布系列AI云电脑与移动互联产品矩阵",
    "source": "东方财富快讯",
    "time": "3小时前",
    "sentiment": "neutral",
    "tag_color": "#FFFFFF",      # 白色
    "tag_text": "中性",
    "confidence": 0.5,
    "reason": "新闻内容信息中性，无明确利好/利空信号",
    "bullish_score": 1,
    "bearish_score": 0,
    "has_negation": False
}
```

---

## 🔍 字段使用指南

### 前端如何使用

#### 1. 显示情感标签
```javascript
// 使用 tag_color 和 tag_text
<span style="background-color: ${news.tag_color}">
    ${news.tag_text}
</span>
```

#### 2. 显示置信度
```javascript
function getConfidenceIndicator(confidence) {
    if (confidence >= 0.9) return '●●●';     // 高置信
    if (confidence >= 0.7) return '●●◐';     // 中高置信
    if (confidence >= 0.6) return '●◐◐';     // 中置信
    return '◐◐◐';                            // 低置信
}
```

#### 3. 显示判断理由
```javascript
// 鼠标悬停显示
<span title="${news.reason}">?</span>
```

#### 4. 根据情感着色
```javascript
function getTextColor(sentiment) {
    switch(sentiment) {
        case 'positive': return '#FF0000';  // 红色
        case 'negative': return '#00B050';  // 绿色
        case 'neutral': return '#999999';   // 灰色
        default: return '#000000';
    }
}
```

---

## 📱 UI 渲染示例

### 基础快讯卡片
```html
<div class="news-item">
    <!-- 标题 -->
    <div class="news-title">${news.title}</div>
    
    <!-- 来源和时间 -->
    <div class="news-meta">
        <span class="source">${news.source}</span>
        <span class="time">${news.time}</span>
    </div>
    
    <!-- 情感标签（使用 tag_color） -->
    <div class="sentiment-row">
        <span 
            class="sentiment-badge" 
            style="background-color: ${news.tag_color}"
        >
            ${news.tag_text}
        </span>
        
        <!-- 置信度 -->
        <span class="confidence-indicator" title="${news.reason}">
            ${getConfidenceIndicator(news.confidence)}
        </span>
    </div>
    
    <!-- 链接 -->
    <a href="${news.link}" class="news-link">查看详情 →</a>
</div>
```

### 高级快讯卡片（带更多细节）
```html
<div class="news-card advanced">
    <div class="header">
        <h3>${news.title}</h3>
        <span 
            class="tag" 
            style="background-color: ${news.tag_color}; color: ${getTagTextColor(news.tag_color)}"
        >
            ${news.tag_text}
        </span>
    </div>
    
    <div class="metadata">
        <span>${news.source}</span>
        <span>${news.time}</span>
    </div>
    
    <div class="analysis">
        <div class="confidence">
            <label>置信度：</label>
            <div class="confidence-bar">
                <div style="width: ${news.confidence * 100}%"></div>
            </div>
            <span>${(news.confidence * 100).toFixed(0)}%</span>
        </div>
        
        <div class="reason" title="${news.reason}">
            <i class="icon-info"></i>
            <span>${news.reason}</span>
        </div>
    </div>
</div>
```

---

## 🎯 后端返回数据结构（JSON格式）

```json
{
    "news": [
        {
            "title": "诺基亚站上16年来新高",
            "source": "财经快讯",
            "time": "2小时前",
            "link": "https://...",
            "sentiment": "positive",
            "tag_color": "#FF0000",
            "tag_text": "利好",
            "confidence": 0.95,
            "impact": "市场影响",
            "reason": "检测到2个强利好词、0个温和利好词"
        },
        {
            "title": "央行宣布降准",
            "source": "新华社",
            "time": "1小时前",
            "link": "https://...",
            "sentiment": "positive",
            "tag_color": "#FF0000",
            "tag_text": "利好",
            "confidence": 0.8,
            "impact": "市场影响",
            "reason": "基于宏观因素判断（无明确多空信号）"
        },
        {
            "title": "中兴通讯发布AI产品",
            "source": "东方财富",
            "time": "3小时前",
            "link": "https://...",
            "sentiment": "neutral",
            "tag_color": "#FFFFFF",
            "tag_text": "中性",
            "confidence": 0.5,
            "impact": "市场影响",
            "reason": "新闻内容信息中性，无明确利好/利空信号"
        }
    ]
}
```

---

## 🔗 API 接口说明

### 快讯查询端点

```
GET /api/market_overview
或
GET /market_overview

返回格式：
{
    "klines": {...},
    "news": [
        {快讯对象1},
        {快讯对象2},
        ...
    ],
    "ai_insights": [...],
    ...
}
```

### 快讯对象字段详解

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| title | string | ✓ | 新闻标题 |
| source | string | ✓ | 来源媒体 |
| time | string | ✓ | 发布时间 |
| link | string | ✗ | 详情链接 |
| sentiment | enum | ✓ | positive\|negative\|neutral |
| tag_color | string | ✓ | 颜色代码 #RRGGBB |
| tag_text | string | ✓ | 标签文本 利好\|利空\|中性 |
| confidence | number | ✓ | 0.0-1.0 置信度 |
| reason | string | ✓ | 判断理由 |
| impact | string | ✓ | 市场影响描述 |

---

## ⚙️ 前端集成清单

- [ ] 更新接收数据的类型定义（TypeScript）
- [ ] 添加 tag_color 和 tag_text 字段的处理
- [ ] 更新情感标签的样式（支持白色中性标签）
- [ ] 更新颜色映射逻辑
- [ ] 测试各种情感的显示效果
- [ ] 验证置信度指示器的显示
- [ ] 验证 tooltip 中的判断理由显示
- [ ] 测试响应式布局

---

**所有字段已准备好，前端可以直接使用！** ✅

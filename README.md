# 智投星 - AI 智能投顾平台 Demo

> 面向财富管理场景的 AI 投顾演示系统，覆盖市场洞察、风险测评、智能配置、智能选股、智能选基、组合管理与 AI 问答。

## 产品定位

**智投星（智能投顾助手）** 是一款面向财富管理 / 投顾演示场景的 **Web Demo**：用「看市场 → 认识自己 → 配资产 → 选标的 → 管组合 → 问 AI」串联完整投顾链路，展示 **数据 + 规则 + 大模型** 如何共同支撑投顾交互。

- **形态**：Flask 后端 + 单页前端（ECharts），偏「可演示、可扩展、可回退」的工程取向，而非面向 C 端交易的商用终端。
- **价值主张**：行情与接口不稳定时仍尽量有界面、有解释、有兜底；在 Kimi（Moonshot）可用时，增强解读、理由、洞察与对话的表达力。

## 核心痛点与应对

| 痛点 | 应对方式 |
|------|----------|
| 投顾讲解抽象、难落地 | 市场快照 + 板块/情绪 + **AI 市场洞察**；智能配置带情绪调仓与 **Kimi 配置建议**；选股/选基带 **AI 理由或解读**。 |
| 客户持仓与问答脱节 | AI 助手支持 **携带当前持仓** 请求，资产识别与上下文更贴合。 |
| 公网数据源常抖动 | AkShare / efinance 多源组合；选股等 **缓存与本地/规则回退**；失败时结构化空态或兜底文案。 |
| 合规与可控性 | 大模型可按模块 **环境变量关闭**；无密钥或失败时走 **本地规则/模板/缓存**。 |
| 组合管理效率 | 持仓 CRUD、收益曲线与沪深 300 对比、**OCR 截图导入（可预览勾选）**；可选 **Kimi 估值、组合再平衡** 等深度能力。 |

## 一页 PPT 大纲（对外口述用）

- **标题**：智投星 — AI 智能投顾演示平台｜数据 + 规则 + Kimi｜非投资建议  
- **定位**：财富管理 / 投顾场景 Web Demo；完整链路可独立模块演示。  
- **痛点 → 解法**：讲不清 → AI 洞察/理由；接不住持仓 → 上下文对话；数据抖 → 多源+缓存+回退；要可控 → 按模块关 AI；录入慢 → OCR。  
- **功能**：市场总览 · 风险测评 · 智能配置 · 智能选股 · 智能选基 · 我的持有 · AI 助手 ·（投教中心，默认隐藏）  
- **技术**：Flask + AkShare/efinance + ECharts；大模型仅 **Kimi（Moonshot）**；默认 `http://127.0.0.1:5008`  

## 项目简介

本项目基于 Flask + 原生前端实现，聚焦「可演示、可扩展、可回退」：

- 多个核心模块可独立展示，也可形成完整投顾链路
- 外部数据异常时提供缓存与兜底，保障页面可用性
- 兼顾专业性（风险指标/同类对比）与交互体验（搜索、导入、编辑）

## 当前版本主要功能

| 模块 | 关键能力 | 说明 |
|------|----------|------|
| 市场总览 | 行情数据 + 快讯情绪 + AI 洞察 | 多源指数/K 线/板块/新闻；Kimi 标注情绪与生成洞察（可关） |
| 风险测评 | KYC 问卷与风险画像 | 输出风险等级和适配建议（规则侧，不调大模型） |
| 智能配置 | 资产配置 + 情绪调仓 + AI 建议 | 规则调仓 + Kimi 文案（可关） |
| 智能选股 | 多因子评分 + 实时数据回退 | 缓存/估算兜底；Kimi 生成选股理由（可关） |
| 智能选基 | 行业雷达 + 基金筛选 + 可选 AI | `fund_selector`；筛选失败有降级；AI 解读可选 |
| 组合管理 | 持仓维护 + 统计分析 + OCR | 编辑/删除/截图导入预览；收益率 vs 沪深300；Kimi 估值/再平衡 |
| AI 助手 | 资产问答 + 持仓上下文 | `POST /api/chat`；Kimi 不可用时 Local-Fallback |
| 投教中心 | 实时行情拼装课程 | 侧栏默认隐藏；`GET /api/education` |

## 技术架构

- 后端：`Python + Flask`
- 前端：`HTML + CSS + JavaScript`（单页）
- 图表：`ECharts 5`（CDN）
- 数据：`AkShare`（多源回退与缓存）+ `efinance`（东财系快照，如市场卡片）
- 直连补充：腾讯 `qt.gtimg.cn`、新浪 `hq.sinajs.cn` 等（指数/量能等）
- OCR：`Tesseract`（`pytesseract`）或 `rapidocr_onnxruntime`（可选，截图识别持仓）
- 大模型：**Moonshot OpenAI 兼容接口（Kimi）**，默认 `https://api.moonshot.cn/v1/chat/completions`

## 配置说明（`.env`）

复制 `.env.example` 为 `.env` 后填写。`dotenv_local.py` 会加载项目根目录 `.env`；其中 **`KIMI_API_KEY`、`MOONSHOT_API_KEY`、`KIMI_MODEL`、`KIMI_API_URL` 以 `.env` 中非空值为准**，可覆盖 shell 中已 export 的旧值。

| 变量 | 作用 |
|------|------|
| `KIMI_API_KEY` / `MOONSHOT_API_KEY` | Moonshot API 密钥，二选一 |
| `KIMI_MODEL` | 模型 ID（默认常见为 `moonshot-v1-8k`，以平台当前文档为准） |
| `KIMI_API_URL` | 可选，覆盖默认 Chat Completions 地址 |
| `NEWS_USE_KIMI` | 设为 `0` 关闭快讯 Kimi 情绪标注 |
| `INSIGHTS_USE_KIMI` | 设为 `0` 关闭 AI 市场洞察的 Kimi 生成 |
| `ALLOCATION_USE_KIMI` | 设为 `0` 关闭智能配置中的 Kimi 建议 |
| `STOCK_REASON_USE_KIMI` | 设为 `0` 关闭智能选股中的 Kimi 理由 |
| `FLASK_APPLICATION_ROOT` | 子路径部署时前端 `fetch` 前缀（如 `/app`） |

## 大模型（Kimi）使用模块一览

| 场景 | 入口 / 模块 |
|------|-------------|
| 快讯利好/利空/中性 | `kimi_news_sentiment.py` → `GET /api/market` |
| AI 市场洞察 | `kimi_market_insights.py` → `GET /api/market` |
| 智能配置文案 | `kimi_allocation_advice.py` → `POST /api/allocation-advice` |
| 智能选股理由 | `kimi_stock_reason.py` → `POST /api/stock-screen` |
| AI 助手对话 | `app.py`（`_call_kimi`）→ `POST /api/chat` |
| 持仓估值分析 | `app.py` → `POST /api/kimi-valuation` |
| 组合再平衡 | `app.py` → `POST /api/kimi/rebalance`、`POST /api/kimi-portfolio-rebalance`（健康检查 `GET /api/kimi/rebalance/health`） |
| 智能选基 AI 解读 | `fund_selector.py`（`FundAIInsights`）→ `POST /api/fund-screen`（`include_ai: true`） |

说明：风险测评打分、情绪调仓数值规则、多数纯拉数接口、`/api/education` 等 **不调用** 大模型。

## 本次更新内容（已落地）

### 1) 组合页收益率曲线升级

- 组合图从「净值走势」升级为「收益率曲线（我的组合 vs 沪深300）」
- 新增后端接口：`/api/hs300-return`
- 优先使用真实沪深300历史数据；失败时自动回退模拟数据，避免空图

### 2) 持仓管理增强（可编辑 + 导入前预览）

- 持仓表支持统一操作列（编辑/删除）
- 新增「编辑持仓」弹窗：
  - 股票可修改：持仓数量、成本价、现价
  - 基金可修改：持有金额、持有收益
- OCR 截图导入新增「导入预览弹窗」：
  - 支持逐条勾选后再确认导入
  - 导入结果区分新增、合并、忽略数量

### 3) 搜索能力增强（股票/基金/统一资产）

- 代码匹配从「精确+前缀」扩展到「精确+前缀+包含」
- 支持数字清洗后的代码匹配，提高模糊输入命中率
- 基金搜索在极端情况下提供 6 位代码兜底候选，避免“完全搜不到”

### 4) 智能选股稳定性增强

- 增加 PE/ROE 行业中位数参考与统一补全逻辑，减少空值
- 实时行情源增加优先级与回退链路
- 选股结果增加缓存，异常时可返回上次可用结果
- 当实时数据不可用时，可回退基础因子估算结果

### 5) AI 助手上下文与容错增强

- 前端在聊天请求中附带当前持仓，后端统一归一化处理
- 资产识别增强：支持更广基金池、持仓优先识别、中文语境代码识别
- Kimi 请求增加重试与限流处理，降低偶发失败影响
- 当用户像在问具体标的但模型不可用时，返回结构化引导提示

## 快速启动

```bash
# 1) 进入项目目录
cd ~/Desktop/智能投顾助手

# 2) 创建虚拟环境（首次需要）
python3 -m venv .venv

# 3) 激活虚拟环境
source .venv/bin/activate

# 4) 安装依赖
python -m pip install -r requirements.txt

# 5) 启动服务
python app.py

# 6) 浏览器访问
# http://127.0.0.1:5008
```

退出虚拟环境：`deactivate`

## 常用接口（节选）

- `GET /api/market`：市场总览（含快讯、洞察、情绪等）
- `GET /api/hs300-return?days=365`：沪深300收益率序列
- `POST /api/chat`：AI 对话（支持携带持仓上下文）
- `POST /api/allocation-advice`：智能配置（含可选 Kimi）
- `POST /api/stock-screen`：智能选股
- `GET /api/sector-radar`、`POST /api/fund-screen`、`GET /api/fund-detail/<code>`：智能选基
- `GET /api/fund-search`、`GET /api/stock-search`、`GET /api/asset-search`：搜索
- `POST /api/portfolio-ocr-import`：截图 OCR 持仓识别
- `POST /api/kimi-valuation`、`POST /api/kimi/rebalance`：Kimi 深度分析（需密钥）

## 预览与验证建议

启动后建议按以下路径体验：

1. 组合管理页查看收益率曲线是否正常加载
2. 在持仓列表中测试编辑股票/基金并刷新页面验证本地持久化
3. 使用截图导入功能，确认可在预览中勾选再导入
4. 在 AI 助手中询问已持有标的，检查回答是否体现持仓信息

## 风险提示

本项目用于产品演示与交互验证，不构成任何投资建议。涉及行情与 AI 输出的内容仅供参考，实际投资请结合专业机构意见与个人风险承受能力。

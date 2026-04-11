// ==================== State ====================
let currentPage = 'dashboard';
let riskQuestions = [];
let currentQuestion = 0;
let userAnswers = [];
let riskProfile = null;
let riskResultData = null;
let allocationData = null;
let rawKlineData = [];
let currentKlinePeriod = 'day';
let rawKlineMap = { shanghai: [], hstech: [], nasdaq: [] };
let currentKlineIndex = 'shanghai';
let holdingsData = [];
let holdingIndicators = {};
let currentHoldingTab = 'stock';
let currentHoldingPage = 1;
const HOLDINGS_PAGE_SIZE = 10;
const RISK_STORAGE_KEY = 'smartAdvisorRiskResultV1';
const HOLDINGS_STORAGE_KEY = 'smartAdvisorMockHoldingsV1';
let portfolioRawData = null;
/** Kimi 组合调仓建议（「AI 调仓建议」卡片） */
let portfolioKimiRebalance = {
    loading: false,
    error: '',
    text: '',
    hash: '',
    macroSnapshot: '',
};
let _portfolioKimiDebounceTimer = null;
let selectedAddAsset = null;
let pendingOcrImportItems = [];
let hs300ReturnCache = null;
const LOCAL_FUND_SUGGEST_POOL = [
    { code: '161725', name: '招商中证白酒指数(LOF)', category: 'LOF' },
    { code: '159915', name: '创业板ETF', category: 'ETF' },
    { code: '510300', name: '沪深300ETF', category: 'ETF' },
    { code: '005827', name: '易方达蓝筹精选混合', category: '混合型' },
    { code: '003095', name: '中欧医疗健康混合A', category: '混合型' },
    { code: '012348', name: '富国中证新能源汽车指数A', category: '指数型' },
    { code: '009865', name: '招商中证白酒指数A', category: '指数型' },
    { code: '000001', name: '华夏成长混合', category: '混合型' }
];
const LOCAL_STOCK_SUGGEST_POOL = [
    { code: '600519', name: '贵州茅台', category: '股票' },
    { code: '300750', name: '宁德时代', category: '股票' },
    { code: '300502', name: '新易盛', category: '股票' },
    { code: '002594', name: '比亚迪', category: '股票' },
    { code: '601318', name: '中国平安', category: '股票' },
    { code: '600036', name: '招商银行', category: '股票' },
    { code: '000858', name: '五粮液', category: '股票' },
    { code: '000333', name: '美的集团', category: '股票' },
    { code: '601899', name: '紫金矿业', category: '股票' }
];

/** 与模板注入的 request.script_root 拼接（子路径部署时 API 仍正确） */
function apiUrl(path) {
    const base = (typeof window !== 'undefined' && window.__API_BASE__)
        ? String(window.__API_BASE__).replace(/\/$/, '')
        : '';
    const p = path.startsWith('/') ? path : ('/' + path);
    return base + p;
}

/** 读取 fetch 响应为 JSON；若为 HTML 或非 JSON 则返回可识别结构，避免 Unexpected token '<' */
async function parseFetchJson(res) {
    const text = await res.text();
    const trimmed = text.trim();
    if (!trimmed) {
        return { _parseFailed: true, _httpStatus: res.status, _message: `空响应（HTTP ${res.status}）` };
    }
    if (trimmed[0] === '<') {
        const m = text.match(/<title>([^<]*)<\/title>/i);
        const title = m ? m[1].trim() : 'HTML';
        return {
            _parseFailed: true,
            _httpStatus: res.status,
            _message: `服务器返回 HTML（${title}），HTTP ${res.status}。常见原因：接口 404（请重启 Flask 加载最新路由）、访问端口与启动端口不一致、或反向代理把 /api 指到了前端首页。`,
        };
    }
    try {
        return JSON.parse(text);
    } catch (e) {
        return {
            _parseFailed: true,
            _httpStatus: res.status,
            _message: `非 JSON（HTTP ${res.status}）：${e.message}。开头：${trimmed.slice(0, 100)}`,
        };
    }
}

function saveRiskResult(data) {
    if (!data || !data.profile || !data.allocation) return;
    const payload = {
        profile: data.profile,
        allocation: data.allocation,
        score: data.score,
        max_score: data.max_score,
        radar: data.radar
    };
    // 优先写服务端（本地文件持久化）
    fetch('/api/risk-result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).catch(e => console.warn('风险测评结果上报服务端失败，仅保存至浏览器缓存:', e));
    // 同步写 localStorage 作为离线缓存
    try {
        localStorage.setItem(RISK_STORAGE_KEY, JSON.stringify(payload));
    } catch (e) {
        console.warn('Failed to save risk result to localStorage:', e);
    }
}

function getDefaultRadar() {
    return {
        risk_tolerance: 3,
        investment_exp: 3,
        financial_knowledge: 3,
        income_stability: 3,
        investment_horizon: 3
    };
}

function loadRiskResult() {
    // 仅作 localStorage 同步读取（用于离线或接口未响应前的快速渲染）
    try {
        const raw = localStorage.getItem(RISK_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || !parsed.profile || !parsed.allocation) return null;
        parsed.radar = parsed.radar || getDefaultRadar();
        parsed.score = typeof parsed.score === 'number' ? parsed.score : 30;
        parsed.max_score = typeof parsed.max_score === 'number' ? parsed.max_score : 50;
        return parsed;
    } catch (e) {
        console.warn('Failed to load risk result from localStorage:', e);
        return null;
    }
}

async function loadRiskResultFromServer() {
    try {
        const res = await fetch('/api/risk-result?id=latest');
        const data = await res.json();
        if (!data.found || !data.result) return null;
        const r = data.result;
        r.radar = r.radar || getDefaultRadar();
        r.score = typeof r.score === 'number' ? r.score : 30;
        r.max_score = typeof r.max_score === 'number' ? r.max_score : 50;
        // 同步写入 localStorage 保持一致
        try { localStorage.setItem(RISK_STORAGE_KEY, JSON.stringify(r)); } catch (_) {}
        return r;
    } catch (e) {
        console.warn('从服务端加载风险测评结果失败，回退到浏览器缓存:', e);
        return loadRiskResult();
    }
}

function clearRiskResult() {
    // 删除服务端记录
    fetch('/api/risk-result', { method: 'DELETE' })
        .catch(e => console.warn('服务端风险测评结果删除失败:', e));
    // 同时清 localStorage
    try {
        localStorage.removeItem(RISK_STORAGE_KEY);
    } catch (e) {
        console.warn('Failed to clear risk result from localStorage:', e);
    }
}

async function restoreRiskAssessmentUI() {
    // 先用 localStorage 快速渲染（避免等待接口时页面空白）
    const cached = loadRiskResult();
    if (cached) {
        riskProfile = cached.profile;
        riskResultData = cached;
        allocationData = cached.allocation;
        document.getElementById('riskIntro').classList.add('hidden');
        document.getElementById('riskQuiz').classList.add('hidden');
        document.getElementById('riskResult').classList.remove('hidden');
    }
    // 再从服务端拉取最新（会覆盖缓存版本）
    const saved = await loadRiskResultFromServer();
    if (!saved) return;
    riskProfile = saved.profile;
    riskResultData = saved;
    allocationData = saved.allocation;
    document.getElementById('riskIntro').classList.add('hidden');
    document.getElementById('riskQuiz').classList.add('hidden');
    document.getElementById('riskResult').classList.remove('hidden');
    // 若当前正处于测评页则刷新显示
    if (currentPage === 'risk') renderResult(saved);
}

// ==================== Page Navigation ====================
function switchPage(page) {
    document.querySelectorAll('.page-content').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    document.getElementById('page-' + page).classList.add('active');
    document.querySelector(`[data-page="${page}"]`).classList.add('active');

    const titles = {
        dashboard: '市场总览', risk: '风险测评', allocation: '智能配置',
        screening: '智能选股', portfolio: '我的持有', chat: 'AI 助手', education: '投教中心'
    };
    document.getElementById('pageTitle').textContent = titles[page] || '';
    currentPage = page;

    if (page === 'dashboard') loadDashboard();
    if (page === 'risk' && riskResultData) renderResult(riskResultData);
    if (page === 'screening') runScreening();
    if (page === 'portfolio') loadPortfolio();
    if (page === 'education') loadEducation();
    if (page === 'allocation' && allocationData) showAllocationDetail(allocationData);
}

// ==================== Dashboard ====================
async function loadDashboard() {
    renderNews([], 'loading');
    renderInsights([], 'loading', '');
    try {
        const res = await fetch('/api/market');
        const data = await res.json();
        // 板块日期徽章须先于可能抛错的渲染更新（例如 sectors 非数组时 renderSectors 会异常）
        const sa = data.sentiment_analysis && typeof data.sentiment_analysis === 'object' ? data.sentiment_analysis : {};
        const boardDate = (data.sector_board_data_date && String(data.sector_board_data_date).trim())
            || (sa.volume_data_date && String(sa.volume_data_date).trim())
            || '';
        setSectorHeatmapDateBadge(boardDate);
        // 缓存行情快照供智能配置调用，避免重复请求
        window.__marketData = {
            a_share_indices: data.indices || [],
            hk_indices: data.hk_indices || [],
            us_indices: data.us_indices || [],
            sectors: data.sectors || [],
            flash_news: data.news || [],
            market_sentiment: data.market_sentiment || {},
            sentiment_analysis: data.sentiment_analysis || {},
        };
        renderIndices(data.indices, data.update_time);  // 传入更新时间
        renderHkIndices(data.hk_indices || []);
        renderUsIndices(data.us_indices || []);
        renderKline(data.kline, data.kline_map);
        renderSectors(data.sectors);
        renderInsights(
            data.ai_insights || [],
            data.insights_engine || 'kimi_disabled',
            data.insights_kimi_error || ''
        );
        renderSentiment(data.market_sentiment, data.sentiment_analysis || {});
        renderNews(data.news || [], data.news_sentiment_engine || 'kimi_disabled', data.news_kimi_error || '');
    } catch (e) {
        console.error('Failed to load dashboard:', e);
        setSectorHeatmapDateBadge('');
        renderInsights([], 'unavailable', '');
        renderNews([], 'unavailable');
    }
}

function setSectorHeatmapDateBadge(label) {
    const el = document.getElementById('sectorHeatmapDateBadge');
    if (!el) return;
    const t = label && String(label).trim();
    el.textContent = t || '—';
}

function renderIndices(indices, updateTime) {
    const row = document.getElementById('indicesRow');
    const topUpdate = document.getElementById('pageUpdateTime');

    if (topUpdate) {
        topUpdate.textContent = updateTime ? `数据更新时间: ${updateTime}` : '';
    }

    let html = `<div class="update-time-banner">
        <span class="update-icon">🇨🇳</span>
        <span class="update-text">A股三大指数</span>
        <span class="update-source">数据源: AkShare（ak.stock_zh_index_daily）</span>
    </div>`;

    // 渲染指数卡片
    html += indices.map(idx => {
        const cls = idx.change >= 0 ? 'up' : 'down';
        const arrow = idx.change >= 0 ? '▲' : '▼';
        return `<div class="index-card">
            <div class="index-name">${idx.name}</div>
            <div class="index-value ${cls}">${idx.value.toFixed(2)}</div>
            <div class="index-change ${cls}">${arrow} ${Math.abs(idx.change).toFixed(2)}%</div>
        </div>`;
    }).join('');

    row.innerHTML = html;
}

function renderUsIndices(indices) {
    const row = document.getElementById('usIndicesRow');
    if (!row) return;

    if (!indices || indices.length === 0) {
        row.innerHTML = '';
        return;
    }

    const title = `<div class="update-time-banner">
        <span class="update-icon">🇺🇸</span>
        <span class="update-text">美股三大指数</span>
        <span class="update-source">数据源: AkShare 新浪美股指数</span>
    </div>`;

    const cards = indices.map(idx => {
        const cls = idx.change >= 0 ? 'up' : 'down';
        const arrow = idx.change >= 0 ? '▲' : '▼';
        return `<div class="index-card">
            <div class="index-name">${idx.name}</div>
            <div class="index-value ${cls}">${idx.value.toFixed(2)}</div>
            <div class="index-change ${cls}">${arrow} ${Math.abs(idx.change).toFixed(2)}%</div>
        </div>`;
    }).join('');

    row.innerHTML = title + cards;
}

function renderHkIndices(indices) {
    const row = document.getElementById('hkIndicesRow');
    if (!row) return;

    if (!indices || indices.length === 0) {
        row.innerHTML = '';
        return;
    }

    const title = `<div class="update-time-banner">
        <span class="update-icon">🇭🇰</span>
        <span class="update-text">港股三大指数</span>
        <span class="update-source">数据源: 腾讯港股实时行情</span>
    </div>`;

    const cards = indices.map(idx => {
        const cls = idx.change >= 0 ? 'up' : 'down';
        const arrow = idx.change >= 0 ? '▲' : '▼';
        return `<div class="index-card">
            <div class="index-name">${idx.name}</div>
            <div class="index-value ${cls}">${idx.value.toFixed(2)}</div>
            <div class="index-change ${cls}">${arrow} ${Math.abs(idx.change).toFixed(2)}%</div>
        </div>`;
    }).join('');

    row.innerHTML = title + cards;
}

function renderKline(data, klineMap) {
    rawKlineData = Array.isArray(data) ? data : [];
    rawKlineMap = {
        shanghai: Array.isArray(klineMap?.shanghai) ? klineMap.shanghai : rawKlineData,
        hstech: Array.isArray(klineMap?.hstech) ? klineMap.hstech : [],
        nasdaq: Array.isArray(klineMap?.nasdaq) ? klineMap.nasdaq : []
    };
    drawKlineByPeriod(currentKlinePeriod);
}

function drawKlineByPeriod(period) {
    const chart = echarts.init(document.getElementById('klineChart'));
    const base = rawKlineMap[currentKlineIndex] || [];
    const source = period === 'week' ? convertDailyToWeekly(base) : base;

    const dates = source.map(d => d.date);
    const closes = source.map(d => d.close);
    const volumes = source.map(d => d.volume);

    const ma5 = calcMA(closes, 5);
    const ma20 = calcMA(closes, 20);
    const colorClose = '#3b82f6';
    const colorMA5 = '#f59e0b';
    const colorMA20 = '#8b5cf6';
    const colorVol = 'rgba(59,130,246,0.4)';

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#1a2332',
            borderColor: '#334155',
            textStyle: { color: '#e2e8f0', fontSize: 12 },
            formatter: function(params) {
                if (!params || !params.length) return '';
                const date = params[0].axisValue || '';
                const lines = [`<div style="margin-bottom:6px;">${date}</div>`];
                const colorMap = {
                    '收盘价': colorClose,
                    'MA5': colorMA5,
                    'MA20': colorMA20,
                    '成交量': colorVol,
                };
                params.forEach(p => {
                    const c = colorMap[p.seriesName] || p.color;
                    const val = (p.value === null || p.value === undefined) ? '-' : Number(p.value).toFixed(2);
                    lines.push(
                        `<div><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${c};margin-right:6px;"></span>${p.seriesName}: ${val}</div>`
                    );
                });
                return lines.join('');
            }
        },
        grid: [
            { left: 60, right: 20, top: 20, height: '60%' },
            { left: 60, right: 20, top: '76%', height: '16%' }
        ],
        xAxis: [
            { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#334155' }}, axisLabel: { color: '#64748b', fontSize: 11 }, gridIndex: 0 },
            { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#334155' }}, axisLabel: { show: false }, gridIndex: 1 }
        ],
        yAxis: [
            { scale: true, splitLine: { lineStyle: { color: '#1e293b' }}, axisLabel: { color: '#64748b', fontSize: 11 }, gridIndex: 0 },
            { scale: true, splitLine: { show: false }, axisLabel: { show: false }, gridIndex: 1 }
        ],
        series: [
            {
                name: '收盘价', type: 'line', data: closes, smooth: true, symbol: 'none',
                lineStyle: { color: colorClose, width: 2 },
                itemStyle: { color: colorClose },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.25)' },
                    { offset: 1, color: 'rgba(59,130,246,0)' }
                ])},
                xAxisIndex: 0, yAxisIndex: 0
            },
            { name: 'MA5', type: 'line', data: ma5, smooth: true, symbol: 'none', lineStyle: { color: colorMA5, width: 1 }, itemStyle: { color: colorMA5 }, xAxisIndex: 0, yAxisIndex: 0 },
            { name: 'MA20', type: 'line', data: ma20, smooth: true, symbol: 'none', lineStyle: { color: colorMA20, width: 1 }, itemStyle: { color: colorMA20 }, xAxisIndex: 0, yAxisIndex: 0 },
            {
                name: '成交量', type: 'bar', data: volumes,
                itemStyle: { color: colorVol },
                xAxisIndex: 1, yAxisIndex: 1
            }
        ]
    }, true);

    window.addEventListener('resize', () => chart.resize());
}

function convertDailyToWeekly(data) {
    if (!Array.isArray(data) || data.length === 0) return [];
    const weekly = [];
    let currentWeek = null;

    for (const item of data) {
        const d = new Date(item.date);
        if (Number.isNaN(d.getTime())) continue;
        const weekKey = `${d.getFullYear()}-${getIsoWeek(d)}`;

        if (!currentWeek || currentWeek.weekKey !== weekKey) {
            if (currentWeek) {
                weekly.push({
                    date: currentWeek.date,
                    open: currentWeek.open,
                    high: currentWeek.high,
                    low: currentWeek.low,
                    close: currentWeek.close,
                    volume: currentWeek.volume
                });
            }
            currentWeek = {
                weekKey,
                date: item.date,
                open: item.open,
                high: item.high,
                low: item.low,
                close: item.close,
                volume: item.volume
            };
        } else {
            currentWeek.high = Math.max(currentWeek.high, item.high);
            currentWeek.low = Math.min(currentWeek.low, item.low);
            currentWeek.close = item.close;
            currentWeek.volume += item.volume;
            currentWeek.date = item.date;
        }
    }

    if (currentWeek) {
        weekly.push({
            date: currentWeek.date,
            open: currentWeek.open,
            high: currentWeek.high,
            low: currentWeek.low,
            close: currentWeek.close,
            volume: currentWeek.volume
        });
    }
    return weekly;
}

function getIsoWeek(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

function changeKlinePeriod(period) {
    currentKlinePeriod = period;
    document.querySelectorAll('.card-actions .btn-sm').forEach(btn => btn.classList.remove('active'));
    const target = period === 'day' ? '日K' : '周K';
    document.querySelectorAll('.card-actions .btn-sm').forEach(btn => {
        if (btn.textContent.trim() === target) btn.classList.add('active');
    });
    drawKlineByPeriod(period);
}

function changeKlineIndex(indexName) {
    currentKlineIndex = indexName;
    const select = document.getElementById('klineIndexSelect');
    if (select && select.value !== indexName) {
        select.value = indexName;
    }
    drawKlineByPeriod(currentKlinePeriod);
}

function renderKlineOld(data) {
    const chart = echarts.init(document.getElementById('klineChart'));
    const dates = data.map(d => d.date);
    const closes = data.map(d => d.close);
    const volumes = data.map(d => d.volume);

    const ma5 = calcMA(closes, 5);
    const ma20 = calcMA(closes, 20);

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#1a2332',
            borderColor: '#334155',
            textStyle: { color: '#e2e8f0', fontSize: 12 }
        },
        grid: [
            { left: 60, right: 20, top: 20, height: '60%' },
            { left: 60, right: 20, top: '76%', height: '16%' }
        ],
        xAxis: [
            { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#334155' }}, axisLabel: { color: '#64748b', fontSize: 11 }, gridIndex: 0 },
            { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#334155' }}, axisLabel: { show: false }, gridIndex: 1 }
        ],
        yAxis: [
            { scale: true, splitLine: { lineStyle: { color: '#1e293b' }}, axisLabel: { color: '#64748b', fontSize: 11 }, gridIndex: 0 },
            { scale: true, splitLine: { show: false }, axisLabel: { show: false }, gridIndex: 1 }
        ],
        series: [
            {
                name: '收盘价', type: 'line', data: closes, smooth: true, symbol: 'none',
                lineStyle: { color: '#3b82f6', width: 2 },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.25)' },
                    { offset: 1, color: 'rgba(59,130,246,0)' }
                ])},
                xAxisIndex: 0, yAxisIndex: 0
            },
            { name: 'MA5', type: 'line', data: ma5, smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 1 }, xAxisIndex: 0, yAxisIndex: 0 },
            { name: 'MA20', type: 'line', data: ma20, smooth: true, symbol: 'none', lineStyle: { color: '#8b5cf6', width: 1 }, xAxisIndex: 0, yAxisIndex: 0 },
            {
                name: '成交量', type: 'bar', data: volumes,
                itemStyle: { color: 'rgba(59,130,246,0.4)' },
                xAxisIndex: 1, yAxisIndex: 1
            }
        ]
    });

    window.addEventListener('resize', () => chart.resize());
}

function calcMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            const slice = data.slice(0, i + 1);
            const sum = slice.reduce((a, b) => a + b, 0);
            result.push(+(sum / slice.length).toFixed(2));
            continue;
        }
        let sum = 0;
        for (let j = 0; j < period; j++) sum += data[i - j];
        result.push(+(sum / period).toFixed(2));
    }
    return result;
}

function renderSectors(sectors) {
    const grid = document.getElementById('sectorGrid');
    if (!grid) return;
    const list = Array.isArray(sectors) ? sectors : [];
    grid.innerHTML = list.map(s => {
        const isUp = s.change >= 0;
        const bg = isUp
            ? `rgba(239,68,68,${Math.min(0.35, Math.abs(s.change) * 0.07)})`
            : `rgba(16,185,129,${Math.min(0.35, Math.abs(s.change) * 0.07)})`;
        const color = isUp ? '#ef4444' : '#10b981';
        return `<div class="sector-item" style="background:${bg}">
            <div class="sector-name">${s.name}</div>
            <div class="sector-change" style="color:${color}">${isUp ? '+' : ''}${s.change.toFixed(2)}%</div>
        </div>`;
    }).join('');
}

function _insightsEngineBanner(engine, kimiError) {
    const e = engine || 'kimi_disabled';
    let cls = 'news-engine-banner is-rules';
    let text = '市场洞察仅使用 Kimi：当前未启用或不可用';
    if (e === 'kimi') {
        cls = 'news-engine-banner is-kimi';
        text = '市场洞察由「Kimi 大模型」根据当日快照（A股/港美股指数、板块热力、7×24 快讯及情绪标注）自动生成';
    } else if (e === 'kimi_failed') {
        cls = 'news-engine-banner is-unavailable';
        text = 'Kimi 生成市场洞察失败，以下为占位说明（无本地规则拼装替代）';
    } else if (e === 'kimi_disabled') {
        cls = 'news-engine-banner is-rules';
        text = '市场洞察未调用 Kimi：请查看下方「详情」原因。常见情况：.env 中未填写 KIMI_API_KEY，或误设 INSIGHTS_USE_KIMI=0，或 shell 里 export 了空密钥挡住 .env。亦支持变量名 MOONSHOT_API_KEY。';
    } else if (e === 'loading') {
        cls = 'news-engine-banner is-loading';
        text = '正在调用 Kimi 生成市场洞察…';
    } else if (e === 'unavailable') {
        cls = 'news-engine-banner is-unavailable';
        text = '市场接口异常，市场洞察未更新';
    }
    const err = (kimiError && String(kimiError).trim()) ? String(kimiError).trim() : '';
    const sub = err && (e === 'kimi_failed' || e === 'kimi_disabled')
        ? `<div class="news-engine-banner-detail">详情：${_escapeHtml(err)}</div>`
        : '';
    return `<div class="${cls}" role="status" aria-live="polite">${text}${sub}</div>`;
}

function renderInsights(insights, engine, kimiError) {
    const el = document.getElementById('aiInsights');
    if (!el) return;
    const eng = engine || 'kimi_disabled';
    const banner = _insightsEngineBanner(eng, kimiError || '');
    const list = Array.isArray(insights) ? insights : [];
    const body = list.length
        ? list.map((text) => `<div class="insight-item">${_escapeHtml(String(text))}</div>`).join('')
        : '<div class="insight-item">暂无市场洞察</div>';
    el.innerHTML = banner + body;
}

function renderSentiment(value, analysis = {}) {
    const gaugeEl = document.getElementById('sentimentGauge');
    const purposeEl = document.getElementById('sentimentPurpose');
    const readoutEl = document.getElementById('sentimentReadout');
    const factorsEl = document.getElementById('sentimentFactors');
    const hintEl = document.getElementById('sentimentHint');
    if (!gaugeEl) return;

    if (window.__sentimentChart) {
        try { window.__sentimentChart.dispose(); } catch (e) { /* ignore */ }
        window.__sentimentChart = null;
    }
    const chart = echarts.init(gaugeEl);
    window.__sentimentChart = chart;

    const v = typeof value === 'number' && !isNaN(value) ? Math.max(0, Math.min(1, value)) : 0.5;
    const label = analysis.label || (v > 0.6 ? '偏贪婪' : v > 0.4 ? '中性' : '偏恐惧');
    const detailColor = v > 0.6 ? '#ef4444' : v > 0.4 ? '#f59e0b' : '#10b981';

    chart.setOption({
        backgroundColor: 'transparent',
        series: [{
            type: 'gauge',
            startAngle: 200,
            endAngle: -20,
            min: 0,
            max: 1,
            splitNumber: 4,
            radius: '88%',
            progress: {
                show: true,
                width: 16,
                itemStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
                        colorStops: [
                            { offset: 0, color: '#10b981' },
                            { offset: 0.5, color: '#f59e0b' },
                            { offset: 1, color: '#ef4444' }
                        ]
                    }
                }
            },
            axisLine: { lineStyle: { width: 16, color: [[1, '#1e293b']] } },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: {
                show: true,
                distance: -42,
                fontSize: 11,
                color: '#64748b',
                formatter(val) {
                    if (val <= 0.01) return '恐惧';
                    if (Math.abs(val - 0.5) < 0.01) return '中性';
                    if (val >= 0.99) return '贪婪';
                    return '';
                }
            },
            pointer: { show: false },
            anchor: { show: true, size: 11, itemStyle: { color: detailColor, borderWidth: 2, borderColor: '#0f172a' } },
            title: { show: true, offsetCenter: [0, '78%'], color: '#94a3b8', fontSize: 12 },
            detail: { show: false },
            data: [{ value: v, name: '情绪温度' }]
        }]
    });

    const volDate = analysis.volume_data_date && String(analysis.volume_data_date).trim();
    const volDateEl = document.getElementById('sentimentVolumeDataDate');
    if (volDateEl) {
        if (volDate) {
            volDateEl.style.display = '';
            volDateEl.textContent = `上证量能等因子对应交易日：${volDate}（周末/休市日展示为最近一个交易日）`;
        } else {
            volDateEl.textContent = '';
            volDateEl.style.display = 'none';
        }
    }

    if (purposeEl) {
        if (analysis.usage_note) {
            purposeEl.textContent = analysis.usage_note;
        } else {
            purposeEl.textContent = volDate
                ? `把板块强弱、快讯多空、标题措辞与上证量能活跃度合成 0–100 分，用于观察 ${volDate} 口径下的风险偏好温度（不构成投资建议）。`
                : '把板块强弱、快讯多空、标题措辞与上证量能活跃度合成 0–100 分，用于观察风险偏好温度（不构成投资建议）。';
        }
    }

    if (readoutEl) {
        const pct = analysis.value_pct != null ? Number(analysis.value_pct) : v * 100;
        const z = typeof analysis.zscore === 'number'
            ? `<div class="sentiment-readout-z">标题措辞波动：约 ${analysis.zscore.toFixed(2)} 倍标准差（越大越极端）</div>`
            : '';
        readoutEl.innerHTML = `
            <div class="sentiment-readout-score">${pct.toFixed(0)}<span class="sentiment-readout-sl">/100</span></div>
            <div class="sentiment-readout-label" style="color:${detailColor}">${_escapeHtml(label)}</div>
            ${z}`;
    }

    if (factorsEl) {
        const factors = Array.isArray(analysis.factors) ? analysis.factors : [];
        if (!factors.length) {
            factorsEl.innerHTML = '<div class="sentiment-factors-empty">因子明细暂不可用</div>';
        } else {
            factorsEl.innerHTML = factors.map((f) => {
                const c = Math.max(-1, Math.min(1, Number(f.contribution) || 0));
                const fill = ((c + 1) / 2) * 100;
                const tip = c > 0.12 ? '偏多' : c < -0.12 ? '偏空' : '中性';
                const col = c > 0.12 ? '#f87171' : c < -0.12 ? '#34d399' : '#94a3b8';
                return `<div class="sentiment-factor">
                    <div class="sentiment-factor-head">
                        <span class="sentiment-factor-name">${_escapeHtml(f.name || '')}</span>
                        <span class="sentiment-factor-w">${f.weight_pct != null ? f.weight_pct : ''}%</span>
                    </div>
                    <div class="sentiment-factor-bar-wrap" title="${_escapeHtml(f.desc || '')}">
                        <div class="sentiment-factor-bar-mid"></div>
                        <div class="sentiment-factor-bar-fill" style="width:${fill}%;background:${col};"></div>
                    </div>
                    <div class="sentiment-factor-foot">
                        <span class="sentiment-factor-tip" style="color:${col}">${tip}</span>
                        <span class="sentiment-factor-desc">${_escapeHtml(f.desc || '')}</span>
                    </div>
                </div>`;
            }).join('');
        }
    }

    if (hintEl) {
        const prompt = _escapeHtml(analysis.prompt || '情绪波动处于常态区间，建议按计划执行。');
        const nlpSummary = analysis.nlp_summary ? _escapeHtml(analysis.nlp_summary) : '';
        const comp = analysis.composite_raw != null
            ? `<div class="sentiment-hint-row"><span class="sentiment-hint-k">合成净向</span><span class="sentiment-hint-v">${Number(analysis.composite_raw).toFixed(2)}</span><span class="sentiment-hint-s">（-1 谨慎 ～ +1 积极）</span></div>`
            : '';
        hintEl.innerHTML = `
            <div class="sentiment-hint-title">快讯与量能摘要</div>
            <div class="sentiment-hint-row sentiment-hint-prompt">${prompt}</div>
            ${comp}
            ${nlpSummary ? `<div class="sentiment-hint-row sentiment-hint-nlp">${nlpSummary}</div>` : ''}`;
    }

    if (!window.__sentimentResizeBound) {
        window.__sentimentResizeBound = true;
        window.addEventListener('resize', () => {
            if (window.__sentimentChart) window.__sentimentChart.resize();
        });
    } else if (window.__sentimentChart) {
        window.__sentimentChart.resize();
    }
}

function _escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function _newsEngineBanner(engine, kimiError) {
    const e = engine || 'kimi_disabled';
    let cls = 'news-engine-banner is-rules';
    let text = '快讯情绪仅使用 Kimi：当前未启用或无法判定';
    if (e === 'kimi') {
        cls = 'news-engine-banner is-kimi';
        text = '利好/利空/中性 由「Kimi 大模型」判定';
    } else if (e === 'kimi_failed') {
        cls = 'news-engine-banner is-unavailable';
        text = 'Kimi 调用失败，快讯已全部标为「中性」（无规则兜底）';
    } else if (e === 'kimi_disabled') {
        cls = 'news-engine-banner is-rules';
        text = 'Kimi 未启用：请在项目根目录配置 .env 中的 KIMI_API_KEY，并重启服务（勿在 shell 中 export 空密钥，否则会挡住 .env）';
    } else if (e === 'loading') {
        cls = 'news-engine-banner is-loading';
        text = '正在获取快讯并调用 Kimi 判定情绪…';
    } else if (e === 'unavailable') {
        cls = 'news-engine-banner is-unavailable';
        text = '市场接口异常，快讯情绪未更新';
    }
    const err = (kimiError && String(kimiError).trim()) ? String(kimiError).trim() : '';
    const sub = err && (e === 'kimi_failed' || e === 'kimi_disabled')
        ? `<div class="news-engine-banner-detail">详情：${_escapeHtml(err)}</div>`
        : '';
    return `<div class="${cls}" role="status" aria-live="polite">${text}${sub}</div>`;
}

function renderNews(news, sentimentEngine, kimiError) {
    const feed = document.getElementById('newsFeed');
    if (!feed) return;
    const engine = sentimentEngine || 'kimi_disabled';
    const banner = _newsEngineBanner(engine, kimiError || '');
    const arr = Array.isArray(news) ? news : [];
    let listHtml = '';
    if (engine === 'loading') {
        listHtml = '<div class="news-placeholder">请稍候…</div>';
    } else if (!arr.length) {
        listHtml = '<div class="news-placeholder">暂无快讯数据</div>';
    } else {
        listHtml = arr.map(n =>
            `<div class="news-item">
            ${n.link ? `<a class="news-title news-link" href="${n.link}" target="_blank" rel="noopener noreferrer">${n.title}</a>` : `<div class="news-title">${n.title}</div>`}
            <div class="news-meta">
                <span>${n.source}</span>
                <span>${n.time}</span>
                <span class="news-sentiment ${n.sentiment}">${n.sentiment === 'positive' ? '利好' : n.sentiment === 'negative' ? '利空' : '中性'}</span>
                <span>${n.impact}</span>
            </div>
        </div>`
        ).join('');
    }
    feed.innerHTML = banner + listHtml;
}

// ==================== Risk Assessment ====================
async function startRiskAssessment() {
    try {
        const res = await fetch('/api/risk-questions');
        const data = await res.json();
        riskQuestions = data.questions;
        currentQuestion = 0;
        userAnswers = new Array(riskQuestions.length).fill(0);

        document.getElementById('riskIntro').classList.add('hidden');
        document.getElementById('riskQuiz').classList.remove('hidden');
        document.getElementById('riskResult').classList.add('hidden');
        renderQuestion();
    } catch (e) {
        console.error('Failed to load questions:', e);
    }
}

function renderQuestion() {
    const q = riskQuestions[currentQuestion];
    document.getElementById('quizProgressFill').style.width = ((currentQuestion + 1) / riskQuestions.length * 100) + '%';
    document.getElementById('quizProgressText').textContent = `${currentQuestion + 1}/${riskQuestions.length}`;

    document.getElementById('quizContent').innerHTML = `
        <div class="quiz-question">${q.id}. ${q.question}</div>
        <div class="quiz-options">
            ${q.options.map((opt, i) =>
                `<div class="quiz-option ${userAnswers[currentQuestion] === opt.score ? 'selected' : ''}"
                     onclick="selectOption(${opt.score})">${opt.label}</div>`
            ).join('')}
        </div>`;

    document.getElementById('btnPrev').disabled = currentQuestion === 0;
    const isLast = currentQuestion === riskQuestions.length - 1;
    document.getElementById('btnNext').textContent = isLast ? '提交测评' : '下一题';
}

function selectOption(score) {
    userAnswers[currentQuestion] = score;
    document.querySelectorAll('.quiz-option').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');
}

function nextQuestion() {
    if (userAnswers[currentQuestion] === 0) {
        alert('请选择一个选项');
        return;
    }
    if (currentQuestion < riskQuestions.length - 1) {
        currentQuestion++;
        renderQuestion();
    } else {
        submitAssessment();
    }
}

function prevQuestion() {
    if (currentQuestion > 0) {
        currentQuestion--;
        renderQuestion();
    }
}

async function submitAssessment() {
    try {
        const res = await fetch('/api/risk-assess', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers: userAnswers })
        });
        const data = await res.json();
        riskProfile = data.profile;
        riskResultData = data;
        allocationData = data.allocation;
        saveRiskResult(data);

        document.getElementById('riskQuiz').classList.add('hidden');
        document.getElementById('riskResult').classList.remove('hidden');
        renderResult(data);
    } catch (e) {
        console.error('Failed to submit assessment:', e);
    }
}

function renderResult(data) {
    const safeData = {
        ...data,
        score: typeof data?.score === 'number' ? data.score : 30,
        max_score: typeof data?.max_score === 'number' ? data.max_score : 50,
        profile: data?.profile || '平衡型',
        allocation: data?.allocation || { description: '', allocation: [] },
        radar: data?.radar || getDefaultRadar()
    };
    renderScoreRing(safeData.score, safeData.max_score, safeData.profile);

    const profileColors = { '保守型': '#3b82f6', '稳健型': '#10b981', '平衡型': '#f59e0b', '进取型': '#f97316', '激进型': '#ef4444' };
    const color = profileColors[safeData.profile] || '#3b82f6';
    document.getElementById('resultProfile').textContent = `您的风险画像：${safeData.profile}`;
    document.getElementById('resultProfile').style.color = color;
    document.getElementById('resultDesc').textContent = safeData.allocation.description || '已为您生成个性化配置建议。';

    renderRadarChart(safeData.radar);
    renderAllocationPreview(safeData.allocation);
}

function renderScoreRing(score, max, profile) {
    const dom = document.getElementById('resultScoreRing');
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom);
    const profileColors = { '保守型': '#3b82f6', '稳健型': '#10b981', '平衡型': '#f59e0b', '进取型': '#f97316', '激进型': '#ef4444' };
    const color = profileColors[profile] || '#3b82f6';

    chart.setOption({
        backgroundColor: 'transparent',
        series: [{
            type: 'gauge', startAngle: 90, endAngle: -270,
            radius: '90%', pointer: { show: false },
            progress: { show: true, overlap: false, roundCap: true, clip: false, width: 10, itemStyle: { color: color }},
            axisLine: { lineStyle: { width: 10, color: [[1, '#1e293b']] }},
            axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
            title: { show: true, offsetCenter: [0, '30%'], color: '#94a3b8', fontSize: 12 },
            detail: { valueAnimation: true, offsetCenter: [0, '-5%'], fontSize: 28, fontWeight: 700, color: color, formatter: '{value}' },
            data: [{ value: score, name: `满分${max}`, detail: { formatter: '{value}分' }}],
            min: 0, max: max
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderRadarChart(radar) {
    const safeRadar = radar || getDefaultRadar();
    const dom = document.getElementById('radarChart');
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom);
    chart.setOption({
        backgroundColor: 'transparent',
        radar: {
            indicator: [
                { name: '风险承受', max: 5 }, { name: '投资经验', max: 5 },
                { name: '金融知识', max: 5 }, { name: '收入稳定', max: 5 },
                { name: '投资期限', max: 5 }
            ],
            shape: 'polygon',
            splitNumber: 5,
            axisName: { color: '#94a3b8', fontSize: 12 },
            splitLine: { lineStyle: { color: '#1e293b' }},
            splitArea: { areaStyle: { color: ['transparent'] }},
            axisLine: { lineStyle: { color: '#1e293b' }}
        },
        series: [{
            type: 'radar',
            data: [{
                value: [
                    safeRadar.risk_tolerance ?? 3,
                    safeRadar.investment_exp ?? 3,
                    safeRadar.financial_knowledge ?? 3,
                    safeRadar.income_stability ?? 3,
                    safeRadar.investment_horizon ?? 3
                ],
                areaStyle: { color: 'rgba(59,130,246,0.2)' },
                lineStyle: { color: '#3b82f6', width: 2 },
                itemStyle: { color: '#3b82f6' }
            }]
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderAllocationPreview(alloc) {
    const allocItems = Array.isArray(alloc?.allocation) ? alloc.allocation : [];
    const dom = document.getElementById('allocationPreview');
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom);
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {d}%', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0' }},
        series: [{
            type: 'pie', radius: ['45%', '70%'], center: ['50%', '50%'],
            avoidLabelOverlap: true,
            label: { show: true, color: '#94a3b8', fontSize: 12, formatter: '{b}\n{d}%' },
            labelLine: { lineStyle: { color: '#334155' }},
            itemStyle: { borderColor: '#1a2332', borderWidth: 2 },
            data: allocItems.map(a => ({ name: a.name, value: a.value, itemStyle: { color: a.color }}))
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function retakeAssessment() {
    document.getElementById('riskResult').classList.add('hidden');
    document.getElementById('riskIntro').classList.remove('hidden');
    riskProfile = null;
    riskResultData = null;
    allocationData = null;
    clearRiskResult();
}

// ==================== Allocation ====================
function showAllocationDetail(data) {
    document.getElementById('allocationEmpty').classList.add('hidden');
    document.getElementById('allocationDetail').classList.remove('hidden');

    const profileColors = { '保守型': '#3b82f6', '稳健型': '#10b981', '平衡型': '#f59e0b', '进取型': '#f97316', '激进型': '#ef4444' };
    const color = profileColors[data.label] || '#3b82f6';

    const badge = document.getElementById('allocProfileBadge');
    badge.textContent = data.label;
    badge.style.background = color + '20';
    badge.style.color = color;

    document.getElementById('allocReturn').textContent = data.expected_return;
    document.getElementById('allocDrawdown').textContent = data.max_drawdown;
    document.getElementById('allocVolatility').textContent = data.volatility;
    document.getElementById('allocSharpe').textContent = data.sharpe.toFixed(1);

    renderAllocPie(data.allocation);
    renderAllocDetails(data.allocation);
    renderBacktest(data.allocation);

    // 清空旧的 Kimi 建议，展示 loading 状态，然后异步加载
    renderAllocationAdvice(null, 'loading', '', [], data.allocation);
    loadAllocationAdvice(data.label);
}

function renderAllocPie(allocation) {
    const chart = echarts.init(document.getElementById('allocPieChart'));
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {c}%', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0' }},
        legend: { orient: 'vertical', right: 20, top: 'center', textStyle: { color: '#94a3b8', fontSize: 12 }},
        series: [{
            type: 'pie', radius: ['40%', '65%'], center: ['40%', '50%'],
            label: { show: true, formatter: '{d}%', color: '#e2e8f0', fontSize: 13, fontWeight: 600 },
            labelLine: { lineStyle: { color: '#334155' }},
            itemStyle: { borderColor: '#1a2332', borderWidth: 3, borderRadius: 6 },
            emphasis: { scaleSize: 8 },
            data: allocation.map(a => ({ name: a.name, value: a.value, itemStyle: { color: a.color }}))
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderAllocDetails(allocation, baseAlloc) {
    document.getElementById('allocDetails').innerHTML = allocation.map(a => {
        let deltaHtml = '';
        if (baseAlloc && baseAlloc.length) {
            const baseItem = baseAlloc.find(b => b.name === a.name);
            if (baseItem) {
                const diff = Math.round((a.value - baseItem.value) * 10) / 10;
                if (diff > 0) {
                    deltaHtml = `<span class="alloc-delta alloc-delta-up">↑${diff}%</span>`;
                } else if (diff < 0) {
                    deltaHtml = `<span class="alloc-delta alloc-delta-down">↓${Math.abs(diff)}%</span>`;
                }
            }
        }
        return `<div class="alloc-item">
            <div class="alloc-color" style="background:${a.color}"></div>
            <span class="alloc-name">${a.name}</span>
            <span class="alloc-pct">${a.value}%${deltaHtml}</span>
            <div class="alloc-bar-bg"><div class="alloc-bar-fill" style="width:${a.value}%;background:${a.color}"></div></div>
        </div>`;
    }).join('');
}

async function getHs300ReturnSeries(days = 365) {
    if (hs300ReturnCache && Array.isArray(hs300ReturnCache.returns) && hs300ReturnCache.returns.length >= Math.min(days, 60)) {
        return hs300ReturnCache;
    }
    const res = await fetch(`/api/hs300-return?days=${days}`);
    const data = await res.json();
    const cache = {
        dates: (data.dates || []).map(d => String(d)),
        returns: (data.returns || []).map(v => Number(v) || 0)
    };
    hs300ReturnCache = cache;
    return cache;
}

// ==================== 智能配置 Kimi 建议 + 情绪调仓 ====================

async function loadAllocationAdvice(profile) {
    const marketData = window.__marketData || {};
    try {
        const res = await fetch('/api/allocation-advice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile, ...marketData }),
        });
        const data = await res.json();
        renderAllocationAdvice(data, data.advice_engine, data.advice_kimi_error, data.adjusted_alloc || [], data.base_alloc || []);
    } catch (e) {
        renderAllocationAdvice(null, 'unavailable', String(e), [], []);
    }
}

function _allocAdviceBanner(engine, kimiError) {
    const e = engine || 'kimi_disabled';
    let cls = 'news-engine-banner is-rules';
    let text = '配置建议仅使用 Kimi：当前未启用或不可用';
    if (e === 'kimi') {
        cls = 'news-engine-banner is-kimi';
        text = '配置建议由「Kimi 大模型」根据您的风险画像 + 当日市场情绪 + 行情快照自动生成';
    } else if (e === 'kimi_failed') {
        cls = 'news-engine-banner is-unavailable';
        text = 'Kimi 生成配置建议失败，以下为兜底建议';
    } else if (e === 'kimi_disabled') {
        cls = 'news-engine-banner is-rules';
        text = '配置建议未调用 Kimi（未配置 KIMI_API_KEY 或已禁用），以下为规则生成建议';
    } else if (e === 'loading') {
        cls = 'news-engine-banner is-loading';
        text = '正在调用 Kimi 生成个性化配置建议…';
    } else if (e === 'unavailable') {
        cls = 'news-engine-banner is-unavailable';
        text = '配置建议接口异常，请稍后重试';
    }
    const err = (kimiError && String(kimiError).trim()) ? String(kimiError).trim() : '';
    const sub = err && (e === 'kimi_failed' || e === 'kimi_disabled')
        ? `<div class="news-engine-banner-detail">详情：${_escapeHtml(err)}</div>`
        : '';
    return `<div class="${cls}" role="status" aria-live="polite">${text}${sub}</div>`;
}

function renderAllocationAdvice(data, engine, kimiError, adjustedAlloc, baseAlloc) {
    const bannerEl = document.getElementById('allocAdviceBanner');
    const tiltEl = document.getElementById('allocTiltNote');
    const cardEl = document.getElementById('allocAdviceCard');
    const textEl = document.getElementById('allocAdviceText');
    const pointsEl = document.getElementById('allocAdvicePoints');

    if (bannerEl) bannerEl.innerHTML = _allocAdviceBanner(engine, kimiError || '');

    // 情绪调仓说明
    const tiltNote = data && data.tilt_note ? String(data.tilt_note).trim() : '';
    if (tiltEl) {
        if (tiltNote) {
            tiltEl.innerHTML = `<span class="alloc-tilt-icon">⚖</span> 调仓说明：${_escapeHtml(tiltNote)}`;
            tiltEl.classList.remove('hidden');
        } else {
            tiltEl.classList.add('hidden');
        }
    }

    // 调整后比例覆盖饼图和明细，并重渲染回测图对比
    if (adjustedAlloc && adjustedAlloc.length && baseAlloc && baseAlloc.length) {
        const hasDiff = adjustedAlloc.some((a, i) => a.value !== (baseAlloc[i] || {}).value);
        if (hasDiff) {
            renderAllocPie(adjustedAlloc);
            renderAllocDetails(adjustedAlloc, baseAlloc);
            // 重渲染回测图：基准 vs 调仓后
            renderBacktest(baseAlloc, adjustedAlloc);
        }
    }

    // loading 状态下不显示文案卡片
    if (engine === 'loading') {
        if (cardEl) cardEl.classList.add('hidden');
        return;
    }

    const advice = data && data.advice ? String(data.advice).trim() : '';
    const keyPoints = data && Array.isArray(data.key_points) ? data.key_points : [];

    if ((advice || keyPoints.length) && cardEl) {
        if (textEl) textEl.textContent = advice;
        if (pointsEl) {
            pointsEl.innerHTML = keyPoints.map(p => `<li>${_escapeHtml(String(p))}</li>`).join('');
        }
        cardEl.classList.remove('hidden');
    } else if (cardEl) {
        cardEl.classList.add('hidden');
    }
}

// ==================== 历史回测：配置比例加权模拟 ====================

// 各类资产典型日均收益率（mu）和日波动率（sigma），基于历史统计
const ASSET_PARAMS = {
    '股票基金': { mu: 0.10 / 252, sigma: 0.015 },   // 年化10%，日波动1.5%
    '混合基金': { mu: 0.07 / 252, sigma: 0.010 },   // 年化7%，日波动1.0%
    '债券基金': { mu: 0.04 / 252, sigma: 0.003 },   // 年化4%，日波动0.3%
    '货币基金': { mu: 0.025 / 252, sigma: 0.0002 }, // 年化2.5%，近零波动
    '另类投资': { mu: 0.08 / 252, sigma: 0.012 },   // 年化8%，日波动1.2%
};

// 与沪深300的相关系数：权益类资产受市场走势影响较大
const ASSET_MARKET_CORR = {
    '股票基金': 0.75,
    '混合基金': 0.50,
    '债券基金': -0.10,
    '货币基金': 0.00,
    '另类投资': 0.30,
};

// Box-Muller 正态随机数（均值0，标准差1）
function _boxMullerRand(rng) {
    let u, v;
    do { u = rng(); } while (u === 0);
    do { v = rng(); } while (v === 0);
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

// 轻量级确定性伪随机（mulberry32），使同一画像每次结果相同
function _makeRng(seed) {
    let s = seed >>> 0;
    return function () {
        s = (s + 0x6d2b79f5) >>> 0;
        let t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) >>> 0;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

// 将画像名映射为整数种子，保证同一画像每次回测曲线一致
function _profileSeed(allocation) {
    const key = (allocation || []).map(a => `${a.name}${a.value}`).join('|');
    let h = 0;
    for (let i = 0; i < key.length; i++) {
        h = (Math.imul(31, h) + key.charCodeAt(i)) >>> 0;
    }
    return h;
}

/**
 * 根据配置比例数组和沪深300每日涨跌幅序列，模拟组合每日累计收益率。
 * @param {Array} allocation  - [{name, value}, ...]，value 为百分比
 * @param {Array} mktChanges  - 沪深300每日涨跌幅序列（百分比，如 1.2 表示涨1.2%）
 * @returns {Array}           - 累计收益率数组（百分比，起点为0）
 */
function calcPortfolioReturns(allocation, mktChanges) {
    const n = mktChanges.length;
    if (!n || !allocation || !allocation.length) return [];

    const rng = _makeRng(_profileSeed(allocation));
    const weights = allocation.map(a => ({
        name: a.name,
        w: (a.value || 0) / 100,
        params: ASSET_PARAMS[a.name] || { mu: 0.05 / 252, sigma: 0.008 },
        corr: ASSET_MARKET_CORR[a.name] !== undefined ? ASSET_MARKET_CORR[a.name] : 0.2,
    }));

    let cumReturn = 0; // 累计对数收益
    const result = [];

    for (let i = 0; i < n; i++) {
        // 沪深300当日收益（转换为小数）
        const mktR = (mktChanges[i] || 0) / 100;
        // 市场特有噪声（用于相关性分解）
        const zMkt = _boxMullerRand(rng);
        // 组合当日加权收益
        let dayR = 0;
        for (const asset of weights) {
            const { mu, sigma } = asset.params;
            const corr = asset.corr;
            // 相关部分 = 市场日收益 × 相关系数，独立部分 = 正态噪声 × sqrt(1 - corr²)
            const zIdio = _boxMullerRand(rng);
            const assetR = mu + sigma * (corr * zMkt + Math.sqrt(1 - corr * corr) * zIdio)
                         + corr * mktR * 0.4; // 加入市场走势联动
            dayR += asset.w * assetR;
        }
        cumReturn += dayR;
        result.push(+(cumReturn * 100).toFixed(2));
    }
    return result;
}

// 回测图实例缓存，防止重复 init 导致内存泄漏
let _backtestChart = null;

/**
 * 渲染历史回测图。
 * @param {Array}  baseAlloc     - 基准配置比例（必选）
 * @param {Array}  [adjustedAlloc] - 情绪调仓后比例（可选，有时显示第三条曲线）
 */
async function renderBacktest(baseAlloc, adjustedAlloc) {
    const el = document.getElementById('backtestChart');
    if (!el) return;

    if (!_backtestChart) {
        _backtestChart = echarts.init(el);
        window.addEventListener('resize', () => _backtestChart && _backtestChart.resize());
    }
    const chart = _backtestChart;

    // 显示加载状态
    chart.showLoading({ text: '加载沪深300历史数据…', textColor: '#94a3b8', maskColor: 'rgba(15,23,42,0.6)' });

    let dates = [];
    let benchmarkReturns = [];

    try {
        const data = await getHs300ReturnSeries(365);
        dates = (data.dates || []).map(d => d.slice(5));
        benchmarkReturns = (data.returns || []).map(v => Number(v) || 0);
    } catch (e) {
        dates = [];
        benchmarkReturns = [];
    }

    // 沪深300无法获取时，用模拟走势兜底
    if (!dates.length || !benchmarkReturns.length) {
        const days = 365;
        const rng = _makeRng(20240101);
        let b = 0;
        for (let i = 0; i < days; i++) {
            const d = new Date();
            d.setDate(d.getDate() - (days - i));
            dates.push(d.toISOString().slice(5, 10));
            b += _boxMullerRand(rng) * 0.6;
            benchmarkReturns.push(+b.toFixed(2));
        }
    }

    // 沪深300每日涨跌幅（用于相关性联动）
    const mktChanges = benchmarkReturns.map((v, i) =>
        i === 0 ? v : v - benchmarkReturns[i - 1]
    );

    // 计算基准组合收益曲线
    const effectiveBase = (baseAlloc && baseAlloc.length) ? baseAlloc : [];
    const portfolioReturns = calcPortfolioReturns(effectiveBase, mktChanges);

    // 判断是否有实质性调仓
    const hasTilt = adjustedAlloc && adjustedAlloc.length &&
        adjustedAlloc.some((a, i) => a.value !== (effectiveBase[i] || {}).value);
    const adjustedReturns = hasTilt ? calcPortfolioReturns(adjustedAlloc, mktChanges) : null;

    chart.hideLoading();

    const legendData = ['AI配置组合', '沪深300'];
    if (hasTilt) legendData.push('情绪调仓后');

    const series = [
        {
            name: 'AI配置组合', type: 'line', data: portfolioReturns, smooth: true, symbol: 'none',
            lineStyle: { color: '#3b82f6', width: 2 },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(59,130,246,0.18)' }, { offset: 1, color: 'rgba(59,130,246,0)' }
            ])}
        },
        {
            name: '沪深300', type: 'line', data: benchmarkReturns, smooth: true, symbol: 'none',
            lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' }
        },
    ];

    if (hasTilt) {
        series.push({
            name: '情绪调仓后', type: 'line', data: adjustedReturns, smooth: true, symbol: 'none',
            lineStyle: { color: '#10b981', width: 2, type: 'solid' },
        });
    }

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#1a2332',
            borderColor: '#334155',
            textStyle: { color: '#e2e8f0', fontSize: 12 },
            formatter: params => {
                const date = params[0] ? params[0].axisValue : '';
                const lines = params.map(p =>
                    `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:5px"></span>${p.seriesName}：${Number(p.value).toFixed(2)}%`
                );
                return `<div style="font-size:12px;color:#94a3b8;margin-bottom:4px">${date}</div>` + lines.join('<br>');
            }
        },
        legend: { data: legendData, textStyle: { color: '#94a3b8', fontSize: 12 }, top: 0 },
        grid: { left: 52, right: 20, top: 40, bottom: 30 },
        xAxis: {
            type: 'category', data: dates,
            axisLabel: { color: '#64748b', fontSize: 11 },
            axisLine: { lineStyle: { color: '#1e293b' }},
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#64748b', fontSize: 11, formatter: v => `${v.toFixed(0)}%` },
            splitLine: { lineStyle: { color: '#1e293b' }},
        },
        series,
    }, true);
}

// ==================== Stock Screening ====================

let _factorChangedTimer = null;

function updateFactorDisplay() {
    ['Value', 'Growth', 'Quality', 'Momentum', 'Sentiment'].forEach(f => {
        const val = document.getElementById('factor' + f).value;
        document.getElementById('factor' + f + 'Display').textContent = val + '%';
    });
    // 防抖 toast：权重变更后 0.5s 显示提示
    clearTimeout(_factorChangedTimer);
    _factorChangedTimer = setTimeout(() => {
        _showScreeningToast('权重已调整，点击「运行AI选股模型」更新结果');
    }, 500);
}

function _showScreeningToast(msg) {
    let toast = document.getElementById('screeningToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'screeningToast';
        toast.className = 'screening-toast';
        // 插入到权重区域按钮前
        const btn = document.querySelector('#page-screening .btn-primary');
        if (btn && btn.parentNode) btn.parentNode.insertBefore(toast, btn);
        else document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add('visible');
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => toast.classList.remove('visible'), 2500);
}

async function runScreening() {
    const btn = document.querySelector('#page-screening .btn-primary');
    const origText = btn ? btn.textContent : '';
    if (btn) { btn.disabled = true; btn.textContent = '选股中…'; }

    // 隐藏 toast
    const toast = document.getElementById('screeningToast');
    if (toast) toast.classList.remove('visible');

    const weights = {
        value: +document.getElementById('factorValue').value,
        growth: +document.getElementById('factorGrowth').value,
        quality: +document.getElementById('factorQuality').value,
        momentum: +document.getElementById('factorMomentum').value,
        sentiment: +document.getElementById('factorSentiment').value,
    };

    try {
        const res = await fetch('/api/stock-screen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(weights)
        });
        const data = await res.json();
        renderStockTable(data.stocks, data.reason_engine, data.reason_kimi_error);
        renderFactorRadar(data.stocks.slice(0, 5));
    } catch (e) {
        console.error('Failed to screen stocks:', e);
        renderStockTable([], 'unavailable', String(e));
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
}

function _screenReasonBanner(engine, kimiError) {
    const e = engine || 'rules';
    let cls = 'news-engine-banner is-rules';
    let text = 'AI选股理由由规则引擎生成（因子阈值判断）';
    if (e === 'kimi') {
        cls = 'news-engine-banner is-kimi';
        text = 'Top 5 AI选股理由由「Kimi 大模型」根据因子评分 + 行情快照自动生成，第6名起为规则理由';
    } else if (e === 'kimi_failed') {
        cls = 'news-engine-banner is-unavailable';
        text = 'Kimi 生成选股理由失败，以下均为规则理由';
    } else if (e === 'kimi_disabled') {
        cls = 'news-engine-banner is-rules';
        text = '选股理由未调用 Kimi（未配置 KIMI_API_KEY 或已禁用）';
    } else if (e === 'unavailable') {
        cls = 'news-engine-banner is-unavailable';
        text = '选股接口异常，请稍后重试';
    }
    const err = (kimiError && String(kimiError).trim()) ? String(kimiError).trim() : '';
    const sub = err && (e === 'kimi_failed' || e === 'kimi_disabled')
        ? `<div class="news-engine-banner-detail">详情：${_escapeHtml(err)}</div>`
        : '';
    return `<div class="${cls}" role="status" aria-live="polite">${text}${sub}</div>`;
}

function renderStockTable(stocks, reasonEngine, reasonKimiError) {
    const bannerEl = document.getElementById('screenReasonBanner');
    if (bannerEl) bannerEl.innerHTML = _screenReasonBanner(reasonEngine, reasonKimiError || '');

    document.getElementById('stockCount').textContent = (stocks || []).length + '只';
    const tbody = document.getElementById('stockTableBody');
    if (!stocks || !stocks.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:24px">暂无数据</td></tr>';
        return;
    }
    tbody.innerHTML = stocks.map((s, i) => {
        const score = s.scores.total;
        const scoreCls = score >= 65 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';
        // PE：若无内置样本对应，值来自行业中位数估算，加 (估) 标注
        const peIsEstimated = !s.pe_source_exact && i >= 0; // 后端可按需设置 pe_source_exact
        const peText = (s.pe === null || s.pe === undefined) ? '--'
            : (s.pe_estimated ? `<span class="pe-estimated">${s.pe}<span class="pe-est-tag">(估)</span></span>` : s.pe);
        const roeText = (s.roe === null || s.roe === undefined) ? '--' : `${s.roe}%`;
        const isKimiReason = s.ai_reason_engine === 'kimi';
        const reasonHtml = isKimiReason
            ? `<span class="ai-reason-text ai-reason-kimi">${_escapeHtml(s.ai_reason)}</span>`
            : `<span class="ai-reason-text">${_escapeHtml(s.ai_reason)}</span>`;
        const changeCls = s.change_pct >= 0 ? 'up' : 'down';
        const changeSign = s.change_pct >= 0 ? '+' : '';
        return `<tr>
            <td><strong>${i + 1}</strong></td>
            <td style="color:var(--text-muted);font-family:monospace">${s.code}</td>
            <td><strong>${s.name}</strong></td>
            <td>${s.industry}</td>
            <td>¥${s.price.toFixed(2)} <span class="${changeCls}" style="font-size:11px">${changeSign}${s.change_pct.toFixed(2)}%</span></td>
            <td>${peText}</td>
            <td>${roeText}</td>
            <td><span class="score-badge ${scoreCls}">${score.toFixed(1)}</span></td>
            <td>${reasonHtml}</td>
        </tr>`;
    }).join('');
}

function renderFactorRadar(top5) {
    const chart = echarts.init(document.getElementById('factorRadar'));
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0' }},
        legend: { data: top5.map(s => s.name), textStyle: { color: '#94a3b8', fontSize: 12 }, bottom: 0 },
        radar: {
            indicator: [
                { name: '价值', max: 100 }, { name: '成长', max: 100 },
                { name: '质量', max: 100 }, { name: '动量', max: 100 },
                { name: '情绪', max: 100 }
            ],
            shape: 'polygon',
            splitNumber: 5,
            axisName: { color: '#94a3b8', fontSize: 12 },
            splitLine: { lineStyle: { color: '#1e293b' }},
            splitArea: { areaStyle: { color: ['transparent'] }},
            axisLine: { lineStyle: { color: '#1e293b' }}
        },
        series: [{
            type: 'radar',
            data: top5.map((s, i) => ({
                name: s.name,
                value: [s.scores.value, s.scores.growth, s.scores.quality, s.scores.momentum, s.scores.sentiment],
                lineStyle: { color: colors[i], width: 2 },
                areaStyle: { color: colors[i] + '20' },
                itemStyle: { color: colors[i] }
            }))
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

// ==================== Portfolio ====================
let currentPortfolioTimeframe = 180;

async function loadPortfolio() {
    try {
        const [holdingsRes, historyRes] = await Promise.all([
            fetch('/api/holdings'),
            fetch(`/api/portfolio-history?days=${currentPortfolioTimeframe}`),
        ]);
        holdingsData = (await holdingsRes.json()) || [];
        const historyData = await historyRes.json();
        portfolioRawData = { history: historyData };
        refreshPortfolioByHoldings();
        renderHoldingTabs();
        renderHoldings();
        // 异步加载各持仓指标（不阻塞主渲染）
        loadHoldingIndicators();
    } catch (e) {
        console.error('Failed to load portfolio:', e);
    }
}

async function loadHoldingIndicators() {
    if (!holdingsData || !holdingsData.length) return;
    try {
        const codes = holdingsData.map(h => ({ code: h.code, name: h.name, asset_type: h.asset_type || '股票', current: h.current, cost: h.cost, shares: h.shares }));
        const res = await fetch(apiUrl('/api/holding-indicators'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ holdings: codes })
        });
        const data = await parseFetchJson(res);
        if (data && !data._parseFailed && data.indicators) {
            holdingIndicators = data.indicators;
            renderHoldings();
        }
    } catch (e) {
        console.warn('指标加载失败（非致命）:', e);
    }
}

async function refreshHoldingIndicators() {
    const btn = document.querySelector('.btn-sm-ai');
    if (btn) { btn.textContent = '加载中…'; btn.disabled = true; }
    holdingIndicators = {};
    renderHoldings();
    await loadHoldingIndicators();
    if (btn) { btn.textContent = '刷新指标'; btn.disabled = false; }
}

async function switchPortfolioTimeframe(days) {
    if (currentPortfolioTimeframe === days) return;
    currentPortfolioTimeframe = days;
    
    // 更新UI按钮高亮
    const btn180 = document.getElementById('btnPortfolio180');
    const btn365 = document.getElementById('btnPortfolio365');
    if (btn180) btn180.classList.toggle('active', days === 180);
    if (btn365) btn365.classList.toggle('active', days === 365);
    
    // 只重新请求history数据
    try {
        const res = await fetch(`/api/portfolio-history?days=${currentPortfolioTimeframe}`);
        const historyData = await res.json();
        if (portfolioRawData) {
            portfolioRawData.history = historyData;
            renderPortfolioChart(historyData, holdingsData);
        }
    } catch (e) {
        console.error('Failed to update portfolio history:', e);
    }
}

function renderPortfolioSummary(data) {
    const profitCls = data.total_profit >= 0 ? 'up' : 'down';
    const holdings = Array.isArray(data.holdings) ? data.holdings : [];
    const stockCount = holdings.filter(h => (h.asset_type || '股票') === '股票').length;
    const fundCount = holdings.filter(h => (h.asset_type || '股票') === '基金').length;
    document.getElementById('portfolioSummary').innerHTML = `
        <div class="summary-card">
            <div class="summary-label">总资产</div>
            <div class="summary-value">¥${(data.total_value / 10000).toFixed(2)}万</div>
            <div class="summary-sub">成本 ¥${(data.total_cost / 10000).toFixed(2)}万</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">总收益</div>
            <div class="summary-value ${profitCls}">¥${data.total_profit >= 0 ? '+' : ''}${data.total_profit.toFixed(2)}</div>
            <div class="summary-sub ${profitCls}">${data.total_return >= 0 ? '+' : ''}${data.total_return.toFixed(2)}%</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">持仓数量</div>
            <div class="summary-value">${holdings.length}</div>
            <div class="summary-sub">股票 ${stockCount} · 基金 ${fundCount}</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">夏普比率</div>
            <div class="summary-value" style="color:#10b981">${Number(data?.risk_metrics?.sharpe_ratio || 0).toFixed(2)}</div>
            <div class="summary-sub">优于82%的组合</div>
        </div>`;
}

function normalizeHolding(item) {
    const type = item.asset_type === '基金' ? '基金' : '股票';
    const shares = Number(item.shares) || 0;
    const cost = Number(item.cost) || 0;
    const current = Number(item.current) || 0;
    const createdAtRaw = item.created_at || item.createdAt || '';
    const createdAt = Number.isNaN(new Date(createdAtRaw).getTime()) ? new Date().toISOString() : new Date(createdAtRaw).toISOString();
    const unit = item.unit || (type === '基金' ? '份' : '股');
    
    // 如果是后端OCR解析出的带 amount 的，直接用它
    const amount = item.amount !== undefined ? Number(item.amount) : +(current * shares).toFixed(2);
    const profit = item.profit !== undefined ? Number(item.profit) : (current - cost) * shares;
    const returnPct = cost > 0 ? ((current - cost) / cost) * 100 : 0;
    
    const ret = {
        code: (item.code || '').toString().trim(),
        name: (item.name || '').toString().trim(),
        asset_type: type,
        shares: shares, // 基金份额可能有小数，不粗暴round
        unit,
        created_at: createdAt,
        cost: +cost.toFixed(4),
        current: +current.toFixed(4),
        amount: amount,
        market_value: amount,
        profit: +profit.toFixed(2),
        return_pct: +returnPct.toFixed(2)
    };
    if (item.input_amount !== undefined) ret.input_amount = item.input_amount;
    if (item.input_profit !== undefined) ret.input_profit = item.input_profit;
    if (item.needs_share_calc !== undefined) ret.needs_share_calc = item.needs_share_calc;
    return ret;
}

function saveMockHoldings() {
    // 持仓现已持久化到服务端，此函数保留为空（兼容老调用点）
}

function loadOrInitMockHoldings(defaultHoldings) {
    // 持仓从服务端加载，此函数仅作兼容保留
    return (defaultHoldings || []).map(normalizeHolding);
}

function inferIndustryByHolding(h) {
    if (!h) return '其他';
    if ((h.asset_type || '股票') === '基金') {
        const n = (h.name || '').toLowerCase();
        if (n.includes('医药')) return '医药基金';
        if (n.includes('新能源')) return '新能源基金';
        if (n.includes('白酒')) return '消费基金';
        if (n.includes('300') || n.includes('etf')) return '指数基金';
        return '基金';
    }
    const name = h.name || '';
    if (/(银行|证券|保险)/.test(name)) return '金融';
    if (/(医药|医疗|药)/.test(name)) return '医药';
    if (/(新能源|电池|光伏|锂|宁德|比亚迪)/.test(name)) return '新能源';
    if (/(白酒|食品|消费|家电|美的|茅台|五粮液|汾酒|泸州)/.test(name)) return '消费';
    if (/(科技|半导体|电子|通信|AI|人工智能|新易盛)/.test(name)) return '科技';
    if (/(有色|矿业|煤|钢|资源)/.test(name)) return '周期资源';
    return '其他行业';
}

function computeIndustryDistributionFromHoldings(holdings) {
    const list = Array.isArray(holdings) ? holdings : [];
    const total = list.reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    if (total <= 0) return [];
    const bucket = {};
    list.forEach(h => {
        const label = inferIndustryByHolding(h);
        const mv = Number(h.market_value) || 0;
        bucket[label] = (bucket[label] || 0) + mv;
    });
    return Object.entries(bucket)
        .map(([name, value]) => ({ name, value: +(value / total * 100).toFixed(2) }))
        .sort((a, b) => b.value - a.value);
}

function computeRiskMetricsFromHoldings(holdings) {
    const list = Array.isArray(holdings) ? holdings : [];
    const values = list.map(h => Number(h.market_value) || 0);
    const totalValue = values.reduce((a, b) => a + b, 0);
    const returns = list.map(h => Number(h.return_pct) || 0);
    const weightedReturn = totalValue > 0
        ? list.reduce((sum, h) => sum + (Number(h.market_value) || 0) * (Number(h.return_pct) || 0), 0) / totalValue
        : 0;
    const mean = returns.length ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
    const variance = returns.length
        ? returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length
        : 0;
    const volatility = Math.sqrt(Math.max(variance, 0));
    const sharpe = volatility > 0.01 ? weightedReturn / volatility : 0;
    const worst = returns.length ? Math.min(...returns) : 0;
    const maxDrawdown = Math.min(-Math.abs(worst) * 1.2, -0.5);
    const stockValue = list
        .filter(h => (h.asset_type || '股票') === '股票')
        .reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    const stockRatio = totalValue > 0 ? stockValue / totalValue : 0;
    const beta = 0.7 + stockRatio * 0.8;
    const alpha = weightedReturn - beta * 0.9;
    const var95 = -(Math.abs(mean) + 1.65 * volatility * 0.6);
    return {
        sharpe_ratio: +sharpe.toFixed(2),
        max_drawdown: +maxDrawdown.toFixed(2),
        volatility: +volatility.toFixed(2),
        beta: +beta.toFixed(2),
        alpha: +alpha.toFixed(2),
        var_95: +var95.toFixed(2)
    };
}

function computeRebalanceAlertsFromHoldings(holdings) {
    const list = Array.isArray(holdings) ? holdings : [];
    if (!list.length) {
        return [{
            type: 'info',
            message: '当前无持仓数据，添加持仓后将自动生成风险与调仓建议。'
        }];
    }
    const total = list.reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    const sorted = list.slice().sort((a, b) => (Number(b.market_value) || 0) - (Number(a.market_value) || 0));
    const top = sorted[0];
    const topWeight = total > 0 ? ((Number(top.market_value) || 0) / total * 100) : 0;
    const fundValue = list
        .filter(h => (h.asset_type || '股票') === '基金')
        .reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    const stockValue = list
        .filter(h => (h.asset_type || '股票') === '股票')
        .reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    const fundRatio = total > 0 ? fundValue / total * 100 : 0;
    const stockRatio = total > 0 ? stockValue / total * 100 : 0;
    const losers = list.filter(h => (Number(h.return_pct) || 0) < -8);
    const winners = list.filter(h => (Number(h.return_pct) || 0) > 15);

    const alerts = [];
    if (top && topWeight > 30) {
        alerts.push({
            type: 'warning',
            message: `${top.name} 当前仓位约 ${topWeight.toFixed(1)}%，集中度偏高，建议分批降至 20%-25% 区间。`
        });
    } else {
        alerts.push({
            type: 'success',
            message: `单一标的最大仓位约 ${topWeight.toFixed(1)}%，集中度可控。`
        });
    }
    alerts.push({
        type: 'info',
        message: `当前结构：股票 ${stockRatio.toFixed(1)}%，基金 ${fundRatio.toFixed(1)}%。建议按风险偏好做股基再平衡。`
    });
    if (losers.length) {
        alerts.push({
            type: 'warning',
            message: `${losers.length} 个持仓回撤超过 8%，建议检查基本面并设置分级止损/减仓规则。`
        });
    } else if (winners.length) {
        alerts.push({
            type: 'success',
            message: `${winners.length} 个持仓收益超过 15%，可考虑“止盈一部分 + 保留趋势仓位”。`
        });
    } else {
        alerts.push({
            type: 'info',
            message: '组合收益分布较均衡，优先维持纪律并按月复盘。'
        });
    }
    return alerts.slice(0, 3);
}

function getHoldingsFingerprint() {
    const list = (holdingsData || []).slice().sort((a, b) => String(a.code || '').localeCompare(String(b.code || '')));
    return list.map(h =>
        `${h.code}|${Math.round(Number(h.market_value || h.amount || 0))}|${Number(h.return_pct || 0).toFixed(2)}`
    ).join(';');
}

function schedulePortfolioKimiRebalanceFetch() {
    clearTimeout(_portfolioKimiDebounceTimer);
    if (!holdingsData || !holdingsData.length) {
        portfolioKimiRebalance = { loading: false, error: '', text: '', hash: '', macroSnapshot: '' };
        renderPortfolioRebalancePanel();
        return;
    }
    _portfolioKimiDebounceTimer = setTimeout(() => {
        fetchPortfolioKimiRebalanceAdvice(false);
    }, 650);
}

async function fetchPortfolioKimiRebalanceAdvice(force) {
    if (!holdingsData || !holdingsData.length) return;
    if (portfolioKimiRebalance.loading && !force) return;
    const fp = getHoldingsFingerprint();
    if (!force && portfolioKimiRebalance.text && portfolioKimiRebalance.hash === fp) return;

    portfolioKimiRebalance.loading = true;
    portfolioKimiRebalance.error = '';
    renderPortfolioRebalancePanel();

    const totalCost = holdingsData.reduce((sum, h) => sum + (Number(h.shares) || 0) * (Number(h.cost) || 0), 0);
    const totalCurrent = holdingsData.reduce((sum, h) => sum + (Number(h.shares) || 0) * (Number(h.current) || 0), 0);
    const totalReturn = totalCost > 0 ? ((totalCurrent - totalCost) / totalCost) * 100 : 0;
    const industry = computeIndustryDistributionFromHoldings(holdingsData);
    const payload = {
        holdings: holdingsData.map(h => ({
            code: h.code,
            name: h.name,
            asset_type: h.asset_type || '股票',
            market_value: Number(h.market_value) || (Number(h.shares) * Number(h.current)) || 0,
            return_pct: Number(h.return_pct) || 0,
            shares: Number(h.shares) || 0,
            cost: Number(h.cost) || 0,
            current: Number(h.current) || 0,
        })),
        total_return_pct: totalReturn,
        total_value: totalCurrent,
        industry_distribution: industry,
    };
    try {
        const urls = [
            apiUrl('/api/kimi/rebalance'),
            apiUrl('/api/kimi-portfolio-rebalance'),
        ];
        let data = null;
        let lastMsg = '';
        for (let i = 0; i < urls.length; i++) {
            const res = await fetch(urls[i], {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            data = await parseFetchJson(res);
            if (!data._parseFailed) {
                break;
            }
            lastMsg = data._message || '响应解析失败';
            if (data._httpStatus !== 404) {
                break;
            }
        }
        if (!data || data._parseFailed) {
            portfolioKimiRebalance.error = lastMsg || (data && data._message) || '响应解析失败';
            portfolioKimiRebalance.text = '';
            portfolioKimiRebalance.macroSnapshot = '';
        } else if (!data.ok) {
            portfolioKimiRebalance.error = data.error || '生成失败';
            portfolioKimiRebalance.text = '';
            portfolioKimiRebalance.macroSnapshot = '';
        } else {
            portfolioKimiRebalance.text = data.analysis || '';
            portfolioKimiRebalance.macroSnapshot = data.macro_snapshot || '';
            portfolioKimiRebalance.hash = fp;
            portfolioKimiRebalance.error = '';
        }
    } catch (e) {
        portfolioKimiRebalance.error = e.message || '网络错误';
        portfolioKimiRebalance.text = '';
        portfolioKimiRebalance.macroSnapshot = '';
    } finally {
        portfolioKimiRebalance.loading = false;
        renderPortfolioRebalancePanel();
    }
}

function renderPortfolioRebalancePanel() {
    const host = document.getElementById('rebalanceAlerts');
    if (!host) return;
    const rules = computeRebalanceAlertsFromHoldings(holdingsData);
    const icons = { warning: '⚠️', info: 'ℹ️', success: '✅' };
    const rulesHtml = rules.map(a =>
        `<div class="alert-item ${a.type}">
            <span class="alert-icon">${icons[a.type]}</span>
            <span>${a.message}</span>
        </div>`
    ).join('');

    let kimiWrap = '';
    if (!holdingsData || !holdingsData.length) {
        kimiWrap = `<div class="rebalance-kimi-placeholder muted" style="font-size:13px;line-height:1.6">添加持仓后，可结合 A 股主要指数快照与行业分布，由 Kimi 生成整体调仓思路。</div>`;
    } else {
        const dis = portfolioKimiRebalance.loading ? 'disabled' : '';
        const btnLabel = portfolioKimiRebalance.loading ? 'Kimi 分析中…' : '刷新 Kimi 建议';
        const toolbar = `<div class="rebalance-kimi-toolbar">
            <button type="button" class="btn-sm btn-sm-ai" ${dis} onclick="fetchPortfolioKimiRebalanceAdvice(true)">${btnLabel}</button>
            <span class="rebalance-kimi-hint">持仓结构 + 行业分布 + 指数宏观快照</span>
        </div>`;

        let main = '';
        if (portfolioKimiRebalance.loading && !portfolioKimiRebalance.text) {
            main = `<div class="rebalance-kimi-loading">
                <div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
                <span class="muted" style="font-size:12px;margin-top:8px">正在调用 Kimi 分析组合与宏观环境（约 15–40 秒）…</span>
            </div>`;
        } else if (portfolioKimiRebalance.error && !portfolioKimiRebalance.text) {
            main = `<div class="rebalance-kimi-error">Kimi：${escapeHtml(portfolioKimiRebalance.error)}</div>
                <p class="muted" style="font-size:12px;margin-top:8px">若为 401/密钥或模型不可用，请核对项目根目录 .env 后<strong>重启 Flask</strong>；终端里误 export 的空密钥也会生效，可先执行 <code>unset KIMI_API_KEY MOONSHOT_API_KEY</code> 再启动。</p>
                <button type="button" class="btn-secondary btn-sm" style="margin-top:8px" onclick="fetchPortfolioKimiRebalanceAdvice(true)">重试</button>`;
        } else if (portfolioKimiRebalance.text) {
            const topNote = portfolioKimiRebalance.loading
                ? `<div class="muted" style="font-size:12px;margin-bottom:8px">正在刷新 Kimi 建议…</div>`
                : '';
            const formatted = formatMarkdown(escapeHtml(portfolioKimiRebalance.text));
            const macroBlock = portfolioKimiRebalance.macroSnapshot
                ? `<details class="rebalance-macro-details"><summary>本次参考的指数快照</summary>
                    <pre class="rebalance-macro-pre">${escapeHtml(String(portfolioKimiRebalance.macroSnapshot).slice(0, 1200))}</pre></details>`
                : '';
            main = `${topNote}<div class="rebalance-kimi-body ${portfolioKimiRebalance.loading ? 'rebalance-kimi-body-dim' : ''}">${formatted}</div>
                ${macroBlock}
                <div class="kimi-disclaimer" style="margin-top:10px">以上内容由 Kimi AI 生成，仅供参考，不构成投资建议。</div>`;
        } else {
            main = `<p class="muted" style="font-size:13px;line-height:1.65;margin-bottom:12px">
                将依据您的<strong>持仓与收益</strong>、<strong>行业分布</strong>，以及<strong>上证 / 深证 / 创业板 / 沪深300</strong>等指数最新涨跌快照，生成加减仓与再平衡思路（需配置 Kimi API）。</p>
                <button type="button" class="btn-primary btn-sm" onclick="fetchPortfolioKimiRebalanceAdvice(true)">生成 AI 调仓建议</button>`;
        }
        kimiWrap = `${toolbar}${main}`;
    }

    host.innerHTML = `
        <div class="rebalance-kimi-wrap">${kimiWrap}</div>
        <div class="rebalance-local-sep"><span>本地规则参考</span></div>
        <div class="rebalance-alerts-rules">${rulesHtml}</div>
    `;
}

function refreshPortfolioByHoldings() {
    const totalCost = holdingsData.reduce((sum, h) => sum + h.shares * h.cost, 0);
    const totalCurrent = holdingsData.reduce((sum, h) => sum + h.shares * h.current, 0);
    const totalProfit = totalCurrent - totalCost;
    const totalReturn = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;
    const riskMetrics = computeRiskMetricsFromHoldings(holdingsData);
    const industryDistribution = computeIndustryDistributionFromHoldings(holdingsData);
    renderPortfolioSummary({
        holdings: holdingsData,
        total_cost: totalCost,
        total_value: totalCurrent,
        total_profit: totalProfit,
        total_return: totalReturn,
        risk_metrics: riskMetrics
    });
    const historyData = portfolioRawData && portfolioRawData.history ? portfolioRawData.history : null;
    renderPortfolioChart(historyData, holdingsData);
    renderRiskMetrics(riskMetrics);
    renderIndustryPie(industryDistribution);
    renderPortfolioRebalancePanel();
    schedulePortfolioKimiRebalanceFetch();
}

function buildDynamicPortfolioReturnSeries(history, holdings, hs300Series = null) {
    const rows = Array.isArray(history) ? history : [];
    const list = Array.isArray(holdings) ? holdings : [];
    if (!rows.length) return { dates: [], portfolioReturns: [], benchmarkReturns: [] };

    // 空持仓：组合收益率应为 0%，避免出现“无持仓仍有收益”的误导
    if (!list.length) {
        const fallbackRows = rows.slice(-60);
        let dates = fallbackRows.map(h => String(h.date || '').slice(5));
        let benchmarkReturns = fallbackRows.map(h => +((((Number(h.benchmark) || 1) - 1) * 100).toFixed(2)));
        if (hs300Series && Array.isArray(hs300Series.returns) && hs300Series.returns.length) {
            const hsReturns = hs300Series.returns.map(v => Number(v) || 0);
            const hsDates = (hs300Series.dates || []).map(d => String(d).slice(5));
            const nAlign = Math.min(hsReturns.length, fallbackRows.length);
            if (nAlign >= 2) {
                dates = hsDates.slice(-nAlign);
                benchmarkReturns = hsReturns.slice(-nAlign).map(v => +v.toFixed(2));
            }
        }
        const portfolioReturns = dates.map(() => 0);
        return { dates, portfolioReturns, benchmarkReturns };
    }

    const createdTimes = list
        .map(h => new Date(h.created_at || '').getTime())
        .filter(ts => Number.isFinite(ts) && ts > 0);
    const startTs = createdTimes.length ? Math.min(...createdTimes) : null;
    const sourceRows = startTs
        ? rows.filter(r => {
            const ts = new Date(r.date || '').getTime();
            return Number.isFinite(ts) && ts >= startTs;
        })
        : rows;
    const effectiveRows = sourceRows.length >= 2 ? sourceRows : rows.slice(-60);

    const totalCost = list.reduce((sum, h) => sum + (Number(h.shares) || 0) * (Number(h.cost) || 0), 0);
    const totalCurrent = list.reduce((sum, h) => sum + (Number(h.shares) || 0) * (Number(h.current) || 0), 0);
    const targetReturn = totalCost > 0 ? ((totalCurrent - totalCost) / totalCost) * 100 : 0;
    const assetReturns = list.map(h => Number(h.return_pct) || 0);
    const avgReturn = assetReturns.length ? assetReturns.reduce((a, b) => a + b, 0) / assetReturns.length : 0;
    const variance = assetReturns.length
        ? assetReturns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / assetReturns.length
        : 0;
    const vol = Math.sqrt(Math.max(variance, 0));
    const stockValue = list
        .filter(h => (h.asset_type || '股票') === '股票')
        .reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    const totalValue = list.reduce((sum, h) => sum + (Number(h.market_value) || 0), 0);
    const stockRatio = totalValue > 0 ? stockValue / totalValue : 0.5;
    const beta = 0.55 + stockRatio * 0.85;
    const dates = effectiveRows.map(h => String(h.date || '').slice(5));
    let benchmarkReturns = effectiveRows.map(h => +((((Number(h.benchmark) || 1) - 1) * 100).toFixed(2)));
    if (hs300Series && Array.isArray(hs300Series.returns) && hs300Series.returns.length) {
        const hsReturns = hs300Series.returns.map(v => Number(v) || 0);
        const hsDates = (hs300Series.dates || []).map(d => String(d).slice(5));
        const nAlign = Math.min(hsReturns.length, effectiveRows.length);
        if (nAlign >= 2) {
            benchmarkReturns = hsReturns.slice(-nAlign).map(v => +v.toFixed(2));
            // 使用同源日期，确保“我的持有”和“智能配置”基准曲线口径一致
            const alignedDates = hsDates.slice(-nAlign);
            if (alignedDates.length === benchmarkReturns.length) {
                for (let i = 0; i < nAlign; i++) {
                    dates[i] = alignedDates[i] || dates[i];
                }
            }
        }
    }
    const n = Math.min(effectiveRows.length, benchmarkReturns.length, dates.length);
    const useDates = dates.slice(0, n);
    benchmarkReturns = benchmarkReturns.slice(0, n);
    const benchmarkEnd = benchmarkReturns[n - 1] || 0;

    let seed = 0;
    list.forEach(h => {
        const token = `${h.code || ''}${h.name || ''}`;
        for (let i = 0; i < token.length; i++) seed += token.charCodeAt(i);
    });
    const phase = (seed % 360) * Math.PI / 180;

    const portfolioReturns = [];
    for (let i = 0; i < n; i++) {
        const t = n > 1 ? i / (n - 1) : 1;
        const linearTarget = t * targetReturn;
        const benchCenter = benchmarkReturns[i] - t * benchmarkEnd;
        const wave = Math.sin(t * Math.PI * 4 + phase) * t * (1 - t);
        const val = linearTarget + benchCenter * beta * 0.35 + wave * Math.min(8, vol * 0.18);
        portfolioReturns.push(val);
    }
    // 强制让终点与当前持仓总收益率一致
    const endDiff = targetReturn - (portfolioReturns[n - 1] || 0);
    for (let i = 0; i < n; i++) {
        const t = n > 1 ? i / (n - 1) : 1;
        portfolioReturns[i] = +(portfolioReturns[i] + endDiff * t).toFixed(2);
    }
    // 起点保持 0
    if (portfolioReturns.length) portfolioReturns[0] = 0;

    return { dates: useDates, portfolioReturns, benchmarkReturns };
}

function renderPortfolioChart(historyData, holdings) {
    const chartEl = document.getElementById('portfolioChart');
    if (!chartEl) return;
    let chart = echarts.getInstanceByDom(chartEl) || echarts.init(chartEl);

    const doRender = (dates, portfolioReturns, benchmarkReturns, startDate) => {
        const hasData = dates && dates.length > 1;
        const startLabel = startDate ? `（自 ${startDate} 起）` : '';
        chart.setOption({
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: '#1a2332',
                borderColor: '#334155',
                textStyle: { color: '#e2e8f0', fontSize: 12 },
                formatter: params => {
                    const d = params[0] && params[0].axisValue || '';
                    let s = `<div style="font-weight:600;margin-bottom:4px">${d}</div>`;
                    params.forEach(p => {
                        const color = p.color || '#fff';
                        const val = typeof p.value === 'number' ? (p.value >= 0 ? `+${p.value.toFixed(2)}%` : `${p.value.toFixed(2)}%`) : '--';
                        s += `<div style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color}"></span>${p.seriesName}: ${val}</div>`;
                    });
                    return s;
                }
            },
            legend: { data: ['我的组合收益率', '沪深300收益率'], textStyle: { color: '#94a3b8' } },
            grid: { left: 60, right: 20, top: 40, bottom: 30 },
            xAxis: {
                type: 'category',
                data: hasData ? dates : ['--'],
                axisLabel: { color: '#64748b', fontSize: 11 },
                axisLine: { lineStyle: { color: '#1e293b' } }
            },
            yAxis: {
                type: 'value',
                axisLabel: { color: '#64748b', fontSize: 11, formatter: v => `${v}%` },
                splitLine: { lineStyle: { color: '#1e293b' } }
            },
            graphic: hasData ? [] : [{
                type: 'text',
                left: 'center', top: 'middle',
                style: { text: '暂无持仓数据，添加持仓后自动生成收益率曲线', fill: '#64748b', fontSize: 13 }
            }],
            series: [
                {
                    name: '我的组合收益率', type: 'line',
                    data: hasData ? portfolioReturns : [],
                    smooth: true, symbol: 'none',
                    lineStyle: { color: '#3b82f6', width: 2 },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(59,130,246,0.18)' },
                            { offset: 1, color: 'rgba(59,130,246,0)' }
                        ])
                    }
                },
                {
                    name: '沪深300收益率', type: 'line',
                    data: hasData ? benchmarkReturns : [],
                    smooth: true, symbol: 'none',
                    lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' }
                }
            ]
        });
        // 更新图表标题说明
        const titleEl = chartEl.closest('.card') && chartEl.closest('.card').querySelector('h3');
        if (titleEl) titleEl.textContent = `收益率曲线（我的组合 vs 沪深300）${startLabel}`;
    };

    // 直接使用服务端已计算好的数据（从最早买入日期起算）
    if (historyData && historyData.dates && historyData.dates.length > 1) {
        const dates = historyData.dates.map(d => String(d).slice(5));
        doRender(dates, historyData.portfolio_returns, historyData.benchmark_returns, historyData.start_date);
    } else if (!holdings || !holdings.length) {
        doRender([], [], [], null);
    } else {
        // 有持仓但还没有服务端数据，显示加载占位
        doRender([], [], [], null);
        // 重新拉取
        fetch(`/api/portfolio-history?days=${currentPortfolioTimeframe}`)
            .then(r => r.json())
            .then(d => {
                if (d && d.dates && d.dates.length > 1) {
                    const dates = d.dates.map(dt => String(dt).slice(5));
                    doRender(dates, d.portfolio_returns, d.benchmark_returns, d.start_date);
                    if (portfolioRawData) portfolioRawData.history = d;
                }
            })
            .catch(() => {});
    }
    window.addEventListener('resize', () => chart.resize());
}

function renderHoldingTabs() {
    const stockBtn = document.getElementById('holdingTabStock');
    const fundBtn = document.getElementById('holdingTabFund');
    if (!stockBtn || !fundBtn) return;
    stockBtn.classList.toggle('active', currentHoldingTab === 'stock');
    fundBtn.classList.toggle('active', currentHoldingTab === 'fund');
}

function switchHoldingTab(tab) {
    currentHoldingTab = tab === 'fund' ? 'fund' : 'stock';
    currentHoldingPage = 1;
    renderHoldingTabs();
    renderHoldings();
    updateAddHoldingModalByTab();
}

function renderHoldingsTableHeader(filteredHoldings = []) {
    const row = document.getElementById('holdingsTableHeadRow');
    if (!row) return;
    
    let dateStr = "";
    if (filteredHoldings && filteredHoldings.length > 0) {
        const dates = filteredHoldings.map(h => h.date).filter(d => d);
        if (dates.length > 0) {
            dateStr = `<br><span style="font-size:10px;font-weight:normal;color:var(--text-muted)">${dates[0]}</span>`;
        }
    }
    
    const isFund = currentHoldingTab === 'fund';
    row.innerHTML = `
        <th>名称</th>
        <th>类型</th>
        <th>持有金额</th>
        <th>当日收益/率${dateStr}</th>
        <th>持有收益/率</th>
        <th class="th-indicator" title="${isFund ? '净值相对近60日区间的分位，越低越便宜' : 'PE/PB所处历史区间，越低越便宜'}">估值百分位</th>
        <th class="th-indicator" title="${isFund ? '从买入至今（最多1年）的区间收益率' : '近一年净利润增速（归母）'}">${isFund ? '近1年收益率' : '盈利增速'}</th>
        <th class="th-indicator" title="${isFund ? '净值从高点的最大跌幅（近1年），越小越稳' : '近5日平均换手率，衡量活跃程度'}">${isFund ? '近1年最大回撤' : '换手率'}</th>
        <th class="th-indicator" title="净值/价格相对20日均线的偏离程度，正值偏高、负值偏低">偏离度(20日)</th>
        <th class="holdings-op-head">操作</th>`;
}

function fundHoldingCostAmount(h) {
    if (h.amount !== undefined && h.amount !== null) return h.amount;
    if (h.market_value !== undefined && h.market_value !== null) return h.market_value;
    return +(h.shares * h.current || h.shares * h.cost).toFixed(2);
}

function renderHoldings() {
    const filtered = (holdingsData || []).filter(h => {
        const type = h.asset_type || '股票';
        return currentHoldingTab === 'fund' ? type === '基金' : type === '股票';
    });
    
    renderHoldingsTableHeader(filtered);

    const totalPages = Math.max(1, Math.ceil(filtered.length / HOLDINGS_PAGE_SIZE));
    if (currentHoldingPage > totalPages) currentHoldingPage = totalPages;
    if (currentHoldingPage < 1) currentHoldingPage = 1;

    const emptyColspan = 6;
    if (!filtered.length) {
        document.getElementById('holdingsBody').innerHTML =
            `<tr><td colspan="${emptyColspan}" style="text-align:center;color:var(--text-muted);padding:14px 0;">暂无${currentHoldingTab === 'fund' ? '基金' : '股票'}持仓</td></tr>`;
        renderHoldingsPagination(0, 1);
        return;
    }

    const start = (currentHoldingPage - 1) * HOLDINGS_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + HOLDINGS_PAGE_SIZE);

    document.getElementById('holdingsBody').innerHTML = pageItems.map(h => {
        const cls = h.return_pct >= 0 ? 'up' : 'down';
        const type = h.asset_type || '股票';
        const typeClass = type === '基金' ? 'fund' : 'stock';
        const amount = fundHoldingCostAmount(h);
        const codeEsc = String(h.code || '').replace(/'/g, "\\'");
        const typeEsc = String(type).replace(/'/g, "\\'");
        const nameEsc = String(h.name || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const opBtns = `<td class="holdings-op-cell">
            <div class="holdings-op-group">
                <button type="button" class="table-action-btn table-kimi-btn" onclick="openKimiValuation('${codeEsc}','${nameEsc}','${typeEsc}')">K·估值</button>
                <button type="button" class="table-action-btn" onclick="openEditHoldingModal('${codeEsc}', '${typeEsc}')">编辑</button>
                <button type="button" class="table-danger-btn" onclick="deleteHolding('${codeEsc}', '${typeEsc}')">删除</button>
            </div>
        </td>`;
        const dailyProfit = h.daily_profit || 0;
        const dailyReturnPct = h.daily_return_pct || 0;
        const dailyCls = dailyProfit >= 0 ? 'up' : 'down';

        // 指标数据（从 holdingIndicators 缓存中取）
        const ind = (holdingIndicators && holdingIndicators[h.code]) || {};
        const isFundRow = (h.asset_type || '股票') === '基金';

        // ── 估值百分位（股票/基金通用）──
        let valHtml = '<span class="ind-na">--</span>';
        if (ind.valuation_pct != null) {
            const v = Number(ind.valuation_pct);
            const vColor = v <= 30 ? '#10b981' : v <= 60 ? '#f59e0b' : '#ef4444';
            const vLabel = v <= 30 ? '低估' : v <= 60 ? '适中' : '高估';
            valHtml = `<span class="ind-badge" style="color:${vColor}">${v.toFixed(0)}%<br><span class="ind-sub">${vLabel}</span></span>`;
        }

        // ── 第二列：股票=盈利增速，基金=近1年收益率 ──
        let col2Html = '<span class="ind-na">--</span>';
        if (isFundRow) {
            if (ind.return_1y != null) {
                const r = Number(ind.return_1y);
                const rColor = r >= 10 ? '#10b981' : r >= 0 ? '#f59e0b' : '#ef4444';
                col2Html = `<span class="ind-badge" style="color:${rColor}">${r >= 0 ? '+' : ''}${r.toFixed(2)}%</span>`;
            }
        } else {
            if (ind.profit_growth != null) {
                const g = Number(ind.profit_growth);
                const gColor = g >= 20 ? '#10b981' : g >= 0 ? '#f59e0b' : '#ef4444';
                col2Html = `<span class="ind-badge" style="color:${gColor}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>`;
            }
        }

        // ── 第三列：股票=换手率，基金=近1年最大回撤 ──
        let col3Html = '<span class="ind-na">--</span>';
        if (isFundRow) {
            if (ind.max_drawdown != null) {
                const dd = Number(ind.max_drawdown);
                const ddColor = dd >= -10 ? '#10b981' : dd >= -20 ? '#f59e0b' : '#ef4444';
                const ddLabel = dd >= -10 ? '稳健' : dd >= -20 ? '一般' : '波动大';
                col3Html = `<span class="ind-badge" style="color:${ddColor}">${dd.toFixed(2)}%<br><span class="ind-sub">${ddLabel}</span></span>`;
            }
        } else {
            if (ind.turnover != null) {
                const t = Number(ind.turnover);
                const tColor = t > 5 ? '#10b981' : t > 1 ? '#f59e0b' : '#64748b';
                col3Html = `<span class="ind-badge" style="color:${tColor}">${t.toFixed(3)}%</span>`;
            }
        }

        // ── 偏离度（20日均线，通用）──
        let devHtml = '<span class="ind-na">--</span>';
        if (ind.deviation != null) {
            const d = Number(ind.deviation);
            const dColor = d > 5 ? '#ef4444' : d > 0 ? '#10b981' : d > -5 ? '#f59e0b' : '#ef4444';
            const dLabel = d > 5 ? '超买' : d > 0 ? '偏高' : d > -5 ? '偏低' : '超卖';
            devHtml = `<span class="ind-badge" style="color:${dColor}">${d >= 0 ? '+' : ''}${d.toFixed(2)}%<br><span class="ind-sub">${dLabel}</span></span>`;
        }
        
        return `<tr>
            <td><strong>${h.name}</strong><br><span style="color:var(--text-muted);font-size:11px">${h.code}</span></td>
            <td><span class="holding-type-tag ${typeClass}">${type}</span></td>
            <td>¥${amount.toFixed(2)}</td>
            <td>
                <span class="${dailyCls}">${dailyProfit >= 0 ? '+' : ''}${dailyProfit.toFixed(2)}</span><br>
                <span class="${dailyCls}" style="font-size:11px">${dailyReturnPct >= 0 ? '+' : ''}${dailyReturnPct.toFixed(2)}%</span>
            </td>
            <td>
                <span class="${cls}">${h.profit >= 0 ? '+' : ''}${h.profit.toFixed(2)}</span><br>
                <span class="${cls}" style="font-size:11px">${h.return_pct >= 0 ? '+' : ''}${h.return_pct.toFixed(2)}%</span>
            </td>
            <td class="td-indicator">${valHtml}</td>
            <td class="td-indicator">${col2Html}</td>
            <td class="td-indicator">${col3Html}</td>
            <td class="td-indicator">${devHtml}</td>
            ${opBtns}
        </tr>`;
    }).join('');

    renderHoldingsPagination(filtered.length, totalPages);
}

function changeHoldingPage(page) {
    currentHoldingPage = page;
    renderHoldings();
}

function renderHoldingsPagination(totalItems, totalPages) {
    const pager = document.getElementById('holdingsPagination');
    if (!pager) return;

    if (totalItems <= HOLDINGS_PAGE_SIZE) {
        pager.innerHTML = '';
        return;
    }

    let pagesHtml = '';
    for (let i = 1; i <= totalPages; i++) {
        pagesHtml += `<button class="page-btn ${i === currentHoldingPage ? 'active' : ''}" onclick="changeHoldingPage(${i})">${i}</button>`;
    }

    const prevDisabled = currentHoldingPage <= 1 ? 'disabled' : '';
    const nextDisabled = currentHoldingPage >= totalPages ? 'disabled' : '';
    pager.innerHTML = `
        <button class="page-btn" ${prevDisabled} onclick="changeHoldingPage(${Math.max(1, currentHoldingPage - 1)})">上一页</button>
        ${pagesHtml}
        <button class="page-btn" ${nextDisabled} onclick="changeHoldingPage(${Math.min(totalPages, currentHoldingPage + 1)})">下一页</button>
    `;
}

function openAddHoldingModal() {
    const modal = document.getElementById('addHoldingModal');
    if (!modal) return;
    updateAddHoldingModalByTab();
    initAddFundSuggest();
    modal.classList.remove('hidden');
}

function updateAddHoldingModalByTab() {
    const label = document.getElementById('addAssetKeywordLabel');
    const input = document.getElementById('addFundKeyword');
    if (!label || !input) return;
    if (currentHoldingTab === 'fund') {
        label.childNodes[0].nodeValue = '基金名称或代码';
        input.placeholder = '先输入关键词搜索（如 白酒 / 1617）';
    } else {
        label.childNodes[0].nodeValue = '股票名称或代码';
        input.placeholder = '先输入关键词搜索（如 宁德 / 300750）';
    }
}

function closeAddHoldingModal() {
    const modal = document.getElementById('addHoldingModal');
    if (!modal) return;
    modal.classList.add('hidden');
    const suggest = document.getElementById('addFundSuggest');
    if (suggest) {
        suggest.classList.remove('show');
        suggest.innerHTML = '';
    }
    selectedAddAsset = null;
}

async function submitAddHolding() {
    const keyword = document.getElementById('addFundKeyword').value.trim();
    const amount = Number(document.getElementById('addAmount').value);
    const profit = Number(document.getElementById('addProfit').value);

    if (!keyword || amount <= 0 || Number.isNaN(profit)) {
        alert(`请完整填写：${currentHoldingTab === 'fund' ? '基金' : '股票'}名称或代码、持有金额、持有收益。`);
        return;
    }

    if (!selectedAddAsset || !selectedAddAsset.code) {
        const typeText = currentHoldingTab === 'fund' ? '基金' : '股票';
        const codeMatch = keyword.match(/\b(\d{6})\b/);
        if (codeMatch) {
            const code = codeMatch[1];
            const rawName = keyword.replace(codeMatch[0], '').replace(/[()（）]/g, '').trim();
            selectedAddAsset = {
                code,
                name: rawName || `${typeText}${code}`,
                asset_type: currentHoldingTab === 'fund' ? '基金' : '股票'
            };
        } else {
            alert(`未命中模糊匹配结果。你可以继续输入更短关键词，或直接输入6位${typeText}代码后再确认添加。`);
            return;
        }
    }

    const assetType = selectedAddAsset.asset_type === '股票' ? '股票' : '基金';
    // 这里的 amount 是用户输入的持有金额（市值）
    const currentValue = amount;
    if (currentValue <= 0) {
        alert('持有金额 必须大于 0。');
        return;
    }
    const costValue = currentValue - profit;

    // 构建持仓数据（临时虚拟份额，后端会自动用真实净值覆盖）
    const shares = costValue > 0 ? costValue : amount;
    const costPrice = 1.0;
    const currentPrice = shares > 0 ? currentValue / shares : 1.0;

    try {
        const res = await fetch('/api/holdings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: selectedAddAsset.code,
                name: selectedAddAsset.name,
                asset_type: assetType,
                shares,
                unit: assetType === '基金' ? '份' : '股',
                cost: costPrice,
                current: currentPrice,
                amount,
                profit,
                created_at: new Date().toISOString().slice(0, 10),
            })
        });
        const result = await res.json();
        if (!result.ok) {
            alert(result.message || '添加失败');
            return;
        }
        // 重新从服务端加载完整数据（包括历史曲线）
        await loadPortfolio();
        currentHoldingTab = assetType === '基金' ? 'fund' : 'stock';
        renderHoldingTabs();
        renderHoldings();
        closeAddHoldingModal();
    } catch (e) {
        alert('添加失败，请稍后重试：' + e.message);
    }
}

let fundSuggestTimer = null;
function getLocalFundSuggestions(keyword, limit = 12) {
    const q = (keyword || '').trim().toLowerCase();
    if (!q) return [];
    return LOCAL_FUND_SUGGEST_POOL
        .filter(f => f.code.includes(q) || f.name.toLowerCase().includes(q))
        .slice(0, limit);
}

function getLocalStockSuggestions(keyword, limit = 12) {
    const q = (keyword || '').trim().toLowerCase();
    if (!q) return [];
    return LOCAL_STOCK_SUGGEST_POOL
        .filter(s => s.code.includes(q) || s.name.toLowerCase().includes(q))
        .slice(0, limit);
}

function mergeLocalAssetSuggestions(keyword, limit = 12) {
    const stocks = getLocalStockSuggestions(keyword, limit).map(x => ({ ...x, asset_type: '股票' }));
    const funds = getLocalFundSuggestions(keyword, limit).map(x => ({ ...x, asset_type: '基金' }));
    const merged = [...stocks, ...funds];
    const seen = new Set();
    const dedup = [];
    for (const item of merged) {
        const key = `${item.asset_type}-${item.code}`;
        if (seen.has(key)) continue;
        seen.add(key);
        dedup.push(item);
        if (dedup.length >= limit) break;
    }
    return dedup;
}

function getLocalSuggestionsByHoldingTab(keyword, tab, limit = 12) {
    if (tab === 'fund') {
        return getLocalFundSuggestions(keyword, limit).map(x => ({ ...x, asset_type: '基金' }));
    }
    if (tab === 'stock') {
        return getLocalStockSuggestions(keyword, limit).map(x => ({ ...x, asset_type: '股票' }));
    }
    return mergeLocalAssetSuggestions(keyword, limit);
}

function initAddFundSuggest() {
    const input = document.getElementById('addFundKeyword');
    const suggest = document.getElementById('addFundSuggest');
    if (!input || !suggest || input.dataset.bindSuggest === '1') return;
    input.dataset.bindSuggest = '1';

    const hideSuggest = () => {
        suggest.classList.remove('show');
        suggest.innerHTML = '';
    };

    input.addEventListener('input', () => {
        selectedAddAsset = null;
        if (fundSuggestTimer) clearTimeout(fundSuggestTimer);
        fundSuggestTimer = setTimeout(async () => {
            const q = input.value.trim();
            if (!q) {
                hideSuggest();
                return;
            }
            suggest.innerHTML = `<div class="search-suggest-item"><div class="search-suggest-meta">正在搜索...</div></div>`;
            suggest.classList.add('show');
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 16000);
                const searchPath = currentHoldingTab === 'fund' ? '/api/fund-search' : '/api/stock-search';
                const res = await fetch(`${searchPath}?q=${encodeURIComponent(q)}&limit=12`, {
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                let items = [];
                if (res.ok) {
                    const data = await res.json();
                    const rawItems = data.items || [];
                    items = rawItems.map(x => ({
                        ...x,
                        asset_type: x.asset_type || (currentHoldingTab === 'fund' ? '基金' : '股票')
                    }));
                } else {
                    // 兼容后端未重启到 stock/fund-search 的情况
                    const fallbackPath = currentHoldingTab === 'fund' ? '/api/asset-search' : '/api/asset-search';
                    const fallbackRes = await fetch(`${fallbackPath}?q=${encodeURIComponent(q)}&limit=12`);
                    const fallbackData = fallbackRes.ok ? await fallbackRes.json() : { items: [] };
                    const fallbackItems = fallbackData.items || [];
                    items = fallbackItems.filter(x => {
                        if (currentHoldingTab === 'fund') return (x.asset_type || '基金') === '基金';
                        return (x.asset_type || '股票') === '股票';
                    });
                }
                if (!items.length) items = getLocalSuggestionsByHoldingTab(q, currentHoldingTab, 12);
                if (!items.length) {
                    const codeDigits = (q.match(/\b(\d{6})\b/) || [null, ''])[1];
                    if (currentHoldingTab === 'fund' && codeDigits) {
                        items = [{
                            code: codeDigits,
                            name: `基金${codeDigits}`,
                            category: '基金',
                            asset_type: '基金'
                        }];
                    }
                }
                if (!items.length) {
                    const tip = currentHoldingTab === 'fund'
                        ? '未找到匹配基金，请更换关键词'
                        : '未找到匹配股票，请更换关键词';
                    suggest.innerHTML = `<div class="search-suggest-item"><div class="search-suggest-meta">${tip}</div></div>`;
                    suggest.classList.add('show');
                    return;
                }
                suggest.innerHTML = items.map(f =>
                    `<div class="search-suggest-item add-fund-item" data-code="${f.code}" data-name="${f.name}" data-asset-type="${f.asset_type || '基金'}">
                        <div class="search-suggest-title">${f.name}</div>
                        <div class="search-suggest-meta">${f.code} · ${f.category || f.asset_type || '资产'}</div>
                    </div>`
                ).join('');
                suggest.classList.add('show');
            } catch (e) {
                const fallback = getLocalSuggestionsByHoldingTab(q, currentHoldingTab, 12);
                if (!fallback.length) {
                    suggest.innerHTML = `<div class="search-suggest-item"><div class="search-suggest-meta">搜索失败，请稍后重试</div></div>`;
                    suggest.classList.add('show');
                    return;
                }
                suggest.innerHTML = fallback.map(f =>
                    `<div class="search-suggest-item add-fund-item" data-code="${f.code}" data-name="${f.name}" data-asset-type="${f.asset_type || '基金'}">
                        <div class="search-suggest-title">${f.name}</div>
                        <div class="search-suggest-meta">${f.code} · ${f.category || f.asset_type || '资产'}</div>
                    </div>`
                ).join('');
                suggest.classList.add('show');
            }
        }, 250);
    });

    suggest.addEventListener('click', (e) => {
        const item = e.target.closest('.add-fund-item');
        if (!item) return;
        const code = item.getAttribute('data-code') || '';
        const name = item.getAttribute('data-name') || '';
        const assetType = item.getAttribute('data-asset-type') || '基金';
        if (!code || !name) return;
        selectedAddAsset = { code, name, asset_type: assetType };
        input.value = `${name} (${code})`;
        hideSuggest();
    });

    document.addEventListener('click', (e) => {
        const modal = document.getElementById('addHoldingModal');
        if (!modal || modal.classList.contains('hidden')) return;
        if (!e.target.closest('#addFundKeyword') && !e.target.closest('#addFundSuggest')) {
            hideSuggest();
        }
    });
}

function triggerScreenshotImport() {
    const input = document.getElementById('screenshotInput');
    if (!input) return;
    input.value = '';
    input.click();
}

async function handleScreenshotImport(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/portfolio-ocr-import', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        const parsed = data.items || [];
        if (!res.ok || !data.ok || !parsed.length) {
            alert(data.message || 'OCR识别失败，请检查截图内容。');
            return;
        }
        pendingOcrImportItems = parsed.map((item, idx) => ({
            id: idx + 1,
            selected: true,
            item: normalizeHolding(item)
        }));
        openImportPreviewModal();
    } catch (e) {
        alert('OCR服务调用失败。请确认后端已安装并配置 Tesseract。');
    } finally {
        if (event?.target) event.target.value = '';
    }
}

function openImportPreviewModal() {
    const modal = document.getElementById('importPreviewModal');
    if (!modal) return;
    renderImportPreviewTable();
    modal.classList.remove('hidden');
}

function closeImportPreviewModal() {
    const modal = document.getElementById('importPreviewModal');
    if (modal) modal.classList.add('hidden');
    pendingOcrImportItems = [];
}

function toggleImportPreviewSelection(id, checked) {
    const target = pendingOcrImportItems.find(x => x.id === id);
    if (!target) return;
    target.selected = !!checked;
    renderImportPreviewSummary();
}

function renderImportPreviewSummary() {
    const summary = document.getElementById('importPreviewSummary');
    if (!summary) return;
    const total = pendingOcrImportItems.length;
    const selected = pendingOcrImportItems.filter(x => x.selected).length;
    summary.textContent = `本次识别 ${total} 条，已勾选 ${selected} 条。仅会导入已勾选条目。`;
}

function renderImportPreviewTable() {
    const tbody = document.getElementById('importPreviewBody');
    if (!tbody) return;
    if (!pendingOcrImportItems.length) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:14px 0;">暂无可导入条目</td></tr>`;
        renderImportPreviewSummary();
        return;
    }
    tbody.innerHTML = pendingOcrImportItems.map(row => {
        const h = row.item;
        const cls = h.return_pct >= 0 ? 'up' : 'down';
        const type = h.asset_type === '基金' ? '基金' : '股票';
        const typeClass = type === '基金' ? 'fund' : 'stock';
        const holdText = type === '基金'
            ? `¥${fundHoldingCostAmount(h).toFixed(2)}`
            : `${h.shares}${h.unit || '股'}`;
        const profitText = `${h.profit >= 0 ? '+' : ''}${h.profit.toFixed(2)}`;
        return `<tr>
            <td><input class="import-preview-check" type="checkbox" ${row.selected ? 'checked' : ''} onchange="toggleImportPreviewSelection(${row.id}, this.checked)"></td>
            <td><span class="holding-type-tag ${typeClass}">${type}</span></td>
            <td style="font-family:monospace;color:var(--text-muted)">${escapeHtml(String(h.code || ''))}</td>
            <td>${escapeHtml(String(h.name || ''))}</td>
            <td>${holdText}</td>
            <td class="${cls}">${profitText}</td>
        </tr>`;
    }).join('');
    renderImportPreviewSummary();
}

async function confirmImportPreview() {
    const selectedItems = pendingOcrImportItems.filter(x => x.selected).map(x => x.item);
    if (!selectedItems.length) {
        alert('请至少勾选一条识别结果再导入。');
        return;
    }
    let added = 0, skipped = 0;
    for (const item of selectedItems) {
        try {
            const res = await fetch('/api/holdings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...item, created_at: new Date().toISOString().slice(0, 10) })
            });
            const result = await res.json();
            if (result.ok) added++;
            else skipped++;  // 可能已存在
        } catch (e) {
            skipped++;
        }
    }
    await loadPortfolio();
    renderHoldings();
    const ignoredCount = pendingOcrImportItems.length - selectedItems.length;
    closeImportPreviewModal();
    alert(`截图OCR导入完成：新增 ${added} 条${skipped > 0 ? `，跳过 ${skipped} 条（已存在或失败）` : ''}${ignoredCount > 0 ? `，忽略 ${ignoredCount} 条` : ''}。`);
}

function mockParseHoldingsFromScreenshot(fileName) {
    const text = (fileName || '').toLowerCase();
    const stockCandidates = [
        { code: '300502', name: '新易盛' },
        { code: '300750', name: '宁德时代' },
        { code: '600519', name: '贵州茅台' },
        { code: '002594', name: '比亚迪' },
        { code: '601318', name: '中国平安' }
    ];
    const fundCandidates = [
        { code: '510300', name: '沪深300ETF' },
        { code: '159915', name: '创业板ETF' },
        { code: '161725', name: '招商中证白酒指数(LOF)' },
        { code: '005827', name: '易方达蓝筹精选混合' }
    ];

    const pickStock = (code, name) => ({
        code,
        name,
        asset_type: '股票',
        shares: randomInt(100, 1800),
        cost: randomFloat(8, 120),
        current: randomFloat(8, 130),
    });
    const pickFund = (code, name) => ({
        code,
        name,
        asset_type: '基金',
        shares: randomInt(2000, 30000),
        cost: randomFloat(0.8, 2.6),
        current: randomFloat(0.8, 2.9),
    });

    if (/新易盛|300502/.test(fileName)) {
        return [pickStock('300502', '新易盛')];
    }
    if (/fund|基金|etf|lof/.test(text)) {
        return shuffle(fundCandidates).slice(0, 2).map(x => pickFund(x.code, x.name));
    }
    if (/stock|股票|持仓|a股/.test(text)) {
        return shuffle(stockCandidates).slice(0, 2).map(x => pickStock(x.code, x.name));
    }
    const mix = [];
    mix.push(pickStock(stockCandidates[0].code, stockCandidates[0].name));
    mix.push(pickFund(fundCandidates[0].code, fundCandidates[0].name));
    return mix;
}

function upsertHolding(item) {
    const normalized = normalizeHolding(item);
    const idx = holdingsData.findIndex(h => h.code === normalized.code && h.asset_type === normalized.asset_type);
    if (idx < 0) {
        holdingsData.push(normalized);
        return 'added';
    }
    const old = holdingsData[idx];
    const totalShares = old.shares + normalized.shares;
    const avgCost = totalShares > 0 ? ((old.cost * old.shares + normalized.cost * normalized.shares) / totalShares) : old.cost;
    const avgCurrent = totalShares > 0 ? ((old.current * old.shares + normalized.current * normalized.shares) / totalShares) : old.current;
    holdingsData[idx] = normalizeHolding({
        ...old,
        shares: totalShares,
        cost: avgCost,
        current: avgCurrent
    });
    return 'updated';
}

function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomFloat(min, max) {
    return +(Math.random() * (max - min) + min).toFixed(2);
}

function shuffle(arr) {
    const copy = arr.slice();
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
}

async function deleteHolding(code, assetType) {
    const target = holdingsData.find(h => h.code === code && h.asset_type === assetType);
    if (!target) return;
    if (!confirm(`确认删除持仓：${target.name}（${target.code}）？`)) return;
    try {
        const res = await fetch(`/api/holdings/${code}?asset_type=${encodeURIComponent(assetType)}`, {
            method: 'DELETE'
        });
        const result = await res.json();
        if (!result.ok) { alert(result.message || '删除失败'); return; }
        await loadPortfolio();
        renderHoldings();
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

function openEditHoldingModal(code, assetType) {
    const h = holdingsData.find(x => x.code === code && x.asset_type === assetType);
    if (!h) return;
    document.getElementById('editHoldingCode').value = code;
    document.getElementById('editHoldingAssetType').value = assetType;
    const titleEl = document.getElementById('editHoldingTitle');
    if (titleEl) titleEl.textContent = `${h.name}（${h.code}）`;

    const stockPanel = document.getElementById('editStockFields');
    const fundPanel = document.getElementById('editFundFields');
    if (assetType === '基金') {
        stockPanel.classList.add('hidden');
        fundPanel.classList.remove('hidden');
        document.getElementById('editFundAmount').value = fundHoldingCostAmount(h);
        document.getElementById('editFundProfit').value = h.profit;
    } else {
        fundPanel.classList.add('hidden');
        stockPanel.classList.remove('hidden');
        document.getElementById('editStockShares').value = h.shares;
        document.getElementById('editStockCost').value = h.cost;
        document.getElementById('editStockCurrent').value = h.current;
    }
    document.getElementById('editHoldingModal').classList.remove('hidden');
}

function closeEditHoldingModal() {
    const modal = document.getElementById('editHoldingModal');
    if (modal) modal.classList.add('hidden');
}

async function submitEditHolding() {
    const code = document.getElementById('editHoldingCode').value;
    const assetType = document.getElementById('editHoldingAssetType').value;
    const prev = holdingsData.find(h => h.code === code && h.asset_type === assetType);
    if (!prev) return;

    let payload = { asset_type: assetType };

    if (assetType === '基金') {
        const amount = Number(document.getElementById('editFundAmount').value);
        const profit = Number(document.getElementById('editFundProfit').value);
        if (!(amount > 0) || Number.isNaN(profit)) {
            alert('请填写有效的持有金额与持有收益。');
            return;
        }
        const currentValue = amount;
        if (currentValue <= 0) { alert('持有金额 必须大于 0。'); return; }
        const costValue = currentValue - profit;
        
        const shares = costValue > 0 ? costValue : amount;
        const costPrice = 1.0;
        const currentPrice = shares > 0 ? currentValue / shares : 1.0;
        payload = { ...payload, shares, unit: '份', cost: costPrice, current: currentPrice, amount, profit };
    } else {
        const shares = Math.round(Number(document.getElementById('editStockShares').value));
        const cost = Number(document.getElementById('editStockCost').value);
        const current = Number(document.getElementById('editStockCurrent').value);
        if (!(shares > 0) || !(cost > 0) || !(current > 0)) {
            alert('请填写有效的持仓数量、成本价与现价。');
            return;
        }
        payload = { ...payload, shares, unit: prev.unit || '股', cost, current };
    }

    try {
        const res = await fetch(`/api/holdings/${code}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (!result.ok) { alert(result.message || '修改失败'); return; }
        await loadPortfolio();
        renderHoldings();
        closeEditHoldingModal();
    } catch (e) {
        alert('修改失败：' + e.message);
    }
}

function renderRiskMetrics(metrics) {
    const el = document.getElementById('riskMetrics');
    if (!el) return;
    const items = [
        { label: '夏普比率', value: metrics.sharpe_ratio, color: '#10b981' },
        { label: '最大回撤', value: metrics.max_drawdown + '%', color: '#ef4444' },
        { label: '年化波动率', value: metrics.volatility + '%', color: '#f59e0b' },
        { label: 'Beta系数', value: metrics.beta, color: '#3b82f6' },
        { label: 'Alpha收益', value: metrics.alpha + '%', color: '#10b981' },
        { label: 'VaR(95%)', value: metrics.var_95 + '%', color: '#ef4444' },
    ];
    el.innerHTML = items.map(m =>
        `<div class="metric-item">
            <div class="metric-label">${m.label}</div>
            <div class="metric-value" style="color:${m.color}">${m.value}</div>
        </div>`
    ).join('');
}

// ==================== Kimi 估值分析弹窗 ====================
async function openKimiValuation(code, name, assetType) {
    const modal = document.getElementById('kimiValuationModal');
    const titleEl = document.getElementById('kimiValuationTitle');
    const metaEl = document.getElementById('kimiValuationMeta');
    const contentEl = document.getElementById('kimiValuationContent');
    if (!modal) return;

    // 重置为加载状态
    titleEl.textContent = `Kimi AI 估值分析 · ${name}（${code}）`;
    metaEl.innerHTML = '';
    contentEl.innerHTML = `<div class="kimi-loading">
        <div class="typing-indicator">
            <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
        </div>
        <span style="color:var(--text-muted);font-size:13px;margin-top:8px">Kimi 正在深度分析估值，请稍候（约10-20秒）…</span>
    </div>`;
    modal.classList.remove('hidden');

    // 获取该持仓的本地指标
    const ind = (holdingIndicators && holdingIndicators[code]) || {};
    const holding = (holdingsData || []).find(h => h.code === code) || {};

    try {
        const res = await fetch(apiUrl('/api/kimi-valuation'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code,
                name,
                asset_type: assetType,
                indicators: ind,
                holding: {
                    cost: holding.cost,
                    current: holding.current,
                    return_pct: holding.return_pct,
                    market_value: holding.market_value || holding.amount
                }
            })
        });
        const data = await parseFetchJson(res);

        if (data._parseFailed) {
            contentEl.innerHTML = `<div class="kimi-error"><span style="color:#ef4444">${escapeHtml(data._message)}</span></div>`;
            return;
        }

        if (data.error) {
            contentEl.innerHTML = `<div class="kimi-error"><span style="color:#ef4444">Kimi 暂时无法响应：${data.error}</span><br><span style="color:var(--text-muted);font-size:12px;margin-top:8px;display:block">可稍后重试，或在 AI 助手中手动询问"分析 ${name} 的估值"</span></div>`;
            return;
        }

        // 渲染指标概览行（股票与基金显示不同指标）
        const isKimiFund = assetType === '基金';
        const indItems = [
            { label: '估值百分位', value: ind.valuation_pct != null ? `${Number(ind.valuation_pct).toFixed(0)}%` : '--', tip: isKimiFund ? '净值相对近60日区间的分位' : 'PE/PB历史分位' },
            {
                label: isKimiFund ? '近1年收益率' : '盈利增速',
                value: isKimiFund
                    ? (ind.return_1y != null ? `${Number(ind.return_1y) >= 0 ? '+' : ''}${Number(ind.return_1y).toFixed(2)}%` : '--')
                    : (ind.profit_growth != null ? `${Number(ind.profit_growth) >= 0 ? '+' : ''}${Number(ind.profit_growth).toFixed(1)}%` : '--'),
                tip: isKimiFund ? '从1年前至今的净值涨幅' : '近一年归母净利润增速'
            },
            {
                label: isKimiFund ? '近1年最大回撤' : '换手率(5日均)',
                value: isKimiFund
                    ? (ind.max_drawdown != null ? `${Number(ind.max_drawdown).toFixed(2)}%` : '--')
                    : (ind.turnover != null ? `${Number(ind.turnover).toFixed(3)}%` : '--'),
                tip: isKimiFund ? '近1年净值从高点的最大跌幅' : '衡量市场活跃度'
            },
            { label: '偏离20日线', value: ind.deviation != null ? `${Number(ind.deviation) >= 0 ? '+' : ''}${Number(ind.deviation).toFixed(2)}%` : '--', tip: '正值偏高于均线，负值偏低' },
        ];
        metaEl.innerHTML = `<div class="kimi-ind-overview">${indItems.map(it => `
            <div class="kimi-ind-item" title="${it.tip}">
                <div class="kimi-ind-label">${it.label}</div>
                <div class="kimi-ind-value">${it.value}</div>
            </div>`).join('')}</div>`;

        // 渲染 Kimi 文字分析（支持简单 Markdown 加粗/换行）
        const formatted = (data.analysis || '').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
        contentEl.innerHTML = `<div class="kimi-analysis-text">${formatted}</div>
            <div class="kimi-disclaimer">以上分析由 Kimi AI 生成，仅供参考，不构成投资建议。</div>`;

    } catch (e) {
        contentEl.innerHTML = `<div class="kimi-error"><span style="color:#ef4444">请求失败：${e.message}</span></div>`;
    }
}

function closeKimiValuationModal() {
    const modal = document.getElementById('kimiValuationModal');
    if (modal) modal.classList.add('hidden');
}

function renderIndustryPie(distribution) {
    const chart = echarts.init(document.getElementById('industryPie'));
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316'];
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {d}%', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0' }},
        series: [{
            type: 'pie', radius: ['40%', '65%'],
            label: { color: '#94a3b8', fontSize: 11, formatter: '{b}\n{d}%' },
            labelLine: { lineStyle: { color: '#334155' }},
            itemStyle: { borderColor: '#1a2332', borderWidth: 2 },
            data: distribution.map((d, i) => ({ name: d.name, value: d.value, itemStyle: { color: colors[i % colors.length] }}))
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

// ==================== Chat ====================
function sendQuickChat(text) {
    document.getElementById('chatInput').value = text;
    sendChat();
}

async function sendChat() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    const container = document.getElementById('chatMessages');
    const welcome = container.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    container.innerHTML += `
        <div class="message user">
            <div class="message-avatar">U</div>
            <div class="message-content">${escapeHtml(message)}</div>
        </div>`;

    input.value = '';

    container.innerHTML += `
        <div class="message ai" id="typingMsg">
            <div class="message-avatar">AI</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>`;
    container.scrollTop = container.scrollHeight;

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                holdings: Array.isArray(holdingsData) ? holdingsData : []
            })
        });
        const data = await res.json();

        const typingMsg = document.getElementById('typingMsg');
        if (typingMsg) typingMsg.remove();

        const formatted = formatMarkdown(data.response);
        container.innerHTML += `
            <div class="message ai">
                <div class="message-avatar">AI</div>
                <div class="message-content">
                    ${formatted}
                    <div class="message-meta">
                        <span>模型: ${data.model}</span>
                        <span>置信度: ${(data.confidence * 100).toFixed(0)}%</span>
                        <span>意图: ${data.intent}</span>
                    </div>
                </div>
            </div>`;
        container.scrollTop = container.scrollHeight;
    } catch (e) {
        const typingMsg = document.getElementById('typingMsg');
        if (typingMsg) typingMsg.remove();
        container.innerHTML += `
            <div class="message ai">
                <div class="message-avatar">AI</div>
                <div class="message-content" style="color:var(--red)">抱歉，服务暂时不可用，请稍后再试。</div>
            </div>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMarkdown(text) {
    return text
        .replace(/^##\s+(.+)$/gm, '<div class="rebalance-md-h2">$1</div>')
        .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)(?=$|[\s)])/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

// ==================== Global Fund Search ====================
function initGlobalSearch() {
    const input = document.getElementById('searchInput');
    const suggest = document.getElementById('searchSuggest');
    if (!input || !suggest) return;

    let timer = null;

    const hideSuggest = () => {
        suggest.classList.remove('show');
        suggest.innerHTML = '';
    };

    const renderItems = (items) => {
        if (!Array.isArray(items) || items.length === 0) {
            suggest.innerHTML = `<div class="search-suggest-item"><div class="search-suggest-meta">未找到匹配基金，请尝试基金代码或更短关键词</div></div>`;
            suggest.classList.add('show');
            return;
        }

        suggest.innerHTML = items.map(f => `
            <div class="search-suggest-item" data-code="${f.code}" data-name="${f.name}">
                <div class="search-suggest-title">${f.name}</div>
                <div class="search-suggest-meta">${f.code} · ${f.category || '基金'}</div>
            </div>
        `).join('');
        suggest.classList.add('show');
    };

    const runSearch = async () => {
        const q = input.value.trim();
        if (!q) {
            hideSuggest();
            return;
        }
        try {
            const res = await fetch(`/api/fund-search?q=${encodeURIComponent(q)}&limit=12`);
            const data = await res.json();
            renderItems(data.items || []);
        } catch (e) {
            suggest.innerHTML = `<div class="search-suggest-item"><div class="search-suggest-meta">搜索服务暂不可用，请稍后重试</div></div>`;
            suggest.classList.add('show');
        }
    };

    input.addEventListener('input', () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(runSearch, 250);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            runSearch();
        }
        if (e.key === 'Escape') hideSuggest();
    });

    suggest.addEventListener('click', (e) => {
        const item = e.target.closest('.search-suggest-item');
        if (!item) return;
        const code = item.getAttribute('data-code') || '';
        const name = item.getAttribute('data-name') || '';
        if (code && name) {
            input.value = `${name} (${code})`;
            hideSuggest();
            switchPage('chat');
            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
                chatInput.value = `请分析基金 ${name}（${code}）的投资价值与风险。`;
            }
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box')) hideSuggest();
    });
}

// ==================== Education ====================
async function loadEducation() {
    try {
        const res = await fetch('/api/education');
        const data = await res.json();
        const courses = Array.isArray(data.courses) ? data.courses : [];
        document.getElementById('eduGrid').innerHTML = courses.map(c =>
            `<div class="edu-card" onclick="openEducationDetail(${c.id})">
                <div class="edu-icon">${c.icon}</div>
                <h4>${c.title}</h4>
                <p>${c.desc}</p>
                <div class="edu-meta">
                    <span class="edu-level ${c.level}">${c.level}</span>
                    <span>${c.duration}</span>
                </div>
                <div class="edu-topics">
                    ${c.topics.map(t => `<span class="edu-topic">${t}</span>`).join('')}
                </div>
            </div>`
        ).join('');
        window.__educationCourses = courses;
        closeEducationDetail();
    } catch (e) {
        console.error('Failed to load education:', e);
    }
}

function openEducationDetail(courseId) {
    const list = Array.isArray(window.__educationCourses) ? window.__educationCourses : [];
    const course = list.find(c => Number(c.id) === Number(courseId));
    if (!course) return;
    const card = document.getElementById('eduDetailCard');
    const title = document.getElementById('eduDetailTitle');
    const meta = document.getElementById('eduDetailMeta');
    const desc = document.getElementById('eduDetailDesc');
    const topics = document.getElementById('eduDetailTopics');
    if (!card || !title || !meta || !desc || !topics) return;

    title.textContent = `${course.icon || ''} ${course.title}`.trim();
    meta.textContent = `${course.level || '未分级'} · ${course.duration || '时长未知'}`;
    desc.textContent = course.desc || '';
    topics.innerHTML = (course.topics || []).map(t => `<span class="edu-topic">${t}</span>`).join('');
    card.classList.remove('hidden');
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function closeEducationDetail() {
    const card = document.getElementById('eduDetailCard');
    if (card) card.classList.add('hidden');
}

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    restoreRiskAssessmentUI();
    initGlobalSearch();
});

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
let currentHoldingTab = 'stock';
let currentHoldingPage = 1;
const HOLDINGS_PAGE_SIZE = 10;
const RISK_STORAGE_KEY = 'smartAdvisorRiskResultV1';
const HOLDINGS_STORAGE_KEY = 'smartAdvisorMockHoldingsV1';
let portfolioRawData = null;
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

function saveRiskResult(data) {
    if (!data || !data.profile || !data.allocation) return;
    try {
        localStorage.setItem(RISK_STORAGE_KEY, JSON.stringify({
            profile: data.profile,
            allocation: data.allocation,
            score: data.score,
            max_score: data.max_score,
            radar: data.radar
        }));
    } catch (e) {
        console.warn('Failed to save risk result:', e);
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
        console.warn('Failed to load risk result:', e);
        return null;
    }
}

function clearRiskResult() {
    try {
        localStorage.removeItem(RISK_STORAGE_KEY);
    } catch (e) {
        console.warn('Failed to clear risk result:', e);
    }
}

function restoreRiskAssessmentUI() {
    const saved = loadRiskResult();
    if (!saved) return;
    riskProfile = saved.profile;
    riskResultData = saved;
    allocationData = saved.allocation;
    document.getElementById('riskIntro').classList.add('hidden');
    document.getElementById('riskQuiz').classList.add('hidden');
    document.getElementById('riskResult').classList.remove('hidden');
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
    try {
        const res = await fetch('/api/market');
        const data = await res.json();
        renderIndices(data.indices, data.update_time);  // 传入更新时间
        renderHkIndices(data.hk_indices || []);
        renderUsIndices(data.us_indices || []);
        renderKline(data.kline, data.kline_map);
        renderSectors(data.sectors);
        renderInsights(data.ai_insights);
        renderSentiment(data.market_sentiment, data.sentiment_analysis || {});
        renderNews(data.news);
    } catch (e) {
        console.error('Failed to load dashboard:', e);
    }
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
    grid.innerHTML = sectors.map(s => {
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

function renderInsights(insights) {
    document.getElementById('aiInsights').innerHTML = insights.map(text =>
        `<div class="insight-item">${text}</div>`
    ).join('');
}

function renderSentiment(value, analysis = {}) {
    const chart = echarts.init(document.getElementById('sentimentGauge'));
    const label = analysis.label || (value > 0.6 ? '偏贪婪' : value > 0.4 ? '中性' : '偏恐惧');
    chart.setOption({
        backgroundColor: 'transparent',
        series: [{
            type: 'gauge',
            startAngle: 200, endAngle: -20,
            min: 0, max: 1,
            radius: '90%',
            progress: { show: true, width: 14, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [
                { offset: 0, color: '#10b981' }, { offset: 0.5, color: '#f59e0b' }, { offset: 1, color: '#ef4444' }
            ]}}},
            axisLine: { lineStyle: { width: 14, color: [[1, '#1e293b']] }},
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            pointer: { show: false },
            title: { show: true, offsetCenter: [0, '40%'], color: '#64748b', fontSize: 13 },
            detail: {
                valueAnimation: true, offsetCenter: [0, '-5%'],
                fontSize: 32, fontWeight: 700,
                formatter: v => (v * 100).toFixed(0),
                color: value > 0.6 ? '#ef4444' : value > 0.4 ? '#f59e0b' : '#10b981'
            },
            data: [{ value: value, name: label }]
        }]
    });

    const hintEl = document.getElementById('sentimentHint');
    if (hintEl) {
        const prompt = analysis.prompt || '情绪波动处于常态区间，建议按计划执行。';
        const nlpSummary = analysis.nlp_summary || '';
        const z = typeof analysis.zscore === 'number' ? `（偏离均值 ${analysis.zscore.toFixed(2)}σ）` : '';
        hintEl.textContent = `${prompt}${z}${nlpSummary ? ` ${nlpSummary}` : ''}`;
    }

    window.addEventListener('resize', () => chart.resize());
}

function renderNews(news) {
    document.getElementById('newsFeed').innerHTML = news.map(n =>
        `<div class="news-item">
            ${n.link ? `<a class="news-title news-link" href="${n.link}" target="_blank" rel="noopener noreferrer">${n.title}</a>` : `<div class="news-title">${n.title}</div>`}
            <div class="news-meta">
                <span>${n.source}</span>
                <span>${n.time}</span>
                <span class="news-sentiment ${n.sentiment}">${n.sentiment === 'positive' ? '利好' : '利空'}</span>
                <span>${n.impact}</span>
            </div>
        </div>`
    ).join('');
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
    renderBacktest();
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

function renderAllocDetails(allocation) {
    document.getElementById('allocDetails').innerHTML = allocation.map(a =>
        `<div class="alloc-item">
            <div class="alloc-color" style="background:${a.color}"></div>
            <span class="alloc-name">${a.name}</span>
            <span class="alloc-pct">${a.value}%</span>
            <div class="alloc-bar-bg"><div class="alloc-bar-fill" style="width:${a.value}%;background:${a.color}"></div></div>
        </div>`
    ).join('');
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

async function renderBacktest() {
    const chart = echarts.init(document.getElementById('backtestChart'));
    let dates = [];
    let benchmarkReturns = [];
    let portfolioReturns = [];
    try {
        const data = await getHs300ReturnSeries(365);
        dates = (data.dates || []).map(d => d.slice(5));
        benchmarkReturns = (data.returns || []).map(v => Number(v) || 0);
    } catch (e) {
        dates = [];
        benchmarkReturns = [];
    }

    if (!dates.length || !benchmarkReturns.length) {
        const days = 365;
        let p = 0;
        let b = 0;
        for (let i = 0; i < days; i++) {
            const d = new Date();
            d.setDate(d.getDate() - (days - i));
            dates.push(d.toISOString().slice(5, 10));
            p += (Math.random() - 0.5) * 1.6;
            b += (Math.random() - 0.5) * 1.2;
            portfolioReturns.push(+p.toFixed(2));
            benchmarkReturns.push(+b.toFixed(2));
        }
    } else {
        let p = 0;
        for (let i = 0; i < benchmarkReturns.length; i++) {
            p += ((benchmarkReturns[i] - (benchmarkReturns[i - 1] ?? 0)) * 0.9) + (Math.random() - 0.5) * 0.3;
            portfolioReturns.push(+p.toFixed(2));
        }
    }

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 12 }},
        legend: { data: ['AI配置组合收益率', '沪深300收益率'], textStyle: { color: '#94a3b8' }, top: 0 },
        grid: { left: 50, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#64748b', fontSize: 11 }, axisLine: { lineStyle: { color: '#1e293b' }}},
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11, formatter: v => `${v.toFixed(0)}%` }, splitLine: { lineStyle: { color: '#1e293b' }}},
        series: [
            {
                name: 'AI配置组合收益率', type: 'line', data: portfolioReturns, smooth: true, symbol: 'none',
                lineStyle: { color: '#3b82f6', width: 2 },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.2)' }, { offset: 1, color: 'rgba(59,130,246,0)' }
                ])}
            },
            {
                name: '沪深300收益率', type: 'line', data: benchmarkReturns, smooth: true, symbol: 'none',
                lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' }
            }
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

// ==================== Stock Screening ====================
function updateFactorDisplay() {
    ['Value', 'Growth', 'Quality', 'Momentum', 'Sentiment'].forEach(f => {
        const val = document.getElementById('factor' + f).value;
        document.getElementById('factor' + f + 'Display').textContent = val + '%';
    });
}

async function runScreening() {
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
        renderStockTable(data.stocks);
        renderFactorRadar(data.stocks.slice(0, 5));
    } catch (e) {
        console.error('Failed to screen stocks:', e);
    }
}

function renderStockTable(stocks) {
    document.getElementById('stockCount').textContent = stocks.length + '只';
    const tbody = document.getElementById('stockTableBody');
    tbody.innerHTML = stocks.map((s, i) => {
        const score = s.scores.total;
        const scoreCls = score >= 65 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';
        const peText = (s.pe === null || s.pe === undefined) ? '--' : s.pe;
        const roeText = (s.roe === null || s.roe === undefined) ? '--' : `${s.roe}%`;
        return `<tr>
            <td><strong>${i + 1}</strong></td>
            <td style="color:var(--text-muted);font-family:monospace">${s.code}</td>
            <td><strong>${s.name}</strong></td>
            <td>${s.industry}</td>
            <td>¥${s.price.toFixed(2)}</td>
            <td>${peText}</td>
            <td>${roeText}</td>
            <td><span class="score-badge ${scoreCls}">${score.toFixed(1)}</span></td>
            <td><span class="ai-reason-text">${s.ai_reason}</span></td>
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
async function loadPortfolio() {
    try {
        const res = await fetch('/api/portfolio');
        const data = await res.json();
        portfolioRawData = data;
        holdingsData = loadOrInitMockHoldings(data.holdings || []);
        refreshPortfolioByHoldings();
        renderHoldingTabs();
        renderHoldings();
    } catch (e) {
        console.error('Failed to load portfolio:', e);
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
    const profit = (current - cost) * shares;
    const returnPct = cost > 0 ? ((current - cost) / cost) * 100 : 0;
    return {
        code: (item.code || '').toString().trim(),
        name: (item.name || '').toString().trim(),
        asset_type: type,
        shares: Math.round(shares),
        unit,
        created_at: createdAt,
        cost: +cost.toFixed(2),
        current: +current.toFixed(2),
        market_value: +(current * shares).toFixed(2),
        profit: +profit.toFixed(2),
        return_pct: +returnPct.toFixed(2)
    };
}

function saveMockHoldings() {
    try {
        localStorage.setItem(HOLDINGS_STORAGE_KEY, JSON.stringify(holdingsData || []));
    } catch (e) {
        console.warn('Failed to save holdings:', e);
    }
}

function loadOrInitMockHoldings(defaultHoldings) {
    try {
        const raw = localStorage.getItem(HOLDINGS_STORAGE_KEY);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) return parsed.map(normalizeHolding);
        }
    } catch (e) {
        console.warn('Failed to load holdings:', e);
    }
    const initial = (defaultHoldings || []).map(normalizeHolding);
    holdingsData = initial;
    saveMockHoldings();
    return initial;
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

function refreshPortfolioByHoldings() {
    if (!portfolioRawData) return;
    const totalCost = holdingsData.reduce((sum, h) => sum + h.shares * h.cost, 0);
    const totalCurrent = holdingsData.reduce((sum, h) => sum + h.shares * h.current, 0);
    const totalProfit = totalCurrent - totalCost;
    const totalReturn = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;
    const riskMetrics = computeRiskMetricsFromHoldings(holdingsData);
    const industryDistribution = computeIndustryDistributionFromHoldings(holdingsData);
    const rebalanceAlerts = computeRebalanceAlertsFromHoldings(holdingsData);
    renderPortfolioSummary({
        ...portfolioRawData,
        holdings: holdingsData,
        total_cost: totalCost,
        total_value: totalCurrent,
        total_profit: totalProfit,
        total_return: totalReturn,
        risk_metrics: riskMetrics
    });
    renderPortfolioChart(portfolioRawData.history || [], holdingsData);
    renderRiskMetrics(riskMetrics);
    renderIndustryPie(industryDistribution);
    renderRebalanceAlerts(rebalanceAlerts);
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

function renderPortfolioChart(history, holdings) {
    const chart = echarts.init(document.getElementById('portfolioChart'));
    const render = (dates, portfolioReturns, benchmarkReturns) => chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 12 }},
        legend: { data: ['我的组合收益率', '沪深300收益率'], textStyle: { color: '#94a3b8' }},
        grid: { left: 60, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#64748b', fontSize: 11 }, axisLine: { lineStyle: { color: '#1e293b' }}},
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11, formatter: v => `${v}%` }, splitLine: { lineStyle: { color: '#1e293b' }}},
        series: [
            {
                name: '我的组合收益率', type: 'line', data: portfolioReturns, smooth: true, symbol: 'none',
                lineStyle: { color: '#3b82f6', width: 2 },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.15)' }, { offset: 1, color: 'rgba(59,130,246,0)' }
                ])}
            },
            { name: '沪深300收益率', type: 'line', data: benchmarkReturns, smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' }}
        ]
    });
    const fallbackSeries = buildDynamicPortfolioReturnSeries(history, holdings);
    render(fallbackSeries.dates, fallbackSeries.portfolioReturns, fallbackSeries.benchmarkReturns);

    getHs300ReturnSeries(Math.max(180, Array.isArray(history) ? history.length : 180))
        .then(hs300 => {
            const latestSeries = buildDynamicPortfolioReturnSeries(history, holdings, hs300);
            render(latestSeries.dates, latestSeries.portfolioReturns, latestSeries.benchmarkReturns);
        })
        .catch(() => {});
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

function renderHoldingsTableHeader() {
    const row = document.getElementById('holdingsTableHeadRow');
    if (!row) return;
    row.innerHTML = `
        <th>名称</th>
        <th>类型</th>
        <th>持有金额</th>
        <th>持有收益</th>
        <th>收益率</th>
        <th class="holdings-op-head">操作</th>`;
}

function fundHoldingCostAmount(h) {
    return +(h.shares * h.cost).toFixed(2);
}

function renderHoldings() {
    renderHoldingsTableHeader();
    const filtered = (holdingsData || []).filter(h => {
        const type = h.asset_type || '股票';
        return currentHoldingTab === 'fund' ? type === '基金' : type === '股票';
    });

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
        const opBtns = `<td class="holdings-op-cell">
            <div class="holdings-op-group">
                <button type="button" class="table-action-btn" onclick="openEditHoldingModal('${codeEsc}', '${typeEsc}')">编辑</button>
                <button type="button" class="table-danger-btn" onclick="deleteHolding('${codeEsc}', '${typeEsc}')">删除</button>
            </div>
        </td>`;
        return `<tr>
            <td><strong>${h.name}</strong><br><span style="color:var(--text-muted);font-size:11px">${h.code}</span></td>
            <td><span class="holding-type-tag ${typeClass}">${type}</span></td>
            <td>¥${amount.toFixed(2)}</td>
            <td class="${cls}">${h.profit >= 0 ? '+' : ''}${h.profit.toFixed(2)}</td>
            <td class="${cls}">${h.return_pct >= 0 ? '+' : ''}${h.return_pct.toFixed(2)}%</td>
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

function submitAddHolding() {
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
            const rawName = keyword
                .replace(codeMatch[0], '')
                .replace(/[()（）]/g, '')
                .trim();
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

    const asset = {
        code: selectedAddAsset.code,
        name: selectedAddAsset.name,
        asset_type: selectedAddAsset.asset_type || (currentHoldingTab === 'fund' ? '基金' : '股票')
    };
    const currentValue = amount + profit;
    if (currentValue <= 0) {
        alert('持有金额 + 持有收益 必须大于 0。');
        return;
    }
    const currentPrice = 1;
    const shares = Math.max(1, Math.round(currentValue / currentPrice));
    const costPrice = amount / shares;

    const assetType = asset.asset_type === '股票' ? '股票' : '基金';
    const unit = assetType === '基金' ? '份' : '股';
    const exists = holdingsData.some(h => h.code === asset.code && h.asset_type === assetType);
    if (exists) {
        alert('该资产已存在，请先删除后再添加。');
        return;
    }

    holdingsData.push(normalizeHolding({
        code: asset.code,
        name: asset.name,
        asset_type: assetType,
        shares,
        unit,
        cost: costPrice,
        current: currentPrice
    }));
    saveMockHoldings();
    refreshPortfolioByHoldings();
    currentHoldingTab = assetType === '基金' ? 'fund' : 'stock';
    renderHoldingTabs();
    renderHoldings();
    closeAddHoldingModal();
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

function confirmImportPreview() {
    const selectedItems = pendingOcrImportItems.filter(x => x.selected).map(x => x.item);
    if (!selectedItems.length) {
        alert('请至少勾选一条识别结果再导入。');
        return;
    }
    let added = 0;
    let updated = 0;
    selectedItems.forEach(item => {
        const merged = upsertHolding(item);
        if (merged === 'added') added += 1;
        if (merged === 'updated') updated += 1;
    });
    saveMockHoldings();
    refreshPortfolioByHoldings();
    renderHoldings();
    const skipped = pendingOcrImportItems.length - selectedItems.length;
    closeImportPreviewModal();
    alert(`截图OCR导入完成：新增 ${added} 条，合并 ${updated} 条${skipped > 0 ? `，忽略 ${skipped} 条` : ''}。`);
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

function deleteHolding(code, assetType) {
    const target = holdingsData.find(h => h.code === code && h.asset_type === assetType);
    if (!target) return;
    if (!confirm(`确认删除持仓：${target.name}（${target.code}）？`)) return;
    holdingsData = holdingsData.filter(h => !(h.code === code && h.asset_type === assetType));
    saveMockHoldings();
    refreshPortfolioByHoldings();
    renderHoldings();
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

function submitEditHolding() {
    const code = document.getElementById('editHoldingCode').value;
    const assetType = document.getElementById('editHoldingAssetType').value;
    const idx = holdingsData.findIndex(h => h.code === code && h.asset_type === assetType);
    if (idx < 0) return;
    const prev = holdingsData[idx];

    if (assetType === '基金') {
        const amount = Number(document.getElementById('editFundAmount').value);
        const profit = Number(document.getElementById('editFundProfit').value);
        if (!(amount > 0) || Number.isNaN(profit)) {
            alert('请填写有效的持有金额与持有收益。');
            return;
        }
        const currentValue = amount + profit;
        if (currentValue <= 0) {
            alert('持有金额 + 持有收益 必须大于 0。');
            return;
        }
        const currentPrice = 1;
        const shares = Math.max(1, Math.round(currentValue / currentPrice));
        const costPrice = amount / shares;
        holdingsData[idx] = normalizeHolding({
            code: prev.code,
            name: prev.name,
            asset_type: '基金',
            shares,
            unit: '份',
            cost: costPrice,
            current: currentPrice
        });
    } else {
        const shares = Math.round(Number(document.getElementById('editStockShares').value));
        const cost = Number(document.getElementById('editStockCost').value);
        const current = Number(document.getElementById('editStockCurrent').value);
        if (!(shares > 0) || !(cost > 0) || !(current > 0)) {
            alert('请填写有效的持仓数量、成本价与现价。');
            return;
        }
        holdingsData[idx] = normalizeHolding({
            code: prev.code,
            name: prev.name,
            asset_type: '股票',
            shares,
            unit: prev.unit || '股',
            cost,
            current
        });
    }
    saveMockHoldings();
    refreshPortfolioByHoldings();
    renderHoldings();
    closeEditHoldingModal();
}

function renderRiskMetrics(metrics) {
    const items = [
        { label: '夏普比率', value: metrics.sharpe_ratio, color: '#10b981' },
        { label: '最大回撤', value: metrics.max_drawdown + '%', color: '#ef4444' },
        { label: '年化波动率', value: metrics.volatility + '%', color: '#f59e0b' },
        { label: 'Beta系数', value: metrics.beta, color: '#3b82f6' },
        { label: 'Alpha收益', value: metrics.alpha + '%', color: '#10b981' },
        { label: 'VaR(95%)', value: metrics.var_95 + '%', color: '#ef4444' },
    ];
    document.getElementById('riskMetrics').innerHTML = items.map(m =>
        `<div class="metric-item">
            <div class="metric-label">${m.label}</div>
            <div class="metric-value" style="color:${m.color}">${m.value}</div>
        </div>`
    ).join('');
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

function renderRebalanceAlerts(alerts) {
    const icons = { warning: '⚠️', info: 'ℹ️', success: '✅' };
    document.getElementById('rebalanceAlerts').innerHTML = alerts.map(a =>
        `<div class="alert-item ${a.type}">
            <span class="alert-icon">${icons[a.type]}</span>
            <span>${a.message}</span>
        </div>`
    ).join('');
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

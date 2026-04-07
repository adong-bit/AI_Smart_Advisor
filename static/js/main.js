// ==================== State ====================
let currentPage = 'dashboard';
let riskQuestions = [];
let currentQuestion = 0;
let userAnswers = [];
let riskProfile = null;
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

function loadRiskResult() {
    try {
        const raw = localStorage.getItem(RISK_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || !parsed.profile || !parsed.allocation) return null;
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
    allocationData = saved.allocation;
    document.getElementById('riskIntro').classList.add('hidden');
    document.getElementById('riskQuiz').classList.add('hidden');
    document.getElementById('riskResult').classList.remove('hidden');
    renderResult(saved);
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
    renderScoreRing(data.score, data.max_score, data.profile);

    const profileColors = { '保守型': '#3b82f6', '稳健型': '#10b981', '平衡型': '#f59e0b', '进取型': '#f97316', '激进型': '#ef4444' };
    const color = profileColors[data.profile] || '#3b82f6';
    document.getElementById('resultProfile').textContent = `您的风险画像：${data.profile}`;
    document.getElementById('resultProfile').style.color = color;
    document.getElementById('resultDesc').textContent = data.allocation.description;

    renderRadarChart(data.radar);
    renderAllocationPreview(data.allocation);
}

function renderScoreRing(score, max, profile) {
    const chart = echarts.init(document.getElementById('resultScoreRing'));
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
    const chart = echarts.init(document.getElementById('radarChart'));
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
                value: [radar.risk_tolerance, radar.investment_exp, radar.financial_knowledge, radar.income_stability, radar.investment_horizon],
                areaStyle: { color: 'rgba(59,130,246,0.2)' },
                lineStyle: { color: '#3b82f6', width: 2 },
                itemStyle: { color: '#3b82f6' }
            }]
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderAllocationPreview(alloc) {
    const chart = echarts.init(document.getElementById('allocationPreview'));
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {d}%', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0' }},
        series: [{
            type: 'pie', radius: ['45%', '70%'], center: ['50%', '50%'],
            avoidLabelOverlap: true,
            label: { show: true, color: '#94a3b8', fontSize: 12, formatter: '{b}\n{d}%' },
            labelLine: { lineStyle: { color: '#334155' }},
            itemStyle: { borderColor: '#1a2332', borderWidth: 2 },
            data: alloc.allocation.map(a => ({ name: a.name, value: a.value, itemStyle: { color: a.color }}))
        }]
    });
    window.addEventListener('resize', () => chart.resize());
}

function retakeAssessment() {
    document.getElementById('riskResult').classList.add('hidden');
    document.getElementById('riskIntro').classList.remove('hidden');
    riskProfile = null;
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

function renderBacktest() {
    const chart = echarts.init(document.getElementById('backtestChart'));
    const days = 365;
    const dates = [];
    const portfolio = [];
    const benchmark = [];
    let pNav = 100, bNav = 100;

    for (let i = 0; i < days; i++) {
        const d = new Date();
        d.setDate(d.getDate() - (days - i));
        dates.push(d.toISOString().slice(5, 10));
        pNav *= (1 + (Math.random() - 0.47) * 0.02);
        bNav *= (1 + (Math.random() - 0.48) * 0.025);
        portfolio.push(+pNav.toFixed(2));
        benchmark.push(+bNav.toFixed(2));
    }

    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 12 }},
        legend: { data: ['AI配置组合', '沪深300'], textStyle: { color: '#94a3b8' }, top: 0 },
        grid: { left: 50, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#64748b', fontSize: 11 }, axisLine: { lineStyle: { color: '#1e293b' }}},
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11, formatter: v => v.toFixed(0) }, splitLine: { lineStyle: { color: '#1e293b' }}},
        series: [
            {
                name: 'AI配置组合', type: 'line', data: portfolio, smooth: true, symbol: 'none',
                lineStyle: { color: '#3b82f6', width: 2 },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.2)' }, { offset: 1, color: 'rgba(59,130,246,0)' }
                ])}
            },
            {
                name: '沪深300', type: 'line', data: benchmark, smooth: true, symbol: 'none',
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
        return `<tr>
            <td><strong>${i + 1}</strong></td>
            <td style="color:var(--text-muted);font-family:monospace">${s.code}</td>
            <td><strong>${s.name}</strong></td>
            <td>${s.industry}</td>
            <td>¥${s.price.toFixed(2)}</td>
            <td>${s.pe}</td>
            <td>${s.roe}%</td>
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
        renderPortfolioSummary(data);
        renderPortfolioChart(data.history);
        holdingsData = data.holdings || [];
        renderHoldingTabs();
        renderHoldings();
        renderRiskMetrics(data.risk_metrics);
        renderIndustryPie(data.industry_distribution);
        renderRebalanceAlerts(data.rebalance_alerts);
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
            <div class="summary-value" style="color:#10b981">${data.risk_metrics.sharpe_ratio}</div>
            <div class="summary-sub">优于82%的组合</div>
        </div>`;
}

function renderPortfolioChart(history) {
    const chart = echarts.init(document.getElementById('portfolioChart'));
    chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 12 }},
        legend: { data: ['我的组合', '沪深300'], textStyle: { color: '#94a3b8' }},
        grid: { left: 60, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: history.map(h => h.date.slice(5)), axisLabel: { color: '#64748b', fontSize: 11 }, axisLine: { lineStyle: { color: '#1e293b' }}},
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11 }, splitLine: { lineStyle: { color: '#1e293b' }}},
        series: [
            {
                name: '我的组合', type: 'line', data: history.map(h => h.nav), smooth: true, symbol: 'none',
                lineStyle: { color: '#3b82f6', width: 2 },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(59,130,246,0.15)' }, { offset: 1, color: 'rgba(59,130,246,0)' }
                ])}
            },
            { name: '沪深300', type: 'line', data: history.map(h => h.benchmark), smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' }}
        ]
    });
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
}

function renderHoldings() {
    const filtered = (holdingsData || []).filter(h => {
        const type = h.asset_type || '股票';
        return currentHoldingTab === 'fund' ? type === '基金' : type === '股票';
    });

    const totalPages = Math.max(1, Math.ceil(filtered.length / HOLDINGS_PAGE_SIZE));
    if (currentHoldingPage > totalPages) currentHoldingPage = totalPages;
    if (currentHoldingPage < 1) currentHoldingPage = 1;

    if (!filtered.length) {
        document.getElementById('holdingsBody').innerHTML =
            `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:14px 0;">暂无${currentHoldingTab === 'fund' ? '基金' : '股票'}持仓</td></tr>`;
        renderHoldingsPagination(0, 1);
        return;
    }

    const start = (currentHoldingPage - 1) * HOLDINGS_PAGE_SIZE;
    const pageItems = filtered.slice(start, start + HOLDINGS_PAGE_SIZE);

    document.getElementById('holdingsBody').innerHTML = pageItems.map(h => {
        const cls = h.return_pct >= 0 ? 'up' : 'down';
        const type = h.asset_type || '股票';
        const unit = h.unit || (type === '基金' ? '份' : '股');
        const typeClass = type === '基金' ? 'fund' : 'stock';
        return `<tr>
            <td><strong>${h.name}</strong><br><span style="color:var(--text-muted);font-size:11px">${h.code}</span></td>
            <td><span class="holding-type-tag ${typeClass}">${type}</span></td>
            <td>${h.shares}${unit}</td>
            <td>¥${h.current.toFixed(2)}</td>
            <td class="${cls}">${h.profit >= 0 ? '+' : ''}${h.profit.toFixed(0)}</td>
            <td class="${cls}">${h.return_pct >= 0 ? '+' : ''}${h.return_pct.toFixed(2)}%</td>
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
            body: JSON.stringify({ message: message })
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
        document.getElementById('eduGrid').innerHTML = data.courses.map(c =>
            `<div class="edu-card">
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
    } catch (e) {
        console.error('Failed to load education:', e);
    }
}

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    restoreRiskAssessmentUI();
    initGlobalSearch();
});

# -*- coding: utf-8 -*-
"""
使用 Moonshot（Kimi）根据风险画像 + 情绪调仓后比例 + 当日行情快照，
生成个性化资产配置分析文案与要点列表。
不配置或调用失败时返回兜底文案，engine = kimi_disabled / kimi_failed。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Tuple

import requests

from dotenv_local import get_kimi_api_key, load_local_env
from kimi_news_sentiment import _extract_json_object, _http_error_message

load_local_env()

logger = logging.getLogger(__name__)

KIMI_API_URL = os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1/chat/completions").strip()
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k").strip()

_PROFILE_DESC = {
    "保守型": "风险承受能力低，追求资产安全与稳定收益，以固定收益类资产为主",
    "稳健型": "风险承受能力中低，在追求稳定的同时兼顾一定收益，债券为主、权益为辅",
    "平衡型": "风险承受能力中等，能够在风险与收益之间寻求平衡，均衡配置各类资产",
    "进取型": "风险承受能力较高，愿意承受较大波动以追求更高收益，以权益类资产为主",
    "激进型": "风险承受能力高，追求收益最大化，能够承受较大幅度的资产波动",
}


def _advice_enabled() -> bool:
    if os.getenv("ALLOCATION_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool(get_kimi_api_key())


def _build_prompt(
    profile: str,
    base_alloc: List[Dict[str, Any]],
    adjusted_alloc: List[Dict[str, Any]],
    tilt_note: str,
    market_bundle: Dict[str, Any],
    sentiment_value: float,
) -> str:
    sentiment_pct = int(round(sentiment_value * 100))
    if sentiment_value >= 0.67:
        sentiment_label = "贪婪"
    elif sentiment_value <= 0.33:
        sentiment_label = "恐惧"
    else:
        sentiment_label = "中性"

    lines = [
        "以下为当日市场快照与配置建议背景，请仅依据这些数据撰写分析，不得编造未出现的数值或新闻。",
        "",
        f"【投资者风险画像】{profile}：{_PROFILE_DESC.get(profile, '')}",
        "",
        f"【当前市场情绪】{sentiment_label}（{sentiment_pct}/100）",
        "",
        "【基准配置（风险画像默认值）】",
    ]
    for item in base_alloc:
        lines.append(f"- {item['name']}: {item['value']}%")

    lines.append("")
    lines.append(f"【情绪调整后配置】调仓说明：{tilt_note or '中性市场，不调整'}")
    for orig, adj in zip(base_alloc, adjusted_alloc):
        diff = adj["value"] - orig["value"]
        diff_str = f"({'+' if diff >= 0 else ''}{diff:.1f}%)" if diff != 0 else ""
        lines.append(f"- {adj['name']}: {adj['value']}% {diff_str}".strip())

    lines.append("")
    lines.append("【A股主要指数】")
    for x in (market_bundle.get("a_share_indices") or []):
        lines.append(f"- {x.get('name', '')}: 涨跌 {x.get('change_pct', 0)}%")
    if not market_bundle.get("a_share_indices"):
        lines.append("- （暂无）")

    lines.append("")
    lines.append("【行业板块涨跌（热力图样本）】")
    for x in (market_bundle.get("sectors") or []):
        lines.append(f"- {x.get('name', '')}: {x.get('change_pct', 0)}%")
    if not market_bundle.get("sectors"):
        lines.append("- （暂无）")

    lines.append("")
    lines.append("【7×24 快讯（含 Kimi 情绪标注）】")
    for i, x in enumerate((market_bundle.get("flash_news") or [])[:8], 1):
        lines.append(f"{i}. [{x.get('sentiment', 'neutral')}] {x.get('title', '')}")
    if not market_bundle.get("flash_news"):
        lines.append("- （暂无）")

    return "\n".join(lines)


def generate_allocation_advice_with_kimi(
    profile: str,
    base_alloc: List[Dict[str, Any]],
    adjusted_alloc: List[Dict[str, Any]],
    tilt_note: str,
    market_bundle: Dict[str, Any],
    sentiment_value: float,
) -> Tuple[str, List[str], str, str]:
    """
    调用 Kimi 生成配置分析文案和要点列表。

    返回 (advice_text, key_points, error, engine)：
    - engine: kimi / kimi_failed / kimi_disabled
    - 成功时 error 为空字符串
    - 失败时返回兜底文案（非空）
    """
    _fallback_advice = (
        f"您的风险画像为「{profile}」，当前市场情绪指数为 {int(round(sentiment_value*100))}/100。"
        f"{tilt_note or '市场处于中性区间，维持基准配置。'}"
        "建议定期检视组合，根据市场变化适时调整。"
    )
    _fallback_points: List[str] = [
        "Kimi 暂不可用，以下为规则生成建议",
        f"当前画像「{profile}」：配置已按情绪指标微调，请参考调仓说明",
        "仅供参考，不构成投资建议",
    ]

    if not _advice_enabled():
        if os.getenv("ALLOCATION_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
            return _fallback_advice, _fallback_points, "已设置 ALLOCATION_USE_KIMI=0，未调用 Kimi", "kimi_disabled"
        if not get_kimi_api_key():
            return _fallback_advice, _fallback_points, "未配置 KIMI_API_KEY，无法生成配置建议", "kimi_disabled"
        return _fallback_advice, _fallback_points, "Kimi 配置建议未启用", "kimi_disabled"

    api_key = get_kimi_api_key()
    user_block = _build_prompt(profile, base_alloc, adjusted_alloc, tilt_note, market_bundle, sentiment_value)

    system_prompt = (
        "你是专业中文投顾助手，专注资产配置分析。请只依据用户给出的「市场快照与配置背景」撰写分析，"
        "不得捏造快照中不存在的数据、日期或新闻来源。"
        "输出必须是合法 JSON 对象，顶层只含键 advice（字符串，1~2 段，总结配置逻辑与当前市场环境的契合度）"
        "和 key_points（字符串数组，2~4 条操作要点，每条 1 句，具体可执行）。"
        "风格克制、客观，末尾必须注明「仅供参考，不构成投资建议」。"
        "不得输出 JSON 以外的任何文字。"
    )
    user_message = (
        "请根据下列配置背景与市场快照生成分析 JSON：\n\n"
        + user_block
        + '\n\n只输出：{"advice":"...","key_points":["...","..."]}'
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _try_parse(content: str) -> Tuple[str, List[str], str]:
        parsed = _extract_json_object(content)
        if not parsed:
            return "", [], f"无法解析 JSON（前 100 字）：{content[:100]!r}"
        advice = str(parsed.get("advice") or "").strip()
        raw_pts = parsed.get("key_points")
        if not advice:
            return "", [], "JSON 中 advice 为空"
        if not isinstance(raw_pts, list):
            return advice, [], ""
        points = [str(x).strip() for x in raw_pts if str(x).strip()][:4]
        return advice, points, ""

    def _call_with_format(json_object_mode: bool) -> Tuple[str, List[str], str, str]:
        last_err = ""
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(2.5)
                payload: Dict[str, Any] = {
                    "model": KIMI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                }
                if json_object_mode:
                    payload["response_format"] = {"type": "json_object"}
                resp = requests.post(KIMI_API_URL, headers=headers, json=payload, timeout=55)
                if resp.status_code == 429:
                    last_err = "HTTP 429：请求过于频繁"
                    continue
                if resp.status_code == 401:
                    return _fallback_advice, _fallback_points, "HTTP 401：API 密钥无效或已过期", "kimi_failed"
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {_http_error_message(resp)}"
                    continue
                data = resp.json() or {}
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                content = (content or "").strip()
                if not content:
                    last_err = "Kimi 返回内容为空"
                    continue
                advice, points, perr = _try_parse(content)
                if advice:
                    return advice, points, "", "kimi"
                last_err = perr or "解析失败"
            except requests.exceptions.Timeout:
                last_err = "请求超时（55s）"
            except requests.exceptions.ConnectionError as e:
                return _fallback_advice, _fallback_points, f"网络连接失败：{e}", "kimi_failed"
            except Exception as e:
                last_err = f"请求异常：{e}"
                logger.warning("Kimi 配置建议: %s", last_err, exc_info=True)
                break
        return _fallback_advice, _fallback_points, last_err or "Kimi 调用失败", "kimi_failed"

    adv, pts, err, eng = _call_with_format(True)
    if eng == "kimi":
        return adv, pts, "", "kimi"
    adv2, pts2, err2, eng2 = _call_with_format(False)
    if eng2 == "kimi":
        return adv2, pts2, "", "kimi"
    return _fallback_advice, _fallback_points, (err2 or err or "Kimi 配置建议生成失败"), "kimi_failed"

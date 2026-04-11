# -*- coding: utf-8 -*-
"""
使用 Moonshot（Kimi）根据当日市场快照生成「AI 市场洞察」短句列表。
不配置或调用失败时返回空列表 + 错误说明，由接口层展示兜底文案。
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


def _insights_enabled() -> bool:
    if os.getenv("INSIGHTS_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool(os.getenv("KIMI_API_KEY", "").strip())


def _bundle_to_prompt_text(bundle: Dict[str, Any]) -> str:
    """将结构化快照压成一段供模型阅读的文本（避免 prompt 过长）。"""
    lines: List[str] = [
        "以下为同一时刻抓取的市场快照，仅供你写「市场洞察」，不得编造未出现的数值或新闻。",
        "",
        f"数据交易日（展示口径）：{bundle.get('trade_date', '')}",
        f"接口组装时间：{bundle.get('data_time', '')}",
        f"A股三大指数平均涨跌幅（%）：{bundle.get('avg_index_change_pct', 0)}",
        "",
        "【A股主要指数】",
    ]
    for x in bundle.get("a_share_indices") or []:
        lines.append(f"- {x.get('name', '')}: 涨跌 {x.get('change_pct', 0)}%")
    lines.append("")
    lines.append("【港股主要指数】")
    for x in bundle.get("hk_indices") or []:
        lines.append(f"- {x.get('name', '')}: 涨跌 {x.get('change_pct', 0)}%")
    if not bundle.get("hk_indices"):
        lines.append("- （暂无）")
    lines.append("")
    lines.append("【美股主要指数】")
    for x in bundle.get("us_indices") or []:
        lines.append(f"- {x.get('name', '')}: 涨跌 {x.get('change_pct', 0)}%")
    if not bundle.get("us_indices"):
        lines.append("- （暂无）")
    lines.append("")
    lines.append("【行业板块涨跌（热力图样本，单位 %）】")
    for x in bundle.get("sectors") or []:
        lines.append(f"- {x.get('name', '')}: {x.get('change_pct', 0)}")
    if not bundle.get("sectors"):
        lines.append("- （暂无）")
    lines.append("")
    lines.append("【7×24 快讯标题与情绪标注（利好/利空/中性）】")
    for i, x in enumerate(bundle.get("flash_news") or [], 1):
        lines.append(f"{i}. [{x.get('sentiment', 'neutral')}] {x.get('title', '')}")
    if not bundle.get("flash_news"):
        lines.append("- （暂无）")
    return "\n".join(lines)


def generate_market_insights_with_kimi(bundle: Dict[str, Any]) -> Tuple[List[str], str, str]:
    """
    调用 Kimi 生成 3～5 条中文洞察短句。

    返回 (insights, error, engine)：
    - engine 为 kimi / kimi_failed / kimi_disabled；
    - 成功时 error 为空字符串，engine 为 kimi；
    - 失败或未启用时 insights 为空列表，error 为可读原因。
    """
    if not _insights_enabled():
        if os.getenv("INSIGHTS_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
            return [], "已设置 INSIGHTS_USE_KIMI=0，未调用 Kimi 生成市场洞察", "kimi_disabled"
        if not get_kimi_api_key():
            return [], "未配置 KIMI_API_KEY（或 MOONSHOT_API_KEY），无法生成 Kimi 市场洞察", "kimi_disabled"
        return [], "Kimi 市场洞察未启用", "kimi_disabled"

    api_key = get_kimi_api_key()
    user_block = _bundle_to_prompt_text(bundle)
    system_prompt = (
        "你是资深 A 股策略与宏观观察编辑。请只依据用户给出的「市场快照」写洞察，"
        "不得捏造快照中不存在的数据、日期或新闻来源。"
        "输出必须是合法 JSON 对象，且顶层只能包含键 insights。"
        "insights 为字符串数组，长度 3～5；每条 1～2 句中文，风格克制、并列点明驱动与风险，避免口号。"
        "不要 markdown，不要编号前缀；最后一条可简要提示「仅供参考，不构成投资建议」。"
        "不得输出 JSON 以外的任何文字。"
    )
    user_message = (
        "请根据下列快照生成市场洞察 JSON：\n\n"
        + user_block
        + "\n\n只输出：{\"insights\":[\"...\",\"...\"]}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _try_parse(content: str) -> Tuple[List[str], str]:
        parsed = _extract_json_object(content)
        if not parsed:
            return [], f"无法解析 JSON（前 100 字）：{content[:100]!r}"
        raw = parsed.get("insights")
        if not isinstance(raw, list):
            return [], f"JSON 中 insights 不是数组，实际类型：{type(raw).__name__}"
        out: List[str] = []
        for i, x in enumerate(raw):
            if not isinstance(x, str):
                return [], f"insights[{i}] 不是字符串"
            t = x.strip()
            if t:
                out.append(t[:400])
        if len(out) < 2:
            return [], f"有效洞察不足 2 条（得到 {len(out)} 条）"
        return out[:5], ""

    def _call_with_format(json_object_mode: bool) -> Tuple[List[str], str]:
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
                    "temperature": 0.35,
                }
                if json_object_mode:
                    payload["response_format"] = {"type": "json_object"}
                resp = requests.post(
                    KIMI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=55,
                )
                if resp.status_code == 429:
                    last_err = "HTTP 429：请求过于频繁，请稍后再试"
                    logger.warning("Kimi 市场洞察: %s", last_err)
                    continue
                if resp.status_code == 401:
                    last_err = "HTTP 401：API 密钥无效或已过期"
                    return [], last_err
                if resp.status_code != 200:
                    detail = _http_error_message(resp)
                    last_err = f"HTTP {resp.status_code}: {detail}"
                    logger.warning("Kimi 市场洞察: %s", last_err)
                    continue
                data = resp.json() or {}
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                content = (content or "").strip()
                if not content:
                    last_err = "Kimi 返回内容为空"
                    continue
                insights, perr = _try_parse(content)
                if insights:
                    return insights, ""
                last_err = perr or "解析失败"
            except requests.exceptions.Timeout:
                last_err = "请求超时（55s），请稍后重试"
            except requests.exceptions.ConnectionError as e:
                return [], f"网络连接失败：{e}"
            except Exception as e:
                last_err = f"请求异常：{e}"
                logger.warning("Kimi 市场洞察: %s", last_err, exc_info=True)
                break
        return [], last_err or "Kimi 市场洞察生成失败"

    ok, err1 = _call_with_format(True)
    if ok:
        return ok, "", "kimi"
    ok2, err2 = _call_with_format(False)
    if ok2:
        return ok2, "", "kimi"
    return [], (err2 or err1 or "Kimi 市场洞察生成失败"), "kimi_failed"

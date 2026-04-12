# -*- coding: utf-8 -*-
"""
使用 Moonshot（Kimi）OpenAPI 对 7×24 快讯标题批量判断利好/利空/中性。
不使用本地规则兜底：未配置/关闭 Kimi 或调用失败时，快讯 sentiment 一律为 neutral。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from dotenv_local import get_kimi_api_key, load_local_env

load_local_env()

logger = logging.getLogger(__name__)

KIMI_API_URL = os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1/chat/completions").strip()
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k").strip()

_LABEL_ALIASES = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
    "利好": "positive",
    "利空": "negative",
    "中性": "neutral",
    "偏多": "positive",
    "偏空": "negative",
    "bullish": "positive",
    "bearish": "negative",
    "pos": "positive",
    "neg": "negative",
    "neu": "neutral",
}


def _kimi_enabled() -> bool:
    if os.getenv("NEWS_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool(get_kimi_api_key())


def _normalize_sentiment(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _LABEL_ALIASES:
        return _LABEL_ALIASES[s]
    s2 = str(raw).strip()
    if s2 in _LABEL_ALIASES:
        return _LABEL_ALIASES[s2]
    return None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    a, b = text.find("{"), text.rfind("}")
    if 0 <= a < b:
        try:
            return json.loads(text[a : b + 1])
        except Exception:
            pass
    return None


def _http_error_message(resp: requests.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or err.get("type") or resp.text)[:400]
        if isinstance(err, str):
            return err[:400]
    except Exception:
        pass
    return (resp.text or "")[:400]


def _build_user_prompt(titles: List[str]) -> str:
    lines = [
        "你是资深A股财经编辑，请仅根据「单条标题字面信息」判断该条资讯对权益市场情绪的倾向（独立判断，互不牵连）。",
        "",
        "分类定义：",
        "- positive（利好）：偏多、业绩/政策/景气/资金面等偏暖，或明确供需紧俏等",
        "- negative（利空）：偏空、业绩恶化、风险事件、收紧、下跌承压等；"
        "地缘冲突升级、军事增兵/调动、中东等热点紧张（即便同时提到谈判）通常仍偏利空，因压制风险偏好",
        "- neutral（中性）：纯事实罗列、无方向、会议通稿无结论、或多空信息对冲难以区分",
        "",
        f"共 {len(titles)} 条，顺序与下列编号一致。",
        "只输出一个 JSON 对象，不要 markdown，不要解释。格式：",
        '{"items":[{"sentiment":"positive"},{"sentiment":"neutral"},...]}',
        "其中 items 长度必须等于标题条数，且 sentiment 只能是 positive、negative、neutral 三个英文小写值之一。",
        "",
        "标题：",
    ]
    for i, t in enumerate(titles):
        lines.append(f"{i + 1}. {t}")
    return "\n".join(lines)


def _call_kimi_json_titles(titles: List[str]) -> Dict[str, Any]:
    """
    返回 {"labels": List[str] | None, "error": str}
    error 仅在失败时非空，供接口与日志排查。
    """
    api_key = get_kimi_api_key()
    if not api_key:
        return {"labels": None, "error": "未配置环境变量 KIMI_API_KEY"}
    if not titles:
        return {"labels": None, "error": "标题列表为空"}

    system_prompt = (
        "你只输出合法 JSON，且顶层必须为对象，包含键 items（数组）。"
        "items 中每个元素为对象，仅含键 sentiment，取值必须是 positive、negative、neutral 之一。"
        "不得输出任何 JSON 以外的文字。"
    )
    user_content = _build_user_prompt(titles)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _try_parse_response(data: Dict[str, Any], titles_len: int) -> Tuple[Optional[List[str]], str]:
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if content is None:
            return None, "Kimi 返回 choices[0].message.content 为空"
        content = str(content).strip()
        if not content:
            return None, "Kimi 返回内容为空字符串"
        parsed = _extract_json_object(content)
        if not parsed:
            return None, f"无法从模型输出中解析 JSON（前80字）：{content[:80]!r}"
        if "items" not in parsed:
            return None, f"JSON 中缺少 items 键，键为：{list(parsed.keys())[:12]}"
        items = parsed["items"]
        if not isinstance(items, list):
            return None, "items 不是数组"
        if len(items) == 0 and titles_len > 0:
            return None, "items 为空数组"
        # 模型偶发少/多 1～2 条，直接判失败会导致整批快讯无标注；小幅差异自动对齐
        diff = abs(len(items) - titles_len)
        max_slack = max(2, min(5, titles_len // 3))
        if diff > max_slack:
            return None, f"items 条数 {len(items)} 与标题条数 {titles_len} 不一致（差距过大，已放弃对齐）"
        if len(items) < titles_len:
            logger.info(
                "Kimi 快讯标注: items 条数 %s 少于标题 %s，已对缺省条目标为 neutral",
                len(items),
                titles_len,
            )
            while len(items) < titles_len:
                items.append({"sentiment": "neutral"})
        elif len(items) > titles_len:
            logger.info(
                "Kimi 快讯标注: items 条数 %s 多于标题 %s，已截断至与标题一致",
                len(items),
                titles_len,
            )
            items = items[:titles_len]
        out: List[str] = []
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                return None, f"items[{idx}] 不是对象"
            lab = _normalize_sentiment(it.get("sentiment"))
            if not lab:
                return None, f"items[{idx}].sentiment 非法：{it.get('sentiment')!r}"
            out.append(lab)
        return out, ""

    def _single_request(json_object_mode: bool) -> Dict[str, Any]:
        last_err = ""
        payload: Dict[str, Any] = {
            "model": KIMI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.15,
        }
        if json_object_mode:
            payload["response_format"] = {"type": "json_object"}
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(2.5)
                resp = requests.post(
                    KIMI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=45,
                )
                if resp.status_code == 429:
                    last_err = "HTTP 429：请求过于频繁，请稍后重试"
                    logger.warning("Kimi 快讯标注: %s", last_err)
                    continue
                if resp.status_code == 401:
                    last_err = "HTTP 401：API 密钥无效或已过期，请检查 KIMI_API_KEY"
                    logger.warning("Kimi 快讯标注: %s", last_err)
                    return {"labels": None, "error": last_err}
                if resp.status_code != 200:
                    detail = _http_error_message(resp)
                    last_err = f"HTTP {resp.status_code}: {detail}"
                    logger.warning("Kimi 快讯标注: %s", last_err)
                    continue
                data = resp.json() or {}
                labels, perr = _try_parse_response(data, len(titles))
                if labels is not None:
                    return {"labels": labels, "error": ""}
                last_err = perr or "解析失败"
                logger.warning("Kimi 快讯标注: %s", last_err)
            except requests.exceptions.Timeout:
                last_err = "请求超时（45s），请检查网络或稍后重试"
                logger.warning("Kimi 快讯标注: %s", last_err)
                continue
            except requests.exceptions.ConnectionError as e:
                last_err = f"网络连接失败：{e}"
                logger.warning("Kimi 快讯标注: %s", last_err)
                return {"labels": None, "error": last_err}
            except Exception as e:
                last_err = f"请求异常：{e}"
                logger.warning("Kimi 快讯标注: %s", last_err, exc_info=True)
                break
        return {"labels": None, "error": last_err or "未知错误"}

    r1 = _single_request(True)
    if r1.get("labels"):
        return r1
    err1 = r1.get("error") or ""
    r2 = _single_request(False)
    if r2.get("labels"):
        return r2
    err2 = r2.get("error") or ""
    combined = err2 or err1 or "Kimi 调用失败"
    return {"labels": None, "error": combined}


def enrich_news_sentiment_with_kimi(news: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    就地写入每条 news 的 sentiment（仅 Kimi，无本地规则兜底）。

    返回 (engine, kimi_error)：
    - engine: 'kimi' | 'kimi_failed' | 'kimi_disabled'
    - kimi_error: Kimi 调用失败或未启用时的说明；成功则为 ''。
    """
    if not news:
        return "kimi_disabled", ""

    if not _kimi_enabled():
        for n in news:
            n["sentiment"] = "neutral"
            n["sentiment_source"] = "kimi_disabled"
        if os.getenv("NEWS_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
            hint = "已设置 NEWS_USE_KIMI=0，未调用 Kimi"
        elif not get_kimi_api_key():
            hint = "未配置 KIMI_API_KEY（或 MOONSHOT_API_KEY）：在 app.py 同目录创建 .env，写入密钥后重启服务"
        else:
            hint = "Kimi 未启用"
        return "kimi_disabled", hint

    titles = [str(n.get("title", "") or "").strip() for n in news]
    if not any(titles):
        for n in news:
            n["sentiment"] = "neutral"
            n["sentiment_source"] = "kimi_disabled"
        return "kimi_disabled", "快讯标题均为空，无法调用 Kimi"

    res = _call_kimi_json_titles(titles)
    llm_labels = res.get("labels")
    err = (res.get("error") or "").strip()

    if not llm_labels:
        if err:
            logger.warning("Kimi 快讯标注失败（未使用规则兜底，已全部标为中性）：%s", err)
        for n, t in zip(news, titles):
            n["sentiment"] = "neutral"
            n["sentiment_source"] = "kimi_failed"
        return "kimi_failed", err

    for n, lab, t in zip(news, llm_labels, titles):
        n["sentiment"] = "neutral" if not t else lab
        n["sentiment_source"] = "kimi"
    return "kimi", ""

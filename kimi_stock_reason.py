# -*- coding: utf-8 -*-
"""
使用 Moonshot（Kimi）批量为 Top N 只股票生成 AI 选股理由。
一次调用返回 {code: reason_text} 字典，失败时返回空字典由后端降级到规则理由。
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


def _reason_enabled() -> bool:
    if os.getenv("STOCK_REASON_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool(get_kimi_api_key())


def _build_prompt(stocks: List[Dict[str, Any]]) -> str:
    lines = [
        "以下是 A 股多因子模型筛选出的综合评分最高的股票，请根据各股数据生成简洁的中文选股理由。",
        "要求：每条理由 30~60 字，客观描述其因子优势，不得编造未提供的财务数据，末尾不加风险提示。",
        "",
        "股票数据：",
    ]
    for s in stocks:
        scores = s.get("scores") or {}
        pe_str = f"PE {s['pe']}" if s.get("pe") else "PE 未知"
        roe_str = f"ROE {s['roe']}%" if s.get("roe") else "ROE 未知"
        lines.append(
            f"- 代码: {s['code']}  名称: {s.get('name','')}  行业: {s.get('industry','未知')}"
            f"  现价: {s.get('price', 0):.2f}  {pe_str}  {roe_str}"
            f"  综合评分: {scores.get('total', 0):.1f}"
            f"  [价值{scores.get('value',0):.0f} 成长{scores.get('growth',0):.0f}"
            f" 质量{scores.get('quality',0):.0f} 动量{scores.get('momentum',0):.0f}"
            f" 情绪{scores.get('sentiment',0):.0f}]"
        )

    codes_json = "{" + ", ".join(f'"{s["code"]}": "..."' for s in stocks) + "}"
    lines += [
        "",
        f"请输出合法 JSON，顶层键为股票代码，值为理由字符串，格式示例：{codes_json}",
        "不得输出 JSON 以外的任何文字。",
    ]
    return "\n".join(lines)


def generate_stock_reasons_with_kimi(
    stocks: List[Dict[str, Any]],
    market_bundle: Dict[str, Any] = None,
) -> Tuple[Dict[str, str], str, str]:
    """
    批量为 Top N 只股票调用 Kimi 生成选股理由。

    返回 (reasons_dict, error, engine)：
    - reasons_dict: {code: reason_text}，成功时包含所有请求代码
    - engine: kimi / kimi_failed / kimi_disabled
    - 失败时返回空字典，由调用方降级到规则理由
    """
    if not stocks:
        return {}, "无股票数据", "kimi_disabled"

    if not _reason_enabled():
        if os.getenv("STOCK_REASON_USE_KIMI", "1").strip().lower() in ("0", "false", "no", "off"):
            return {}, "已设置 STOCK_REASON_USE_KIMI=0，未调用 Kimi", "kimi_disabled"
        return {}, "未配置 KIMI_API_KEY，无法生成选股理由", "kimi_disabled"

    api_key = get_kimi_api_key()
    user_message = _build_prompt(stocks)
    system_prompt = (
        "你是专业的 A 股投资分析助手，仅根据用户提供的因子数据撰写选股理由，"
        "不得编造未出现的数据。只输出 JSON 对象，键为股票代码字符串，值为理由字符串。"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _try_call(json_mode: bool) -> Tuple[Dict[str, str], str, str]:
        last_err = ""
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(2.0)
                payload: Dict[str, Any] = {
                    "model": KIMI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                resp = requests.post(KIMI_API_URL, headers=headers, json=payload, timeout=55)
                if resp.status_code == 429:
                    last_err = "HTTP 429：请求过于频繁"
                    continue
                if resp.status_code == 401:
                    return {}, "HTTP 401：API 密钥无效或已过期", "kimi_failed"
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {_http_error_message(resp)}"
                    continue
                data = resp.json() or {}
                content = (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
                if not content:
                    last_err = "Kimi 返回内容为空"
                    continue
                parsed = _extract_json_object(content)
                if not parsed:
                    last_err = f"无法解析 JSON（前100字）：{content[:100]!r}"
                    continue
                # 提取各股理由，允许部分缺失
                reasons: Dict[str, str] = {}
                for s in stocks:
                    code = s["code"]
                    val = parsed.get(code) or parsed.get(str(code)) or ""
                    if val and str(val).strip():
                        reasons[code] = str(val).strip()
                if reasons:
                    return reasons, "", "kimi"
                last_err = "Kimi 返回 JSON 中无匹配股票代码"
            except requests.exceptions.Timeout:
                last_err = "请求超时（55s）"
            except requests.exceptions.ConnectionError as e:
                return {}, f"网络连接失败：{e}", "kimi_failed"
            except Exception as e:
                last_err = f"请求异常：{e}"
                logger.warning("Kimi 选股理由: %s", last_err, exc_info=True)
                break
        return {}, last_err or "Kimi 调用失败", "kimi_failed"

    reasons, err, eng = _try_call(True)
    if eng == "kimi":
        return reasons, "", "kimi"
    reasons2, err2, eng2 = _try_call(False)
    if eng2 == "kimi":
        return reasons2, "", "kimi"
    return {}, (err2 or err or "Kimi 选股理由生成失败"), "kimi_failed"

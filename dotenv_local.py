# -*- coding: utf-8 -*-
"""从项目根目录（与本文件同目录）加载 .env，供 app 与 Kimi 相关模块在任意导入顺序下使用。"""

from __future__ import annotations

import os


# 这些键：若 .env 里写了非空值，则始终以 .env 为准（覆盖 shell 里 export 的旧密钥/空密钥），
# 避免「明明改了 .env 却仍用环境变量里的空值或过期 key」。
_ENV_FILE_OVERRIDES_SHELL = frozenset({
    "KIMI_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_MODEL",
    "KIMI_API_URL",
})


def load_local_env() -> None:
    """
    读取与当前文件同目录下的 .env 并写入 os.environ。
    - 对 KIMI_* / MOONSHOT_API_KEY 等：.env 中非空值始终覆盖 shell（项目根 .env 为真源）。
    - 其他键：若环境中已存在非空字符串，则不覆盖（避免误 export 永久挡住 .env）。
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue
                if key in _ENV_FILE_OVERRIDES_SHELL:
                    if value != "":
                        os.environ[key] = value
                    continue
                cur = os.environ.get(key, "")
                if cur is not None and str(cur).strip() != "":
                    continue
                os.environ[key] = value
    except Exception:
        pass


def get_kimi_api_key() -> str:
    """Moonshot 常用环境名：KIMI_API_KEY；部分环境使用 MOONSHOT_API_KEY，二者取其一。"""
    load_local_env()
    return (os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or "").strip()


def get_kimi_model(default: str = "moonshot-v1-8k") -> str:
    """每次调用前刷新 .env，避免仅用模块 import 时读到的旧 KIMI_MODEL。"""
    load_local_env()
    return (os.getenv("KIMI_MODEL") or default).strip()

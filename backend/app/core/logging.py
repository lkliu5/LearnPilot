"""日志脱敏（需求文档 7.4 / CLAUDE.md 工程纪律）。

在日志输出前对手机号、邮箱做掩码，避免 PII 落盘：
- 手机号 13800138000 → 138****8000
- 邮箱 carmela@teachers.org → c****a@teachers.org

实现为 logging.Filter，挂到 root 及 uvicorn 各 logger；对 record.msg 与
record.args（格式化参数）一并脱敏，确保 `logger.info("%s", phone)` 也被覆盖。
"""
from __future__ import annotations

import logging
import re

# 中国大陆手机号：1 开头第二位 3-9，共 11 位（避免误伤更长数字串用边界约束）
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
# 邮箱
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*([A-Za-z0-9])(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
# API Key（模型管理 21.3+ 红线兜底）：sk-/ms- 开头的令牌串（DeepSeek/魔搭等常见形态）。
# 主防线是「不打含 key 的日志 + llm_userconf.redact 清洗异常串」，此处为过滤器级兜底。
_API_KEY_RE = re.compile(r"\b(sk|ms)-[A-Za-z0-9\-_]{8,}\b")


def mask_pii(text: str) -> str:
    """对单个字符串做手机号/邮箱/API Key 掩码。"""
    text = _PHONE_RE.sub(r"\g<1>****\g<2>", text)
    text = _EMAIL_RE.sub(_mask_email, text)
    text = _API_KEY_RE.sub(lambda m: f"{m.group(1)}-****{m.group(0)[-4:]}", text)
    return text


def _mask_email(m: re.Match[str]) -> str:
    first, last, domain = m.group(1), m.group(2), m.group(3)
    return f"{first}****{last}{domain}"


class PiiMaskingFilter(logging.Filter):
    """掩码 record 的消息与字符串参数。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_pii(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask_arg(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._mask_arg(a) for a in record.args)
        return True

    @staticmethod
    def _mask_arg(value: object) -> object:
        return mask_pii(value) if isinstance(value, str) else value


def setup_logging() -> None:
    """安装脱敏过滤器到 root 与 uvicorn 日志器（幂等）。"""
    pii_filter = PiiMaskingFilter()
    targets = [
        logging.getLogger(),  # root
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("uvicorn.error"),
    ]
    for logger in targets:
        if not any(isinstance(f, PiiMaskingFilter) for f in logger.filters):
            logger.addFilter(pii_filter)
        for handler in logger.handlers:
            if not any(isinstance(f, PiiMaskingFilter) for f in handler.filters):
                handler.addFilter(pii_filter)

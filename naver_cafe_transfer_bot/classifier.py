"""양도글 판별 로직.

'명의 변경' 목적이 아니라 '일정 관리 부담/개인 사정' 때문에 양도하는 글만 골라낸다.
키워드는 띄어쓰기 차이를 무시하고 비교한다 (예: "명의 변경" == "명의변경").
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(text: str | None) -> str:
    """HTML 태그/엔티티를 제거하고 공백을 정리한다."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _squash(text: str) -> str:
    return _WS_RE.sub("", text).lower()


def _find(keywords: list[str], squashed_text: str) -> list[str]:
    hits = []
    for kw in keywords:
        k = _squash(kw)
        if k and k in squashed_text and kw not in hits:
            hits.append(kw)
    return hits


@dataclass
class Verdict:
    matched: bool
    transfer_hits: list[str] = field(default_factory=list)
    reason_hits: list[str] = field(default_factory=list)
    exclude_hits: list[str] = field(default_factory=list)

    @property
    def why(self) -> str:
        if self.exclude_hits:
            return "제외 키워드: " + ", ".join(self.exclude_hits)
        if not self.transfer_hits:
            return "양도 표현 없음"
        if not self.reason_hits:
            return "일정/사정 관련 표현 없음"
        return "사유: " + ", ".join(self.reason_hits)


class TransferClassifier:
    def __init__(
        self,
        transfer_keywords: list[str],
        reason_keywords: list[str],
        exclude_keywords: list[str],
        require_reason: bool = True,
    ):
        self.transfer_keywords = transfer_keywords
        self.reason_keywords = reason_keywords
        self.exclude_keywords = exclude_keywords
        self.require_reason = require_reason

    def classify(self, title: str, body: str = "") -> Verdict:
        text = _squash(clean_text(title) + " " + clean_text(body))
        transfer = _find(self.transfer_keywords, text)
        reasons = _find(self.reason_keywords, text)
        excludes = _find(self.exclude_keywords, text)

        matched = bool(transfer) and not excludes and (bool(reasons) or not self.require_reason)
        return Verdict(matched, transfer, reasons, excludes)

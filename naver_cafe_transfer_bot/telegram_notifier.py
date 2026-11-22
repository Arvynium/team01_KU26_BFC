"""텔레그램 봇 API 로 메시지 전송."""

from __future__ import annotations

import html
import logging
import time

import requests

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 10.0):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    def _call(self, method: str, **payload):
        url = API.format(token=self.token, method=method)
        for attempt in range(4):
            resp = requests.post(url, json=payload, timeout=self.timeout)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if resp.status_code == 429:  # 너무 많이 보냄 → 기다렸다 재시도
                wait = data.get("parameters", {}).get("retry_after", 2 ** attempt)
                log.warning("텔레그램 rate limit, %s초 대기", wait)
                time.sleep(wait)
                continue
            if not data.get("ok"):
                raise RuntimeError(f"텔레그램 API 오류 {resp.status_code}: {resp.text[:300]}")
            return data["result"]
        raise RuntimeError("텔레그램 전송 재시도 초과")

    def send(self, text: str) -> None:
        self._call(
            "sendMessage",
            chat_id=self.chat_id,
            text=text[:4096],
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
        time.sleep(1.1)  # 같은 채팅방에는 초당 1개 정도로 제한

    def recent_chat_ids(self) -> list[tuple[str, str]]:
        """봇에게 최근 메시지를 보낸 채팅방 (id, 이름) 목록. chat_id 확인용."""
        updates = self._call("getUpdates")
        seen = {}
        for u in updates:
            msg = u.get("message") or u.get("channel_post") or {}
            chat = msg.get("chat")
            if chat:
                name = chat.get("title") or chat.get("username") or chat.get("first_name", "")
                seen[str(chat["id"])] = name
        return list(seen.items())


def format_article(article, verdict) -> str:
    e = html.escape
    summary = article.body or article.description
    if len(summary) > 300:
        summary = summary[:300] + "…"
    lines = [
        f"📢 <b>{e(article.title)}</b>",
        f"☕ {e(article.cafe_name)}",
        "",
        e(summary),
        "",
        f"🔎 {e(verdict.why)}",
        f'🔗 <a href="{e(article.link, quote=True)}">글 보러가기</a>',
    ]
    return "\n".join(lines)

"""네이버 카페 글 수집.

1) 공식 네이버 검색 API (카페글) 로 검색 — 메인 수집 경로
   https://developers.naver.com/docs/serviceapi/search/cafearticle/cafearticle.md
2) (선택) 카페 웹이 사용하는 비공식 API 로 본문 전체를 읽어 정확도를 높임.
   공개 카페/전체공개 글에서만 동작하며, 실패하면 조용히 요약(description)만 사용한다.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from classifier import clean_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://openapi.naver.com/v1/search/cafearticle.json"
CAFE_INFO_URL = "https://apis.naver.com/cafe-web/cafe2/CafeGateInfo.json"
ARTICLE_URL = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{cafe_id}/articles/{article_id}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


@dataclass
class CafeArticle:
    title: str
    description: str
    link: str
    cafe_name: str
    cafe_url: str
    body: str = ""
    writer: str = ""
    menu_name: str = ""
    key_override: str = ""

    @property
    def key(self) -> str:
        """중복 판단용 키: 'cafe아이디/글번호' (쿼리스트링/프로토콜 차이 무시)."""
        if self.key_override:
            return self.key_override
        parsed = _parse_article_link(self.link)
        if parsed:
            return f"{parsed[0]}/{parsed[1]}"
        return self.link.split("?")[0].replace("https://", "").replace("http://", "")

    @property
    def cafe_id(self) -> str:
        return urlparse(self.cafe_url).path.strip("/")


def _parse_article_link(link: str) -> tuple[str, str] | None:
    """'https://cafe.naver.com/{cafe}/{articleId}' → (cafe, articleId)."""
    m = re.search(r"cafe\.naver\.com/([^/?#]+)/(\d+)", link)
    if m:
        return m.group(1), m.group(2)
    # 'ArticleRead.nhn?clubid=..&articleid=..' 형태
    club = re.search(r"clubid=(\d+)", link)
    art = re.search(r"articleid=(\d+)", link, re.I)
    if club and art:
        return club.group(1), art.group(1)
    return None


class NaverCafeClient:
    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.api_headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }
        self.timeout = timeout
        self._club_id_cache: dict[str, str | None] = {}

    # ---------- 공식 검색 API ----------
    def search(self, query: str, max_results: int = 100, sort: str = "date") -> list[CafeArticle]:
        results: list[CafeArticle] = []
        max_results = max(1, min(max_results, 1000))
        start = 1
        while start <= max_results:
            display = min(100, max_results - start + 1)
            resp = self.session.get(
                SEARCH_URL,
                headers=self.api_headers,
                params={"query": query, "display": display, "start": start, "sort": sort},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"네이버 검색 API 오류 {resp.status_code}: {resp.text[:300]}")
            items = resp.json().get("items", [])
            for it in items:
                results.append(
                    CafeArticle(
                        title=clean_text(it.get("title")),
                        description=clean_text(it.get("description")),
                        link=it.get("link", ""),
                        cafe_name=clean_text(it.get("cafename")),
                        cafe_url=it.get("cafeurl", ""),
                    )
                )
            if len(items) < display:
                break
            start += display
            time.sleep(0.2)
        return results

    # ---------- (선택) 본문 전체 읽기 ----------
    def fetch_body(self, article: CafeArticle) -> str:
        parsed = _parse_article_link(article.link)
        if not parsed:
            return ""
        cafe, article_id = parsed
        club_id = cafe if cafe.isdigit() else self._club_id(cafe)
        if not club_id:
            return ""
        try:
            resp = self.session.get(
                ARTICLE_URL.format(cafe_id=club_id, article_id=article_id),
                headers={"Referer": f"https://cafe.naver.com/{cafe}/{article_id}"},
                params={"useCafeId": "true"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                log.debug("본문 조회 실패(%s) %s", resp.status_code, article.link)
                return ""
            data = resp.json().get("result", {}).get("article", {})
            return clean_text(data.get("contentHtml", ""))
        except (requests.RequestException, ValueError) as e:
            log.debug("본문 조회 예외 %s: %s", article.link, e)
            return ""

    def _club_id(self, cafe_url: str) -> str | None:
        if cafe_url in self._club_id_cache:
            return self._club_id_cache[cafe_url]
        club_id = None
        try:
            resp = self.session.get(CAFE_INFO_URL, params={"cafeUrl": cafe_url}, timeout=self.timeout)
            if resp.status_code == 200:
                info = resp.json().get("message", {}).get("result", {}).get("cafeInfoView", {})
                cid = info.get("cafeId")
                club_id = str(cid) if cid else None
        except (requests.RequestException, ValueError) as e:
            log.debug("카페 ID 조회 실패 %s: %s", cafe_url, e)
        self._club_id_cache[cafe_url] = club_id
        return club_id

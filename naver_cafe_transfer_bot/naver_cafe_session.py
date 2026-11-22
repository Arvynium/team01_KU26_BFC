"""내 네이버 로그인 쿠키로 카페 게시판/본문을 직접 읽는 클라이언트.

브라우저에서 카페를 볼 때 cafe.naver.com 웹이 호출하는 내부 API 를 그대로 사용한다.
로그인 쿠키(NID_AUT, NID_SES)가 있으면 내가 가입한 카페의 '멤버 공개' 글도 읽을 수 있다.

※ 비공식 API 라 네이버가 응답 형식을 바꿀 수 있다.
   이상하면 `python main.py --probe` 로 원본 응답을 확인하자.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass

import requests

from classifier import clean_text

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
CAFE_GATE_URL = "https://apis.naver.com/cafe-web/cafe2/CafeGateInfo.json"
LIST_URL_V2 = "https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json"
LIST_URL_BOARD = "https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/{club}/menus/{menu}/articles"
ARTICLE_URL = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{club}/articles/{article}"


class LoginRequired(Exception):
    """쿠키가 없거나 만료됨."""


class AccessDenied(Exception):
    """로그인은 됐지만 이 글/카페를 볼 권한이 없음 (미가입, 등급 제한 등)."""


@dataclass
class BoardItem:
    article_id: str
    subject: str
    writer: str = ""
    menu_name: str = ""
    write_ts: int = 0  # ms


def parse_cookie_string(cookie: str) -> dict[str, str]:
    """'NID_AUT=...; NID_SES=...' 형식(브라우저 개발자도구에서 복사한 값)을 dict 로."""
    jar = {}
    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip():
                jar[k.strip()] = v.strip()
    return jar


def _first(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


class NaverCafeSession:
    def __init__(self, cookie: str, min_delay: float = 1.5, max_delay: float = 4.0, timeout: float = 15.0):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Origin": "https://cafe.naver.com",
            "Referer": "https://cafe.naver.com/",
        })
        jar = parse_cookie_string(cookie)
        for k, v in jar.items():
            self.s.cookies.set(k, v, domain=".naver.com")
        if not {"NID_AUT", "NID_SES"} <= jar.keys():
            log.warning("쿠키에 NID_AUT / NID_SES 가 없습니다. 멤버 전용 글은 못 읽을 수 있어요.")
        self.min_delay, self.max_delay = min_delay, max_delay
        self.timeout = timeout
        self._club_cache: dict[str, tuple[str, str, str]] = {}

    # ---------- 공통 ----------
    def pause(self) -> None:
        """사람이 클릭하는 정도의 간격으로 쉬기 (서버 부담/계정 보호)."""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _get_json(self, url: str, referer: str | None = None, **params):
        headers = {"Referer": referer} if referer else None
        resp = self.s.get(url, params=params, headers=headers, timeout=self.timeout)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return resp.status_code, data, resp

    # ---------- 카페 정보 ----------
    def resolve_cafe(self, cafe: str | int) -> tuple[str, str, str]:
        """카페 주소 아이디 또는 숫자 clubid → (clubid, 카페주소아이디, 카페이름)."""
        cafe = str(cafe).strip().rstrip("/").split("/")[-1]
        if cafe in self._club_cache:
            return self._club_cache[cafe]

        club_id, url_id, name = (cafe if cafe.isdigit() else ""), ("" if cafe.isdigit() else cafe), cafe
        if url_id:
            status, data, _ = self._get_json(CAFE_GATE_URL, cafeUrl=url_id)
            info = (data.get("message", {}).get("result", {}) or {}).get("cafeInfoView", {}) or {}
            club_id = str(_first(info, "cafeId", "clubId", default="") or "")
            name = _first(info, "cafeName", "clubName", default=name)
            if not club_id:  # 폴백: 카페 메인 HTML 에서 clubid 추출
                html = self.s.get(f"https://cafe.naver.com/{url_id}", timeout=self.timeout).text
                m = re.search(r"g_sClubId\s*=\s*['\"](\d+)", html) or re.search(r"clubid=(\d+)", html)
                if m:
                    club_id = m.group(1)
        if not club_id:
            raise RuntimeError(f"카페 '{cafe}' 의 clubid 를 찾지 못했습니다. config 에 숫자 clubid 를 직접 넣어보세요.")
        self._club_cache[cafe] = (club_id, url_id, name)
        return self._club_cache[cafe]

    # ---------- 게시판 목록 ----------
    def list_articles(self, club_id: str, menu_id: int = 0, page: int = 1, per_page: int = 50) -> list[BoardItem]:
        """최신순 게시글 목록. menu_id=0 이면 전체글보기."""
        params = {
            "search.clubid": club_id,
            "search.queryType": "lastArticle",
            "search.page": page,
            "search.perPage": per_page,
            "ad": "false",
        }
        if menu_id:
            params["search.menuid"] = menu_id
        status, data, _ = self._get_json(LIST_URL_V2, **params)
        self._raise_for_access(status, data)
        raw = (data.get("message", {}).get("result", {}) or {}).get("articleList")

        if raw is None and menu_id:  # 신형 게시판 API 폴백
            status, data, _ = self._get_json(
                LIST_URL_BOARD.format(club=club_id, menu=menu_id),
                page=page, pageSize=per_page, sortBy="TIME", viewType="L",
            )
            self._raise_for_access(status, data)
            raw = [x.get("item", x) for x in (data.get("result", {}) or {}).get("articleList", [])]

        items = []
        for a in raw or []:
            aid = _first(a, "articleId", "articleid")
            if aid is None:
                continue
            items.append(BoardItem(
                article_id=str(aid),
                subject=clean_text(_first(a, "subject", "title", default="")),
                writer=clean_text(_first(a, "writerNickname", "nickname", "writerNick", default="")),
                menu_name=clean_text(_first(a, "menuName", default="")),
                write_ts=int(_first(a, "writeDateTimestamp", "writeDate", default=0) or 0),
            ))
        return items

    # ---------- 본문 ----------
    def get_article(self, club_id: str, article_id: str, url_id: str = "") -> dict:
        referer = f"https://cafe.naver.com/{url_id or 'ca-fe/cafes/' + club_id}/{article_id}"
        status, data, _ = self._get_json(
            ARTICLE_URL.format(club=club_id, article=article_id), referer=referer,
            useCafeId="true", requestFrom="A",
        )
        self._raise_for_access(status, data)
        art = (data.get("result", {}) or {}).get("article", {}) or {}
        if not art:
            raise RuntimeError(f"본문 응답 형식을 알 수 없음 (status {status}): {str(data)[:200]}")
        writer = art.get("writer", {}) or {}
        return {
            "subject": clean_text(art.get("subject", "")),
            "body": clean_text(art.get("contentHtml", "")),
            "writer": clean_text(_first(writer, "nick", "nickname", default="")),
            "menu_name": clean_text((art.get("menu", {}) or {}).get("name", "")),
            "write_ts": int(art.get("writeDate", 0) or 0),
        }

    @staticmethod
    def _raise_for_access(status: int, data: dict) -> None:
        if status == 200:
            return
        text = str(data)[:300]
        if status == 401 or "로그인" in text:
            raise LoginRequired(f"로그인이 필요합니다 (status {status}): {text}")
        if status == 403 or "권한" in text or "멤버" in text or "가입" in text:
            raise AccessDenied(f"접근 권한 없음 (status {status}): {text}")
        raise RuntimeError(f"카페 API 오류 (status {status}): {text}")

    @staticmethod
    def article_link(club_id: str, article_id: str, url_id: str = "") -> str:
        if url_id:
            return f"https://cafe.naver.com/{url_id}/{article_id}"
        return f"https://cafe.naver.com/ca-fe/cafes/{club_id}/articles/{article_id}"

"""네이버 카페에서 '일정 관리 부담 등으로 인한 양도글' 만 골라 텔레그램으로 보내는 봇.

내 네이버 로그인 쿠키(NAVER_COOKIE)로 지정한 카페 게시판을 직접 돌면서
멤버 전용 글까지 읽고, 조건에 맞는 글만 텔레그램으로 보낸다.

사용법:
    python main.py                 # 1회 실행 (cron/작업 스케줄러용)
    python main.py --loop          # interval_seconds 마다 계속 실행
    python main.py --probe         # 쿠키/카페 설정이 제대로 되는지 원본 응답 확인
    python main.py --dry-run       # 텔레그램 전송 없이 판별 결과만 출력
    python main.py --mark-seen     # 지금 있는 글은 전부 '본 것'으로 처리 (첫 실행 알림 폭탄 방지)
    python main.py --find-chat-id  # 봇에게 메시지를 보낸 뒤 실행하면 내 chat_id 출력
    python main.py --test-telegram # 테스트 메시지 전송
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
import tomllib
from pathlib import Path

from classifier import TransferClassifier
from naver import CafeArticle, NaverCafeClient
from naver_cafe_session import AccessDenied, LoginRequired, NaverCafeSession
from storage import SeenStore
from telegram_notifier import TelegramNotifier, format_article

BASE_DIR = Path(__file__).resolve().parent
LOGIN_ALERT_INTERVAL = 6 * 3600  # 쿠키 만료 알림은 6시간에 한 번만
log = logging.getLogger("cafe-bot")


# ---------------- 설정 로딩 ----------------
def load_dotenv(path: Path) -> None:
    """의존성 없이 .env 파일을 읽어 환경변수로 등록 (이미 설정된 값은 유지)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(path: Path) -> dict:
    if not path.exists():
        example = BASE_DIR / "config.example.toml"
        log.warning("%s 가 없어 %s 를 사용합니다.", path.name, example.name)
        path = example
    with open(path, "rb") as f:
        return tomllib.load(f)


def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"환경변수가 없습니다: {', '.join(missing)}  (.env 파일을 확인하세요)")
    return [os.environ[n] for n in names]


# ---------------- 수집: 로그인 쿠키로 카페 게시판 직접 ----------------
def collect_from_cafes(sess: NaverCafeSession, cfg: dict, store: SeenStore,
                       classifier: TransferClassifier, fetch_bodies: bool = True) -> list[CafeArticle]:
    c = cfg.get("cafe", {})
    pages = c.get("pages_per_board", 1)
    per_page = c.get("per_page", 50)
    out: list[CafeArticle] = []

    for board in c.get("boards", []):
        try:
            club_id, url_id, cafe_name = sess.resolve_cafe(board["cafe"])
        except LoginRequired:
            raise
        except Exception as e:
            log.error("카페 확인 실패 [%s]: %s", board.get("cafe"), e)
            continue
        cafe_name = board.get("name", cafe_name)

        for menu_id in board.get("menu_ids") or [0]:
            for page in range(1, pages + 1):
                try:
                    items = sess.list_articles(club_id, menu_id, page, per_page)
                except AccessDenied as e:
                    log.error("[%s] 게시판 %s 접근 불가 (가입/등급 확인): %s", cafe_name, menu_id, e)
                    break
                sess.pause()
                new_items = [it for it in items if not store.has(f"{club_id}/{it.article_id}")]
                log.info("[%s] 게시판 %s p%d: %d건 중 새 글 %d건", cafe_name, menu_id or "전체", page,
                         len(items), len(new_items))

                for it in new_items:
                    art = CafeArticle(
                        title=it.subject, description="",
                        link=sess.article_link(club_id, it.article_id, url_id),
                        cafe_name=cafe_name, cafe_url=f"https://cafe.naver.com/{url_id}",
                        writer=it.writer, menu_name=it.menu_name,
                        key_override=f"{club_id}/{it.article_id}",
                    )
                    # 제목만으로 이미 제외 대상이면 본문을 열지 않는다 (요청 절약)
                    if fetch_bodies and not classifier.classify(it.subject).exclude_hits:
                        try:
                            detail = sess.get_article(club_id, it.article_id, url_id)
                            art.title = detail["subject"] or art.title
                            art.body = detail["body"]
                            art.writer = detail["writer"] or art.writer
                            art.menu_name = detail["menu_name"] or art.menu_name
                        except AccessDenied as e:
                            log.warning("본문 권한 없음, 제목으로만 판단: %s (%s)", art.title, e)
                        except LoginRequired:
                            raise
                        except Exception as e:
                            log.warning("본문 조회 실패, 제목으로만 판단: %s (%s)", art.title, e)
                        sess.pause()
                    out.append(art)

                if len(items) < per_page or not new_items:
                    break  # 마지막 페이지이거나 이미 본 글까지 도달
    return out


# ---------------- 수집: (선택) 공식 검색 API ----------------
def collect_from_search(client: NaverCafeClient, cfg: dict) -> list[CafeArticle]:
    s = cfg["search"]
    allowed_cafes = {c.lower() for c in s.get("cafe_ids", [])}
    by_key: dict[str, CafeArticle] = {}
    for q in s.get("queries", []):
        try:
            found = client.search(q, s.get("max_results_per_query", 100), s.get("sort", "date"))
        except Exception as e:
            log.error("검색 실패 [%s]: %s", q, e)
            continue
        log.info("검색 [%s] → %d건", q, len(found))
        for a in found:
            if allowed_cafes and a.cafe_id.lower() not in allowed_cafes:
                continue
            by_key.setdefault(a.key, a)
    return list(by_key.values())


# ---------------- 실행 ----------------
def alert_login_expired(notifier, store: SeenStore, err: Exception) -> None:
    log.error("네이버 로그인 쿠키가 만료됐거나 잘못됐습니다: %s", err)
    last = float(store.get_meta("login_alert_at") or 0)
    if notifier and time.time() - last > LOGIN_ALERT_INTERVAL:
        try:
            notifier.send("⚠️ 네이버 로그인 쿠키가 만료된 것 같아요.\n"
                          "브라우저에서 다시 로그인 후 .env 의 NAVER_COOKIE 를 갱신해 주세요.")
            store.set_meta("login_alert_at", str(time.time()))
        except Exception as e:
            log.error("만료 알림 전송 실패: %s", e)


def run_once(cfg: dict, args, sess, search_client, classifier, store, notifier) -> int:
    f = cfg["filter"]
    max_send = cfg["run"].get("max_messages_per_run", 30)

    articles: list[CafeArticle] = []
    if sess and cfg.get("cafe", {}).get("boards"):
        try:
            articles += collect_from_cafes(sess, cfg, store, classifier, fetch_bodies=not args.mark_seen)
        except LoginRequired as e:
            alert_login_expired(notifier, store, e)
    if search_client and cfg.get("search", {}).get("enabled", False):
        found = [a for a in collect_from_search(search_client, cfg) if not store.has(a.key)]
        for a in found:  # 검색 결과도 로그인 세션이 있으면 본문까지 읽기
            if args.mark_seen or not f.get("fetch_full_text", True):
                continue
            v = classifier.classify(a.title, a.description)
            if v.transfer_hits and not v.exclude_hits:
                a.body = search_client.fetch_body(a) if not sess else _body_via_session(sess, a)
                time.sleep(0.5)
        articles += found

    sent = 0
    for a in articles:
        if store.has(a.key):
            continue
        verdict = classifier.classify(a.title, a.body or a.description)

        if args.mark_seen:
            store.add(a.key, a.title, a.link, verdict.matched, sent=False)
            continue
        if args.dry_run:
            print(f"{'✅' if verdict.matched else '❌'} [{a.cafe_name}] {a.title}\n    {verdict.why}\n    {a.link}")
            continue

        did_send = False
        if verdict.matched:
            if sent >= max_send:
                continue  # 이번 실행 전송 한도 초과 → 다음 실행으로 미룸
            try:
                notifier.send(format_article(a, verdict))
                did_send = True
                sent += 1
                log.info("전송: %s", a.title)
            except Exception as e:
                log.error("텔레그램 전송 실패(다음 실행 때 재시도): %s", e)
                continue
        store.add(a.key, a.title, a.link, verdict.matched, did_send)

    if args.mark_seen:
        log.info("%d건을 '본 글'로 기록했습니다. 이제부터 새 글만 알림이 갑니다.", len(articles))
    return sent


def _body_via_session(sess: NaverCafeSession, a: CafeArticle) -> str:
    from naver import _parse_article_link
    parsed = _parse_article_link(a.link)
    if not parsed:
        return ""
    try:
        club_id, url_id, _ = sess.resolve_cafe(parsed[0])
        return sess.get_article(club_id, parsed[1], url_id)["body"]
    except Exception as e:
        log.debug("검색글 본문 조회 실패 %s: %s", a.link, e)
        return ""


def probe(sess: NaverCafeSession, cfg: dict) -> None:
    """설정 점검: 카페 → 게시판 목록 → 첫 글 본문까지 실제로 읽히는지 확인."""
    boards = cfg.get("cafe", {}).get("boards", [])
    if not boards:
        sys.exit("config.toml 의 [cafe] boards 에 카페를 하나 이상 넣어주세요.")
    for b in boards:
        print(f"\n=== {b['cafe']} ===")
        try:
            club_id, url_id, name = sess.resolve_cafe(b["cafe"])
            print(f"clubid={club_id}  주소={url_id}  이름={name}")
            for menu_id in b.get("menu_ids") or [0]:
                items = sess.list_articles(club_id, menu_id, 1, 5)
                print(f"- 게시판 {menu_id or '전체'}: {len(items)}건")
                for it in items:
                    print(f"    #{it.article_id} {it.subject}  ({it.writer})")
                if items:
                    sess.pause()
                    d = sess.get_article(club_id, items[0].article_id, url_id)
                    print(f"  첫 글 본문 미리보기: {d['body'][:150]}")
                sess.pause()
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")


def main() -> None:
    p = argparse.ArgumentParser(description="네이버 카페 일정 부담 양도글 → 텔레그램 알림")
    p.add_argument("--config", default=str(BASE_DIR / "config.toml"))
    p.add_argument("--loop", action="store_true", help="주기적으로 계속 실행")
    p.add_argument("--probe", action="store_true", help="쿠키/카페 설정 점검")
    p.add_argument("--dry-run", action="store_true", help="전송/저장 없이 판별 결과만 출력")
    p.add_argument("--mark-seen", action="store_true", help="현재 글을 모두 본 것으로 기록")
    p.add_argument("--find-chat-id", action="store_true", help="내 텔레그램 chat_id 확인")
    p.add_argument("--test-telegram", action="store_true", help="텔레그램 테스트 메시지 전송")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    load_dotenv(BASE_DIR / ".env")

    if args.find_chat_id:
        (token,) = require_env("TELEGRAM_BOT_TOKEN")
        chats = TelegramNotifier(token, "").recent_chat_ids()
        if not chats:
            print("봇에게 텔레그램으로 아무 메시지나 먼저 보낸 뒤 다시 실행하세요.")
        for cid, name in chats:
            print(f"TELEGRAM_CHAT_ID={cid}    # {name}")
        return
    if args.test_telegram:
        token, chat_id = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        TelegramNotifier(token, chat_id).send("✅ 네이버 카페 양도글 알림 봇 연결 성공!")
        print("전송 완료")
        return

    cfg = load_config(Path(args.config))
    c = cfg.get("cafe", {})

    sess = None
    if os.environ.get("NAVER_COOKIE"):
        sess = NaverCafeSession(os.environ["NAVER_COOKIE"], c.get("min_delay", 1.5), c.get("max_delay", 4.0))
    elif c.get("boards"):
        sys.exit("NAVER_COOKIE 가 없습니다. README 의 '로그인 쿠키 넣기' 를 참고해 .env 에 넣어주세요.")

    if args.probe:
        probe(sess, cfg)
        return

    search_client = None
    if cfg.get("search", {}).get("enabled", False):
        search_client = NaverCafeClient(*require_env("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"))
    if not sess and not search_client:
        sys.exit("수집 경로가 없습니다. [cafe] boards + NAVER_COOKIE 또는 [search] enabled 를 설정하세요.")

    notifier = None
    if not (args.dry_run or args.mark_seen):
        notifier = TelegramNotifier(*require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))

    f = cfg["filter"]
    classifier = TransferClassifier(
        f["transfer_keywords"], f["reason_keywords"], f["exclude_keywords"], f.get("require_reason", True)
    )
    db_path = Path(cfg["run"].get("db_path", "seen_articles.db"))
    store = SeenStore(str(db_path if db_path.is_absolute() else BASE_DIR / db_path))

    try:
        while True:
            try:
                n = run_once(cfg, args, sess, search_client, classifier, store, notifier)
                log.info("이번 실행에서 %d건 전송", n)
            except Exception:
                log.exception("실행 중 오류")
            if not args.loop or args.dry_run or args.mark_seen:
                break
            base = cfg["run"].get("interval_seconds", 600)
            time.sleep(base * random.uniform(0.8, 1.2))  # 매번 같은 간격으로 두드리지 않게
    except KeyboardInterrupt:
        pass
    finally:
        store.close()


if __name__ == "__main__":
    main()

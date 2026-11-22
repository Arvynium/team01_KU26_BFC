"""네이버 카페에서 '일정 관리 부담 등으로 인한 양도글' 만 골라 텔레그램으로 보내는 봇.

사용법:
    python main.py                 # 1회 실행 (cron/작업 스케줄러용)
    python main.py --loop          # interval_seconds 마다 계속 실행
    python main.py --dry-run       # 텔레그램 전송 없이 판별 결과만 출력
    python main.py --mark-seen     # 지금 있는 글은 전부 '본 것'으로 처리 (첫 실행 알림 폭탄 방지)
    python main.py --find-chat-id  # 봇에게 메시지를 보낸 뒤 실행하면 내 chat_id 출력
    python main.py --test-telegram # 테스트 메시지 전송
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import tomllib
from pathlib import Path

from classifier import TransferClassifier
from naver import CafeArticle, NaverCafeClient
from storage import SeenStore
from telegram_notifier import TelegramNotifier, format_article

BASE_DIR = Path(__file__).resolve().parent
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


# ---------------- 핵심 로직 ----------------
def collect(client: NaverCafeClient, cfg: dict) -> list[CafeArticle]:
    s = cfg["search"]
    allowed_cafes = {c.lower() for c in s.get("cafe_ids", [])}
    by_key: dict[str, CafeArticle] = {}
    for q in s["queries"]:
        try:
            found = client.search(q, s.get("max_results_per_query", 100), s.get("sort", "date"))
        except Exception as e:  # 한 검색어 실패해도 나머지는 계속
            log.error("검색 실패 [%s]: %s", q, e)
            continue
        log.info("검색 [%s] → %d건", q, len(found))
        for a in found:
            if allowed_cafes and a.cafe_id.lower() not in allowed_cafes:
                continue
            by_key.setdefault(a.key, a)
    return list(by_key.values())


def run_once(cfg: dict, args, client, classifier, store, notifier) -> int:
    f = cfg["filter"]
    max_send = cfg["run"].get("max_messages_per_run", 30)
    articles = collect(client, cfg)
    new = [a for a in articles if not store.has(a.key)]
    log.info("수집 %d건 / 새 글 %d건", len(articles), len(new))

    sent = 0
    for a in new:
        verdict = classifier.classify(a.title, a.description)

        # 요약상 후보이면 본문을 읽어서 다시 판단 (본문에 '명의변경' 등이 숨어있을 수 있음)
        if f.get("fetch_full_text", True) and verdict.transfer_hits and not verdict.exclude_hits:
            body = client.fetch_body(a)
            if body:
                a.body = body
                verdict = classifier.classify(a.title, body)
            time.sleep(0.3)

        if args.mark_seen:
            store.add(a.key, a.title, a.link, verdict.matched, sent=False)
            continue

        if args.dry_run:
            mark = "✅" if verdict.matched else "❌"
            print(f"{mark} [{a.cafe_name}] {a.title}\n    {verdict.why}\n    {a.link}")
            continue

        did_send = False
        if verdict.matched and sent < max_send:
            try:
                notifier.send(format_article(a, verdict))
                did_send = True
                sent += 1
                log.info("전송: %s", a.title)
            except Exception as e:
                log.error("텔레그램 전송 실패(다음 실행 때 재시도): %s", e)
                continue  # 저장하지 않아 다음에 다시 시도
        elif verdict.matched:
            continue  # 이번 실행 전송 한도 초과 → 다음 실행으로 미룸
        store.add(a.key, a.title, a.link, verdict.matched, did_send)

    if args.mark_seen:
        log.info("%d건을 '본 글'로 기록했습니다. 이제부터 새 글만 알림이 갑니다.", len(new))
    return sent


def main() -> None:
    p = argparse.ArgumentParser(description="네이버 카페 일정 부담 양도글 → 텔레그램 알림")
    p.add_argument("--config", default=str(BASE_DIR / "config.toml"))
    p.add_argument("--loop", action="store_true", help="주기적으로 계속 실행")
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
    cid, secret = require_env("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
    notifier = None
    if not (args.dry_run or args.mark_seen):
        notifier = TelegramNotifier(*require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))

    f = cfg["filter"]
    classifier = TransferClassifier(
        f["transfer_keywords"], f["reason_keywords"], f["exclude_keywords"], f.get("require_reason", True)
    )
    client = NaverCafeClient(cid, secret)
    db_path = Path(cfg["run"].get("db_path", "seen_articles.db"))
    store = SeenStore(str(db_path if db_path.is_absolute() else BASE_DIR / db_path))

    try:
        while True:
            try:
                n = run_once(cfg, args, client, classifier, store, notifier)
                log.info("이번 실행에서 %d건 전송", n)
            except Exception:
                log.exception("실행 중 오류")
            if not args.loop or args.dry_run or args.mark_seen:
                break
            time.sleep(cfg["run"].get("interval_seconds", 600))
    except KeyboardInterrupt:
        pass
    finally:
        store.close()


if __name__ == "__main__":
    main()

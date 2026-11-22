import sys
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from classifier import TransferClassifier, clean_text  # noqa: E402
from naver import CafeArticle, NaverCafeClient  # noqa: E402
from naver_cafe_session import NaverCafeSession, parse_cookie_string  # noqa: E402
from storage import SeenStore  # noqa: E402

CFG = tomllib.loads((ROOT / "config.example.toml").read_text(encoding="utf-8"))
F = CFG["filter"]
CLF = TransferClassifier(F["transfer_keywords"], F["reason_keywords"], F["exclude_keywords"], F["require_reason"])


class ClassifierTest(unittest.TestCase):
    def ok(self, title, body=""):
        self.assertTrue(CLF.classify(title, body).matched, (title, body, CLF.classify(title, body).why))

    def no(self, title, body=""):
        self.assertFalse(CLF.classify(title, body).matched, (title, body))

    def test_schedule_reasons_pass(self):
        self.ok("필라테스 20회 양도합니다", "회사 일정이 바뀌어서 다닐 시간이 없네요")
        self.ok("PT 10회 양도", "출장이 잦아져서 양도해요")
        self.ok("골프 레슨권 넘겨드립니다", "요즘 너무 바빠서 못가요")
        self.ok("헬스 회원권 양도", "개인사정으로 양도합니다")
        self.ok("수영 강습 양도", "스케쥴 관리가 부담돼서요")

    def test_name_change_excluded(self):
        self.no("헬스장 회원권 양도", "명의변경 해드립니다 바빠서요")
        self.no("핸드폰 명의 이전 양도", "일정상")
        self.no("명의양도 합니다", "시간이 없어서")
        self.no("인터넷 명변 양도", "이사로 인해")

    def test_other_exclusions(self):
        self.no("필라테스 양수합니다", "일정 맞는 분")
        self.no("[완료] PT 양도", "바빠서")
        self.no("PT 양도완료", "출장")

    def test_reason_required(self):
        self.no("필라테스 30회 양도합니다", "가격 협의 가능")
        self.no("일정이 바빠서 힘드네요", "그냥 하소연")  # 양도 아님

    def test_spacing_and_html(self):
        self.no("회원권 양도", "명의 변 경 아니고 명의\n변경입니다")  # 공백 무시
        self.assertEqual(clean_text("<b>양도</b> &amp; 일정"), "양도 & 일정")


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.text = str(payload)

    def json(self):
        return self._p


class EndToEndTest(unittest.TestCase):
    def test_run_once_sends_only_matching_and_dedupes(self):
        items = [
            {"title": "<b>필라테스</b> 20회 <b>양도</b>", "description": "일정이 안 맞아서 양도합니다",
             "link": "https://cafe.naver.com/fitcafe/111", "cafename": "운동카페", "cafeurl": "https://cafe.naver.com/fitcafe"},
            {"title": "헬스 회원권 양도", "description": "명의변경 가능, 바빠서",
             "link": "https://cafe.naver.com/fitcafe/112", "cafename": "운동카페", "cafeurl": "https://cafe.naver.com/fitcafe"},
            {"title": "PT 양도", "description": "출장 때문에",
             "link": "https://cafe.naver.com/fitcafe/113?art=abc", "cafename": "운동카페", "cafeurl": "https://cafe.naver.com/fitcafe"},
        ]

        def fake_get(url, **kw):
            if "openapi.naver.com" in url:
                return FakeResp(200, {"items": items})
            if "CafeGateInfo" in url:
                return FakeResp(200, {"message": {"result": {"cafeInfoView": {"cafeId": 999}}}})
            if "articles/113" in url:  # 본문에 명의변경이 숨어있는 경우
                return FakeResp(200, {"result": {"article": {"contentHtml": "<p>출장 많아서 PT 양도, 명의 변경 필요</p>"}}})
            return FakeResp(403, {})

        cfg = {**CFG, "search": {**CFG["search"], "enabled": True, "queries": ["양도 일정"]}}
        client = NaverCafeClient("id", "secret")
        client.session.get = fake_get
        notifier = mock.Mock()
        store = SeenStore(":memory:")
        args = SimpleNamespace(dry_run=False, mark_seen=False)

        with mock.patch("time.sleep"):
            sent = main.run_once(cfg, args, None, client, CLF, store, notifier)
            self.assertEqual(sent, 1)
            self.assertIn("필라테스", notifier.send.call_args[0][0])
            self.assertEqual(main.run_once(cfg, args, None, client, CLF, store, notifier), 0)  # 중복 없음
        self.assertEqual(notifier.send.call_count, 1)

    def test_cookie_session_reads_member_boards(self):
        board = [
            {"articleId": 501, "subject": "필라테스 30회 양도", "writerNickname": "a", "menuName": "양도"},
            {"articleId": 502, "subject": "명의변경 양도", "writerNickname": "b"},   # 제목에서 바로 제외
            {"articleId": 503, "subject": "PT 넘겨드려요", "writerNickname": "c"},
            {"articleId": 504, "subject": "골프 레슨 양도", "writerNickname": "d"},
        ]
        bodies = {
            "501": "<p>회사 <b>스케줄</b>이 바뀌어서 다닐 시간이 없네요</p>",  # 멤버 공개 본문
            "503": "출장 때문에 넘겨드립니다. 명의 이전 필요합니다",
            "504": "가격 협의 가능",
        }
        calls = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append(url)
            if "CafeGateInfo" in url:
                return FakeResp(200, {"message": {"result": {"cafeInfoView": {"cafeId": 777, "cafeName": "운동카페"}}}})
            if "ArticleListV2dot1" in url:
                assert params["search.menuid"] == 15
                return FakeResp(200, {"message": {"result": {"articleList": board}}})
            if "/articles/" in url:
                aid = url.rsplit("/", 1)[1]
                return FakeResp(200, {"result": {"article": {"subject": "", "contentHtml": bodies[aid],
                                                             "writer": {"nick": "w"}}}})
            return FakeResp(404, {})

        sess = NaverCafeSession("NID_AUT=x; NID_SES=y", 0, 0)
        sess.s.get = fake_get
        cfg = {**CFG, "cafe": {**CFG["cafe"], "boards": [{"cafe": "fitcafe", "menu_ids": [15]}]}}
        notifier, store = mock.Mock(), SeenStore(":memory:")
        args = SimpleNamespace(dry_run=False, mark_seen=False)
        with mock.patch("time.sleep"):
            self.assertEqual(main.run_once(cfg, args, sess, None, CLF, store, notifier), 1)
        msg = notifier.send.call_args[0][0]
        self.assertIn("필라테스", msg)
        self.assertIn("https://cafe.naver.com/fitcafe/501", msg)
        self.assertFalse(any(u.endswith("/articles/502") for u in calls))  # 제목 제외글은 본문 안 엶
        self.assertTrue(store.has("777/503") and store.has("777/504"))

    def test_login_expired_alerts_once(self):
        sess = NaverCafeSession("NID_AUT=x; NID_SES=y", 0, 0)
        sess.s.get = lambda url, **kw: (
            FakeResp(200, {"message": {"result": {"cafeInfoView": {"cafeId": 1}}}}) if "CafeGateInfo" in url
            else FakeResp(401, {"message": "로그인이 필요합니다"}))
        cfg = {**CFG, "cafe": {**CFG["cafe"], "boards": [{"cafe": "fitcafe"}]}}
        notifier, store = mock.Mock(), SeenStore(":memory:")
        args = SimpleNamespace(dry_run=False, mark_seen=False)
        with mock.patch("time.sleep"):
            main.run_once(cfg, args, sess, None, CLF, store, notifier)
            main.run_once(cfg, args, sess, None, CLF, store, notifier)
        self.assertEqual(notifier.send.call_count, 1)
        self.assertIn("쿠키", notifier.send.call_args[0][0])

    def test_parse_cookie_string(self):
        self.assertEqual(parse_cookie_string(" NID_AUT=a=b; NID_SES=c ;"), {"NID_AUT": "a=b", "NID_SES": "c"})

    def test_article_key_normalizes_links(self):
        a = CafeArticle("t", "d", "http://cafe.naver.com/abc/5?x=1", "c", "https://cafe.naver.com/abc")
        b = CafeArticle("t", "d", "https://cafe.naver.com/abc/5", "c", "https://cafe.naver.com/abc")
        self.assertEqual(a.key, b.key)


if __name__ == "__main__":
    unittest.main()

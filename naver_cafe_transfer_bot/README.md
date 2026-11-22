# 네이버 카페 양도글 → 텔레그램 알림 봇

네이버 카페 글 가운데 **명의 변경이 아니라 일정 관리 부담이나 개인 사정(바빠서, 출장, 이사 등) 때문에 양도하는 글**만 골라서 내 텔레그램으로 보내 줍니다.

## 동작 방식

1. **수집**: 공식 [네이버 검색 API(카페글)](https://developers.naver.com/docs/serviceapi/search/cafearticle/cafearticle.md)로 `config.toml`에 적은 검색어를 검색합니다.
2. **1차 판별**: 검색 결과의 제목과 요약으로 판단합니다. 띄어쓰기 차이는 무시합니다.
   - ✅ 양도 표현이 있어야 합니다 (`양도`, `넘겨드립니다`, `양수자 구함` …).
   - ✅ 일정이나 사정 관련 표현이 있어야 합니다 (`일정`, `스케줄`, `바빠서`, `출장`, `이사`, `개인사정`, `다닐 시간이 없` …).
   - ❌ 아래 표현이 하나라도 있으면 제외합니다.
     - 명의 관련: `명의변경`, `명의이전`, `명의양도`, `명변` …
     - 구매 희망글: `양수합니다`, `구합니다`
     - 끝난 거래: `양도완료`, `[완료]`
3. **2차 판별 (선택)**: 후보 글은 본문 전체를 한 번 더 읽고 다시 판단합니다. 본문에만 '명의변경'이 적힌 글을 걸러내기 위해서입니다. 공개 카페에서만 되고, 실패하면 요약으로만 판단합니다.
4. **중복 방지**: 이미 확인한 글은 `seen_articles.db`(SQLite)에 기록합니다.
5. **전송**: 텔레그램 봇이 제목, 카페 이름, 요약, 판단 사유, 링크를 보냅니다.

## 설치

```bash
cd naver_cafe_transfer_bot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt                     # Python 3.11 이상
cp .env.example .env
cp config.example.toml config.toml
```

### 1) 네이버 API 키
[네이버 개발자센터](https://developers.naver.com/apps)에서 애플리케이션을 등록하고 사용 API로 **검색**을 고릅니다. 발급받은 Client ID와 Secret을 `.env`에 넣습니다. 하루 25,000회까지 무료입니다.

### 2) 텔레그램 봇
1. 텔레그램에서 `@BotFather`를 열고 `/newbot`으로 봇을 만든 뒤, 받은 토큰을 `.env`의 `TELEGRAM_BOT_TOKEN`에 넣습니다.
2. 만든 봇에게 아무 메시지나 하나 보냅니다.
3. `python main.py --find-chat-id`를 실행하고, 출력된 값을 `.env`의 `TELEGRAM_CHAT_ID`에 넣습니다.
4. `python main.py --test-telegram`을 실행해 "연결 성공" 메시지가 오는지 확인합니다.

## 실행

```bash
python main.py --dry-run     # 전송하지 않고 ✅/❌ 판별 결과만 출력합니다. 키워드를 다듬을 때 쓰세요.
python main.py --mark-seen   # 처음 한 번: 지금 있는 글을 '본 글'로 기록해 알림 폭탄을 막습니다.
python main.py               # 1회 실행 (cron이나 작업 스케줄러용)
python main.py --loop        # interval_seconds(기본 10분)마다 계속 실행
```

cron 예시 (10분마다):
```
*/10 * * * * cd /path/to/naver_cafe_transfer_bot && .venv/bin/python main.py >> bot.log 2>&1
```

## 정확도 높이기

`config.toml`에서 조정하면 됩니다.
- `queries`: 양도할 대상을 검색어에 넣으면 훨씬 정확해집니다. 예: `"필라테스 양도 일정"`, `"PT 양도 출장"`
- `cafe_ids`: 특정 카페만 보려면 카페 주소(`cafe.naver.com/여기`)의 아이디를 넣습니다.
- `reason_keywords`, `exclude_keywords`: `--dry-run` 결과를 보면서 키워드를 더하거나 뺍니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

## 참고 사항
- 검색 API는 글 전체가 아니라 요약만 돌려줍니다. 또 멤버 공개 글은 검색에 잡히지 않을 수 있습니다.
- 본문 읽기(`fetch_full_text`)는 카페 웹이 쓰는 비공식 API입니다. 네이버가 사양을 바꾸면 동작하지 않을 수 있습니다. 그래도 봇은 요약만으로 계속 동작합니다.
- 너무 짧은 주기로 돌리지 마세요. 네이버 이용약관과 각 카페의 규칙을 지켜 주세요.

# 네이버 카페 양도글 → 텔레그램 알림 봇

네이버 카페 글 가운데 **명의 변경이 아니라 일정 관리 부담이나 개인 사정(바빠서, 출장, 이사 등) 때문에 양도하는 글**만 골라서 내 텔레그램으로 보내 줍니다.

## 동작 방식

1. **수집**: **내 네이버 로그인 쿠키**로 `config.toml`에 적은 카페 게시판을 최신순으로 읽습니다. 브라우저에서 보는 것과 같은 내부 API를 쓰기 때문에, 가입한 카페라면 **멤버 공개 글과 본문 전체**도 읽을 수 있습니다. 요청 사이에는 1.5~4초씩 무작위로 쉽니다.
   - (선택) 공식 네이버 검색 API를 함께 켤 수도 있습니다: `[search] enabled = true`
2. **판별**: 제목과 본문 전체로 판단합니다. 띄어쓰기 차이는 무시합니다.
   - ✅ 양도 표현이 있어야 합니다 (`양도`, `넘겨드립니다`, `양수자 구함` …).
   - ✅ 일정이나 사정 관련 표현이 있어야 합니다 (`일정`, `스케줄`, `바빠서`, `출장`, `이사`, `개인사정`, `다닐 시간이 없` …).
   - ❌ 아래 표현이 하나라도 있으면 제외합니다.
     - 명의 관련: `명의변경`, `명의이전`, `명의양도`, `명변` …
     - 구매 희망글: `양수합니다`, `구합니다`
     - 끝난 거래: `양도완료`, `[완료]`
   - 제목에 이미 제외 키워드가 있는 글은 본문을 열지 않습니다 (요청 절약).
3. **쿠키 만료 감지**: 쿠키가 만료되면 텔레그램으로 "쿠키 갱신 필요" 알림을 보냅니다 (6시간에 한 번).
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

### 1) 로그인 쿠키 넣기
1. PC 크롬에서 네이버에 로그인합니다. 이때 **로그인 상태 유지**를 체크해야 쿠키가 오래 갑니다.
2. `cafe.naver.com`을 연 상태에서 `F12` → **Application** → **Cookies** → `https://cafe.naver.com`으로 들어갑니다.
3. `NID_AUT`와 `NID_SES` 값을 복사해서 `.env`에 이렇게 넣습니다.
   ```
   NAVER_COOKIE="NID_AUT=복사한값; NID_SES=복사한값"
   ```
4. ⚠️ 이 쿠키는 **비밀번호와 같습니다.** 다른 사람에게 보내거나 git에 올리지 마세요 (`.env`는 `.gitignore`에 들어 있습니다). 브라우저에서 **로그아웃하면 쿠키가 무효**가 되니, 봇용으로 따로 로그인해 두는 것을 권합니다.

### 2) 볼 카페와 게시판 정하기
`config.toml`의 `[cafe] boards`에 적습니다.
```toml
boards = [
  { cafe = "mycafe123", menu_ids = [15, 22], name = "우리동네" },
]
```
- `cafe`: 카페 주소 `cafe.naver.com/mycafe123`에서 `mycafe123` 부분입니다. 숫자 clubid를 넣어도 됩니다.
- `menu_ids`: 게시판을 클릭했을 때 주소에 나오는 `menuid=15` 또는 `/menus/15`의 숫자입니다. 비우면 전체글보기를 봅니다.

설정한 다음 `python main.py --probe`를 실행해, 게시판 목록과 첫 글 본문이 실제로 읽히는지 확인하세요.

### 3) 텔레그램 봇
1. 텔레그램에서 `@BotFather`를 열고 `/newbot`으로 봇을 만든 뒤, 받은 토큰을 `.env`의 `TELEGRAM_BOT_TOKEN`에 넣습니다.
2. 만든 봇에게 아무 메시지나 하나 보냅니다.
3. `python main.py --find-chat-id`를 실행하고, 출력된 값을 `.env`의 `TELEGRAM_CHAT_ID`에 넣습니다.
4. `python main.py --test-telegram`을 실행해 "연결 성공" 메시지가 오는지 확인합니다.

## 실행

```bash
python main.py --probe       # 쿠키와 카페 설정 점검 (목록, 본문이 읽히는지)
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
- `boards`: 양도·판매 게시판만 `menu_ids`로 지정하면 잡음이 크게 줄어듭니다.
- `reason_keywords`, `exclude_keywords`: `--dry-run` 결과를 보면서 키워드를 더하거나 뺍니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

## 참고 사항
- 카페 게시판과 본문은 cafe.naver.com 웹이 쓰는 **비공식 내부 API**로 읽습니다. 네이버가 응답 형식을 바꾸면 고쳐야 할 수 있습니다. 이상하면 `python main.py --probe -v`의 출력을 확인하세요.
- **볼 권한이 있는 글만 읽힙니다.** 미가입 카페나 등급 제한 게시판은 "접근 권한 없음"으로 건너뜁니다.
- 자동화로 계정을 쓰는 것은 네이버 이용약관에 어긋날 수 있고, 너무 자주 요청하면 계정에 보호 조치가 걸릴 수 있습니다. 주기는 10분 이상, 게시판 수는 적게 유지하세요. 카페 글을 외부로 퍼 나르지 말고 개인 알림용으로만 쓰세요.

# CCS-KU BFC: Relay

[English](README.md)

Relay는 고려대학교 수업 보안 실습인 CCS-KU Bug Finding Challenge에서 사용하는 장비 대여 서비스입니다. 장비 검색, 대여 서류, 반납 상태 기록, 사진 및 매뉴얼 미리보기 기능을 탐색합니다. 과제에서는 실행 중인 웹사이트와 제공된 소스를 분석하고, 발견한 문제를 실제로 검증해 보고서로 제출합니다.

## 로컬 실행

macOS와 Windows에서는 Docker Desktop을 설치합니다. Ubuntu 22.04와 26.04에서는 Docker Engine과 Compose 플러그인을 설치합니다. Docker를 실행한 뒤 저장소 최상위에서 로컬 실습용 비밀값을 생성하고 다음 명령을 실행합니다.

```bash
python3 scripts/init_practice.py
docker compose up --build
```

Windows에서 `python3` 명령을 사용할 수 없다면 `py -3 scripts/init_practice.py`를 실행합니다. 이 스크립트는 `.env`가 없을 때만 임의 값을 생성합니다. `.env.example`에는 사용할 수 있는 비밀값이 들어 있지 않습니다. 실제 팀별 채점 환경은 별도의 팀 전용 환경 파일을 사용합니다.

[http://localhost:3000](http://localhost:3000)을 엽니다. 로컬 실습에는 로그인이 필요하지 않습니다. 이미지·문서 워커의 첫 빌드에는 시간이 걸릴 수 있습니다. 종료하려면 `docker compose down`을 실행합니다.

**Reset practice environment**는 저장된 목록, 픽업 묶음, 반납 기록, 승인 기록과 미리보기 작업을 지웁니다. Docker 전체 재설치는 아닙니다.

## 주요 기능

- **Gear inventory:** 장비 검색, 필터 저장, 픽업 목록 내보내기와 픽업 묶음 준비
- **Loan documents:** 대여·관리 문서 열기
- **Condition reports:** 반납 상태 기록과 직원 검토 요청
- **Item photos:** 장비 이미지 미리보기 생성
- **Manual viewer:** 장비 매뉴얼 및 대여 문서 렌더링

강의에서 제공하는 소스 ZIP을 IoTcube에 넣어 SBOM을 생성하고, 결과를 소스와 Docker 빌드 파일과 비교합니다. 컴포넌트와 버전이 일치한다는 사실만으로 취약점이 실제로 재현된다고 판단하지 않습니다.

보고서 작성 및 제출 안내는 별도로 공지합니다.

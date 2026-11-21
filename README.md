# 캠퍼스 찾음

FastAPI와 SQLite로 분실·습득 신고를 저장하고, Gemini로 사진의 특징과 검색 키워드를 추출합니다.
팀원이 제작한 HTML의 디자인을 유지해 홈·검색·신고·내 정보·상세 화면을 실제 API에 연결했습니다.
별도의 Node.js 설치나 프런트엔드 개발 서버 없이 FastAPI 한 개로 실행합니다.

상시 배포를 위한 Docker·영구 저장·운영 환경변수·백업·복구·검증 방법은
[배포 준비 가이드](docs/DEPLOYMENT.md)에 정리했습니다. 배포 서비스는 아직 확정하지 않았으며,
현재 단계는 공통 설정을 준비한 상태입니다.

## 웹사이트 사용

서버 실행 후 **<http://127.0.0.1:8000/>**에서 엽니다. 받은 원본 HTML 파일을 직접 열면
이전 로컬 저장 데모가 열리므로, 위 서버 주소를 사용하세요.

1. 홈에서 실제 DB 목록을 조회하고 이름·키워드·장소로 검색합니다. 건물과 신고 유형을 함께 필터링할 수 있습니다.
2. 발견/분실 신고에서 사진을 선택하고 **AI로 특징 채우기**를 누르면 분석 결과를 입력란에 채웁니다.
3. 내용을 확인·수정하고 날짜·장소·작성자·연락처를 입력해 저장합니다. 사진이나 AI 분석 없이 수동 등록도 가능합니다.
4. **내 정보**에서는 같은 브라우저에서 등록한 물품을 확인합니다. 카드를 열면 **신고 수정**으로 내용을 변경하거나 자신의 신고를 삭제할 수 있습니다.
5. 물건을 찾거나 돌려주면 **해결 완료로 표시**를 누릅니다. 잘못 처리했으면 **진행 중으로 되돌리기**로 복구합니다.
   홈과 내 정보의 **처리 상태** 필터에서 전체·진행 중·해결 완료를 선택할 수 있습니다.

수정 화면은 기존 사진·날짜·연락처·키워드를 불러옵니다. 저장할 때 기존 좌표와 처리 상태를 유지하고,
새 사진을 선택하면 교체하며 **사진 삭제**를 누르면 신고에서 사진 연결을 제거합니다.
**수정 취소**를 누르면 저장하지 않고 상세 화면으로 돌아옵니다. 이전 신고에 날짜·연락처가 없었다면
임의의 값으로 채우지 않습니다. 상태 변경은 별도 API로 상태만 수정하므로 다른 신고 내용을 덮어쓰지 않습니다.

React 18.3.1 파일과 라이선스는 `static/vendor/`에 포함되어 화면을 열 때 외부 CDN을 사용하지 않습니다.
AI 분석에는 인터넷과 Gemini 키가 필요합니다. AI 오류가 발생해도 수동 등록은 가능합니다.
원본 HTML의 예시 물품과 `campus-find-v1` 로컬 저장 데이터는 자동으로 DB에 옮기지 않습니다.

## 팀원에게 임시로 공유

실제 `database.db`와 분리한 시연용 서버를 실행할 수 있습니다. 예시 신고 3개로 시작하고,
팀원도 신고·검색·사진 분석을 시험할 수 있습니다. 데이터와 비밀번호는 서버를 종료하면 초기화됩니다.

```powershell
.\.venv313\Scripts\python.exe -m scripts.share_preview
```

서버는 `http://127.0.0.1:8002`에서 실행되고, 접속 사용자 이름 `campus`와 임의 비밀번호를
터미널에 표시합니다. 비밀번호는 소스나 설정 파일에 저장하지 않습니다.

별도 터미널에서 [Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)로
해당 서버를 공유하면 임시 HTTPS 주소를 받을 수 있습니다. Cloudflare 공식 `cloudflared` 도구를 설치했거나
이 프로젝트의 `.tools/cloudflared.exe`로 내려받은 경우 다음 명령을 사용합니다.

```powershell
.\.tools\cloudflared.exe tunnel --url http://127.0.0.1:8002 --no-autoupdate
```

출력되는 `https://....trycloudflare.com` 주소와 사용자 이름·시연 비밀번호를 팀원에게 전달합니다.
이 접속 비밀번호는 Gemini API 키와 별개입니다. 실제 API 키는 `.env`에서 서버만 읽습니다.
공유 중에는 PC와 두 프로세스가 실행 중이어야 합니다. 종료하려면 두 터미널에서 각각 `Ctrl+C`를 누릅니다.
재실행하면 공유 주소와 비밀번호가 달라질 수 있습니다. `.tools/`는 Git에서 제외됩니다.

## 구현한 필수 백엔드 기능

- JPG·PNG·WEBP 업로드와 정적 이미지 URL 제공
- Gemini 이미지 분석: 제목, 종류, 색상, 재질, 설명, 한국어 검색 키워드 추출
- 사진 분석과 신고 저장을 한 요청으로 처리하는 multipart API
- 분석 결과를 사용자가 수정한 뒤 JSON으로 저장하는 두 단계 API
- 장소, 작성자, 연락처, 위도·경도, 분실/습득 구분, 처리 상태 저장
- 최신순 목록, 한글 키워드 검색, 장소·종류·색상·신고 유형·상태 필터, 페이지 조회
- 기존 SQLite 데이터를 보존하면서 `contact` 열 자동 추가
- 발견·분실 날짜 저장, 브라우저별 내 등록 조회, 본인 등록 삭제
- 내 신고 수정 화면, 해결 완료·진행 중 전환, 홈·내 정보의 처리 상태 필터

지도에서 건물을 판별하는 기능과 실제 클라우드 배포는 별도 작업입니다. 좌표 저장·조회 API와
Docker 기반 상시 배포 설정은 준비되어 있습니다.
현재는 계정 로그인 대신 브라우저에 생성한 임의 식별 토큰으로 내 등록을 구분합니다.
토큰은 `X-Owner-Token` 헤더로 전송하며 서버에는 SHA-256 해시만 저장하고 응답에서는 제외합니다.
같은 표시 이름을 입력해도 다른 브라우저의 신고를 수정·삭제할 수 없습니다. 브라우저 저장 정보를 지우거나
다른 브라우저·주소로 접속하면 이전 내 등록 관리 권한을 복구할 수 없으며, 표시 이름은 로그인 신원이 아닙니다.
이전 토큰 없는 신고는 전체 목록에서 보존되지만 내 등록으로 자동 귀속되지 않습니다.
운영 모드에서는 토큰 없는 새 등록과 이전 소유 정보 없는 신고의 수정을 거부합니다.
연락처는 목록·상세 응답에 포함됩니다. 현재 버전은 로컬 개발과 기능 확인용입니다.

## 실행 방법

Python 3.11 이상을 사용합니다. 이 프로젝트에서 검증한 환경은 Python 3.13입니다.

Windows PowerShell에서 새 환경을 만드는 경우:

```powershell
py -3.13 -m venv .venv313
.\.venv313\Scripts\python.exe -m pip install -r requirements.txt
```

이미 `.venv313`이 있으면 생성 단계를 건너뜁니다. 가상환경을 활성화하지 않아도 위처럼
Python 실행 경로를 직접 지정할 수 있습니다.

`.env`가 없다면 `.env.example`을 복사하고 키를 입력합니다. 기존 `.env`는 덮어쓰지 마세요.

```powershell
Copy-Item .env.example .env
```

```dotenv
GEMINI_API_KEY=발급받은_API_키
GEMINI_MODEL=gemini-3.5-flash-lite
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

키는 [Google AI Studio](https://aistudio.google.com/apikey)에서 발급합니다.
모델은 계정에서 사용할 수 있는 이미지 입력·구조화 출력 지원 모델로 변경할 수 있습니다.
기본값은 간단한 물품 특징 추출에 맞춘 [Gemini 3.5 Flash-Lite](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite)입니다.
이미지 분석은 [Google Gen AI SDK](https://googleapis.github.io/python-genai/)의 이미지 입력과
JSON 구조화 출력을 사용합니다. `.env`와 업로드 파일, 로컬 DB는 Git에서 제외됩니다.

```powershell
.\.venv313\Scripts\python.exe -m uvicorn main:app --reload
```

- API 문서와 요청 테스트: <http://127.0.0.1:8000/docs>
- 웹사이트 홈: <http://127.0.0.1:8000/>
- 상태 확인: <http://127.0.0.1:8000/api/health>
- OpenAPI 명세: <http://127.0.0.1:8000/openapi.json>

실행 시 기본 DB는 프로젝트의 `database.db`, 사진은 `static/uploads/`에 저장됩니다.
`DATABASE_URL`로 다른 SQLite 파일 경로를 지정할 수 있습니다. 기존 테이블이 있으면
행을 삭제하지 않고 `contact`, `event_date`, `owner_token_hash` 열을 추가합니다.
이전 신고의 연락처와 발견·분실 날짜는 `null`이며, 화면에서는 날짜가 없는 신고에 등록일을 표시합니다.
키가 없어도 서버와 수동 등록·검색·사진 업로드는 작동하며 AI 분석 요청만 503을 반환합니다.
이는 기본 개발 모드의 동작입니다. 운영 모드는 필수 키·접속 비밀번호·영구 저장 경로·허용 호스트가
누락되면 시작하지 않으며, API 문서도 기본적으로 비활성화됩니다.

## API

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/api/health` | 서버 실행 확인 |
| POST | `/api/images` | 사진만 업로드 |
| POST | `/api/images/analyze` | 사진 분석 후 이미지 경로와 특징 반환 |
| POST | `/api/items/report` | 사진 분석과 신고 등록을 한 번에 처리 |
| POST | `/api/items` | JSON으로 신고 등록 |
| GET | `/api/items` | 목록·검색·필터·페이지 조회 |
| GET | `/api/items/{id}` | 신고 상세 조회 |
| PUT | `/api/items/{id}` | 신고 전체 수정 |
| PATCH | `/api/items/{id}/status` | 본인 신고의 처리 상태만 수정 |
| DELETE | `/api/items/{id}` | 같은 브라우저에서 등록한 신고 삭제 |

### 사진과 신고를 한 번에 등록

`POST /api/items/report`에 `multipart/form-data`로 보냅니다.

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `file` | 예 | 최대 5MiB, 최대 2천만 화소의 JPG·PNG·WEBP |
| `location` | 예 | 발견/분실 장소, 최대 200자 |
| `contact` | 예 | 연락 가능한 이메일·전화번호 등, 최대 200자 |
| `author` | 예 | 작성자 표시 이름, 최대 50자 |
| `report_type` | 아니오 | `found`(기본) 또는 `lost` |
| `latitude`, `longitude` | 아니오 | 좌표는 둘을 함께 입력 |
| `event_date` | 아니오 | 발견·분실 날짜 (`YYYY-MM-DD`) |
| `title`, `category`, `description` | 아니오 | 입력하면 해당 AI 제안보다 우선 적용 |

PowerShell에서는 `curl.exe`를 사용합니다.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/items/report `
  -F "file=@C:/photos/wallet.jpg" `
  -F "location=중앙도서관 1층" `
  -F "contact=test@example.com" `
  -F "author=테스트 사용자" `
  -F "report_type=found"
```

성공 시 201과 저장된 신고를 반환합니다. AI 분석 실패 시 신고와 사진을 저장하지 않으며,
분석 후 DB 저장이 실패하면 새로 저장한 사진을 삭제합니다. 네트워크 호출과 파일 처리는
동기 라우트의 작업 스레드에서 실행하며 Gemini 호출 제한 시간은 60초입니다.

### 분석 결과 확인 후 등록

1. `POST /api/images/analyze`에 `file`을 보내면 `image_path`, `title`, `category`,
   `color`, `material`, `description`, `keywords`를 반환합니다. 이 단계는 신고를 저장하지 않습니다.
2. 프런트엔드에서 결과를 보여 주고 수정합니다.
3. 장소·연락처·작성자와 함께 `POST /api/items`로 JSON을 보냅니다.

```json
{
  "title": "검정 지갑",
  "category": "지갑",
  "color": "검정",
  "material": "가죽",
  "description": "도서관 1층에서 발견",
  "keywords": ["지갑", "검정", "가죽"],
  "location": "중앙도서관 1층",
  "author": "테스트 사용자",
  "contact": "test@example.com",
  "report_type": "found",
  "status": "open"
}
```

사진이 있다면 업로드 API가 반환한 `image_path`를 그대로 추가합니다. 임의의 외부 URL이나
존재하지 않는 이미지 경로는 거부합니다. 사진 없이 수동 등록도 가능합니다.
기존 JSON 요청과의 호환성을 위해 `contact`는 JSON API에서 생략 가능하며,
새 multipart 신고에서는 필수입니다. `PUT`은 전체 수정이므로 모든 필수 필드를 다시 보냅니다.
웹사이트는 등록·조회·수정·삭제 요청에 같은 `X-Owner-Token`을 보냅니다.
토큰이 있는 신고의 수정·삭제는 일치하는 토큰이 있어야 하며, `GET /api/items?mine=true`로 내 등록을 조회합니다.
신고 삭제 시 공유 중일 수 있는 원본 업로드 이미지는 유지합니다.

처리 상태만 바꾸려면 `PATCH /api/items/{id}/status`에 `{"status":"resolved"}`를 보냅니다.
다시 진행 중으로 돌릴 때는 `{"status":"open"}`을 보냅니다. 상태 API는 일치하는 `X-Owner-Token`이
필수이며, 다른 필드를 함께 보내면 422를 반환합니다. 일반 수정 화면의 `PUT` 요청은 기존 처리 상태와
사진·좌표를 포함한 전체 정보를 전송합니다.

브라우저에서는 `FormData` 전송 시 `Content-Type`을 직접 지정하지 않습니다.

```javascript
const form = new FormData();
form.append("file", fileInput.files[0]);
form.append("location", "중앙도서관 1층");
form.append("contact", "test@example.com");
form.append("author", "테스트 사용자");
const response = await fetch("http://127.0.0.1:8000/api/items/report", {
  method: "POST",
  body: form,
});
const result = await response.json();
if (!response.ok) throw new Error(JSON.stringify(result.detail));
```

### 검색과 필터

```text
GET /api/items?keyword=가죽&location=도서관&report_type=found&status=open&offset=0&limit=20
```

- `keyword`: 제목·종류·색상·재질·설명·장소·AI 키워드에서 부분 검색
- `location`: 장소 부분 검색
- `category`, `color`: 정확히 일치하는 값으로 필터
- `report_type`: `lost` / `found`
- `status`: `open` / `resolved`
- `mine=true`: 같은 `X-Owner-Token`으로 등록한 신고만 조회
- `offset`: 0부터 시작, `limit`: 기본 20, 최대 100

필터를 함께 지정하면 모두 만족하는 신고만 반환합니다. 결과는 생성 시각과 ID의 내림차순이며,
응답은 JSON 배열입니다. 다음 페이지는 `offset`을 늘려 조회합니다.

### 오류 응답

| 상태 | 의미 |
| --- | --- |
| 400 | 빈 파일 |
| 401 | 내 등록 조회에 브라우저 식별 정보 누락 |
| 403 | 다른 브라우저의 등록 수정·삭제 시도 |
| 404 | 없는 신고 |
| 413 | 이미지 용량·해상도 초과 |
| 415 | 지원하지 않는 형식 또는 손상된 이미지 |
| 422 | 필수 값·좌표·필터·이미지 경로 검증 실패 |
| 502 | Gemini 연결·요청 실패 또는 분석 결과 형식 오류 |
| 503 | Gemini 키 미설정·무효, 모델 사용 불가, 요청 한도 초과 또는 서비스 혼잡 |
| 504 | Gemini 응답 시간 초과 |

## 테스트

```powershell
.\.venv313\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv313\Scripts\python.exe -m pytest -q
```

테스트는 임시 SQLite 파일과 임시 업로드 폴더를 사용합니다. 실제 Gemini 호출은 대체하므로
키·네트워크·API 사용 비용 없이 실행되며 프로젝트의 기존 DB와 사진은 변경하지 않습니다.
신고 저장·조회·수정, 한글 검색, 복합 필터·페이지 조회, 이미지 형식·크기 검증,
AI 오류·응답 검증, 실패 시 파일 정리, 기존 SQLite 스키마 변경을 확인합니다.
홈 및 로컬 정적 파일, 발견·분실 날짜, 브라우저별 소유 구분과 수정·삭제 권한도 검증합니다.
상태 변경·되돌리기, 상태 변경 시 내용 보존, 다른 브라우저의 상태 변경 차단, 복합 상태 필터도 검증합니다.

Node.js가 설치된 환경에서는 수정 요청 생성 로직을 추가로 검사할 수 있습니다.
이 검사는 사진·좌표·상태 보존, 기존 장소 유지, 누락된 날짜·연락처 보존 등을 확인하며 서버나 API 키를 사용하지 않습니다.

```powershell
node --test tests/test_ui_logic.cjs
```

실제 DB와 분리한 브라우저 검증용 화면을 띄우려면 다음 명령을 사용합니다.
임시 DB에 예시 물품 21개를 만들며 서버 종료 후 임시 폴더를 정리합니다. 주소는 <http://127.0.0.1:8001/>입니다.

```powershell
.\.venv313\Scripts\python.exe -m scripts.preview_qa
```

실제 키와 모델 연결은 아래 명령으로 확인합니다. 기본값은 합성 테스트 이미지 한 장이며,
실제 Gemini 요청 한 번이 발생하므로 계정의 API 한도와 요금이 적용됩니다.
DB나 업로드 폴더에는 저장하지 않습니다.

```powershell
.\.venv313\Scripts\python.exe -m scripts.smoke_gemini
# 실제 사진으로 확인할 때
.\.venv313\Scripts\python.exe -m scripts.smoke_gemini C:/photos/wallet.jpg
```

## 파일 구성

```text
main.py                 FastAPI 앱, CORS, 정적 파일, 시작 처리
config.py               .env와 환경변수 설정
database.py             DB 연결·세션·기존 SQLite 스키마 변경
models.py               SQLAlchemy Item 모델
schemas.py              요청·응답·AI 결과 검증
routers/items.py        신고·목록·검색·수정 API
routers/ai_vision.py    이미지 업로드·분석 API
services/gemini.py      Gemini 이미지 분석 호출
services/images.py      이미지 검증·저장
services/ownership.py   브라우저 식별 토큰 검증
services/access.py      공용 접속 비밀번호 보호
templates/index.html    실제 웹사이트 시작 페이지
static/css/             팀원 디자인 및 연결 화면 스타일
static/js/app.js        화면과 API 연결
static/vendor/          React 18.3.1 및 MIT 라이선스
tests/                  외부 API 호출 없는 통합·단위 테스트
Dockerfile              운영용 컨테이너 이미지
compose.yaml            영구 볼륨을 사용하는 로컬/서버 실행
docs/DEPLOYMENT.md       클라우드 선택 전 공통 배포 준비 안내
```

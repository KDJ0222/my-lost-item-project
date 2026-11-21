# 캠퍼스 찾음 상시 배포 준비

배포 서비스가 정해지기 전까지 공통으로 사용할 실행·저장·검증 구성을 준비했습니다.
현재 구조는 **FastAPI 프로세스 1개 + SQLite + 영구 디스크의 업로드 폴더**입니다.
프런트엔드도 같은 서버가 제공하므로 별도의 Node.js 서버나 프런트엔드 호스팅이 필요하지 않습니다.
이 문서를 준비하는 과정에서는 클라우드 서비스·유료 리소스를 생성하지 않습니다.

## 준비된 파일

| 파일 | 역할 |
| --- | --- |
| `Dockerfile`, `.dockerignore` | Python 3.13 운영 이미지, 소스만 포함하고 비밀·실제 데이터 제외 |
| `compose.yaml` | 컨테이너와 영구 데이터 볼륨 실행 |
| `.env.production.example` | 운영 환경변수 예시 |
| `requirements-production.txt` | 검증한 주요 운영 라이브러리 버전 고정 |
| `scripts/start_server.py` | 클라우드의 `PORT`에 맞춰 단일 프로세스로 실행 |
| `scripts/data_backup.py` | SQLite 온라인 백업과 사진 보관, 새 폴더로 복구 |
| `scripts/smoke_deployment.py` | 신고·사진 저장 후 재시작 검증 |
| `scripts/verify_runtime.py` | 임시 데이터로 운영 서버 실행·재시작·백업·복구 검증 |
| `.github/workflows/deployment-check.yml` | GitHub에서 테스트와 Linux Docker 빌드·재시작 검사 |

기존 팀 저장소에 옮길 때는 위 추가 파일과 함께 변경한 `config.py`, `database.py`, `main.py`,
`routers/items.py`, `services/access.py`, `scripts/share_preview.py`, `.gitignore`, `.env.example`,
`README.md`, 관련 테스트도 같은 폴더 구조로 반영합니다. `.env.production` 실제 파일과
`.venv-deploy/`, 데이터·백업·`.tools/`는 옮기거나 GitHub에 올리지 않습니다.

운영 의존성 파일은 직접 사용하는 패키지 버전을 고정합니다. 간접 의존성 전체를 잠그는 lockfile은 아닙니다.
현재 PC의 Docker 설치 여부와 실제 빌드 결과는 별도로 확인해야 합니다. YAML 구문 검사나 Python 실행 검증만으로
Docker 이미지가 빌드되었다고 판단하지 않습니다. GitHub에 올린 후 `Deployment readiness` 실행 결과를 확인하세요.

## 팀에서 결정할 항목

- 사용할 서비스·계정과 예산
- 고정 HTTPS 주소 또는 도메인
- 재배포 후에도 유지되는 디스크의 마운트 경로·용량
- 공용 접속 사용자 이름·비밀번호와 Gemini 키를 관리할 담당자

SQLite를 사용하는 현재 배포는 **서비스 인스턴스 1개, 워커 1개**로 운영합니다.
여러 서버로 확장하려면 DB와 사진 저장 방식을 먼저 변경해야 합니다. 현재 SQL 검색은 SQLite용이므로
PostgreSQL 주소만 넣어서 전환할 수는 없습니다.

## 운영 환경변수

클라우드에서는 대시보드의 비밀 환경변수에 값을 입력합니다. `.env`를 저장소나 이미지에 넣지 않습니다.
운영 모드는 로컬 `.env` 파일을 자동으로 읽지 않습니다.

| 변수 | 설정 |
| --- | --- |
| `APP_ENV` | `production` |
| `DATA_DIR` | 영구 디스크의 절대 경로, Docker 기본 `/data` |
| `GEMINI_API_KEY` | 실제 키, 서버의 비밀 환경변수로 입력 |
| `GEMINI_MODEL` | 기본 `gemini-3.5-flash-lite` |
| `APP_ACCESS_USERNAME` | 기본 `campus` |
| `APP_ACCESS_PASSWORD` | 직접 정한 임의 비밀번호, 16자 이상. 예시 문구는 사용할 수 없음 |
| `ALLOWED_HOSTS` | 실제 호스트 이름. 예: `campus.example.com`. `https://`나 경로는 넣지 않음 |
| `PORT` | 플랫폼이 제공하는 포트. Docker Compose는 `8000` 사용 |
| `FORWARDED_ALLOW_IPS` | 신뢰하는 HTTPS 프록시의 IP. 기본 `127.0.0.1` |
| `CORS_ORIGINS` | 같은 서버에서 화면을 제공하므로 기본 빈 값 |
| `ENABLE_API_DOCS` | 운영 기본 `false`. 필요 시 일시적으로 `true` |

`DATA_DIR`을 지정하면 기본 DB는 `DATA_DIR/database.db`, 사진은 `DATA_DIR/uploads/`에 저장됩니다.
`DATABASE_URL`, `UPLOAD_DIR`로 바꿀 수 있으나 운영 모드에서는 둘 다 `DATA_DIR` 안에 있어야 합니다.
이 디렉터리를 영구 디스크에 연결하는 일은 배포 서비스 설정에서 해야 합니다. 환경변수만으로 디스크가 생기지는 않습니다.

호스트를 지정하면 내부 상태 검사에 필요한 `localhost`, `127.0.0.1`, `[::1]`도 허용합니다.
Render를 선택한 경우 `ALLOWED_HOSTS`를 생략하면 플랫폼의 `RENDER_EXTERNAL_HOSTNAME`을 사용합니다.
다른 플랫폼에서는 실제 호스트를 직접 설정합니다.

접속 비밀번호는 정식 회원 계정 기능을 만들기 전 팀원용 배포를 보호하기 위한 공용 비밀번호입니다.
등록자 구분은 별도의 브라우저 토큰으로 유지합니다. 운영에서는 토큰 없는 등록과 기존 소유 정보 없는 신고의 수정을 거부합니다.
다른 주소나 브라우저에서는 기존 ‘내 등록’ 권한이 자동으로 이전되지 않습니다.

설정 검사는 필수 값·저장 경로를 확인합니다. Gemini 키의 실제 유효성이나 디스크가 영구 저장소인지까지 자동으로 보증하지는 않습니다.

## Docker로 로컬 실행

Docker Engine과 Compose가 설치되어 있어야 합니다. 아래 명령은 프로젝트 루트에서 실행합니다.

1. `.env.production.example`을 `.env.production`으로 복사합니다. 기존 파일이 있으면 덮어쓰지 않습니다.

```powershell
if (-not (Test-Path .env.production)) { Copy-Item .env.production.example .env.production }
```

2. `.env.production`의 Gemini 키와 접속 비밀번호를 실제 값으로 변경합니다.
   로컬 확인에는 `ALLOWED_HOSTS=localhost,127.0.0.1`을 사용합니다.
   새 비밀번호는 다음처럼 생성할 수 있습니다.

```powershell
.\.venv313\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(24))"
```

3. 설정을 검사하고 이미지를 빌드한 뒤 실행합니다. `config --quiet`는 비밀번호 값을 화면에 출력하지 않습니다.

```powershell
docker compose config --quiet
docker compose build
docker compose run --rm web python -m scripts.start_server --check
docker compose up -d
docker compose ps
```

4. <http://127.0.0.1:8000/>에서 공용 사용자 이름·비밀번호로 접속합니다.
   상태 검사는 로그인 없이 <http://127.0.0.1:8000/api/health>에서 `{"status":"ok"}`를 반환합니다.
   DB 연결 또는 업로드 폴더가 준비되지 않으면 503을 반환합니다.

로그·종료·업데이트 명령:

```powershell
docker compose logs --tail 100 web
docker compose down
docker compose up -d --build
```

기본 `down`은 데이터 볼륨을 남깁니다. `down -v`는 볼륨까지 삭제하므로 데이터 보존이 필요할 때 사용하지 않습니다.
현재 Compose 포트는 로컬 PC에서만 접속하도록 묶여 있습니다. 외부 접속은 클라우드의 HTTPS 주소나 서버의 HTTPS 프록시로 제공합니다.

컨테이너는 UID 10001의 일반 사용자로 실행합니다. Docker named volume은 초기 이미지의 `/data` 권한을 사용합니다.
직접 만든 호스트 폴더나 클라우드 디스크를 연결하는 경우 해당 사용자에게 쓰기 권한이 있는지 확인해야 합니다.

## 클라우드 서비스 선택 후 적용

Docker를 지원하는 서비스라면 다음 값을 옮겨 설정합니다.

1. GitHub의 최신 소스에서 `Dockerfile`로 빌드합니다. 이 준비 단계에서 저장소에 자동 Push하지는 않습니다.
2. 디스크를 `/data`에 연결하고 `DATA_DIR=/data`로 지정합니다. 이미지의 `/app`에 실제 데이터를 저장하지 않습니다.
3. 환경변수 표의 비밀 값·호스트·프록시를 설정합니다. Docker 시작 명령은 기본 `CMD`를 사용합니다.
4. 상태 검사 경로를 `/api/health`로 지정하고 서비스 인스턴스 수는 1로 유지합니다.
5. HTTPS 주소로 접속한 뒤 신고와 사진을 등록하고 서버를 재시작해 유지되는지 확인합니다.

플랫폼이 포트를 지정하면 `scripts.start_server`가 `PORT`를 읽습니다.
HTTPS 프록시 뒤에서는 올바른 전달 헤더 설정이 필요합니다. 모든 요청이 신뢰하는 플랫폼 프록시에서만 들어오는 환경에서만
`FORWARDED_ALLOW_IPS=*`를 사용할 수 있습니다. 직접 인터넷에 노출한 서버에는 이 값을 사용하지 않습니다.
이 동작은 [FastAPI의 프록시 안내](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)를 따릅니다.

### Render를 선택하는 경우의 참고 예시

확정된 배포 대상은 아닙니다. Render의 [영구 디스크](https://render.com/docs/disks)는 유료 서비스에 연결하며,
디스크가 없는 기본 파일시스템의 변경은 재시작·재배포 시 유지되지 않습니다.
[무료 웹 서비스](https://render.com/docs/free)는 유휴 시 중지되고 영구 디스크를 지원하지 않으므로
현재 SQLite·사진 파일 구성의 상시 저장 용도로 선택하면 안 됩니다.

Python 네이티브 서비스로 배포한다면 다음 설정을 참고합니다.

| 항목 | 값 |
| --- | --- |
| Runtime | Python 3.13 |
| Build command | `pip install -r requirements-production.txt` |
| Start command | `python -m scripts.start_server` |
| Health check | `/api/health` |
| Persistent disk mount | `/var/data` |
| `DATA_DIR` | `/var/data` |
| `FORWARDED_ALLOW_IPS` | 플랫폼 프록시만 받는 Render 네이티브 서비스에서는 `*` |

나머지 비밀 환경변수도 위 표대로 설정합니다. DB 초기화는 영구 디스크가 연결된 서버 시작 시 수행하므로
디스크가 없는 빌드 단계에 DB 파일을 만들거나 복사하지 않습니다.
Render 디스크는 단일 서비스 인스턴스에서 사용하며, 디스크를 사용하는 재배포에는 잠깐 중단이 발생할 수 있습니다.
실제 플랜·비용은 계정에서 서비스 생성 전에 팀이 확인합니다.

## 백업과 복구

백업은 SQLite의 온라인 백업 API로 일관된 DB 사본을 만들고, 그 사본이 참조하는 사진과 체크섬 목록을 ZIP에 넣습니다.
키·`.env`·가상환경은 포함하지 않습니다. 백업에는 신고 내용·연락처·소유권 해시가 있으므로 GitHub에 올리지 않고 별도 보관합니다.
DB가 참조하는 사진이 없으면 불완전한 백업을 만들지 않고 오류를 반환합니다.
다른 디스크나 별도 보관소에도 백업 사본을 남겨야 원래 디스크를 잃었을 때 복구할 수 있습니다.

로컬 데이터를 백업할 때:

```powershell
.\.venv313\Scripts\python.exe -m scripts.data_backup backup --output backups/local-first.zip
```

Docker의 영구 디스크를 백업하고 PC로 복사할 때:

```powershell
docker compose exec web python -m scripts.data_backup backup --output /data/backups/campus-first.zip
New-Item -ItemType Directory -Path backups -Force
docker compose cp web:/data/backups/campus-first.zip ./backups/campus-first.zip
```

백업 파일은 덮어쓰지 않으므로 다음 백업은 다른 이름을 지정합니다.
복구는 실행 중인 데이터에 덮어쓰지 않고 **아직 존재하지 않는 새 폴더**에만 수행합니다.

```powershell
.\.venv313\Scripts\python.exe -m scripts.data_backup restore backups/local-first.zip --target data-restored
```

체크섬과 DB 무결성 검사가 통과하면 새 폴더에 `database.db`와 `uploads/`가 생깁니다.
운영 전환 시 서버를 중지하고 이 데이터가 있는 디스크·폴더를 연결한 후 `DATA_DIR`을 맞춰 다시 시작합니다.
기존 폴더를 자동 삭제하거나 덮어쓰지 않습니다. 복구 도구는 현재 소규모 프로젝트 기준으로 총 2 GiB 이하의 백업을 지원합니다.

로컬·임시 공유 주소에서 만든 브라우저 소유 토큰은 새 클라우드 주소로 자동 이전되지 않습니다.
복구한 신고는 조회되지만, 내 등록 관리 권한을 여러 기기에서 복구하려면 추후 계정 기능이 필요합니다.

## 배포 전 검증

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
node --test tests/test_ui_logic.cjs
.\.venv313\Scripts\python.exe -m scripts.verify_runtime
```

마지막 명령은 별도 임시 DB·사진과 임의 접속 비밀번호를 사용합니다.
운영 모드로 켠 서버에 신고와 사진을 저장하고, 재시작 후 유지 여부를 검사한 뒤 백업을 새 폴더에 복구해 다시 확인합니다.
프로젝트의 실제 DB와 Gemini 호출은 사용하지 않습니다. 이 검사가 Docker 빌드 검증을 대신하지는 않습니다.

GitHub Actions는 Ubuntu에서 Python·JavaScript 테스트를 실행한 뒤 Docker 이미지를 빌드하고,
실제 named volume을 붙인 컨테이너를 재시작해 데이터 유지 여부를 검사합니다.
이 워크플로는 검사만 수행하며 클라우드 계정에 배포하거나 이미지를 레지스트리에 Push하지 않습니다.

배포 후 실제 키를 확인하려면 Docker에서 아래 명령을 선택적으로 실행할 수 있습니다.
합성 이미지 1장에 대한 실제 Gemini 요청이 발생합니다.

```powershell
docker compose exec web python -m scripts.smoke_gemini
```

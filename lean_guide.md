# LEAN 사용 가이드

QuantConnect LEAN 엔진을 이 저장소에서 쓰는 방법을 처음부터 정리한 문서입니다.
명령과 출력은 2026-08-07 WSL2(Ubuntu 24.04) 환경에서 실제로 실행해 확인했습니다.
**단, 화면 출력은 버전·설치 상태에 따라 달라질 수 있습니다.** 문서와 조금 다르게 나와도
당황하지 마시고, 다르면 9절 트러블슈팅을 보세요.

---

## 목차

| 절 | 내용 | 대상 |
| --- | --- | :---: |
| [0](#0-시작하기-전에--길이-두-갈래입니다) | 두 갈래 길 · 읽는 순서 | 공통 |
| [1](#1-사전-준비물) | 사전 준비물 (Docker · 디스크 · 네트워크 · Python) | 공통 |
| [2](#2-방법-b-docker-직접-실행--계정도-cli-도-필요-없음) | **방법 B: Docker 직접 실행** ← 처음이면 여기부터 | B |
| [3](#3-lean-cli-설치) | LEAN CLI 설치 + **`lean` 이름 충돌(elan) 해결** | A |
| [4](#4-로그인-없이-되는-것과-안-되는-것) | 로그인 없이 되는 것 / 안 되는 것 | A |
| [5](#5-quantconnect-로그인--lean-init) | QuantConnect 로그인 → `lean init` | A |
| [6](#6-프로젝트-만들고-백테스트-돌리기) | 프로젝트 생성 · 백테스트 · 결과 보기 | A |
| [7](#7-이-저장소의-삼성전자-전략을-cli-로-돌리기) | 이 저장소의 삼성전자 전략을 CLI 로 | A |
| [8](#8-두-방식-비교) | 두 방식 비교 | 공통 |
| [9](#9-트러블슈팅) | 트러블슈팅 | 공통 |
| [부록 A](#부록-a-로그인-없이-백테스트가-되는가-검증-기록) | "로그인 없이 되는가" 검증 기록 | — |
| [부록 B](#부록-b-정리와-삭제) | 정리와 삭제 | — |

> **`lean --version` 이 `ELAN_HOME` 또는 `no default toolchain` 오류를 낸다면
> → [3-2절](#3-2-lean-을-쳤는데-elan-오류가-난다면)** 로 바로 가세요.

이 문서에서 `<저장소>` 는 이 저장소의 루트를 뜻합니다.
현재 경로는 `/mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-portfolio-site` 입니다.

```bash
cd /mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-portfolio-site
```

---

## 0. 시작하기 전에 — 길이 두 갈래입니다

LEAN 을 돌리는 방법은 두 가지고, **필요한 준비물이 다릅니다.**

| | 방법 A: LEAN CLI | 방법 B: Docker 직접 실행 |
| --- | --- | --- |
| 명령 | `lean backtest` | `docker compose -f docker-compose.lean.yml run --rm samsung-backtest` |
| Docker | 필요 | 필요 |
| QuantConnect 계정 | **필요함** (`lean init` 단계에서) | 필요 없음 |
| 추가 설치 | Python venv + `pip install lean` | 없음 |
| 이 저장소 기본값 | 아님 | **맞음** (`lean-samsung/`) |
| 장점 | 프로젝트 관리 · 리포트 · research 노트북 | 계정 없이 바로 됨 |

### 읽는 순서 (처음이라면)

1. **1절**(준비물) → **2절**(방법 B) — 계정 없이 결과를 한 번 봅니다.
   1절과 2절은 `lean` 명령을 전혀 쓰지 않으므로 **elan 오류와 무관합니다.**
2. 감이 잡히면 **3절 → 7절** 순서로 CLI 를 진행합니다.

> ⏱ **첫 실행은 오래 걸립니다.** 두 방법 모두 LEAN 엔진 Docker 이미지를 받아야 하고,
> 이게 **다운로드 14GB · 디스크 42.5GB** 입니다. 회선에 따라 20분~수 시간입니다.
> "5분 만에" 되는 건 이미지를 이미 받아둔 다음부터입니다.

---

## 1. 사전 준비물

### 1-1. Docker

LEAN 은 CLI 든 Docker 직접 실행이든 **결국 컨테이너 안에서 돕니다.** Docker 없이는 아무것도 안 됩니다.

**아직 설치하지 않았다면** 둘 중 하나를 고릅니다.

- **Docker Desktop for Windows** (권장, 초보자용)
  <https://www.docker.com/products/docker-desktop/> 에서 설치 →
  **Settings → Resources → WSL Integration** 에서 쓰는 배포판(Ubuntu)을 켜야
  WSL 터미널에서 `docker` 가 잡힙니다.
- **WSL 안에 Docker Engine 직접 설치**
  <https://docs.docker.com/engine/install/ubuntu/> 공식 절차를 따릅니다.

설치했으면 확인합니다.

```bash
docker --version          # Docker version 29.7.1, build e9452d6
docker compose version    # Docker Compose version v2.40.3-desktop.1
docker ps                 # 오류 없이 표가 나와야 합니다 (비어 있어도 정상)
```

> `docker compose version` 의 숫자는 설치 방식에 따라 다릅니다. **오류만 없으면 됩니다.**

`docker ps` 에서 막히면 → [9절 Docker 관련 오류](#docker-cannot-connect-to-the-docker-daemon).

### 1-2. 디스크 여유

| 항목 | 용량 | 어디에 |
| --- | --- | --- |
| LEAN 엔진 이미지 | 다운로드 14GB / **디스크 42.5GB** | Docker 저장소 |
| CLI 샘플 데이터 (`lean init`) | 226MB | 리눅스 홈 |
| CLI venv | 약 330MB | 리눅스 홈 |

```bash
docker system df    # Docker 가 실제로 쓰는 용량
df -h /             # 리눅스 파일시스템 여유
df -h /mnt/c        # Windows C: 여유 (Docker Desktop 은 여기에 데이터를 둡니다)
```

**최소 50GB 이상 여유를 권장합니다.**

### 1-3. 네트워크

세 군데에 외부 접속이 필요합니다. 방화벽·프록시 환경이라면 미리 확인하세요.

| 언제 | 어디로 | 용량 |
| --- | --- | --- |
| 첫 실행 (A·B 공통) | Docker Hub | 14GB |
| `lean init` (A) | GitHub | 226MB |
| 방법 B 매 실행 | Yahoo Finance | 수십 KB |

> Docker Hub 는 로그인 없이 받을 수 있지만 **시간당 pull 횟수 제한**이 있습니다.
> 반복 실패하면 잠시 기다렸다 다시 시도하세요.

### 1-4. Python (방법 A 만)

```bash
python3 --version          # Python 3.12.3
python3 -m venv --help     # 오류가 나면 아래 패키지를 설치합니다
```

`ensurepip is not available` 류의 오류가 나면:

```bash
sudo apt install python3-venv
```

---

## 2. 방법 B: Docker 직접 실행 — 계정도 CLI 도 필요 없음

이 저장소가 원래 쓰는 방식입니다. **QuantConnect 계정도, `lean` 명령도 필요 없습니다.**

### 2-1. 실행

```bash
cd /mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-portfolio-site
docker compose -f docker-compose.lean.yml run --rm samsung-backtest
```

> ⏱ **첫 실행은 14GB 이미지를 받느라 매우 오래 걸립니다.** 화면이 한동안 멈춘 것처럼 보여도
> 정상입니다. Ctrl-C 로 끊으면 다시 받아야 하니 기다리세요.
> 끊었다면 [2-4절](#2-4-중단하거나-실패했을-때)을 보세요.

성공하면 마지막에 이렇게 나옵니다.

```
STATISTICS:: Net Profit -2.640%
Engine.Main(): Analysis Complete.
```

### 2-2. 결과 보기

결과는 `<저장소>/lean-results/` 에 생깁니다.

```bash
# 체결 내역
cat lean-results/orders.csv
# 2024-01-03 00:00:00,005930,Buy,1,79600

# 성과 요약
jq -r '.statistics | to_entries[] | "\(.key): \(.value)"' \
  lean-results/SamsungBuyAndHold-summary.json
```

`jq` 가 없으면 `sudo apt install jq` 하거나 파이썬을 쓰세요.

```bash
python3 -c "import json;d=json.load(open('lean-results/SamsungBuyAndHold-summary.json'));[print(f'{k}: {v}') for k,v in d['statistics'].items()]"
```

출력:

```
Total Orders: 1
Compounding Annual Return: -2.641%
Drawdown: 3.800%
Start Equity: 1000000
End Equity: 973600
Net Profit: -2.640%
Sharpe Ratio: -3.919
...
```

> ⚠️ `python3 -m json.tool 파일1 파일2` 형태로 **와일드카드(`*`)를 쓰지 마세요.**
> `json.tool` 의 두 번째 인자는 *출력 파일*이라, 파일이 두 개 이상 매칭되면
> **두 번째 파일이 첫 번째 내용으로 덮어써집니다.** 결과가 소리 없이 파괴됩니다.

Windows 탐색기로 결과 폴더를 열려면:

```bash
explorer.exe .          # 현재 폴더를 탐색기로 열기
```

### 2-3. 기간 바꾸기 · 전략 고치기

기간은 환경 변수로 바꿉니다.

```bash
SAMSUNG_START_DATE=2023-01-01 SAMSUNG_END_DATE=2024-01-01 \
  docker compose -f docker-compose.lean.yml run --rm samsung-backtest
```

**전략 코드(`lean-samsung/SamsungBuyAndHold.py`)를 고쳤다면 반드시 `--build` 를 붙이세요.**
코드가 `COPY` 로 이미지에 구워지기 때문에, 안 붙이면 예전 코드가 그대로 돕니다.

```bash
docker compose -f docker-compose.lean.yml run --build --rm samsung-backtest
```

### 2-4. 중단하거나 실패했을 때

`--rm` 은 정상 종료한 컨테이너만 지웁니다. Ctrl-C 로 끊으면 컨테이너가 남습니다.

```bash
docker compose -f docker-compose.lean.yml ps -a    # 남은 컨테이너 확인
docker compose -f docker-compose.lean.yml down     # 정리
```

남은 컨테이너를 안 지우면 나중에 [부록 B](#부록-b-정리와-삭제)의 이미지 삭제가 실패합니다.

### 2-5. 왜 계정이 필요 없는가

CLI 를 거치지 않고 **엔진 실행 파일을 직접 부르기** 때문입니다.
`lean-samsung/entrypoint.sh` 마지막 줄:

```sh
exec dotnet /Lean/Launcher/bin/Debug/QuantConnect.Lean.Launcher.dll
```

설정은 `lean-samsung/config.json` 을 `/results/` 에 복사해 주입합니다.
CLI 가 하던 일(설정 생성 → 컨테이너 기동 → 결과 회수)을
Dockerfile + entrypoint + compose 볼륨 마운트가 대신하는 구조입니다.

실행 로그에서도 인증이 없다는 게 보입니다.

```bash
grep -E "Setup\(LocalPlatform\)|SetUp Backtesting" lean-results/log.txt | tail -2
```

```
... TRACE:: BaseSetupHandler.Setup(LocalPlatform): UID: 0, PID: 0, Version: 2.5.0.0, Source: WebIDE
... TRACE:: SetUp Backtesting: User: 0 ProjectId: 0 AlgoId: SamsungBuyAndHold
```

`UID: 0` · `User: 0` — 로그인한 사용자가 없다는 뜻입니다.

### 2-6. 구성 파일

| 파일 | 역할 |
| --- | --- |
| `docker-compose.lean.yml` | LEAN 전용 Compose 서비스. 웹앱과 독립 |
| `lean-samsung/Dockerfile` | `quantconnect/lean:latest` 기반 이미지 빌드 |
| `lean-samsung/entrypoint.sh` | 데이터 다운로드 → 설정 복사 → 엔진 시작 |
| `lean-samsung/download_samsung_data.py` | Yahoo Finance `005930.KS` 일봉 → CSV |
| `lean-samsung/SamsungBuyAndHold.py` | Custom Data 로 1주 매수·보유 |
| `lean-samsung/config.json` | 엔진 설정 (Python 알고리즘·백테스팅 핸들러) |

### 2-7. 결과 파일

| 파일 | 내용 | 재실행하면 |
| --- | --- | --- |
| `orders.csv` | 체결 내역 | 덮어씀 |
| `SamsungBuyAndHold-summary.json` | **성과 요약** | 덮어씀 |
| `SamsungBuyAndHold.json` | 차트용 전체 시계열 | 덮어씀 |
| `SamsungBuyAndHold-order-events.json` | 주문 제출·체결 이벤트 | 덮어씀 |
| `log.txt` | 실행 로그 | **이어붙음(append)** |
| `data-monitor-report-*.json` 등 | 데이터 요청 통계 | 실행마다 **쌓임** |

> `log.txt` 는 실행할 때마다 뒤에 붙습니다. 최근 실행만 보려면 `tail` 을 쓰세요.

> ⚠️ 이 전략은 **동작 확인용**입니다. KRX 거래일 · 수수료 · 세금 · 호가단위 · 배당 · 환율 모델이
> 하나도 없습니다. 나온 수익률을 실제 투자 성과로 해석하면 안 됩니다.

---

## 3. LEAN CLI 설치

여기부터는 **방법 A** 입니다. 2절만으로 충분하다면 안 하셔도 됩니다.

### 3-1. 설치

시스템 Python 을 오염시키지 않도록 **전용 가상환경**에 넣습니다.

```bash
python3 -m venv ~/.local/lean-cli-venv
~/.local/lean-cli-venv/bin/pip install -U pip
~/.local/lean-cli-venv/bin/pip install 'lean==1.0.227'
```

> 버전을 고정한 이유: 이 문서의 4~7절 설명이 1.0.227 기준입니다.
> 최신판을 원하면 `pip install lean` 으로 하시되, 화면이 조금 다를 수 있습니다.

의존성(pandas · matplotlib · docker SDK 등)이 많아 **2~5분 걸립니다.**

```
Successfully installed ... lean-1.0.227 ...
```

설치 확인 — **경로를 직접 지정**해서 부릅니다. (이유는 바로 다음 절)

```bash
~/.local/lean-cli-venv/bin/lean --version
# lean 1.0.227
```

여기까지 잘 나오면 설치는 끝입니다.

### 3-2. `lean` 을 쳤는데 elan 오류가 난다면

#### 증상

```bash
$ lean --version
error: couldn't find value of ELAN_HOME
info: caused by: No such file or directory (os error 2)
```

또는

```bash
$ lean --version
error: no default toolchain configured. run `elan default stable` to install & configure the latest Lean 4 stable release.
```

> 문구는 elan 의 상태에 따라 다릅니다.
> **`elan` · `ELAN_HOME` · `toolchain` 중 하나라도 보이면 전부 같은 원인**입니다.

#### 원인 — `lean` 이라는 이름을 쓰는 프로그램이 두 개입니다

| | QuantConnect LEAN | Lean 4 |
| --- | --- | --- |
| 정체 | 알고리즘 트레이딩 백테스트 엔진 | **수학 정리 증명기**(theorem prover) |
| 우리가 원하는 것 | **이것** | 아님 |
| 설치 | `pip install lean` | `apt install elan` |
| 실행 파일 | venv 안의 `lean` | `/usr/bin/lean` |

우분투에서 `lean` 명령을 찾으면 패키지 관리자가 `elan` 을 알려주기 때문에,
**아무 잘못 없이도 자연스럽게 밟게 되는 함정**입니다.

지금 상태를 확인해 보세요.

```bash
which -a lean
ls -l /usr/bin/lean 2>/dev/null
dpkg -l 2>/dev/null | grep elan
```

`/usr/bin/lean -> elan` 이 보이면 이 경우입니다. `elan` 은 Lean 4 의 툴체인 관리자로,
`rustup` 과 같은 역할입니다. `lean` 이라는 이름으로 불리면 **자기가 관리하는 Lean 4 툴체인에
그대로 넘기는 프록시**로 동작하는데, 넘겨줄 툴체인이 없어서 그 자리에서 실패합니다.

```bash
elan show    # no active toolchain  ← 넘겨줄 대상이 없다
```

#### 해결 — 세 가지 중 **하나만** 고르세요

> 겹쳐서 적용하면 아래 확인 출력이 문서와 달라집니다.
> 세 방법 모두 **3-1 설치를 먼저 끝낸 상태**를 전제합니다.

##### 방법 1 (가장 안전): venv 를 활성화해서 쓴다

`elan` 을 건드리지 않고, 작업하는 터미널에서만 우리 `lean` 이 우선하게 만듭니다.

```bash
source ~/.local/lean-cli-venv/bin/activate
```

```bash
$ which lean
/home/dongwon/.local/lean-cli-venv/bin/lean
$ lean --version
lean 1.0.227
```

끝나면 `deactivate` 로 되돌립니다.
프롬프트 앞에 `(lean-cli-venv)` 가 붙어 있으면 활성화된 상태입니다.
**터미널을 새로 열 때마다 다시 `source` 해야 합니다.**

##### 방법 2: 매번 전체 경로로 부른다

```bash
~/.local/lean-cli-venv/bin/lean --version
```

헷갈릴 일이 없어 확실합니다. 아무것도 바꾸지 않습니다.

##### 방법 3: `~/.local/bin` 에 심볼릭 링크를 건다 (sudo 불필요)

`~/.local/bin` 이 `PATH` 의 맨 앞이라 **elan 을 지우지 않아도** 우리 `lean` 이 먼저 잡힙니다.

```bash
ln -s ~/.local/lean-cli-venv/bin/lean ~/.local/bin/lean
hash -r          # 이 셸이 캐싱한 명령 경로를 비웁니다 (다른 터미널은 새로 열면 됩니다)
lean --version   # lean 1.0.227
```

되돌리려면 `rm ~/.local/bin/lean`.

**(선택) Lean 4 정리 증명기를 전혀 쓸 계획이 없다면** elan 자체를 지워도 됩니다.

```bash
sudo apt remove elan   # lean 외에 lake·leanc·leanchecker·leanmake·leanpkg 도 함께 사라집니다
```

> 되돌리려면 `sudo apt install elan`. 단 재설치만으로는 툴체인이 없어 `lean` 이 여전히
> 실패하므로, Lean 4 를 실제로 쓰려면 `elan default stable` 까지 실행해야 합니다.

**이 문서의 나머지는 `lean` 이라고만 씁니다.** 방법 1을 골랐다면 매번 `source` 를 먼저,
방법 2를 골랐다면 `lean` 을 `~/.local/lean-cli-venv/bin/lean` 으로 바꿔 읽으세요.

---

## 4. 로그인 없이 되는 것과 안 되는 것

**중요합니다.** LEAN 엔진 자체는 인증을 전혀 하지 않지만,
**CLI 의 `init` 단계가 QuantConnect 계정을 강제합니다.**

| 명령 | 로그인 없이 | 비고 |
| --- | :---: | --- |
| `lean --version` / `--help` | ✅ | |
| `lean whoami` | ✅ | `You are not logged in` 출력 |
| `lean config list` | ✅ | |
| `lean create-project` | ✅ | |
| **`lean init`** | ❌ | **`User id:` 프롬프트에서 막힘** |
| `lean backtest` | ⚠️ | `lean.json` 이 있는 폴더에서만. 그건 `init` 이 만듭니다 |
| `lean logs` | ⚠️ | 위와 같음 (`lean.json` 필요) |
| `lean report` | ⚠️ | 위와 같음 |
| `lean cloud *` / `lean data download` | ❌ | 애초에 클라우드 기능 |

### 왜 `init` 이 막히는가

CLI 소스 `lean/commands/init.py` 의 `init()` 함수는 지연 import 두 줄 뒤에
바로 인증을 겁니다 (1.0.227 기준 134~136행).

```python
current_user_id, current_api_token = get_lean_config_credentials()
user_id, api_token = get_credentials(current_user_id, current_api_token, False)
validate_credentials(user_id, api_token)          # ← QuantConnect API 호출
```

`--organization <id>` 를 줘도 인증 검사가 먼저라 우회되지 않습니다.

그리고 이게 연쇄됩니다. `lean.json` 에는 `organization-id` 값이 있어야 하는데,
그걸 써주는 건 `lean init` 뿐입니다. 없으면 이렇게 거부합니다.

```
This is an old Lean CLI root folder.
From now on, a Lean CLI root folder must be created for each organization for improved usability.
For each organization you'd like to use with the CLI, please create a new folder and run `lean init`.
```

> 이 검사는 `lean backtest` 전용이 아니라 **최상위 `lean` 그룹**(`lean/commands/lean.py`)에
> 있습니다. 그래서 `lean.json` 이 있지만 `organization-id` 가 빠진 폴더 안에서는
> `lean whoami` 같은 명령까지 전부 이 오류로 죽습니다.
> (`lean.json` 이 아예 없는 폴더에서는 검사를 건너뛰므로 `lean whoami` 는 잘 됩니다.)

**결론: CLI 를 정상 경로로 쓰려면 QuantConnect 계정이 필요합니다.**
계정을 만들기 싫으면 [2절](#2-방법-b-docker-직접-실행--계정도-cli-도-필요-없음)로 가세요.

---

## 5. QuantConnect 로그인 → `lean init`

### 5-1. 계정 만들고 API 토큰 받기

1. <https://www.quantconnect.com/> 에서 무료 회원가입 (신용카드 불필요)
2. <https://www.quantconnect.com/account> 접속
3. **User ID** 와 **API Token** 두 값을 복사

### 5-2. 로그인

```bash
lean login
```

`User id:` 와 `API token:` 을 차례로 물어봅니다. 입력은 화면에 표시되지 않습니다.

> ⚠️ `lean login --user-id ... --api-token ...` 처럼 **명령줄 인자로 토큰을 넘기지 마세요.**
> `~/.bash_history` 와 프로세스 목록에 평문으로 남습니다. 대화식 프롬프트를 쓰세요.

자격증명은 `~/.lean/credentials` 에 저장됩니다. 저장소 밖이라 커밋될 걱정은 없지만,
**이 파일을 저장소 안으로 복사하지 마세요.** 이 저장소는 Public 입니다.

확인:

```bash
lean whoami    # 로그인한 계정 이름이 나옵니다
```

### 5-3. `lean init`

**반드시 빈 디렉터리에서** 실행해야 합니다.

```bash
mkdir -p ~/lean-workspace
cd ~/lean-workspace
lean init --language python
```

하는 일:

1. QuantConnect API 로 소속 조직 조회 → 선택
2. GitHub 에서 LEAN 저장소를 통째로 내려받아 **샘플 데이터 226MB** 를 `data/` 에 풀기
3. `lean.json` 생성 (엔진 설정)

끝나면:

```
~/lean-workspace/
├── lean.json      # 엔진 설정 (organization-id 포함)
└── data/          # 샘플 시세 데이터 (226MB)
```

> 💡 **이 저장소 안에도 이미 동작하는 CLI 워크스페이스가 있습니다** — `<저장소>/lean-cli/`.
> [부록 A](#부록-a-로그인-없이-백테스트가-되는가-검증-기록)의 검증 과정에서 만든 것으로,
> `lean.json` · `data/` · `SamsungBuyAndHold` 프로젝트 · 백테스트 결과가 다 들어 있습니다.
> 단 `organization-id` 가 **자리표시자**라 정상 사용에는 적합하지 않습니다.
> 구조를 눈으로 보는 참고용으로만 쓰세요. (git 추적 대상 아님)

---

## 6. 프로젝트 만들고 백테스트 돌리기

### 6-1. 프로젝트 생성

```bash
cd ~/lean-workspace
lean create-project "MyFirstStrategy" --language python
```

```
Successfully created Python project 'MyFirstStrategy'
```

| 파일 | 역할 |
| --- | --- |
| `main.py` | **전략 코드.** 여기를 수정합니다 |
| `config.json` | 프로젝트 설정 |
| `research.ipynb` | `lean research` 용 노트북 |
| `.vscode/`, `.idea/` | 에디터 자동완성 설정 |

**기본 `main.py` 는 SPY 를 2013-10-07 ~ 10-11 (5일) 동안 보유하는 템플릿**입니다.
기간이 짧아 수익률이 거의 0에 가깝게 나옵니다 — 정상입니다. 먼저 한 번 열어보세요.

```bash
cat MyFirstStrategy/main.py
```

### 6-2. 백테스트 실행

```bash
lean backtest "MyFirstStrategy"
```

> ⏱ **첫 실행은 14GB 엔진 이미지를 받습니다.** 2절을 이미 했다면 같은 이미지라 재사용됩니다.

성공하면:

```
Successfully ran 'MyFirstStrategy' in the 'backtesting' environment and stored
the output in 'MyFirstStrategy/backtests/2026-08-07_15-47-59'
```

### 6-3. 결과 보기

결과는 `<프로젝트>/backtests/<날짜_시각>/` 에 **실행마다 새 폴더**로 쌓입니다.
파일 이름 앞에는 백테스트 ID 숫자가 붙습니다 (예: `1563115117-summary.json`).

| 파일 | 내용 |
| --- | --- |
| `*-summary.json` | 수익률 · 샤프지수 등 **성과 요약** |
| `*-order-events.json` | 주문 제출 · 체결 이벤트 |
| `*.json` | 차트용 전체 시계열 (요약보다 큼) |
| `*-log.txt`, `log.txt` | 실행 로그 |
| `code/` | 그때 돌린 전략 코드 사본 |
| `config` | 그때 쓴 엔진 설정 |
| `data-monitor-report-*.json`, `*-data-requests-*.txt` | 데이터 요청 통계 |

```bash
# 최근 백테스트 로그
lean logs --backtest

# 가장 최근 결과 폴더 경로 잡기
LATEST=$(ls -dt MyFirstStrategy/backtests/*/ | head -1)
echo "$LATEST"

# 성과 요약 보기
jq -r '.statistics | to_entries[] | "\(.key): \(.value)"' "$LATEST"/*-summary.json
```

> ⚠️ `python3 -m json.tool <경로>/*-summary.json` 처럼 **와일드카드를 그대로 넘기지 마세요.**
> 파일이 둘 이상 매칭되면 두 번째 파일이 첫 번째 내용으로 **덮어써집니다.**
> 위처럼 폴더를 하나로 좁힌 뒤 쓰세요.

### 6-4. 자주 쓰는 옵션

```bash
lean backtest "MyFirstStrategy" --output ./결과폴더   # 결과 저장 위치 지정
lean backtest "MyFirstStrategy" --no-update           # 이미지 갱신 확인 건너뛰기(빠름)
lean backtest "MyFirstStrategy" --update              # 엔진 이미지를 최신으로 pull
```

`--debug` 도 있지만 VS Code 쪽에서 attach 설정이 따로 필요하고
프로젝트의 `.vscode/launch.json` 을 CLI 가 수정합니다. 처음에는 건너뛰세요.

### 6-5. 리포트 생성 (선택)

```bash
lean report
```

가장 최근 백테스트로 **`./report.html` 한 개**를 만듭니다.
백테스트와 **같은 엔진 이미지**를 쓰므로 추가 다운로드는 없습니다.

```bash
lean report --pdf         # PDF 도 함께
lean report --overwrite   # 기존 report.html 덮어쓰기 (없으면 거부됩니다)
```

만든 리포트를 Windows 브라우저로 열려면:

```bash
wslview report.html       # 기본 브라우저로 열기
# 또는
explorer.exe .            # 탐색기로 폴더 열기
```

---

## 7. 이 저장소의 삼성전자 전략을 CLI 로 돌리기

`lean-samsung/SamsungBuyAndHold.py` 를 CLI 프로젝트로 옮겨 돌립니다.

```bash
# 저장소 경로를 변수에 담아둡니다 (오타 방지)
REPO=/mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-portfolio-site

cd ~/lean-workspace

# 1) 프로젝트 만들고 전략 코드 얹기
lean create-project "SamsungBuyAndHold" --language python
cp "$REPO/lean-samsung/SamsungBuyAndHold.py" SamsungBuyAndHold/main.py

# 2) 삼성전자 일봉 CSV 를 data/ 에 내려받기
python3 "$REPO/lean-samsung/download_samsung_data.py" \
  --output data/samsung.csv --start 2024-01-01 --end 2025-01-01
# Downloaded 244 daily bars to data/samsung.csv

# 3) 백테스트
lean backtest "SamsungBuyAndHold"
```

실제 실행 결과 (2026-08-07 확인):

```
STATISTICS:: Start Equity 1000000
STATISTICS:: End Equity 973600
STATISTICS:: Net Profit -2.640%
STATISTICS:: Sharpe Ratio -3.919
Successfully ran 'SamsungBuyAndHold' in the 'backtesting' environment
```

체결 1건: `2024-01-03  005930  buy  1주  @ 79,600`

### 기간을 바꾸려면

전략은 환경 변수로 기간을 읽습니다.

```python
start = date.fromisoformat(os.getenv("SAMSUNG_START_DATE", "2024-01-01"))
```

방법 B 는 compose 의 `environment:` 가 이 값을 컨테이너에 넣어주지만,
**`lean backtest` 에는 환경 변수를 컨테이너로 전달하는 간단한 방법이 없습니다.**
CLI 로 기간을 바꾸려면 `main.py` 의 기본값을 직접 고치고,
CSV 도 같은 기간으로 다시 받으세요.

```bash
python3 "$REPO/lean-samsung/download_samsung_data.py" \
  --output data/samsung.csv --start 2023-01-01 --end 2024-01-01
```

### 동작 원리

전략은 `samsung.csv` 를 LEAN 의 **Custom Data**(`PythonData`)로 읽습니다.

```python
class SamsungDaily(PythonData):
    def get_source(self, config, date, is_live):
        source = os.path.join(Globals.data_folder, "samsung.csv")
        return SubscriptionDataSource(source, SubscriptionTransportMedium.LOCAL_FILE)
```

`Globals.data_folder` 는 **컨테이너 안의 경로**(`/Lean/Data`)입니다.
CLI 가 호스트의 `data/` 폴더를 거기에 바인드 마운트하므로,
**CSV 를 `data/samsung.csv` 에 두기만 하면 됩니다.**

---

## 8. 두 방식 비교

| 항목 | 방법 A: CLI | 방법 B: Docker 직접 |
| --- | --- | --- |
| Docker | 필요 | 필요 |
| QuantConnect 계정 | **필요** | 불필요 |
| 추가 설치 | Python venv + `pip install lean` | 없음 |
| 샘플 데이터 | `lean init` 이 226MB 내려받음 | 이미지에 포함 |
| 삼성전자 시세 | 한 번 받아 `data/` 에 둠 | **매 실행 Yahoo 에서 새로 받음** |
| 프로젝트 관리 | `create-project` 로 스캐폴딩 | 직접 파일 작성 |
| 결과 정리 | 실행마다 타임스탬프 폴더 | 대부분 덮어씀 (`log.txt` 는 이어붙음) |
| 리포트 | `lean report` → `report.html` | 없음 |
| research 노트북 | `lean research` (별도 이미지 추가 다운로드) | 없음 |
| 클라우드 동기화 | 가능 | 불가 |
| 재현성 | `lean.json` 이 로컬 상태에 의존 | 엔진 버전은 `latest` 태그, 데이터는 매번 외부 조회 |

> **둘 다 완전한 재현성은 없습니다.** 방법 B 의 `Dockerfile` 은 `FROM quantconnect/lean:latest`
> 라 빌드 시점마다 엔진이 바뀔 수 있고, `entrypoint.sh` 가 매 실행 Yahoo Finance 에서
> 시세를 새로 받습니다. 결과를 남겨야 한다면 그때의 CSV 와 엔진 버전을 따로 기록하세요.

**학습 목적이면 B 로 시작해 감을 잡고, 전략을 여러 개 관리하기 시작하면 A 로 넘어가는 순서**를 권합니다.

---

## 9. 트러블슈팅

### elan 관련 오류 (`ELAN_HOME` / `no default toolchain`)

`elan`(Lean 4 정리 증명기)의 `lean` 이 잡힌 겁니다. → [3-2절](#3-2-lean-을-쳤는데-elan-오류가-난다면)

### `lean: command not found`

세 경우입니다.

1. 아직 CLI 를 설치하지 않았다 → [3-1절](#3-1-설치)
2. venv 를 활성화하지 않았다 → `source ~/.local/lean-cli-venv/bin/activate`
3. 심볼릭 링크(방법 3)를 걸었는데 venv 를 지웠다 → 링크가 깨진 것. `rm ~/.local/bin/lean` 후 재설치

### `User id:` 프롬프트에서 멈춤 (`lean init`)

정상 동작입니다. `lean init` 은 로그인이 필수입니다. → [4절](#4-로그인-없이-되는-것과-안-되는-것) · [5절](#5-quantconnect-로그인--lean-init)

### `Error: This is an old Lean CLI root folder.`

`lean.json` 에 `organization-id` 가 없습니다. 빈 폴더에서 `lean init` 을 다시 도세요.
이 오류는 그 폴더 안의 **모든** `lean` 명령에서 납니다.

### `This command requires a Lean configuration file, run 'lean init' ...`

`lean.json` 이 있는 폴더(=`lean init` 을 돌린 폴더) 안에서 실행해야 합니다.
다른 위치의 설정을 쓰려면 `--lean-config <경로>` 를 줄 수도 있습니다.
전에 쓰던 `lean.json` 이 캐시돼 있으면 오류 대신 **선택 프롬프트**가 먼저 뜨기도 합니다.

### Docker: `Cannot connect to the Docker daemon`

가장 흔한 원인 순서대로:

1. **Docker Desktop 이 꺼져 있다** — Windows 재부팅하면 (자동 시작을 안 켜뒀다면) 꺼집니다. 켜세요.
2. **WSL Integration 이 꺼져 있다** — Docker Desktop → Settings → Resources → WSL Integration
3. **권한 문제** — 아래 실행 후 WSL 재시작

```bash
sudo usermod -aG docker $USER
```

WSL 재시작은 **Windows PowerShell** 에서:

```powershell
wsl --shutdown
```

### 이미지 다운로드가 너무 느림 / 중간에 끊김

14GB 라 오래 걸립니다. 재실행하면 받은 레이어부터 이어받습니다.
Docker Hub 는 미인증 pull 에 시간당 횟수 제한이 있으니, 반복 실패 시 잠시 후 재시도하세요.

### `download_samsung_data.py` 가 실패

Yahoo Finance 의 비공식 엔드포인트라 차단·변경될 수 있습니다. 증상이 다릅니다.

| 화면 | 원인 |
| --- | --- |
| `HTTPError: 403` / `429` 트레이스백 | 차단·요청 제한 → 잠시 후 재시도 |
| `KeyError` / `TypeError` 트레이스백 | 응답 형식이 바뀜 → 스크립트 수정 필요 |
| `No Samsung Electronics price rows were downloaded` | 응답은 정상인데 유효 행이 0건 → 기간을 바꿔보세요 |

### 디스크가 꽉 참

```bash
docker system df                # 무엇이 얼마나 쓰는지
docker image prune -a           # 안 쓰는 이미지 전부 (-a 없으면 dangling 만 지웁니다)
docker builder prune            # 빌드 캐시
```

> `docker image prune` 은 `-a` 없이는 **태그 없는 이미지만** 지웁니다.
> 42.5GB 를 차지하는 `quantconnect/lean:latest` 는 태그가 있어 그대로 남습니다.

### 백테스트는 됐는데 결과가 안 보임

`head -40` 으로 summary.json 을 보면 차트 좌표만 나옵니다.
`statistics` 는 파일 중간(약 446번째 줄)에 있습니다. [2-2절](#2-2-결과-보기)의 `jq` 명령을 쓰세요.

---

## 부록 A. "로그인 없이 백테스트가 되는가" 검증 기록

2026-08-07 에 실제로 확인한 내용입니다.
**엔진은 인증을 하지 않고, 막는 건 CLI 의 `init` 뿐**입니다.

`lean init` 을 건너뛰고 그 산출물(`lean.json` + `data/`)을 수동으로 갖춘 뒤,
`organization-id` 에 자리표시자(32자리 0)를 넣고 백테스트를 돌렸습니다.

```
Successfully ran 'SamsungBuyAndHold' in the 'backtesting' environment
BaseSetupHandler.Setup(LocalPlatform): UID: 0, PID: -1
STATISTICS:: Net Profit -2.640%
```

실행 후에도:

```
$ lean whoami
You are not logged in

$ ls ~/.lean/
cache          # credentials 파일이 생성되지 않음
```

자리표시자 조직 ID 가 그대로 통과했다는 건 **이 값이 서버 검증 없이 로컬에서만 쓰인다**는 뜻입니다.
`lean.json` 에서 `organization-id` 를 지우면 즉시 거부되므로, 값의 **존재 자체만** 검사합니다.

그때 만든 워크스페이스가 `<저장소>/lean-cli/` 로 남아 있습니다 (git 추적 대상 아님).

> ⚠️ 이건 원리를 확인하려고 한 **편법**입니다. 정상 사용법이 아니고 QuantConnect 가 지원하지도 않습니다.
> CLI 를 쓰실 거면 [5절](#5-quantconnect-로그인--lean-init)대로 계정을 만들어
> `lean login` → `lean init` 을 거치세요.

---

## 부록 B. 정리와 삭제

> ⚠️ **`rm -rf` 는 되돌릴 수 없습니다.** 아래 명령은 **하나씩** 확인하며 실행하세요.
> 특히 `~/lean-workspace` 에는 6·7절에서 **직접 작성한 전략 코드와 모든 백테스트 결과**가
> 들어 있습니다. 남기고 싶은 게 있는지 먼저 확인하세요.

```bash
ls ~/lean-workspace                    # 지우기 전에 무엇이 있는지 확인
```

### 1) 남은 컨테이너 먼저 정리 (이걸 안 하면 이미지 삭제가 실패합니다)

```bash
cd /mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-portfolio-site
docker compose -f docker-compose.lean.yml down
docker ps -a --filter "ancestor=samsung-lean-module:local"    # 남은 게 있는지 확인
```

### 2) 백테스트 산출물

```bash
cd /mnt/c/Users/kik32/workspace/EST-Camp-AI-Quant/projects/investment-portfolio-site
rm -rf lean-results        # 방법 B 결과 (재실행으로 다시 만들어집니다)
rm -rf lean-results-old    # 예전 실행 결과
rm -rf lean-cli            # 부록 A 검증용 CLI 워크스페이스 (226MB)
```

### 3) CLI 워크스페이스

```bash
rm -rf ~/lean-workspace    # ⚠️ 직접 작성한 전략과 백테스트 결과가 전부 사라집니다
```

### 4) CLI 자체

```bash
rm -f  ~/.local/bin/lean          # 3-2 방법 3 으로 만든 심볼릭 링크 (안 지우면 깨진 링크가 남습니다)
rm -rf ~/.local/lean-cli-venv     # CLI 가상환경
rm -rf ~/.lean                    # 자격증명 · 설정 · 캐시
```

### 5) Docker 이미지 (디스크 42.5GB 회수)

```bash
docker rmi samsung-lean-module:local
docker rmi quantconnect/lean:latest
docker system df                  # 회수됐는지 확인
```

> 다운로드는 14GB 였지만 **디스크에서 회수되는 건 42.5GB** 입니다 (압축이 풀려 저장되기 때문).

### 6) elan (Lean 4 정리 증명기)

```bash
sudo apt remove elan   # lean·lake·leanc·leanchecker·leanmake·leanpkg 가 함께 사라집니다
```

---

## 참고 링크

- LEAN CLI 공식 문서 — <https://www.lean.io/docs/v2/lean-cli/key-concepts/getting-started>
- LEAN 엔진 소스 — <https://github.com/QuantConnect/Lean>
- Docker Hub 이미지 — <https://hub.docker.com/r/quantconnect/lean>
- QuantConnect 계정 / API 토큰 — <https://www.quantconnect.com/account>
- Docker Desktop — <https://www.docker.com/products/docker-desktop/>
- 이 저장소의 LEAN 설명 — `docs/07.md` 부록, `README.md` 5절

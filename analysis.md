# Terminal Tetris — 코드 분석 문서

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 파일 | `tetris.py` (단일 파일, 596줄) |
| 언어 | Python 3 |
| 주요 라이브러리 | `curses` (터미널 UI), `json` (점수 저장), `random`, `time`, `os`, `datetime` |
| 실행 방식 | `python3 tetris.py` 또는 shebang(`#!/usr/bin/env python3`) 직접 실행 |

---

## 2. 파일 구조 및 함수 목록

```
tetris.py
├── 상수 정의 (L.11–52)
│   ├── BOARD_WIDTH, BOARD_HEIGHT
│   ├── SHAPES          — 7종 테트로미노 형태
│   ├── COLORS          — 조각별 색상 ID
│   ├── COLOR_TO_NAME   — 색상 ID → 조각 이름 역조회
│   ├── LINE_SCORES     — 줄 제거 점수 테이블
│   ├── FALL_SPEEDS     — 레벨별 낙하 속도 (초)
│   ├── CELL_W / CELL_H — 터미널 셀 크기 (4열 × 2행)
│   ├── LEFT_W          — 왼쪽 Hold 패널 너비
│   ├── HOLD_KEY        — Hold 키 (F)
│   └── SCORE_FILE      — ~/.tetris_scores.json
│
├── 점수 영속성 (L.59–134)
│   ├── load_scores()
│   ├── save_score()
│   └── show_leaderboard()
│
├── UI 보조 (L.136–256)
│   ├── input_name()
│   ├── rotate_cw()
│   ├── create_board()
│   ├── is_valid()
│   ├── lock_piece()
│   ├── clear_lines()
│   ├── get_fall_speed()
│   ├── random_piece()
│   └── original_piece()
│
├── 렌더링 (L.257–424)
│   └── draw()
│
└── 게임 루프 (L.427–595)
    └── main()
```

---

## 3. 핵심 모듈 상세 분석

### 3-1. 테트로미노 정의

```python
SHAPES = {
    'I': [[1, 1, 1, 1]],
    'O': [[1, 1], [1, 1]],
    'T': [[0,1,0], [1,1,1]],
    'S': [[0,1,1], [1,1,0]],
    'Z': [[1,1,0], [0,1,1]],
    'J': [[1,0,0], [1,1,1]],
    'L': [[0,0,1], [1,1,1]],
}
```
- 표준 7종 테트로미노를 2D 리스트(0/1 행렬)로 정의
- 각 조각에 고유 색상 ID 매핑 (cyan, yellow, magenta, green, red, blue, white)

### 3-2. 보드 상태 관리

| 함수 | 동작 |
|------|------|
| `create_board()` | 10×20 2D 리스트, 0으로 초기화 |
| `is_valid(board, shape, x, y)` | 경계 초과 및 겹침 검사 |
| `lock_piece(board, shape, x, y, color)` | 조각을 보드에 영구 고정 (색상 ID 기록) |
| `clear_lines(board)` | 완성된 줄 제거 후 빈 줄 상단 삽입, 제거 수 반환 |

### 3-3. 회전 & 월 킥

```python
def rotate_cw(shape):
    return [list(row) for row in zip(*shape[::-1])]
```
- 행렬 전치 + 역순으로 시계 방향 90° 회전 구현
- 회전 후 `kick ∈ {0, -1, +1, -2, +2}` 5단계 오프셋을 순차 시도하는 **월 킥** 적용 (`main()` L.499–504)

### 3-4. 점수 시스템

| 제거 줄 수 | 기본 점수 |
|-----------|---------|
| 1 | 100 |
| 2 | 300 |
| 3 | 500 |
| 4 (테트리스) | 800 |

- 최종 점수 = 기본 점수 × (레벨 + 1)
- 레벨 = 누적 제거 줄 수 ÷ 10 (정수)

### 3-5. 낙하 속도

```python
FALL_SPEEDS = [0.80, 0.72, 0.63, 0.55, 0.47, 0.38, 0.30, 0.22, 0.13, 0.10, 0.08]
```
- 레벨 0~10 각각 초 단위 낙하 간격
- 레벨 10 이상은 최소 0.08초 고정

### 3-6. Hold 기능

- `F` 키로 현재 조각을 Hold 슬롯에 저장/교환
- 조각당 1회만 사용 가능 (`hold_used` 플래그)
- Hold 시 원형 조각(무회전 상태)으로 저장 (`original_piece()`)
- Hold 직후 새 위치에서 `is_valid()` 실패 시 즉시 게임 오버

### 3-7. 렌더링 구조 (`draw()`)

```
[왼쪽 패널: Hold]  [중앙: 게임 보드]  [오른쪽 패널: Stats + Next]
```

- **셀 크기**: 4열 × 2행 (`CELL_W=4`, `CELL_H=2`) — 가로로 넓은 터미널 블록
- **고스트 피스**: 현재 조각이 낙하할 최종 위치를 `::::` 문자(DIM 속성)로 표시
- **경계선**: `|`, `-`, `+` ASCII 문자로 보드 테두리 구성
- **오버레이**: PAUSE / GAME OVER 메시지를 보드 중앙에 REVERSE 속성으로 표시

### 3-8. 점수 영속성

- 파일: `~/.tetris_scores.json`
- 구조: `[{name, score, level, lines, date}, ...]`
- 상위 50개 항목만 유지 (점수 내림차순 정렬)
- 리더보드 조회: Top 10 표시, 현재 게임 점수 행 강조(BOLD+REVERSE)

---

## 4. 게임 루프 흐름

```
main()
 └─ while True (재시작 루프)
     ├─ 게임 상태 초기화 (board, piece, score, level ...)
     └─ while game_result is None (메인 루프, ~50fps)
         ├─ 키 입력 처리
         │   ├─ Q       → game_result = 'quit'
         │   ├─ P       → paused 토글
         │   ├─ L       → show_leaderboard()
         │   ├─ ←/→     → 좌우 이동
         │   ├─ ↑       → 회전 + 월 킥
         │   ├─ ↓       → 소프트 드롭
         │   ├─ Space   → 하드 드롭 (즉시 낙하)
         │   └─ F       → Hold
         ├─ 중력 처리 (FALL_SPEEDS 기반 타이머)
         │   ├─ 낙하 가능 → py++
         │   └─ 낙하 불가 → lock → clear_lines → 새 조각 스폰
         │                    └─ 스폰 실패 → 게임 오버 처리
         ├─ draw() 호출
         └─ time.sleep(0.02)  — 약 50fps
```

---

## 5. 조작 키 요약

| 키 | 동작 |
|----|------|
| `←` / `→` | 좌우 이동 |
| `↑` | 시계 방향 회전 |
| `↓` | 소프트 드롭 |
| `Space` | 하드 드롭 |
| `F` | Hold (조각 보관/교환) |
| `P` | 일시정지 토글 |
| `L` | 리더보드 열기 |
| `R` | 재시작 |
| `Q` | 종료 |

---

## 6. 개선 가능 사항

| 분류 | 내용 |
|------|------|
| **기능** | 7-bag 랜덤 알고리즘 (현재 완전 랜덤, 같은 조각 연속 가능) |
| **기능** | SRS(Super Rotation System) 정식 월 킥 테이블 적용 |
| **기능** | 소프트 드롭 점수 추가 (1점/셀) [완료] |
| **기능** | 하드 드롭 점수 추가 (2점/셀) [완료] |
| **기능** | 게임 진행중 게임 재시작 기능(R키) |
| **구조** | `main()` 함수 분리 — 입력 처리 / 물리 / 렌더를 별도 함수로 분리 |
| **구조** | 게임 상태를 dataclass로 묶어 가독성 향상 |
| **안정성** | 터미널 크기 부족 시 경고 메시지 표시 (현재 일부 `curses.error` 묵음 처리) |
| **테스트** | `is_valid`, `clear_lines`, `rotate_cw` 등 순수 함수 단위 테스트 추가 |

---

## 7. 의존성

```
Python 표준 라이브러리만 사용 (외부 패키지 없음)
- curses    : 터미널 UI
- json      : 점수 파일 저장/로드
- os        : 파일 경로 처리
- random    : 무작위 조각 선택
- time      : 낙하 타이머 / 프레임 제한
- datetime  : 점수 저장 시 날짜 기록
```

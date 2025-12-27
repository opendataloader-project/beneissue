# Beneissue 메트릭 대시보드 구현 계획

## 개요

AI 이슈 자동화 성능을 측정하고 시각화하는 웹 대시보드

**목적:**
- 투자자/파트너에게 AX 성과 증명
- 경영진에게 비즈니스 언어로 ROI 설명
- 내부 성능 모니터링

**URL:** `beneissue.opendataloader.org`

---

## 아키텍처

```
[GitHub Actions]
       │
       ▼
[beneissue Python] ──POST──▶ [Supabase PostgreSQL]
                                      │
                              ◀──SELECT──
                                      │
                              [Next.js + Vercel]
                              (API Routes = 비즈니스 로직)
                                      │
                                      ▼
                        beneissue.opendataloader.org
```

**핵심 설계:**
- Python → Supabase 직접 쓰기 (service_key)
- Next.js → Supabase 읽기 전용 (anon_key)
- 별도 백엔드 서버 불필요 (서버리스)

---

## 배포 구조

| 레포 | 도메인 | 역할 |
|------|--------|------|
| `opendataloader/beneissue` | - | Python CLI, 메트릭 수집 |
| `opendataloader/beneissue-dashboard` | beneissue.opendataloader.org | 대시보드 UI |

---

## 기술 스택

| 항목 | 선택 |
|------|------|
| 프론트엔드 | Next.js 15 + shadcn/ui + Recharts |
| DB | Supabase PostgreSQL |
| 호스팅 | Vercel (무료) |
| 인증 | API Key (로그인 불필요) |

**무료 한도:**
- Vercel: 100GB/월 대역폭
- Supabase: 500MB DB, 50K 요청/월

---

## 대시보드 페이지

| 경로 | 인증 | 용도 |
|------|------|------|
| `/` | 없음 | Public Stats (집계 지표만) |
| `/dashboard` | API Key | Executive Dashboard (ROI, 비용절감) |
| `/ops` | API Key | Operations Dashboard (기술 지표) |

---

## 메트릭 정의

### Executive (경영진용)

| 지표 | 계산 |
|------|------|
| 시간 절감 | `triage×5분 + analyze×30분 + fix×120분` |
| 비용 절감 | `절감시간 × 시급(5만원) - AI비용` |
| ROI | `(절감비용 - AI비용) / AI비용 × 100` |
| 처리량 | 총 처리 이슈 수 |

### Operations (운영팀용)

| 지표 | 계산 |
|------|------|
| AI 필터링율 | `(invalid + duplicate) / total × 100` |
| 자동 해결율 | `fix_success / fix_attempted × 100` |
| 평균 응답 시간 | `avg(first_response - issue_created)` |
| 토큰 사용량 | 누적 input/output 토큰 |

---

## 데이터 모델

### workflow_runs
```sql
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER NOT NULL,
    workflow_type VARCHAR(20),           -- triage/analyze/fix/full

    -- Timestamps
    issue_created_at TIMESTAMPTZ,
    workflow_started_at TIMESTAMPTZ DEFAULT NOW(),
    workflow_completed_at TIMESTAMPTZ,

    -- Triage
    triage_decision VARCHAR(20),         -- valid/invalid/duplicate/needs_info
    duplicate_of INTEGER,

    -- Analyze
    fix_decision VARCHAR(20),            -- auto_eligible/manual_required
    priority VARCHAR(5),
    story_points INTEGER,

    -- Fix
    fix_success BOOLEAN,
    pr_url VARCHAR(500),

    -- Usage
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0
);
```

### daily_metrics (집계)
```sql
CREATE TABLE daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    repo VARCHAR(255),
    total_issues INTEGER DEFAULT 0,
    ai_filtered_count INTEGER DEFAULT 0,
    fix_success_count INTEGER DEFAULT 0,
    avg_first_response_seconds DECIMAL,
    total_cost_usd DECIMAL(10, 4) DEFAULT 0,
    UNIQUE(date, repo)
);
```

---

## 구현 단계

### Phase 1: Supabase 설정
1. Supabase 프로젝트 생성
2. 테이블 생성 (workflow_runs, daily_metrics)
3. RLS: 공개 읽기, service_key 쓰기

### Phase 2: Python 메트릭 수집

**새 파일:**
- `src/beneissue/metrics/schemas.py`
- `src/beneissue/metrics/collector.py`
- `src/beneissue/metrics/storage.py`

**수정 파일:**
- `src/beneissue/graph/state.py` - timestamp 추가
- `src/beneissue/graph/workflow.py` - record_metrics 노드

### Phase 3: Next.js 대시보드

```bash
# 새 레포 생성
npx create-next-app@latest beneissue-dashboard --typescript --tailwind --app
cd beneissue-dashboard
npx shadcn@latest init
npx shadcn@latest add card button table
npm install @supabase/supabase-js recharts
```

**프로젝트 구조:**
```
beneissue-dashboard/
├── app/
│   ├── page.tsx              # Public Stats
│   ├── dashboard/page.tsx    # Executive
│   ├── ops/page.tsx          # Operations
│   └── api/metrics/route.ts  # API (비즈니스 로직)
├── components/
│   ├── ui/                   # shadcn
│   └── charts/
│       ├── roi-card.tsx
│       ├── trend-chart.tsx
│       └── distribution-pie.tsx
└── lib/
    ├── supabase.ts
    └── metrics.ts
```

### Phase 4: Vercel 배포
1. GitHub 레포 연결
2. 도메인: `beneissue.opendataloader.org`
3. 환경변수 설정

---

## 환경 변수

### beneissue (Python)
```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=xxx  # 쓰기용
```

### beneissue-dashboard (Vercel)
```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx  # 읽기용
DASHBOARD_API_KEY=xxx  # 인증용
```

---

## 접근 제어

| 데이터 | 공개 여부 |
|--------|----------|
| 총 건수, ROI, 평균값 | 공개 (/) |
| 이슈 제목/내용, PR URL | 비공개 (/dashboard) |
| 레포명, 사용자명 | 비공개 (/dashboard) |

---

## 와이어프레임

### Public Stats (/)
```
┌─────────────────────────────────────────────────────┐
│  Beneissue - AI Issue Automation                    │
├─────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │  12,847  │ │   45초   │ │   32%    │ │  847%  │ │
│  │ 처리이슈  │ │ 평균응답  │ │ 자동해결  │ │  ROI   │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  [────────────────────────] 월별 추이               │
└─────────────────────────────────────────────────────┘
```

### Executive Dashboard (/dashboard)
```
┌─────────────────────────────────────────────────────┐
│  Executive Dashboard              [이번 달▾] [Export]│
├─────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 847% ROI │ │ 152시간  │ │₩7,600,000│ │ 1,247건│ │
│  │ ▲+23%   │ │ ▲+15%   │ │ ▲+18%   │ │ ▲+31% │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                                                     │
│  ┌─────────────────────┐ ┌───────────────────────┐ │
│  │ 월별 비용 절감 추이    │ │ AI 처리 분포          │ │
│  │ [차트]               │ │ [파이차트]            │ │
│  └─────────────────────┘ └───────────────────────┘ │
│                                                     │
│  "이번 달 AI가 1,247건 처리, 152시간 절약, ROI 847%" │
└─────────────────────────────────────────────────────┘
```

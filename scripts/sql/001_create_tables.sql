-- Beneissue Metrics Tables
-- Run this in Supabase SQL Editor

-- workflow_runs: 각 워크플로우 실행 기록
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER NOT NULL,
    workflow_type VARCHAR(20) NOT NULL,  -- triage/analyze/fix/full

    -- Timestamps
    issue_created_at TIMESTAMPTZ,
    workflow_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    workflow_completed_at TIMESTAMPTZ,

    -- Triage results
    triage_decision VARCHAR(20),         -- valid/invalid/duplicate/needs_info
    triage_reason TEXT,
    duplicate_of INTEGER,

    -- Analyze results
    fix_decision VARCHAR(20),            -- auto_eligible/manual_required/comment_only
    priority VARCHAR(5),                 -- P0/P1/P2
    story_points INTEGER,
    assignee VARCHAR(100),

    -- Fix results
    fix_success BOOLEAN,
    pr_url VARCHAR(500),
    fix_error TEXT,

    -- Token usage
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    input_cost DECIMAL(10, 6) DEFAULT 0,
    output_cost DECIMAL(10, 6) DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_workflow_runs_repo ON workflow_runs(repo);
CREATE INDEX idx_workflow_runs_created ON workflow_runs(created_at);
CREATE INDEX idx_workflow_runs_workflow_type ON workflow_runs(workflow_type);
CREATE INDEX idx_workflow_runs_repo_issue_started ON workflow_runs(repo, issue_number, workflow_started_at);

-- daily_metrics: 일별 집계 (대시보드 쿼리 최적화)
CREATE TABLE daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    repo VARCHAR(255),  -- NULL = 전체 집계

    -- Counts
    total_runs INTEGER DEFAULT 0,      -- 워크플로우 실행 횟수
    unique_issues INTEGER DEFAULT 0,   -- 고유 이슈 수 (중복 제외)
    triage_count INTEGER DEFAULT 0,
    analyze_count INTEGER DEFAULT 0,
    fix_count INTEGER DEFAULT 0,

    -- AI filtering
    ai_filtered_count INTEGER DEFAULT 0,  -- invalid + duplicate
    valid_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    needs_info_count INTEGER DEFAULT 0,

    -- Fix outcomes
    fix_attempted_count INTEGER DEFAULT 0,
    fix_success_count INTEGER DEFAULT 0,
    comment_only_count INTEGER DEFAULT 0,

    -- Response time (seconds)
    avg_first_response_seconds DECIMAL,
    min_first_response_seconds DECIMAL,
    max_first_response_seconds DECIMAL,

    -- Cost
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_input_cost DECIMAL(10, 6) DEFAULT 0,
    total_output_cost DECIMAL(10, 6) DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(date, repo)
);

CREATE INDEX idx_daily_metrics_date ON daily_metrics(date);
CREATE INDEX idx_daily_metrics_repo ON daily_metrics(repo);

-- Row Level Security
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;

-- 공개 읽기 허용
CREATE POLICY "Allow public read" ON workflow_runs
    FOR SELECT USING (true);

CREATE POLICY "Allow public read" ON daily_metrics
    FOR SELECT USING (true);

-- service_role만 쓰기 허용 (Python에서 service_key 사용)
CREATE POLICY "Allow service write" ON workflow_runs
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Allow service write" ON daily_metrics
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Allow service update" ON daily_metrics
    FOR UPDATE USING (auth.role() = 'service_role');

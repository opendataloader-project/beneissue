-- Beneissue Metrics Tables
-- Run this in Supabase SQL Editor

-- workflow_runs: Per-step execution records (separate record for each triage, analyze, fix step)
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER NOT NULL,
    workflow_type VARCHAR(20) NOT NULL,  -- triage/analyze/fix (one record per step)

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


-- Row Level Security
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;

-- Allow public read access
CREATE POLICY "Allow public read" ON workflow_runs
    FOR SELECT USING (true);

-- Allow write only for service_role (Python uses service_key)
CREATE POLICY "Allow service write" ON workflow_runs
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

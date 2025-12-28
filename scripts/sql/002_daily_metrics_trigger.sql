-- Daily Metrics Auto-Update Trigger
-- Run this in Supabase SQL Editor after 001_create_tables.sql

-- workflow_runs INSERT 시 daily_metrics 자동 업데이트
CREATE OR REPLACE FUNCTION update_daily_metrics()
RETURNS TRIGGER AS $$
DECLARE
    run_date DATE;
    is_first_run BOOLEAN;
BEGIN
    run_date := DATE(NEW.workflow_started_at);

    -- 오늘 이 이슈의 첫 실행인지 확인 (unique_issues 정확한 카운트를 위해)
    -- 범위 쿼리로 인덱스 활용 (DATE() 함수 대신)
    SELECT NOT EXISTS (
        SELECT 1 FROM workflow_runs
        WHERE repo = NEW.repo
          AND issue_number = NEW.issue_number
          AND workflow_started_at >= run_date
          AND workflow_started_at < run_date + INTERVAL '1 day'
          AND id != NEW.id
    ) INTO is_first_run;

    INSERT INTO daily_metrics (
        date, repo, total_runs, unique_issues,
        total_input_tokens, total_output_tokens, total_input_cost, total_output_cost
    )
    VALUES (
        run_date, NEW.repo, 1, CASE WHEN is_first_run THEN 1 ELSE 0 END,
        COALESCE(NEW.input_tokens, 0), COALESCE(NEW.output_tokens, 0),
        COALESCE(NEW.input_cost, 0), COALESCE(NEW.output_cost, 0)
    )
    ON CONFLICT (date, repo) DO UPDATE SET
        total_runs = daily_metrics.total_runs + 1,
        unique_issues = daily_metrics.unique_issues +
            CASE WHEN is_first_run THEN 1 ELSE 0 END,

        -- Workflow type counts
        triage_count = daily_metrics.triage_count +
            CASE WHEN NEW.workflow_type IN ('triage', 'full') THEN 1 ELSE 0 END,
        analyze_count = daily_metrics.analyze_count +
            CASE WHEN NEW.workflow_type IN ('analyze', 'full') THEN 1 ELSE 0 END,
        fix_count = daily_metrics.fix_count +
            CASE WHEN NEW.workflow_type IN ('fix', 'full') THEN 1 ELSE 0 END,

        -- Triage results
        ai_filtered_count = daily_metrics.ai_filtered_count +
            CASE WHEN NEW.triage_decision IN ('invalid', 'duplicate') THEN 1 ELSE 0 END,
        valid_count = daily_metrics.valid_count +
            CASE WHEN NEW.triage_decision = 'valid' THEN 1 ELSE 0 END,
        duplicate_count = daily_metrics.duplicate_count +
            CASE WHEN NEW.triage_decision = 'duplicate' THEN 1 ELSE 0 END,
        needs_info_count = daily_metrics.needs_info_count +
            CASE WHEN NEW.triage_decision = 'needs_info' THEN 1 ELSE 0 END,

        -- Fix results (including comment_only)
        fix_attempted_count = daily_metrics.fix_attempted_count +
            CASE WHEN NEW.fix_success IS NOT NULL THEN 1 ELSE 0 END,
        fix_success_count = daily_metrics.fix_success_count +
            CASE WHEN NEW.fix_success = true THEN 1 ELSE 0 END,
        comment_only_count = daily_metrics.comment_only_count +
            CASE WHEN NEW.fix_decision = 'comment_only' THEN 1 ELSE 0 END,

        -- Tokens & cost
        total_input_tokens = daily_metrics.total_input_tokens + COALESCE(NEW.input_tokens, 0),
        total_output_tokens = daily_metrics.total_output_tokens + COALESCE(NEW.output_tokens, 0),
        total_input_cost = daily_metrics.total_input_cost + COALESCE(NEW.input_cost, 0),
        total_output_cost = daily_metrics.total_output_cost + COALESCE(NEW.output_cost, 0),

        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 트리거 생성
DROP TRIGGER IF EXISTS trigger_update_daily_metrics ON workflow_runs;
CREATE TRIGGER trigger_update_daily_metrics
    AFTER INSERT ON workflow_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_daily_metrics();

-- Migration: Replace total_cost_usd with input_cost and output_cost
-- Run this in Supabase SQL Editor after 001_create_tables.sql

-- Add new columns
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS input_cost DECIMAL(10, 6) DEFAULT 0;
ALTER TABLE workflow_runs ADD COLUMN IF NOT EXISTS output_cost DECIMAL(10, 6) DEFAULT 0;

-- Drop old column (if exists)
ALTER TABLE workflow_runs DROP COLUMN IF EXISTS total_cost_usd;

-- Update daily_metrics table as well
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS total_input_cost DECIMAL(10, 6) DEFAULT 0;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS total_output_cost DECIMAL(10, 6) DEFAULT 0;
ALTER TABLE daily_metrics DROP COLUMN IF EXISTS total_cost_usd;

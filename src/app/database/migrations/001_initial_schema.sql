-- Migration: Initial Database Schema
-- Description: Create basic tables for users, jobs, file metadata, and job queue
-- Version: 001
-- Date: 2024-12-19

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    image_url TEXT,
    email_addresses JSONB DEFAULT '[]',
    phone_numbers JSONB DEFAULT '[]',
    primary_email VARCHAR(255),
    primary_phone VARCHAR(50),
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    role VARCHAR(50) DEFAULT 'user',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sign_in_at TIMESTAMP,
    last_active_at TIMESTAMP,
    user_metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    job_type VARCHAR(50) DEFAULT 'video_generation',
    priority VARCHAR(20) DEFAULT 'normal',
    configuration JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'queued',
    progress_percentage DECIMAL(5,2) DEFAULT 0,
    current_stage VARCHAR(100),
    stages_completed JSONB DEFAULT '[]',
    estimated_completion TIMESTAMP,
    processing_time_seconds DECIMAL(10,2),
    error_info JSONB,
    metrics JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    batch_id UUID,
    parent_job_id UUID REFERENCES jobs(id),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- File metadata table
CREATE TABLE IF NOT EXISTS file_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    job_id UUID REFERENCES jobs(id),
    file_type VARCHAR(50) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    s3_bucket VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    s3_version_id VARCHAR(255),
    file_size BIGINT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    checksum VARCHAR(64),
    file_metadata JSONB DEFAULT '{}',
    description TEXT,
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Job queue table
CREATE TABLE IF NOT EXISTS job_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL UNIQUE REFERENCES jobs(id),
    priority VARCHAR(20) DEFAULT 'normal',
    queue_status VARCHAR(50) DEFAULT 'queued',
    worker_id VARCHAR(255),
    processing_node VARCHAR(255),
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,
    queue_position INTEGER
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_clerk_id ON users(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(primary_email);
CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_deleted, status);

-- Create indexes for jobs table
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_deleted, status);
CREATE INDEX IF NOT EXISTS idx_jobs_queue_priority ON jobs(status, priority, created_at);

-- Create indexes for file_metadata table
CREATE INDEX IF NOT EXISTS idx_files_user_id ON file_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_files_job_id ON file_metadata(job_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON file_metadata(file_type);
CREATE INDEX IF NOT EXISTS idx_files_s3_key ON file_metadata(s3_key);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON file_metadata(created_at);
CREATE INDEX IF NOT EXISTS idx_files_user_type ON file_metadata(user_id, file_type);
CREATE INDEX IF NOT EXISTS idx_files_active ON file_metadata(is_deleted);

-- Create indexes for job_queue table
CREATE INDEX IF NOT EXISTS idx_queue_job_id ON job_queue(job_id);
CREATE INDEX IF NOT EXISTS idx_queue_status ON job_queue(queue_status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON job_queue(priority);
CREATE INDEX IF NOT EXISTS idx_queue_position ON job_queue(queue_position);
CREATE INDEX IF NOT EXISTS idx_queue_processing ON job_queue(queue_status, priority, queued_at);
CREATE INDEX IF NOT EXISTS idx_queue_retry ON job_queue(next_retry_at, retry_count);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at 
    BEFORE UPDATE ON jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_file_metadata_updated_at 
    BEFORE UPDATE ON file_metadata 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create migration log table
CREATE TABLE IF NOT EXISTS migration_log (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert migration record
INSERT INTO migration_log (version, description, applied_at) 
VALUES (1, 'Initial Database Schema', CURRENT_TIMESTAMP)
ON CONFLICT (version) DO UPDATE SET 
    applied_at = CURRENT_TIMESTAMP,
    description = EXCLUDED.description;
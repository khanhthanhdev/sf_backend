-- Migration: Add batch_metadata table for batch job management
-- This table stores metadata for batch job operations

CREATE TABLE IF NOT EXISTS batch_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Batch information
    total_jobs INTEGER NOT NULL DEFAULT 0,
    created_jobs INTEGER NOT NULL DEFAULT 0,
    failed_jobs INTEGER NOT NULL DEFAULT 0,
    batch_priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    
    -- Job IDs in the batch (JSON array)
    job_ids JSONB NOT NULL DEFAULT '[]',
    
    -- Complete metadata (JSON object)
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Soft delete support
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_batch_metadata_batch_id ON batch_metadata(batch_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_batch_metadata_user_id ON batch_metadata(user_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_batch_metadata_created_at ON batch_metadata(created_at) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_batch_metadata_priority ON batch_metadata(batch_priority) WHERE is_deleted = FALSE;

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_batch_metadata_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_batch_metadata_updated_at
    BEFORE UPDATE ON batch_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_batch_metadata_updated_at();

-- Add comments for documentation
COMMENT ON TABLE batch_metadata IS 'Stores metadata for batch job operations';
COMMENT ON COLUMN batch_metadata.batch_id IS 'Unique identifier for the batch';
COMMENT ON COLUMN batch_metadata.user_id IS 'User who created the batch';
COMMENT ON COLUMN batch_metadata.total_jobs IS 'Total number of jobs requested in batch';
COMMENT ON COLUMN batch_metadata.created_jobs IS 'Number of jobs successfully created';
COMMENT ON COLUMN batch_metadata.failed_jobs IS 'Number of jobs that failed to create';
COMMENT ON COLUMN batch_metadata.job_ids IS 'JSON array of job IDs in the batch';
COMMENT ON COLUMN batch_metadata.metadata IS 'Complete batch metadata as JSON';
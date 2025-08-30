-- Migration: User Service Tables for RDS Integration
-- Description: Create tables for user sessions, permissions, and activity logging
-- Version: 006
-- Date: 2024-12-19

-- User Sessions Table
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    clerk_user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    token_claims JSONB DEFAULT '{}',
    verified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for user sessions
CREATE INDEX IF NOT EXISTS idx_user_sessions_clerk_user_id ON user_sessions(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active, expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

-- Create unique constraint for active sessions per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_sessions_unique_active 
ON user_sessions(clerk_user_id) 
WHERE is_active = TRUE;

-- User Permissions Table
CREATE TABLE IF NOT EXISTS user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    clerk_user_id VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    permissions JSONB DEFAULT '[]',
    
    -- Video generation permissions
    can_generate_videos BOOLEAN DEFAULT TRUE,
    can_upload_files BOOLEAN DEFAULT TRUE,
    can_access_premium_features BOOLEAN DEFAULT FALSE,
    
    -- Administrative permissions
    can_view_all_jobs BOOLEAN DEFAULT FALSE,
    can_cancel_any_job BOOLEAN DEFAULT FALSE,
    can_access_system_metrics BOOLEAN DEFAULT FALSE,
    
    -- Rate limits
    max_concurrent_jobs INTEGER DEFAULT 3,
    max_daily_jobs INTEGER DEFAULT 50,
    max_file_size_mb INTEGER DEFAULT 100,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for user permissions
CREATE INDEX IF NOT EXISTS idx_user_permissions_clerk_user_id ON user_permissions(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_permissions_role ON user_permissions(role);

-- User Activity Log Table
CREATE TABLE IF NOT EXISTS user_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    clerk_user_id VARCHAR(255) NOT NULL,
    activity_type VARCHAR(100) NOT NULL,
    details JSONB DEFAULT '{}',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    
    -- Partitioning support (for future optimization)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for user activity log
CREATE INDEX IF NOT EXISTS idx_user_activity_log_user_id ON user_activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_log_clerk_user_id ON user_activity_log(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_log_activity_type ON user_activity_log(activity_type);
CREATE INDEX IF NOT EXISTS idx_user_activity_log_timestamp ON user_activity_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_log_user_timestamp ON user_activity_log(user_id, timestamp DESC);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_user_activity_log_user_type_timestamp 
ON user_activity_log(user_id, activity_type, timestamp DESC);

-- Add triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables with updated_at columns
CREATE TRIGGER update_user_sessions_updated_at 
    BEFORE UPDATE ON user_sessions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_permissions_updated_at 
    BEFORE UPDATE ON user_permissions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE user_sessions IS 'Stores user session information for authentication';
COMMENT ON TABLE user_permissions IS 'Stores user permissions and role-based access control';
COMMENT ON TABLE user_activity_log IS 'Logs user activities for audit and analytics';

COMMENT ON COLUMN user_sessions.clerk_user_id IS 'Clerk user ID for external authentication';
COMMENT ON COLUMN user_sessions.token_claims IS 'JWT token claims stored as JSON';
COMMENT ON COLUMN user_sessions.expires_at IS 'Session expiration timestamp';

COMMENT ON COLUMN user_permissions.permissions IS 'Array of specific permission strings';
COMMENT ON COLUMN user_permissions.max_concurrent_jobs IS 'Maximum number of concurrent jobs allowed';
COMMENT ON COLUMN user_permissions.max_daily_jobs IS 'Maximum number of jobs per day';
COMMENT ON COLUMN user_permissions.max_file_size_mb IS 'Maximum file size in megabytes';

COMMENT ON COLUMN user_activity_log.details IS 'Activity-specific details stored as JSON';
COMMENT ON COLUMN user_activity_log.ip_address IS 'IP address of the user when activity occurred';
COMMENT ON COLUMN user_activity_log.user_agent IS 'User agent string from the request';

-- Create a view for active user sessions
CREATE OR REPLACE VIEW active_user_sessions AS
SELECT 
    us.*,
    u.username,
    u.primary_email,
    u.role as user_role
FROM user_sessions us
JOIN users u ON us.user_id = u.id
WHERE us.is_active = TRUE 
  AND us.expires_at > CURRENT_TIMESTAMP
  AND u.is_deleted = FALSE;

COMMENT ON VIEW active_user_sessions IS 'View of currently active user sessions with user details';

-- Create a view for user permissions with user details
CREATE OR REPLACE VIEW user_permissions_view AS
SELECT 
    up.*,
    u.username,
    u.primary_email,
    u.status as user_status,
    u.created_at as user_created_at
FROM user_permissions up
JOIN users u ON up.user_id = u.id
WHERE u.is_deleted = FALSE;

COMMENT ON VIEW user_permissions_view IS 'View of user permissions with associated user details';

-- Create function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    cleaned_count INTEGER;
BEGIN
    UPDATE user_sessions 
    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
    WHERE expires_at < CURRENT_TIMESTAMP AND is_active = TRUE;
    
    GET DIAGNOSTICS cleaned_count = ROW_COUNT;
    
    RETURN cleaned_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_sessions() IS 'Function to clean up expired user sessions';

-- Create function to get user activity summary
CREATE OR REPLACE FUNCTION get_user_activity_summary(
    p_user_id UUID,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    activity_type VARCHAR(100),
    activity_count BIGINT,
    last_activity TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ual.activity_type,
        COUNT(*) as activity_count,
        MAX(ual.timestamp) as last_activity
    FROM user_activity_log ual
    WHERE ual.user_id = p_user_id
      AND ual.timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * p_days
    GROUP BY ual.activity_type
    ORDER BY activity_count DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_user_activity_summary(UUID, INTEGER) IS 'Get activity summary for a user over specified days';

-- Insert default permissions for existing users
INSERT INTO user_permissions (user_id, clerk_user_id, role)
SELECT 
    id,
    clerk_user_id,
    COALESCE(role, 'user')
FROM users 
WHERE is_deleted = FALSE
  AND clerk_user_id NOT IN (SELECT clerk_user_id FROM user_permissions)
ON CONFLICT (clerk_user_id) DO NOTHING;

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active_at DESC) WHERE is_deleted = FALSE;

-- Add constraint to ensure session expiration is in the future
ALTER TABLE user_sessions 
ADD CONSTRAINT chk_session_expires_future 
CHECK (expires_at > verified_at);

-- Add constraint to ensure positive rate limits
ALTER TABLE user_permissions 
ADD CONSTRAINT chk_positive_limits 
CHECK (max_concurrent_jobs > 0 AND max_daily_jobs > 0 AND max_file_size_mb > 0);

-- Migration completion log
INSERT INTO migration_log (version, description, applied_at) 
VALUES (6, 'User Service Tables for RDS Integration', CURRENT_TIMESTAMP)
ON CONFLICT (version) DO UPDATE SET 
    applied_at = CURRENT_TIMESTAMP,
    description = EXCLUDED.description;
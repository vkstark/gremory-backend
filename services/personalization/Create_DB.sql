-- ====================================================================
-- Simplified Personalization Schema
-- Reduces complexity while maintaining functionality
-- ====================================================================

CREATE SCHEMA IF NOT EXISTS personalization;
CREATE EXTENSION IF NOT EXISTS vector;

-- ====================================================================
-- CORE TABLES
-- ====================================================================

-- Unified user profiles (static + dynamic data)
CREATE TABLE personalization.user_profiles (
    user_id INT PRIMARY KEY,
    
    -- Static profile data
    name VARCHAR(255),
    email VARCHAR(255),
    birthdate DATE,
    signup_source VARCHAR(100),
    language_preference VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50),
    preferences JSONB DEFAULT '{}',
    
    -- Dynamic activity data
    last_login_at TIMESTAMP WITH TIME ZONE,
    activity_summary JSONB DEFAULT '{}', -- session counts, daily activity, etc.
    recent_interactions JSONB DEFAULT '{}', -- topics, feedback, etc.
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT fk_user_profiles_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- User embeddings for ML/AI features
CREATE TABLE personalization.user_embeddings (
    user_id INT,
    embedding_type VARCHAR(50), -- 'interests', 'communication_style', 'behavior'
    model_version VARCHAR(50),
    embedding_vector VECTOR(1536),
    confidence_score DECIMAL(3,2),
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '30 days',
    
    PRIMARY KEY (user_id, embedding_type, model_version),
    
    CONSTRAINT fk_user_embeddings_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_confidence_score 
        CHECK (confidence_score >= 0.00 AND confidence_score <= 1.00)
);

-- Unified configurations (features, experiments, flags)
CREATE TABLE personalization.user_configurations (
    user_id INT,
    config_type VARCHAR(20), -- 'feature', 'experiment', 'setting'
    config_key VARCHAR(100),
    config_value JSONB NOT NULL,
    meta_data JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (user_id, config_type, config_key),
    
    CONSTRAINT fk_user_configurations_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_config_type 
        CHECK (config_type IN ('feature', 'experiment', 'setting')),
    CONSTRAINT chk_status 
        CHECK (status IN ('active', 'inactive', 'completed'))
);

-- Time-series events (partitioned for performance)
CREATE TABLE personalization.user_events (
    id BIGSERIAL,
    user_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (id, created_at),
    
    CONSTRAINT fk_user_events_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE
) PARTITION BY RANGE (created_at);

-- Create monthly partitions (example for current period)
CREATE TABLE personalization.user_events_2025_06 PARTITION OF personalization.user_events
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');

-- Cached recommendations
CREATE TABLE personalization.user_recommendations (
    user_id INT PRIMARY KEY,
    recommendation_type VARCHAR(50) DEFAULT 'general',
    recommendations JSONB NOT NULL,
    meta_data JSONB DEFAULT '{}',
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '1 hour',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT fk_user_recommendations_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE
);

-- ====================================================================
-- PERFORMANCE INDEXES
-- ====================================================================

-- User profiles indexes
CREATE INDEX idx_user_profiles_last_login ON personalization.user_profiles(last_login_at);
CREATE INDEX idx_user_profiles_updated_at ON personalization.user_profiles(updated_at);
CREATE INDEX idx_user_profiles_preferences ON personalization.user_profiles USING GIN(preferences);
CREATE INDEX idx_user_profiles_activity ON personalization.user_profiles USING GIN(activity_summary);

-- Embeddings indexes
CREATE INDEX idx_user_embeddings_type_expires ON personalization.user_embeddings(embedding_type, expires_at);
CREATE INDEX idx_user_embeddings_confidence ON personalization.user_embeddings(confidence_score) WHERE confidence_score >= 0.8;

-- Configurations indexes
CREATE INDEX idx_user_configurations_type_status ON personalization.user_configurations(config_type, status);
CREATE INDEX idx_user_configurations_expires ON personalization.user_configurations(expires_at) WHERE expires_at IS NOT NULL;
CREATE UNIQUE INDEX idx_user_configurations_active_experiments ON personalization.user_configurations(user_id, config_key) 
    WHERE config_type = 'experiment' AND status = 'active';

-- Events indexes (on partition)
CREATE INDEX idx_user_events_user_type ON personalization.user_events_2025_06(user_id, event_type);
CREATE INDEX idx_user_events_created_at ON personalization.user_events_2025_06(created_at);

-- Recommendations indexes
CREATE INDEX idx_user_recommendations_expires ON personalization.user_recommendations(expires_at);
CREATE INDEX idx_user_recommendations_type ON personalization.user_recommendations(recommendation_type);

-- ====================================================================
-- HELPER FUNCTIONS
-- ====================================================================

-- Function to clean up expired data
CREATE OR REPLACE FUNCTION personalization.cleanup_expired_data()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    temp_count INTEGER;
BEGIN
    -- Clean expired embeddings
    DELETE FROM personalization.user_embeddings WHERE expires_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Clean expired configurations
    DELETE FROM personalization.user_configurations WHERE expires_at IS NOT NULL AND expires_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Clean expired recommendations
    DELETE FROM personalization.user_recommendations WHERE expires_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ====================================================================
-- EXAMPLE USAGE PATTERNS
-- ====================================================================

-- Get complete user profile
/*
SELECT 
    up.*,
    json_agg(
        json_build_object(
            'type', ue.embedding_type,
            'confidence', ue.confidence_score,
            'created_at', ue.created_at
        )
    ) FILTER (WHERE ue.user_id IS NOT NULL) as embeddings,
    json_agg(
        json_build_object(
            'config_type', uc.config_type,
            'config_key', uc.config_key,
            'config_value', uc.config_value
        )
    ) FILTER (WHERE uc.user_id IS NOT NULL) as configurations
FROM personalization.user_profiles up
LEFT JOIN personalization.user_embeddings ue ON up.user_id = ue.user_id AND ue.expires_at > NOW()
LEFT JOIN personalization.user_configurations uc ON up.user_id = uc.user_id AND uc.status = 'active'
WHERE up.user_id = $1
GROUP BY up.user_id;
*/
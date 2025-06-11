-- Create personalization schema
CREATE SCHEMA IF NOT EXISTS personalization;

-- Enable vector extension if using pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Static user profile data (rarely changes)
CREATE TABLE personalization.user_profiles_static (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    name VARCHAR(255),
    email VARCHAR(255),
    birthdate DATE,
    signup_source VARCHAR(100),
    language_preference VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50),
    long_term_goals JSONB,
    immutable_preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Cross-schema foreign key constraint with cascading delete
    CONSTRAINT fk_user_profiles_static_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- Dynamic user profile data (frequently changing)
CREATE TABLE personalization.user_profiles_dynamic (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    last_login_at TIMESTAMP WITH TIME ZONE,
    session_message_count INTEGER DEFAULT 0,
    daily_activity_count INTEGER DEFAULT 0,
    recent_topics JSONB,
    real_time_feedback JSONB,
    session_metrics JSONB,
    activity_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '90 days',
    
    UNIQUE(user_id, activity_date),
    
    -- Cross-schema foreign key constraint with cascading delete
    CONSTRAINT fk_user_profiles_dynamic_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- User embeddings for ML/AI features
CREATE TABLE personalization.user_embeddings (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    embedding_type VARCHAR(50) NOT NULL, -- 'interests', 'communication_style', 'preferences'
    embedding_vector VECTOR(1536), -- Adjust dimension as needed
    metadata JSONB,
    model_version VARCHAR(50),
    confidence_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '30 days',
    
    UNIQUE(user_id, embedding_type),
    
    -- Cross-schema foreign key constraint with cascading delete
    CONSTRAINT fk_user_embeddings_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
        
    -- Validation constraints
    CONSTRAINT chk_confidence_score 
        CHECK (confidence_score >= 0.00 AND confidence_score <= 1.00),
    CONSTRAINT chk_embedding_type 
        CHECK (embedding_type IN ('interests', 'communication_style', 'preferences', 'behavior', 'content_affinity'))
);

-- User features for A/B testing and feature flags
CREATE TABLE personalization.user_features (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    feature_value JSONB NOT NULL,
    feature_version VARCHAR(20) DEFAULT '1.0',
    change_frequency VARCHAR(20) CHECK (change_frequency IN ('static', 'slow', 'dynamic')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(user_id, feature_name, feature_version),
    
    -- Cross-schema foreign key constraint with cascading delete
    CONSTRAINT fk_user_features_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- User experiments for A/B testing
CREATE TABLE personalization.user_experiments (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    experiment_name VARCHAR(100) NOT NULL,
    variant VARCHAR(50) NOT NULL,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'disabled')),
    metadata JSONB, -- Additional experiment data
    
    UNIQUE(user_id, experiment_name),
    
    -- Cross-schema foreign key constraint with cascading delete
    CONSTRAINT fk_user_experiments_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES gremory.users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- Performance indexes
CREATE INDEX idx_user_profiles_static_user_id ON personalization.user_profiles_static(user_id);
CREATE INDEX idx_user_profiles_static_created_at ON personalization.user_profiles_static(created_at);
CREATE INDEX idx_user_profiles_static_updated_at ON personalization.user_profiles_static(updated_at);

CREATE INDEX idx_user_profiles_dynamic_user_id ON personalization.user_profiles_dynamic(user_id);
CREATE INDEX idx_user_profiles_dynamic_activity_date ON personalization.user_profiles_dynamic(activity_date);
CREATE INDEX idx_user_profiles_dynamic_expires_at ON personalization.user_profiles_dynamic(expires_at);
CREATE INDEX idx_user_profiles_dynamic_last_login ON personalization.user_profiles_dynamic(last_login_at);

CREATE INDEX idx_user_embeddings_user_id_type ON personalization.user_embeddings(user_id, embedding_type);
CREATE INDEX idx_user_embeddings_expires_at ON personalization.user_embeddings(expires_at);
CREATE INDEX idx_user_embeddings_model_version ON personalization.user_embeddings(model_version);
CREATE INDEX idx_user_embeddings_confidence ON personalization.user_embeddings(confidence_score);

CREATE INDEX idx_user_features_user_id_name ON personalization.user_features(user_id, feature_name);
CREATE INDEX idx_user_features_expires_at ON personalization.user_features(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_user_features_change_freq ON personalization.user_features(change_frequency);

CREATE INDEX idx_user_experiments_user_id ON personalization.user_experiments(user_id);
CREATE INDEX idx_user_experiments_status ON personalization.user_experiments(status);
CREATE INDEX idx_user_experiments_assigned_at ON personalization.user_experiments(assigned_at);

-- GIN indexes for JSONB columns (for fast JSON queries)
CREATE INDEX idx_user_profiles_static_preferences ON personalization.user_profiles_static USING GIN(immutable_preferences);
CREATE INDEX idx_user_profiles_static_goals ON personalization.user_profiles_static USING GIN(long_term_goals);
CREATE INDEX idx_user_profiles_dynamic_topics ON personalization.user_profiles_dynamic USING GIN(recent_topics);
CREATE INDEX idx_user_profiles_dynamic_feedback ON personalization.user_profiles_dynamic USING GIN(real_time_feedback);
CREATE INDEX idx_user_profiles_dynamic_metrics ON personalization.user_profiles_dynamic USING GIN(session_metrics);
CREATE INDEX idx_user_embeddings_metadata ON personalization.user_embeddings USING GIN(metadata);
CREATE INDEX idx_user_features_value ON personalization.user_features USING GIN(feature_value);
CREATE INDEX idx_user_experiments_metadata ON personalization.user_experiments USING GIN(metadata);

-- Partial indexes for common queries
CREATE INDEX idx_user_profiles_dynamic_active_sessions 
ON personalization.user_profiles_dynamic(user_id, last_login_at) 
WHERE last_login_at > NOW() - INTERVAL '24 hours';

CREATE INDEX idx_user_embeddings_recent 
ON personalization.user_embeddings(user_id, embedding_type, updated_at) 
WHERE expires_at > NOW();

CREATE INDEX idx_user_experiments_active 
ON personalization.user_experiments(user_id, experiment_name) 
WHERE status = 'active';
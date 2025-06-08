-- Reset sequences to 1 for clean testing (gremory schema)
DO $$
DECLARE
    r RECORD;
BEGIN
    -- Reset BIGINT sequences (messages, encrypted_messages)
    FOR r IN 
        SELECT 'messages' AS table_name
        UNION ALL
        SELECT 'encrypted_messages'
    LOOP
        -- Clear the table first
        EXECUTE format('TRUNCATE TABLE gremory.%I RESTART IDENTITY CASCADE', r.table_name);
        -- Reset sequence to 1
        EXECUTE format('ALTER SEQUENCE gremory.%I_id_seq RESTART WITH 1', r.table_name);
        RAISE NOTICE 'Reset BIGINT sequence for table: gremory.%', r.table_name;
    END LOOP;
    
    -- Reset INTEGER sequences
    FOR r IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'gremory' 
        AND table_name IN (
            'users', 'conversations', 'user_sessions', 'user_preferences',
            'message_attachments', 'cross_device_session_sync', 'session_state_snapshots',
            'message_nlp_analysis', 'intent_recognition', 'entity_extraction',
            'function_execution_pipeline', 'api_call_metrics', 'function_performance_analytics',
            'user_behavior_profiles', 'conversation_contexts', 'user_authentication',
            'user_permissions', 'user_consent_records', 'data_processing_logs', 'encryption_keys'
        )
    LOOP
        -- Clear the table first
        EXECUTE format('TRUNCATE TABLE gremory.%I RESTART IDENTITY CASCADE', r.table_name);
        -- Reset sequence to 1
        EXECUTE format('ALTER SEQUENCE gremory.%I_id_seq RESTART WITH 1', r.table_name);
        RAISE NOTICE 'Reset INTEGER sequence for table: gremory.%', r.table_name;
    END LOOP;
    
    RAISE NOTICE 'All sequences have been reset to 1 for gremory schema';
END $$;



-- Check the tables
SELECT 'Users' AS table_name, id::text AS record_id, username AS description
FROM (
    SELECT id, username FROM gremory.users ORDER BY id DESC LIMIT 3
) AS users_sub

UNION ALL

SELECT 'Conversations', id::text, name
FROM (
    SELECT id, name FROM gremory.conversations ORDER BY id DESC LIMIT 3
) AS conv_sub

UNION ALL

SELECT 'Messages', id::text, content
FROM (
    SELECT id, content FROM gremory.messages ORDER BY id DESC LIMIT 3
) AS msg_sub;

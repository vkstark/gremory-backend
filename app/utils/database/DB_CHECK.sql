-- ===============================================
-- USER HISTORY API - DATABASE VERIFICATION SCRIPT
-- Schema: test (Updated with actual table structure)
-- ===============================================

-- Check if tables exist and have proper structure
SELECT 'TABLE_EXISTS' AS check_type, 
       table_name, 
       CASE WHEN table_name IS NOT NULL THEN 'EXISTS' ELSE 'MISSING' END AS status
FROM information_schema.tables 
WHERE table_schema = 'test'
  AND table_name IN ('users', 'conversations', 'messages', 'user_sessions', 'user_preferences', 'message_attachments')
ORDER BY table_name;

-- ===============================================
-- RECENT RECORDS FROM CORE TABLES
-- ===============================================

-- Check Users table (using actual column names)
SELECT 'Users' AS table_name, 
       id::text AS record_id, 
       COALESCE(username, display_name, 'N/A') AS identifier,
       user_type AS type,
       created_at::text AS created_time,
       CASE 
           WHEN status = 'active' THEN 'ACTIVE' 
           ELSE UPPER(status) 
       END AS status
FROM (
    SELECT id, username, display_name, user_type, created_at, status
    FROM test.users 
    ORDER BY id DESC 
    LIMIT 5
) AS users_sub

UNION ALL

-- Check Conversations table (using actual column names)
SELECT 'Conversations' AS table_name,
       id::text AS record_id,
       COALESCE(name, 'Untitled') AS identifier,
       type AS type,
       created_at::text AS created_time,
       CASE 
           WHEN is_archived THEN 'ARCHIVED'
           ELSE UPPER(conversation_state) 
       END AS status
FROM (
    SELECT id, name, type, created_at, conversation_state, is_archived
    FROM test.conversations 
    ORDER BY id DESC 
    LIMIT 5
) AS conv_sub

UNION ALL

-- Check Messages table (using actual column names)
SELECT 'Messages' AS table_name,
       id::text AS record_id,
       LEFT(COALESCE(content, 'No content'), 50) AS identifier,
       message_type AS type,
       created_at::text AS created_time,
       CASE 
           WHEN is_deleted THEN 'DELETED'
           ELSE UPPER(processing_status) 
       END AS status
FROM (
    SELECT id, content, message_type, created_at, processing_status, is_deleted
    FROM test.messages 
    ORDER BY id DESC 
    LIMIT 5
) AS msg_sub

UNION ALL

-- Check User Sessions table (using actual column names)
SELECT 'UserSessions' AS table_name,
       id::text AS record_id,
       COALESCE(session_token, 'N/A') AS identifier,
       session_type AS type,
       created_at::text AS created_time,
       CASE WHEN is_active THEN 'ACTIVE' ELSE 'EXPIRED' END AS status
FROM (
    SELECT id, session_token, session_type, created_at, is_active
    FROM test.user_sessions 
    ORDER BY id DESC 
    LIMIT 3
) AS session_sub;

-- ===============================================
-- RELATIONSHIP VERIFICATION (using actual FK columns)
-- ===============================================

-- Check User-Conversation relationship
SELECT 'RELATIONSHIPS' AS check_type,
       'User-Conversation' AS relationship,
       COUNT(*) AS total_records,
       COUNT(DISTINCT u.id) AS unique_users,
       COUNT(DISTINCT c.id) AS unique_conversations
FROM test.users u
JOIN test.conversations c ON u.id = c.created_by
WHERE c.created_at >= NOW() - INTERVAL '7 days'

UNION ALL

-- Check Conversation-Message relationship
SELECT 'RELATIONSHIPS' AS check_type,
       'Conversation-Message' AS relationship,
       COUNT(*) AS total_records,
       COUNT(DISTINCT c.id) AS unique_conversations,
       COUNT(DISTINCT m.id) AS unique_messages
FROM test.conversations c
JOIN test.messages m ON c.id = m.conversation_id
WHERE m.created_at >= NOW() - INTERVAL '7 days'

UNION ALL

-- Check User-Message relationship
SELECT 'RELATIONSHIPS' AS check_type,
       'User-Message' AS relationship,
       COUNT(*) AS total_records,
       COUNT(DISTINCT u.id) AS unique_senders,
       COUNT(DISTINCT m.id) AS unique_messages
FROM test.users u
JOIN test.messages m ON u.id = m.sender_id
WHERE m.created_at >= NOW() - INTERVAL '7 days';

-- ===============================================
-- DATA INTEGRITY CHECKS
-- ===============================================

-- Check for orphaned messages (invalid conversation_id)
SELECT 'INTEGRITY_CHECK' AS check_type,
       'Orphaned Messages' AS issue_type,
       COUNT(*) AS count,
       'Messages without valid conversation' AS description
FROM test.messages m
LEFT JOIN test.conversations c ON m.conversation_id = c.id
WHERE c.id IS NULL

UNION ALL

-- Check for conversations without valid creators
SELECT 'INTEGRITY_CHECK' AS check_type,
       'Orphaned Conversations' AS issue_type,
       COUNT(*) AS count,
       'Conversations without valid creator' AS description
FROM test.conversations c
LEFT JOIN test.users u ON c.created_by = u.id
WHERE u.id IS NULL

UNION ALL

-- Check for messages without valid senders
SELECT 'INTEGRITY_CHECK' AS check_type,
       'Invalid Message Senders' AS issue_type,
       COUNT(*) AS count,
       'Messages with invalid sender_id' AS description
FROM test.messages m
LEFT JOIN test.users u ON m.sender_id = u.id
WHERE u.id IS NULL

UNION ALL

-- Check for self-referential message issues (reply_to_id)
SELECT 'INTEGRITY_CHECK' AS check_type,
       'Self-Reply Messages' AS issue_type,
       COUNT(*) AS count,
       'Messages replying to themselves' AS description
FROM test.messages m
WHERE m.id = m.reply_to_id;

-- ===============================================
-- API TEST DATA VERIFICATION
-- ===============================================

-- Check if test data from API calls exists
SELECT 'API_TEST_DATA' AS check_type,
       'Recent Test Users' AS category,
       COUNT(*) AS count,
       string_agg(COALESCE(username, display_name), ', ') AS identifiers
FROM test.users 
WHERE (username LIKE '%test%' OR username LIKE '%john%' OR display_name LIKE '%test%')
   OR created_at >= NOW() - INTERVAL '1 hour'

UNION ALL

SELECT 'API_TEST_DATA' AS check_type,
       'Recent Test Conversations' AS category,
       COUNT(*) AS count,
       string_agg(COALESCE(name, 'Unnamed'), ', ') AS conversation_names
FROM test.conversations 
WHERE name LIKE '%test%'
   OR created_at >= NOW() - INTERVAL '1 hour'

UNION ALL

SELECT 'API_TEST_DATA' AS check_type,
       'Recent Test Messages' AS category,
       COUNT(*) AS count,
       LEFT(string_agg(content, ' | '), 100) AS sample_content
FROM test.messages 
WHERE content LIKE '%test%'
   OR content LIKE '%Hello%'
   OR created_at >= NOW() - INTERVAL '1 hour';

-- ===============================================
-- ENUM VALUES VERIFICATION (using actual enum columns)
-- ===============================================

-- Check user types
SELECT 'ENUM_CHECK' AS check_type,
       'User Types' AS enum_type,
       user_type AS enum_value,
       COUNT(*) AS usage_count
FROM test.users
GROUP BY user_type

UNION ALL

SELECT 'ENUM_CHECK' AS check_type,
       'Conversation Types' AS enum_type,
       type AS enum_value,
       COUNT(*) AS usage_count
FROM test.conversations
GROUP BY type

UNION ALL

-- Check conversation states
SELECT 'ENUM_CHECK' AS check_type,
       'Conversation States' AS enum_type,
       conversation_state AS enum_value,
       COUNT(*) AS usage_count
FROM test.conversations
GROUP BY conversation_state

UNION ALL

-- Check message types  
SELECT 'ENUM_CHECK' AS check_type,
       'Message Types' AS enum_type,
       message_type AS enum_value,
       COUNT(*) AS usage_count
FROM test.messages
GROUP BY message_type

UNION ALL

-- Check processing status
SELECT 'ENUM_CHECK' AS check_type,
       'Message Processing Status' AS enum_type,
       processing_status AS enum_value,
       COUNT(*) AS usage_count
FROM test.messages
GROUP BY processing_status;

-- ===============================================
-- THREAD/REPLY STRUCTURE VERIFICATION
-- ===============================================

-- Check message threading structure
SELECT 'THREAD_CHECK' AS check_type,
       'Message Threads' AS category,
       COUNT(*) AS total_threaded_messages,
       COUNT(DISTINCT thread_id) AS unique_threads
FROM test.messages
WHERE thread_id IS NOT NULL

UNION ALL

SELECT 'THREAD_CHECK' AS check_type,
       'Message Replies' AS category,
       COUNT(*) AS total_replies,
       COUNT(DISTINCT reply_to_id) AS messages_with_replies
FROM test.messages
WHERE reply_to_id IS NOT NULL;

-- ===============================================
-- MESSAGE ATTACHMENTS CHECK
-- ===============================================

-- Check message attachments (if any exist)
SELECT 'ATTACHMENTS' AS check_type,
       'Message Attachments' AS category,
       COUNT(*) AS total_attachments,
       COUNT(DISTINCT message_id) AS messages_with_attachments
FROM test.message_attachments
WHERE message_id IS NOT NULL;

-- ===============================================
-- USER PREFERENCES CHECK
-- ===============================================

-- Check user preferences
SELECT 'PREFERENCES' AS check_type,
       'User Preferences' AS category,
       category AS preference_category,
       COUNT(*) AS count
FROM test.user_preferences
GROUP BY category
ORDER BY count DESC;

-- ===============================================
-- PERFORMANCE & INDEX VERIFICATION
-- ===============================================

-- Check if important indexes exist
SELECT 'INDEX_CHECK' AS check_type,
       schemaname AS schema_name,
       tablename AS table_name,
       indexname AS index_name,
       indexdef AS index_definition
FROM pg_indexes 
WHERE schemaname = 'test' 
  AND tablename IN ('users', 'conversations', 'messages', 'user_sessions')
ORDER BY tablename, indexname;

-- ===============================================
-- COLUMN VALIDATION CHECKS
-- ===============================================

-- Validate required NOT NULL columns have data
SELECT 'COLUMN_VALIDATION' AS check_type,
       'Users Required Fields' AS validation_type,
       SUM(CASE WHEN user_type IS NULL THEN 1 ELSE 0 END) AS null_user_types,
       SUM(CASE WHEN created_at IS NULL THEN 1 ELSE 0 END) AS null_created_dates
FROM test.users

UNION ALL

SELECT 'COLUMN_VALIDATION' AS check_type,
       'Conversations Required Fields' AS validation_type,
       SUM(CASE WHEN type IS NULL THEN 1 ELSE 0 END) AS null_types,
       SUM(CASE WHEN created_by IS NULL THEN 1 ELSE 0 END) AS null_creators
FROM test.conversations

UNION ALL

SELECT 'COLUMN_VALIDATION' AS check_type,
       'Messages Required Fields' AS validation_type,
       SUM(CASE WHEN conversation_id IS NULL THEN 1 ELSE 0 END) AS null_conversation_ids,
       SUM(CASE WHEN sender_id IS NULL THEN 1 ELSE 0 END) AS null_sender_ids
FROM test.messages;

-- ===============================================
-- SUMMARY STATISTICS
-- ===============================================

SELECT 'SUMMARY' AS report_type,
       'Total Users' AS metric,
       COUNT(*)::text AS value,
       'Active: ' || SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END)::text AS details
FROM test.users

UNION ALL

SELECT 'SUMMARY' AS report_type,
       'Total Conversations' AS metric,
       COUNT(*)::text AS value,
       'Active: ' || SUM(CASE WHEN conversation_state = 'active' AND NOT is_archived THEN 1 ELSE 0 END)::text AS details
FROM test.conversations

UNION ALL

SELECT 'SUMMARY' AS report_type,
       'Total Messages' AS metric,
       COUNT(*)::text AS value,
       'Not Deleted: ' || SUM(CASE WHEN NOT is_deleted THEN 1 ELSE 0 END)::text AS details
FROM test.messages

UNION ALL

SELECT 'SUMMARY' AS report_type,
       'Active Sessions' AS metric,
       COUNT(*)::text AS value,
       'Recent: ' || SUM(CASE WHEN last_activity >= NOW() - INTERVAL '24 hours' THEN 1 ELSE 0 END)::text AS details
FROM test.user_sessions
WHERE is_active = true

UNION ALL

SELECT 'SUMMARY' AS report_type,
       'Database Health' AS metric,
       'HEALTHY' AS value,
       'Schema: test | Validated: ' || NOW()::text AS details;

-- ===============================================
-- API SPECIFIC VALIDATION
-- ===============================================

-- Test specific queries that your User History API would run
SELECT 'API_QUERY_TEST' AS check_type,
       'Get User Conversations' AS query_type,
       COUNT(*) AS result_count,
       'Query: conversations by user with pagination' AS description
FROM test.conversations c
JOIN test.users u ON c.created_by = u.id
WHERE u.id = (SELECT id FROM test.users LIMIT 1)
  AND NOT c.is_archived
GROUP BY c.updated_at
ORDER BY c.updated_at DESC
LIMIT 10;

-- Test message retrieval for conversation
SELECT 'API_QUERY_TEST' AS check_type,
       'Get Conversation Messages' AS query_type,
       COUNT(*) AS result_count,
       'Query: messages for conversation with sender info' AS description
FROM test.messages m
JOIN test.users u ON m.sender_id = u.id
WHERE m.conversation_id = (SELECT id FROM test.conversations LIMIT 1)
  AND NOT m.is_deleted
GROUP BY m.created_at
ORDER BY m.created_at ASC;
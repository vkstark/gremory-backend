from datetime import datetime, timedelta

# Migration utilities
class ChatbotMigrations:
    """Database migration utilities for schema updates."""
    
    def __init__(self, engine):
        self.engine = engine
    
    def add_indexes_if_not_exist(self):
        """Add performance indexes if they don't already exist."""
        with self.engine.connect() as conn:
            # Message indexes
            conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conversation_time 
                ON messages(conversation_id, created_at DESC)
            """)
            
            conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_sender_time 
                ON messages(sender_id, created_at DESC)
            """)
            
            conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_thread 
                ON messages(thread_id, created_at) 
                WHERE thread_id IS NOT NULL
            """)
            
            # Full-text search index
            conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_content_search 
                ON messages USING gin(to_tsvector('english', content))
            """)
            
            # Session management
            conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_active 
                ON user_sessions(user_id, is_active, last_activity DESC)
            """)
            
            # Function call analytics
            conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_function_calls_time_function 
                ON function_call_logs(execution_start_time, function_name)
            """)
            
            conn.commit()
    
    def create_partitions_for_messages(self, months_ahead: int = 6):
        """Create monthly partitions for the messages table."""
        with self.engine.connect() as conn:
            current_date = datetime.utcnow()
            
            for i in range(months_ahead):
                partition_date = current_date + timedelta(days=30 * i)
                year_month = partition_date.strftime('%Y_%m')
                next_month = (partition_date + timedelta(days=32)).replace(day=1)
                
                # Create partition table
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS messages_{year_month} 
                    PARTITION OF messages 
                    FOR VALUES FROM ('{partition_date.strftime('%Y-%m-01')}') 
                    TO ('{next_month.strftime('%Y-%m-01')}')
                """)
            
            conn.commit()


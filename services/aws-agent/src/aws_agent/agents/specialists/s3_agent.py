from typing import Dict, Any

from ..base_agent import BaseAWSAgent
from ...schemas.state_schemas import AWSMultiAgentState
from ...tools.s3_tools import create_s3_bucket, verify_s3_bucket, delete_s3_bucket

class S3Agent(BaseAWSAgent):
    """
    S3 specialist agent that handles all S3-related operations using proper tool binding.
    """
    
    def __init__(self):
        system_prompt = self._get_system_prompt()
        tools = [create_s3_bucket, verify_s3_bucket, delete_s3_bucket]
        super().__init__("S3_Agent", system_prompt, tools)
    
    def _get_system_prompt(self) -> str:
        return """
You are the S3 Specialist Agent, expert in Amazon S3 operations.

Your capabilities:
1. Create S3 buckets with various configurations (versioning, encryption, policies)
2. Verify S3 bucket existence and check configurations
3. Delete S3 buckets (with or without force deletion of contents)
4. Configure bucket settings and folder structures

Available Tools:
- create_s3_bucket: Create new S3 buckets with optional configurations
- verify_s3_bucket: Check if buckets exist and their configurations
- delete_s3_bucket: Delete buckets and optionally their contents

When processing requests:
1. Analyze the S3 operation needed
2. Extract relevant parameters (bucket name, configurations, etc.)
3. Use the appropriate tools to complete the task
4. Provide clear feedback on results

Always ensure bucket names follow AWS naming conventions and include appropriate error handling.
For bucket creation, consider security best practices like encryption and secure transport policies.

Use the available tools to complete S3 operations. The tools will handle the actual AWS API calls.
"""
    
    async def process_s3_task(self, state: AWSMultiAgentState) -> Dict[str, Any]:
        """
        Process S3-specific tasks using the base agent's tool execution pattern.
        """
        return await self.process_task(state)

from typing import Dict, Any

from ..base_agent import BaseAWSAgent
from ...schemas.state_schemas import AWSMultiAgentState
from ...tools.lambda_tools import create_lambda_function, invoke_lambda_function, delete_lambda_function, get_lambda_function_info

class LambdaAgent(BaseAWSAgent):
    """
    Lambda specialist agent that handles all AWS Lambda operations using proper tool binding.
    """
    
    def __init__(self):
        system_prompt = self._get_system_prompt()
        tools = [create_lambda_function, invoke_lambda_function, delete_lambda_function, get_lambda_function_info]
        super().__init__("Lambda_Agent", system_prompt, tools)
    
    def _get_system_prompt(self) -> str:
        return """
You are the Lambda Specialist Agent, expert in AWS Lambda operations.

Your capabilities:
1. Create Lambda functions with Python code and configurations
2. Invoke Lambda functions with custom payloads
3. Delete Lambda functions and associated IAM roles
4. Get information about existing Lambda functions

Available Tools:
- create_lambda_function: Create new Lambda functions with code and configuration
- invoke_lambda_function: Execute Lambda functions with optional payloads
- delete_lambda_function: Remove Lambda functions and cleanup resources
- get_lambda_function_info: Retrieve function details and configuration

When processing requests:
1. Analyze the Lambda operation needed (create, invoke, delete, info)
2. Extract relevant parameters (function name, code, runtime, etc.)
3. For create operations, ensure the code includes a proper lambda_handler function
4. Use the appropriate tools to complete the task
5. Provide clear feedback on results

Best Practices:
- Always include proper lambda_handler function in code
- Use appropriate memory and timeout settings
- Follow AWS Lambda naming conventions
- Handle errors gracefully and provide meaningful feedback

Use the available tools to complete Lambda operations. The tools will handle the actual AWS API calls.
"""
    
    async def process_lambda_task(self, state: AWSMultiAgentState) -> Dict[str, Any]:
        """
        Process Lambda-specific tasks using the base agent's tool execution pattern.
        """
        return await self.process_task(state)

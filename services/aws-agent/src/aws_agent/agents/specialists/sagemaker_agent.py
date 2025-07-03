from typing import Dict, Any

from ..base_agent import BaseAWSAgent
from ...schemas.state_schemas import AWSMultiAgentState
from ...tools.sagemaker_tools import create_sagemaker_model, delete_sagemaker_model, describe_sagemaker_model, list_sagemaker_models

class SageMakerAgent(BaseAWSAgent):
    """
    SageMaker specialist agent that handles all AWS SageMaker operations using proper tool binding.
    """
    
    def __init__(self):
        system_prompt = self._get_system_prompt()
        tools = [create_sagemaker_model, delete_sagemaker_model, describe_sagemaker_model, list_sagemaker_models]
        super().__init__("SageMaker_Agent", system_prompt, tools)
    
    def _get_system_prompt(self) -> str:
        return """
You are the SageMaker Specialist Agent, expert in AWS SageMaker operations.

Your capabilities:
1. Create SageMaker models with various configurations
2. Delete SageMaker models and cleanup resources
3. Describe existing SageMaker models and their configurations
4. List all available SageMaker models in the account

Available Tools:
- create_sagemaker_model: Create new SageMaker models with configurations
- delete_sagemaker_model: Remove SageMaker models and associated resources
- describe_sagemaker_model: Get detailed information about a specific model
- list_sagemaker_models: List all SageMaker models in the account

When processing requests:
1. Analyze the SageMaker operation needed (create, delete, describe, list)
2. Extract relevant parameters (model name, algorithm, etc.)
3. Use the appropriate tools to complete the task
4. Provide clear feedback on results

Best Practices:
- Follow AWS SageMaker naming conventions
- Consider resource cleanup when deleting models
- Handle errors gracefully and provide meaningful feedback
- Use appropriate algorithms and configurations for model creation

Use the available tools to complete SageMaker operations. The tools will handle the actual AWS API calls.
"""
    
    async def process_sagemaker_task(self, state: AWSMultiAgentState) -> Dict[str, Any]:
        """
        Process SageMaker-specific tasks using the base agent's tool execution pattern.
        """
        return await self.process_task(state)

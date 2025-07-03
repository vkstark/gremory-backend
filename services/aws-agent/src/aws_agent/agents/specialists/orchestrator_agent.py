from typing import Dict, Any, List
import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models.base import BaseLanguageModel

from ...utils.model_utils import ModelFactory
from ...schemas.state_schemas import AWSMultiAgentState, TaskAnalysis
from ...schemas.request_schemas import ModelProvider
from ...tools.all_aws_tools import ALL_AWS_TOOLS

class OrchestratorAgent:
    """
    Orchestrator agent that analyzes tasks and routes them to appropriate specialist agents.
    """
    
    def __init__(self):
        self.name = "Orchestrator"
        self.system_prompt = self._get_system_prompt()
    
    def _get_system_prompt(self) -> str:
        return """
You are the AWS Orchestrator Agent, responsible for analyzing user requests and routing them to the appropriate AWS specialist agents.

Your responsibilities:
1. Analyze incoming tasks to understand what AWS services are needed
2. Determine the complexity and requirements of the task
3. Route tasks to the appropriate specialist agents (S3, Lambda, SageMaker)
4. Coordinate multi-service tasks that require multiple specialists
5. Provide clear task breakdown and execution planning

Available Specialist Agents:
- s3_specialist: Handles S3 bucket operations (create, verify, delete, configure)
- lambda_specialist: Handles Lambda function operations (create, invoke, delete, manage)
- sagemaker_specialist: Handles SageMaker model operations (create, describe, delete, list)

When analyzing tasks:
- Identify the primary AWS service needed
- Determine if multiple services are required
- Assess task complexity (0.0 to 1.0 scale)
- Provide step-by-step breakdown
- Estimate execution time

Respond with a JSON object containing:
- primary_service: The main AWS service needed (s3, lambda, sagemaker)
- secondary_services: List of additional services that might be needed
- complexity_score: Task complexity from 0.0 (simple) to 1.0 (complex)
- recommended_specialist: Which specialist agent to use (s3_specialist, lambda_specialist, sagemaker_specialist)
- task_breakdown: List of steps to complete the task
- estimated_execution_time: Estimated time in seconds
- requires_coordination: Whether multiple agents are needed
"""
    
    async def analyze_task(self, state: AWSMultiAgentState) -> Dict[str, Any]:
        """
        Analyze the task and determine routing strategy.
        """
        model = ModelFactory.create_model(
            model_name=state["model_name"],
            model_provider=ModelProvider(state["model_provider"]),
            temperature=state["temperature"],
            max_tokens=state["max_tokens"]
        )
        
        # Create analysis prompt
        analysis_prompt = f"""
Task Description: {state['task_description']}

Service Preferences: {state.get('service_preferences', 'None specified')}

Additional Context: {state.get('additional_context', 'None provided')}

Analyze this task and provide routing recommendations in the following JSON format:
{{
    "primary_service": "s3|lambda|sagemaker",
    "secondary_services": ["service1", "service2"],
    "complexity_score": 0.0-1.0,
    "recommended_specialist": "s3_specialist|lambda_specialist|sagemaker_specialist",
    "task_breakdown": ["step1", "step2", "step3"],
    "estimated_execution_time": seconds,
    "requires_coordination": true/false,
    "reasoning": "Explanation of the analysis"
}}
"""
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=analysis_prompt)
        ]
        
        try:
            response = await model.ainvoke(messages)
            
            # Log the raw response for debugging
            print(f"DEBUG: Orchestrator raw response: {response.content}")
            
            # Try to parse JSON response
            analysis_data = json.loads(response.content)
            
            # Validate the analysis
            task_analysis = TaskAnalysis(**analysis_data)
            
            return {
                "success": True,
                "analysis": task_analysis.dict(),
                "raw_response": response.content
            }
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"DEBUG: Orchestrator analysis failed: {str(e)}")
            # Fallback analysis if JSON parsing fails or other errors
            return self._fallback_analysis(state)
    
    def _fallback_analysis(self, state: AWSMultiAgentState) -> Dict[str, Any]:
        """
        Provide fallback analysis based on simple keyword matching.
        """
        task_description = state['task_description'].lower()
        
        # Simple keyword-based routing
        if any(keyword in task_description for keyword in ['bucket', 's3', 'storage', 'upload', 'download']):
            primary_service = "s3"
            recommended_specialist = "s3_specialist"
        elif any(keyword in task_description for keyword in ['lambda', 'function', 'serverless', 'invoke', 'code']):
            primary_service = "lambda"
            recommended_specialist = "lambda_specialist"
        elif any(keyword in task_description for keyword in ['sagemaker', 'model', 'ml', 'machine learning', 'train']):
            primary_service = "sagemaker"
            recommended_specialist = "sagemaker_specialist"
        else:
            # Default to S3 if unclear
            primary_service = "s3"
            recommended_specialist = "s3_specialist"
        
        analysis = TaskAnalysis(
            primary_service=primary_service,
            secondary_services=[],
            complexity_score=0.5,
            recommended_specialist=recommended_specialist,
            task_breakdown=[
                "Analyze task requirements",
                f"Execute {primary_service} operations",
                "Return results"
            ],
            estimated_execution_time=30.0,
            requires_coordination=False
        )
        
        return {
            "success": True,
            "analysis": analysis.dict(),
            "raw_response": "Fallback analysis used"
        }
    
    async def create_task_summary(self, state: AWSMultiAgentState) -> str:
        """
        Create a summary of the completed task.
        """
        model = ModelFactory.create_model(
            model_name=state["model_name"],
            model_provider=ModelProvider(state["model_provider"]),
            temperature=state["temperature"],
            max_tokens=state["max_tokens"]
        )
        
        summary_prompt = f"""
Create a comprehensive summary of the AWS task execution:

Original Task: {state['task_description']}
Execution Path: {' -> '.join(state['execution_path'])}
Final Result: {state.get('final_result', {})}

Provide a clear, professional summary including:
1. What was requested
2. What was accomplished
3. Any important details or configurations
4. Success/failure status
5. Next steps or recommendations (if applicable)

Keep the summary concise but informative.
"""
        
        messages = [
            SystemMessage(content="You are a helpful assistant that creates clear, professional summaries of AWS task executions."),
            HumanMessage(content=summary_prompt)
        ]
        
        try:
            response = await model.ainvoke(messages)
            return response.content
        except Exception as e:
            final_result = state.get('final_result') or {}
            success = final_result.get('success', False) if isinstance(final_result, dict) else False
            return f"Task completed. Original request: {state['task_description']}. Execution path: {' -> '.join(state['execution_path'])}. Status: {'Success' if success else 'Failed'}"

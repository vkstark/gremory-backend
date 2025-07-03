from typing import Dict, List, Optional, Any, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
import operator

class AgentState(TypedDict):
    """Base state for all agents"""
    messages: Annotated[List[BaseMessage], "The list of messages in the conversation"]
    model_name: str
    model_provider: str
    temperature: float
    max_tokens: int
    current_agent: Optional[str]
    execution_path: List[str]
    task_description: str
    service_preferences: Optional[List[str]]
    additional_context: Optional[Dict[str, Any]]

class AgentTask(BaseModel):
    """Individual task for a specialist agent"""
    agent_name: str = Field(..., description="Name of the agent assigned to this task")
    task_id: str = Field(..., description="Unique identifier for this task")
    task_description: str = Field(..., description="Description of the task")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs this task depends on")
    status: str = Field(default="pending", description="Status: pending, in_progress, completed, failed")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Result of the task execution")
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    priority: int = Field(default=0, description="Task priority (higher number = higher priority)")

class ConversationTurn(BaseModel):
    """A single turn in agent conversation"""
    turn_id: int = Field(..., description="Turn number")
    agent_name: str = Field(..., description="Agent that spoke in this turn")
    message: str = Field(..., description="Message content")
    action_taken: Optional[str] = Field(default=None, description="Action taken in this turn")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Result of the action")
    
class OrchestratorState(AgentState):
    """State for the orchestrator agent"""
    assigned_specialist: Optional[str]
    task_analysis: Optional[Dict[str, Any]]
    specialist_recommendations: Optional[List[str]]
    
class S3AgentState(AgentState):
    """State for the S3 specialist agent"""
    s3_action: Optional[str]
    bucket_name: Optional[str]
    bucket_config: Optional[Dict[str, Any]]
    s3_result: Optional[Dict[str, Any]]
    
class LambdaAgentState(AgentState):
    """State for the Lambda specialist agent"""
    lambda_action: Optional[str]
    function_name: Optional[str]
    function_code: Optional[str]
    function_config: Optional[Dict[str, Any]]
    lambda_result: Optional[Dict[str, Any]]
    
class SageMakerAgentState(AgentState):
    """State for the SageMaker specialist agent"""
    sagemaker_action: Optional[str]
    sagemaker_model_name: Optional[str]
    model_config: Optional[Dict[str, Any]]
    sagemaker_result: Optional[Dict[str, Any]]
    
class AWSMultiAgentState(TypedDict):
    """Complete state for the AWS multi-agent system"""
    # Core execution state
    messages: Annotated[List[BaseMessage], "The list of messages in the conversation"]
    model_name: str
    model_provider: str
    temperature: float
    max_tokens: int
    current_agent: Optional[str]
    execution_path: List[str]
    
    # Task information
    task_description: str
    service_preferences: Optional[List[str]]
    additional_context: Optional[Dict[str, Any]]
    
    # Orchestrator state
    assigned_specialist: Optional[str]
    task_analysis: Optional[Dict[str, Any]]
    specialist_recommendations: Optional[List[str]]
    
    # S3 agent state
    s3_action: Optional[str]
    bucket_name: Optional[str]
    bucket_config: Optional[Dict[str, Any]]
    s3_result: Optional[Dict[str, Any]]
    
    # Lambda agent state
    lambda_action: Optional[str]
    function_name: Optional[str]
    function_code: Optional[str]
    function_config: Optional[Dict[str, Any]]
    lambda_result: Optional[Dict[str, Any]]
    
    # SageMaker agent state
    sagemaker_action: Optional[str]
    sagemaker_model_name: Optional[str]
    model_config: Optional[Dict[str, Any]]
    sagemaker_result: Optional[Dict[str, Any]]
    
    # Final results
    final_result: Optional[Dict[str, Any]]
    completed: bool
    
class TaskAnalysis(BaseModel):
    """Analysis of a task by the orchestrator"""
    primary_service: str = Field(..., description="Primary AWS service needed")
    secondary_services: List[str] = Field(default_factory=list, description="Secondary services that might be needed")
    complexity_score: float = Field(..., description="Task complexity from 0-1")
    recommended_specialist: List[str] = Field(..., description="Recommended specialist agent")
    task_breakdown: List[str] = Field(..., description="Breakdown of task steps")
    estimated_execution_time: float = Field(..., description="Estimated execution time in seconds")
    requires_coordination: bool = Field(default=False, description="Whether multiple agents are needed")

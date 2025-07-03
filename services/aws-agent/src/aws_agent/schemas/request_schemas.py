from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum

class ModelProvider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google" 
    OLLAMA = "ollama"

class AWSServiceType(str, Enum):
    S3 = "s3"
    LAMBDA = "lambda"
    SAGEMAKER = "sagemaker"

class TaskRequest(BaseModel):
    """Base request model for AWS tasks"""
    model_name: str = Field(..., description="Name of the LLM model to use")
    model_provider: ModelProvider = Field(default=ModelProvider.OPENAI, description="Model provider")
    temperature: Optional[float] = Field(default=0.1, description="Model temperature")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum tokens for response")
    
class AWSTaskRequest(TaskRequest):
    """Request model for AWS tasks"""
    task_description: str = Field(..., description="Description of the AWS task to perform")
    service_preferences: Optional[List[AWSServiceType]] = Field(default=None, description="Preferred AWS services to use")
    additional_context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for the task")

class S3TaskRequest(TaskRequest):
    """Request model for S3-specific tasks"""
    action: str = Field(..., description="S3 action to perform (create, verify, delete)")
    bucket_name: Optional[str] = Field(default=None, description="S3 bucket name")
    enable_versioning: Optional[bool] = Field(default=False, description="Enable versioning")
    enable_encryption: Optional[bool] = Field(default=True, description="Enable encryption")
    create_folders: Optional[List[str]] = Field(default=None, description="Folders to create")
    force_delete: Optional[bool] = Field(default=False, description="Force delete bucket")

class LambdaTaskRequest(TaskRequest):
    """Request model for Lambda-specific tasks"""
    action: str = Field(..., description="Lambda action to perform (create, invoke, delete)")
    function_name: Optional[str] = Field(default=None, description="Lambda function name")
    code: Optional[str] = Field(default=None, description="Lambda function code")
    runtime: Optional[str] = Field(default="python3.12", description="Lambda runtime")
    handler: Optional[str] = Field(default="lambda_function.lambda_handler", description="Lambda handler")
    timeout: Optional[int] = Field(default=30, description="Function timeout")
    memory_size: Optional[int] = Field(default=128, description="Function memory size")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Payload for invoke action")

class SageMakerTaskRequest(TaskRequest):
    """Request model for SageMaker-specific tasks"""
    action: str = Field(..., description="SageMaker action to perform (create, describe, delete)")
    model_name: Optional[str] = Field(default=None, description="SageMaker model name")
    algorithm: Optional[str] = Field(default="xgboost", description="Algorithm to use")
    model_data_url: Optional[str] = Field(default=None, description="S3 URL of model artifacts")
    environment_variables: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")

class TaskResponse(BaseModel):
    """Response model for AWS tasks"""
    success: bool = Field(..., description="Whether the task was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    execution_path: Optional[List[str]] = Field(default=None, description="Execution path through agents")
    model_used: Optional[str] = Field(default=None, description="Model used for the task")
    total_execution_time: Optional[float] = Field(default=None, description="Total execution time in seconds")

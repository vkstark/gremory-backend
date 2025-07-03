"""
AWS Multi-Agent Service

A sophisticated multi-agent system for AWS operations using LangGraph.
Provides orchestrated AWS operations through specialized agents for S3, Lambda, and SageMaker.
"""

from .graph.aws_multi_agent_graph import aws_multi_agent_graph
from .schemas.request_schemas import (
    AWSTaskRequest,
    S3TaskRequest, 
    LambdaTaskRequest,
    SageMakerTaskRequest,
    TaskResponse,
    ModelProvider,
    AWSServiceType
)

__version__ = "1.0.0"
__all__ = [
    "aws_multi_agent_graph",
    "AWSTaskRequest",
    "S3TaskRequest",
    "LambdaTaskRequest", 
    "SageMakerTaskRequest",
    "TaskResponse",
    "ModelProvider",
    "AWSServiceType"
]
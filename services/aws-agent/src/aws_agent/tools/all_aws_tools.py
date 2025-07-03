from typing import Dict, Any, List
from langchain_core.tools import tool

# Import all AWS tools
from .s3_tools import create_s3_bucket, verify_s3_bucket, delete_s3_bucket
from .lambda_tools import create_lambda_function, invoke_lambda_function, delete_lambda_function, get_lambda_function_info
from .sagemaker_tools import create_sagemaker_model, delete_sagemaker_model, describe_sagemaker_model, list_sagemaker_models

# Compile all AWS tools into a single list
ALL_AWS_TOOLS = [
    # S3 Tools
    create_s3_bucket,
    verify_s3_bucket,
    delete_s3_bucket,
    
    # Lambda Tools
    create_lambda_function,
    invoke_lambda_function,
    delete_lambda_function,
    get_lambda_function_info,
    
    # SageMaker Tools
    create_sagemaker_model,
    delete_sagemaker_model,
    describe_sagemaker_model,
    list_sagemaker_models
]

def get_aws_tools_dict() -> Dict[str, Any]:
    """Get AWS tools as a dictionary mapped by name."""
    return {tool.name.lower(): tool for tool in ALL_AWS_TOOLS}

def get_aws_tools_info() -> List[Dict[str, Any]]:
    """Get information about all AWS tools."""
    tools_info = []
    for tool in ALL_AWS_TOOLS:
        tool_info = {
            "name": tool.name,
            "description": tool.description,
            "args_schema": getattr(tool, 'args_schema', None)
        }
        tools_info.append(tool_info)
    return tools_info

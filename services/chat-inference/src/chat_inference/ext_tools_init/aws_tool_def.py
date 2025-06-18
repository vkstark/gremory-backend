from typing import Optional

from langchain_core.tools import tool

@tool
def create_s3_bucket_tool(
    bucket_name: str,
    enable_versioning: bool = False,
    enable_encryption: bool = True,
    create_folders: str = "",
    add_policy: bool = False
) -> Optional[str]:
    """
    Create an S3 bucket with optional configurations.
    
    This tool creates a new S3 bucket in AWS with various optional features like versioning,
    encryption, folder structure, and security policies.
    
    Args:
        bucket_name: Name of the S3 bucket to create
        OPTIONAL enable_versioning: Whether to enable versioning on the bucket
        OPTIONAL enable_encryption: Whether to enable server-side encryption
        OPTIONAL create_folders: Comma-separated list of folder paths to create (e.g., "data/raw/,data/processed/,logs/")
        OPTIONAL add_policy: Whether to add a secure transport policy
        
    Returns:
        JSON string with creation result and bucket details
    """
    pass

@tool
def verify_s3_bucket_tool(bucket_name: str, check_contents: bool = True) -> Optional[str]:
    """
    Verify that an S3 bucket exists and check its configuration and contents.
    
    This tool checks if an S3 bucket exists, verifies its configuration (versioning, encryption),
    and optionally lists its contents.
    
    Args:
        bucket_name: Name of the S3 bucket to verify
        check_contents: Whether to list and return bucket contents
        
    Returns:
        JSON string with verification result and bucket details
    """
    pass

@tool
def delete_s3_bucket_tool(bucket_name: str, force_delete: bool = False) -> Optional[str]:
    """
    Delete an S3 bucket and optionally all its contents.
    
    This tool deletes an S3 bucket. If the bucket contains objects, you can use force_delete
    to automatically delete all objects and versions before deleting the bucket.
    
    Args:
        bucket_name: Name of the S3 bucket to delete
        force_delete: Whether to delete all objects and versions before deleting bucket
        
    Returns:
        JSON string with deletion result and details
    """
    pass


# ==== SAGE MAKER TOOLS ====
@tool
def create_sagemaker_model_tool(
    model_name: str,
    algorithm: str = "xgboost",
    model_data_url: str = "",
    environment_variables: str = "",
    tags: str = ""
) -> Optional[str]:
    """
    Create a SageMaker model with the specified configuration.
    
    This tool creates a new AWS SageMaker model using built-in algorithms,
    automatically creating the necessary IAM role and container configuration.
    
    Args:
        model_name: Name of the SageMaker model to create
        OPTIONAL algorithm: Algorithm to use (xgboost, linear-learner). Defaults to "xgboost".
        model_data_url: S3 URL of model artifacts (optional)
        OPTIONAL environment_variables: JSON string of environment variables (e.g., '{"KEY": "value"}')
        OPTIONAL tags: JSON string of tags (e.g., '[{"Key": "Environment", "Value": "Test"}]')
        
    Returns:
        JSON string with creation result and model details
    """
    pass

@tool
def describe_sagemaker_model_tool(model_name: str) -> Optional[str]:
    """
    Describe a SageMaker model and verify it exists.
    
    This tool retrieves detailed information about an AWS SageMaker model,
    including its configuration, container details, and execution role.
    
    Args:
        model_name: Name of the SageMaker model to describe
        
    Returns:
        JSON string with model description and verification details
    """
    pass

@tool
def delete_sagemaker_model_tool(model_name: str, delete_role: bool = True) -> Optional[str]:
    """
    Delete a SageMaker model and optionally its IAM role.
    
    This tool deletes an AWS SageMaker model and can also remove the associated
    IAM execution role that was created with the model.
    
    Args:
        model_name: Name of the SageMaker model to delete
        OPTIONAL delete_role: Whether to delete the associated IAM role
        
    Returns:
        JSON string with deletion result and details
    """
    pass


# ==== LAMBDA TOOLS ====
@tool
def create_lambda_function_tool(
    function_name: str,
    code: str,
    runtime: str = "python3.12",
    handler: str = "lambda_function.lambda_handler",
    timeout: int = 30,
    memory_size: int = 128,
    environment_variables: str = "",
    description: str = ""
) -> Optional[str]:
    """
    Create a Lambda function with the specified code and configuration.
    
    This tool creates a new AWS Lambda function with the provided Python code,
    automatically creating the necessary IAM role and deployment package.
    
    Args:
        function_name: Name of the Lambda function to create
        code: Python code for the Lambda function (must include lambda_handler function)
        OPTIONAL runtime: Lambda runtime version (default: python3.9)
        OPTIONAL handler: Function handler (default: lambda_function.lambda_handler)
        OPTIONAL timeout: Function timeout in seconds (default: 30)
        OPTIONAL memory_size: Function memory in MB (default: 128)
        OPTIONAL environment_variables: JSON string of environment variables (e.g., '{"KEY": "value"}')
        OPTIONAL description: Description of the Lambda function
        
    Returns:
        JSON string with creation result and function details
    """
    pass

@tool
def invoke_lambda_function_tool(
    function_name: str,
    payload: str = "",
    invocation_type: str = "RequestResponse"
) -> Optional[str]:
    """
    Invoke a Lambda function and return the result.
    
    This tool invokes an AWS Lambda function with an optional payload and returns
    the execution result, including response data and logs.
    
    Args:
        function_name: Name of the Lambda function to invoke
        OPTIONAL payload: JSON string payload to send to the function (e.g., '{"key": "value"}')
        OPTIONAL invocation_type: Type of invocation (RequestResponse, Event, DryRun). Default is RequestResponse.
        
    Returns:
        JSON string with invocation result and response details
    """
    pass

@tool
def delete_lambda_function_tool(function_name: str, delete_role: bool = True) -> Optional[str]:
    """
    Delete a Lambda function and optionally its IAM role.
    
    This tool deletes an AWS Lambda function and can also remove the associated
    IAM execution role that was created with the function.
    
    Args:
        function_name: Name of the Lambda function to delete
        OPTIONAL delete_role: Whether to delete the associated IAM role. Default is True.
        
    Returns:
        JSON string with deletion result and details
    """
    pass
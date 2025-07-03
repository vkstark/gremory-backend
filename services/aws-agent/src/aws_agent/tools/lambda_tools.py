#!/usr/bin/env python3
"""
Lambda Service Operations for AWS Multi-Agent System
Provides create, verify/invoke, and delete operations for Lambda functions
"""

import boto3
import json
import time
import zipfile
import tempfile
import os
from datetime import datetime
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool

class LambdaService:
    def __init__(self):
        """Initialize Lambda service client and get AWS account information."""
        self.lambda_client = boto3.client('lambda')
        self.iam = boto3.client('iam')
        self.sts = boto3.client('sts')
        
        self.account_id = self.sts.get_caller_identity()['Account']
        self.region = boto3.Session().region_name or 'us-east-1'
    
    def _create_lambda_execution_role(self, role_name: str) -> str:
        """Create an IAM role for Lambda execution with proper permissions."""
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        try:
            response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f'Execution role for Lambda function'
            )
            
            # Attach basic execution policy
            self.iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
            )
            
            return response['Role']['Arn']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                return f'arn:aws:iam::{self.account_id}:role/{role_name}'
            raise e
    
    def _delete_lambda_execution_role(self, role_name: str):
        """Delete the IAM role created for Lambda execution."""
        try:
            # Detach policies
            response = self.iam.list_attached_role_policies(RoleName=role_name)
            for policy in response['AttachedPolicies']:
                self.iam.detach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy['PolicyArn']
                )
            
            # Delete role
            self.iam.delete_role(RoleName=role_name)
            
        except ClientError:
            pass  # Role might not exist or already deleted
    
    def _create_lambda_package(self, code: str, handler_file: str = "lambda_function.py") -> str:
        """Create a Lambda deployment package from code string."""
        # Create temporary zip file
        temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        temp_zip.close()
        
        with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
            zip_file.writestr(handler_file, code)
        
        return temp_zip.name
    
    def create_lambda_function(
        self,
        function_name: str,
        code: str,
        runtime: str = "python3.9",
        handler: str = "lambda_function.lambda_handler",
        timeout: int = 30,
        memory_size: int = 128,
        environment_variables: Optional[Dict[str, str]] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a Lambda function with the specified code and configuration."""
        # Create unique function name
        full_function_name = f"{function_name}-gremory-test"
        role_name = f"{function_name}-role-gremory-test"
        zip_path = None
        
        try:
            # Create IAM role
            role_arn = self._create_lambda_execution_role(role_name)
            
            # Wait for role propagation
            time.sleep(10)
            
            # Create deployment package
            zip_path = self._create_lambda_package(code)
            
            # Prepare function configuration
            function_config = {
                'FunctionName': full_function_name,
                'Runtime': runtime,
                'Role': role_arn,
                'Handler': handler,
                'Description': description or f'Lambda function {function_name}',
                'Timeout': timeout,
                'MemorySize': memory_size
            }
            
            # Add environment variables if provided
            if environment_variables:
                function_config['Environment'] = {'Variables': environment_variables}
            
            # Read zip file and create function
            with open(zip_path, 'rb') as zip_file:
                function_config['Code'] = {'ZipFile': zip_file.read()}
                response = self.lambda_client.create_function(**function_config)
            
            # Clean up zip file
            os.unlink(zip_path)
            
            return {
                'success': True,
                'function_name': full_function_name,
                'function_arn': response['FunctionArn'],
                'runtime': response['Runtime'],
                'handler': response['Handler'],
                'role_arn': role_arn,
                'role_name': role_name,
                'timeout': response['Timeout'],
                'memory_size': response['MemorySize'],
                'code_size': response['CodeSize'],
                'state': response['State'],
                'message': f'Lambda function {full_function_name} created successfully'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # Cleanup on failure
            try:
                self._delete_lambda_execution_role(role_name)
                if zip_path and os.path.exists(zip_path):
                    os.unlink(zip_path)
            except:
                pass
                
            if error_code == 'ResourceConflictException':
                return {
                    'success': False,
                    'function_name': full_function_name,
                    'error_code': error_code,
                    'message': f'Lambda function {full_function_name} already exists'
                }
            else:
                return {
                    'success': False,
                    'function_name': full_function_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to create Lambda function {full_function_name}'
                }
    
    def invoke_lambda_function(
        self,
        function_name: str,
        payload: Optional[Dict] = None,
        invocation_type: str = "RequestResponse"
    ) -> Dict[str, Any]:
        """Invoke a Lambda function and return the result."""
        # Create full function name
        full_function_name = function_name
        if not full_function_name.endswith('-gremory-test'):
            full_function_name = f"{function_name}-gremory-test"
        
        try:
            # Prepare invocation parameters
            invoke_params = {
                'FunctionName': full_function_name,
                'InvocationType': invocation_type
            }
            
            # Add payload if provided
            if payload:
                invoke_params['Payload'] = json.dumps(payload)
            
            # Invoke function
            response = self.lambda_client.invoke(**invoke_params)
            
            # Parse response
            status_code = response['StatusCode']
            
            result = {
                'success': True,
                'function_name': full_function_name,
                'status_code': status_code,
                'invocation_type': invocation_type,
                'executed_version': response.get('ExecutedVersion', '$LATEST')
            }
            
            # Read response payload if present
            if 'Payload' in response:
                payload_data = response['Payload'].read().decode('utf-8')
                try:
                    result['response_payload'] = json.loads(payload_data)
                except json.JSONDecodeError:
                    result['response_payload'] = payload_data
            
            # Check for function errors
            if 'FunctionError' in response:
                result['function_error'] = response['FunctionError']
                result['success'] = False
                result['message'] = f'Lambda function {full_function_name} executed with error: {response["FunctionError"]}'
            else:
                result['message'] = f'Lambda function {full_function_name} executed successfully'
            
            # Add log result if available
            if 'LogResult' in response:
                import base64
                log_data = base64.b64decode(response['LogResult']).decode('utf-8')
                result['log_result'] = log_data
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                return {
                    'success': False,
                    'function_name': full_function_name,
                    'error_code': error_code,
                    'message': f'Lambda function {full_function_name} not found'
                }
            else:
                return {
                    'success': False,
                    'function_name': full_function_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to invoke Lambda function {full_function_name}'
                }
    
    def delete_lambda_function(self, function_name: str, delete_role: bool = True) -> Dict[str, Any]:
        """Delete a Lambda function and optionally its IAM role."""
        # Create full function name and role name
        full_function_name = function_name
        if not full_function_name.endswith('-gremory-test'):
            full_function_name = f"{function_name}-gremory-test"

        role_name = f"{function_name}-role-gremory-test"
        
        try:
            # Delete Lambda function
            self.lambda_client.delete_function(FunctionName=full_function_name)
            
            result = {
                'success': True,
                'function_name': full_function_name,
                'role_deleted': False,
                'message': f'Lambda function {full_function_name} deleted successfully'
            }
            
            # Delete IAM role if requested
            if delete_role:
                try:
                    self._delete_lambda_execution_role(role_name)
                    result['role_deleted'] = True
                    result['role_name'] = role_name
                    result['message'] += f' and IAM role {role_name} deleted'
                except Exception as e:
                    result['role_deletion_error'] = str(e)
                    result['message'] += f' but failed to delete IAM role: {str(e)}'
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                return {
                    'success': True,
                    'function_name': full_function_name,
                    'message': f'Lambda function {full_function_name} does not exist (already deleted)'
                }
            else:
                return {
                    'success': False,
                    'function_name': full_function_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to delete Lambda function {full_function_name}'
                }

@tool
def create_lambda_function(
    function_name: str,
    code: str,
    runtime: str = "python3.12",
    handler: str = "lambda_function.lambda_handler",
    timeout: int = 30,
    memory_size: int = 128,
    environment_variables: str = "",
    description: str = ""
) -> str:
    """
    Create a Lambda function with the specified code and configuration.
    
    Args:
        function_name: Name of the Lambda function to create
        code: Python code for the Lambda function (must include lambda_handler function)
        runtime: Lambda runtime version (default: python3.12)
        handler: Function handler (default: lambda_function.lambda_handler)
        timeout: Function timeout in seconds (default: 30)
        memory_size: Function memory in MB (default: 128)
        environment_variables: JSON string of environment variables (e.g., '{"KEY": "value"}')
        description: Description of the Lambda function
        
    Returns:
        JSON string with creation result and function details
    """
    lambda_service = LambdaService()
    
    # Parse environment variables if provided
    env_vars = None
    if environment_variables:
        try:
            env_vars = json.loads(environment_variables)
        except json.JSONDecodeError:
            env_vars = None
    
    result = lambda_service.create_lambda_function(
        function_name, code, runtime, handler, timeout, memory_size, env_vars, description
    )
    return json.dumps(result, indent=2)

@tool
def invoke_lambda_function(
    function_name: str,
    payload: str = "",
    invocation_type: str = "RequestResponse"
) -> str:
    """
    Invoke a Lambda function and return the result.
    
    Args:
        function_name: Name of the Lambda function to invoke
        payload: JSON string payload to send to the function (e.g., '{"key": "value"}')
        invocation_type: Type of invocation (RequestResponse, Event, DryRun)
        
    Returns:
        JSON string with invocation result and response details
    """
    lambda_service = LambdaService()
    
    # Parse payload if provided
    payload_dict = None
    if payload:
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError:
            payload_dict = {"message": payload}  # Fallback to simple message
    
    result = lambda_service.invoke_lambda_function(function_name, payload_dict, invocation_type)
    return json.dumps(result, indent=2)

@tool
def delete_lambda_function(function_name: str, delete_role: bool = True) -> str:
    """
    Delete a Lambda function and optionally its IAM role.
    
    Args:
        function_name: Name of the Lambda function to delete
        delete_role: Whether to delete the associated IAM role
        
    Returns:
        JSON string with deletion result and details
    """
    lambda_service = LambdaService()
    result = lambda_service.delete_lambda_function(function_name, delete_role)
    return json.dumps(result, indent=2)

@tool
def get_lambda_function_info(function_name: str) -> str:
    """
    Get information about a Lambda function.
    
    Args:
        function_name: Name of the Lambda function to get information about
        
    Returns:
        JSON string with function information
    """
    lambda_service = LambdaService()
    # Use dry run invocation to get function info without executing
    result = lambda_service.invoke_lambda_function(function_name, None, "DryRun")
    return json.dumps(result, indent=2)

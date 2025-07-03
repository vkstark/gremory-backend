#!/usr/bin/env python3
"""
SageMaker Service Operations for AWS Multi-Agent System
Provides create, verify, and delete operations for SageMaker models
"""

import boto3
import json
import time
from datetime import datetime
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool

class SageMakerService:
    def __init__(self):
        """Initialize SageMaker service client and get AWS account information."""
        self.sagemaker = boto3.client('sagemaker')
        self.iam = boto3.client('iam')
        self.sts = boto3.client('sts')
        
        self.account_id = self.sts.get_caller_identity()['Account']
        self.region = boto3.Session().region_name or 'us-east-1'
    
    def _create_sagemaker_execution_role(self, role_name: str) -> str:
        """Create an IAM role for SageMaker execution with proper permissions."""
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "sagemaker.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # Custom policy for SageMaker operations
        sagemaker_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        "arn:aws:s3:::*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams"
                    ],
                    "Resource": "arn:aws:logs:*:*:*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        try:
            # Create role
            response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f'Execution role for SageMaker model'
            )
            
            # Attach managed policies
            managed_policies = [
                'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess',
                'arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly'
            ]
            
            for policy_arn in managed_policies:
                try:
                    self.iam.attach_role_policy(
                        RoleName=role_name,
                        PolicyArn=policy_arn
                    )
                except ClientError as e:
                    print(f"Warning: Could not attach policy {policy_arn}: {e}")
            
            # Create and attach custom policy
            custom_policy_name = f"{role_name}CustomPolicy"
            try:
                self.iam.create_policy(
                    PolicyName=custom_policy_name,
                    PolicyDocument=json.dumps(sagemaker_policy),
                    Description='Custom policy for SageMaker model execution'
                )
                
                self.iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=f'arn:aws:iam::{self.account_id}:policy/{custom_policy_name}'
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'EntityAlreadyExists':
                    print(f"Warning: Could not create custom policy: {e}")
            
            return response['Role']['Arn']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                return f'arn:aws:iam::{self.account_id}:role/{role_name}'
            raise e
    
    def _delete_sagemaker_execution_role(self, role_name: str):
        """Delete the IAM role created for SageMaker execution."""
        try:
            # Detach managed policies
            response = self.iam.list_attached_role_policies(RoleName=role_name)
            for policy in response['AttachedPolicies']:
                self.iam.detach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy['PolicyArn']
                )
            
            # Delete custom policy
            custom_policy_name = f"{role_name}CustomPolicy"
            try:
                self.iam.delete_policy(
                    PolicyArn=f'arn:aws:iam::{self.account_id}:policy/{custom_policy_name}'
                )
            except ClientError:
                pass  # Policy might not exist
            
            # Delete role
            self.iam.delete_role(RoleName=role_name)
            
        except ClientError:
            pass  # Role might not exist or already deleted
    
    def _get_sagemaker_container_uris(self) -> List[str]:
        """Get available SageMaker container URIs for different algorithms."""
        # XGBoost algorithm container mapping
        xgboost_mapping = {
            'us-east-1': '683313688378',
            'us-east-2': '257758044811',
            'us-west-1': '632365934929',
            'us-west-2': '246618743249',
            'eu-west-1': '685385470294',
            'eu-central-1': '813361260812',
            'ap-southeast-1': '475088953585',
            'ap-southeast-2': '544295431143',
            'ap-northeast-1': '501404015308',
            'ap-northeast-2': '306986355934',
            'ap-south-1': '720646828776',
            'ca-central-1': '469771592824',
            'eu-north-1': '662702820516',
            'eu-west-2': '764974769150',
            'eu-west-3': '659782779980',
            'sa-east-1': '737474898029'
        }
        
        # Linear learner container mapping
        linear_learner_mapping = {
            'us-east-1': '382416733822',
            'us-east-2': '404615174143',
            'us-west-1': '632365934929',
            'us-west-2': '174872318107',
            'eu-west-1': '438346466558',
            'eu-central-1': '664544806723',
            'ap-southeast-1': '475088953585',
            'ap-southeast-2': '712309505854',
            'ap-northeast-1': '351501993468'
        }
        
        container_uris = []
        
        # Add XGBoost containers
        if self.region in xgboost_mapping:
            account_id = xgboost_mapping[self.region]
            container_uris.append(f"{account_id}.dkr.ecr.{self.region}.amazonaws.com/xgboost:latest")
        
        # Add linear learner containers
        if self.region in linear_learner_mapping:
            account_id = linear_learner_mapping[self.region]
            container_uris.append(f"{account_id}.dkr.ecr.{self.region}.amazonaws.com/linear-learner:latest")
        
        # Fallback to us-east-1 XGBoost if no regional mapping
        if not container_uris:
            container_uris.append("683313688378.dkr.ecr.us-east-1.amazonaws.com/xgboost:latest")
        
        return container_uris
    
    def create_sagemaker_model(
        self,
        model_name: str,
        algorithm: str = "xgboost",
        model_data_url: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        tags: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Create a SageMaker model with the specified configuration."""
        # Create unique model name
        full_model_name = f"{model_name}-gremory-test"
        role_name = f"{model_name}-sagemaker-role-gremory-test"
        response = None
        
        try:
            # Create IAM role
            role_arn = self._create_sagemaker_execution_role(role_name)
            
            # Wait for role propagation
            time.sleep(15)
            
            # Get container URIs based on algorithm preference
            container_uris = self._get_sagemaker_container_uris()
            
            # Try different container images
            model_created = False
            used_container = None
            
            for container_uri in container_uris:
                # Skip if algorithm preference doesn't match
                if algorithm == "xgboost" and "xgboost" not in container_uri:
                    continue
                elif algorithm == "linear-learner" and "linear-learner" not in container_uri:
                    continue
                
                try:
                    # Prepare container definition
                    container_def = {
                        'Image': container_uri
                    }
                    
                    # Add model data URL if provided
                    if model_data_url:
                        container_def['ModelDataUrl'] = model_data_url
                    
                    # Create model
                    response = self.sagemaker.create_model(
                        ModelName=full_model_name,
                        PrimaryContainer=container_def,
                        ExecutionRoleArn=role_arn,
                        Tags=tags or []
                    )
                    
                    model_created = True
                    used_container = container_uri
                    break
                    
                except ClientError as e:
                    error_message = str(e)
                    if ("does not exist" in error_message or 
                        "not found" in error_message or 
                        "not grant" in error_message):
                        continue
                    else:
                        raise e
            
            if not model_created:
                raise Exception("No suitable container image found for the specified algorithm")
            
            # Ensure response is not None
            if response is None:
                raise Exception("Model creation succeeded but response is missing")
            
            return {
                'success': True,
                'model_name': full_model_name,
                'model_arn': response['ModelArn'],
                'algorithm': algorithm,
                'container_image': used_container,
                'execution_role_arn': role_arn,
                'role_name': role_name,
                'model_data_url': model_data_url,
                'region': self.region,
                'message': f'SageMaker model {full_model_name} created successfully'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # Cleanup on failure
            try:
                self._delete_sagemaker_execution_role(role_name)
            except:
                pass
                
            if error_code == 'ValidationException' and 'already exists' in str(e):
                return {
                    'success': False,
                    'model_name': full_model_name,
                    'error_code': error_code,
                    'message': f'SageMaker model {full_model_name} already exists'
                }
            else:
                return {
                    'success': False,
                    'model_name': full_model_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to create SageMaker model {full_model_name}'
                }
        except Exception as e:
            # Cleanup on failure
            try:
                self._delete_sagemaker_execution_role(role_name)
            except:
                pass
                
            return {
                'success': False,
                'model_name': full_model_name,
                'error': str(e),
                'message': f'Failed to create SageMaker model {full_model_name}: {str(e)}'
            }
    
    def describe_sagemaker_model(self, model_name: str) -> Dict[str, Any]:
        """Describe a SageMaker model and verify it exists."""
        # Create full model name
        full_model_name = model_name
        if not full_model_name.endswith('-gremory-test'):
            full_model_name = f"{model_name}-gremory-test"
        
        try:
            # Get model information
            response = self.sagemaker.describe_model(ModelName=full_model_name)
            
            # Extract container information
            primary_container = response.get('PrimaryContainer', {})
            
            return {
                'success': True,
                'model_name': full_model_name,
                'model_arn': response['ModelArn'],
                'creation_time': response['CreationTime'].isoformat(),
                'execution_role_arn': response['ExecutionRoleArn'],
                'primary_container': {
                    'image': primary_container.get('Image'),
                    'model_data_url': primary_container.get('ModelDataUrl'),
                    'environment': primary_container.get('Environment', {})
                },
                'enable_network_isolation': response.get('EnableNetworkIsolation', False),
                'vpc_config': response.get('VpcConfig'),
                'message': f'SageMaker model {full_model_name} exists and is accessible'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ValidationException' and 'does not exist' in str(e):
                return {
                    'success': False,
                    'model_name': full_model_name,
                    'exists': False,
                    'error_code': error_code,
                    'message': f'SageMaker model {full_model_name} does not exist'
                }
            else:
                return {
                    'success': False,
                    'model_name': full_model_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to describe SageMaker model {full_model_name}'
                }
    
    def delete_sagemaker_model(self, model_name: str, delete_role: bool = True) -> Dict[str, Any]:
        """Delete a SageMaker model and optionally its IAM role."""
        # Create full model name and role name
        full_model_name = model_name
        if not full_model_name.endswith('-gremory-test'):
            full_model_name = f"{model_name}-gremory-test"
        
        role_name = f"{model_name}-sagemaker-role-gremory-test"

        try:
            # Delete SageMaker model
            self.sagemaker.delete_model(ModelName=full_model_name)
            
            result = {
                'success': True,
                'model_name': full_model_name,
                'role_deleted': False,
                'message': f'SageMaker model {full_model_name} deleted successfully'
            }
            
            # Delete IAM role if requested
            if delete_role:
                try:
                    self._delete_sagemaker_execution_role(role_name)
                    result['role_deleted'] = True
                    result['role_name'] = role_name
                    result['message'] += f' and IAM role {role_name} deleted'
                except Exception as e:
                    result['role_deletion_error'] = str(e)
                    result['message'] += f' but failed to delete IAM role: {str(e)}'
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ValidationException' and 'does not exist' in str(e):
                return {
                    'success': True,
                    'model_name': full_model_name,
                    'message': f'SageMaker model {full_model_name} does not exist (already deleted)'
                }
            else:
                return {
                    'success': False,
                    'model_name': full_model_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to delete SageMaker model {full_model_name}'
                }
    
    def list_sagemaker_models(self) -> Dict[str, Any]:
        """List all SageMaker models in the account."""
        try:
            response = self.sagemaker.list_models()
            
            models = []
            for model in response['Models']:
                models.append({
                    'model_name': model['ModelName'],
                    'model_arn': model['ModelArn'],
                    'creation_time': model['CreationTime'].isoformat()
                })
            
            return {
                'success': True,
                'total_models': len(models),
                'models': models,
                'message': f'Found {len(models)} SageMaker models'
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': e.response['Error']['Code'],
                'message': 'Failed to list SageMaker models'
            }

@tool
def create_sagemaker_model(
    model_name: str,
    algorithm: str = "xgboost",
    model_data_url: str = "",
    environment_variables: str = "",
    tags: str = ""
) -> str:
    """
    Create a SageMaker model with the specified configuration.
    
    Args:
        model_name: Name of the SageMaker model to create
        algorithm: Algorithm to use (xgboost, linear-learner). Defaults to "xgboost".
        model_data_url: S3 URL of model artifacts (optional)
        environment_variables: JSON string of environment variables (e.g., '{"KEY": "value"}')
        tags: JSON string of tags (e.g., '[{"Key": "Environment", "Value": "Test"}]')
        
    Returns:
        JSON string with creation result and model details
    """
    sagemaker_service = SageMakerService()
    
    # Parse environment variables if provided
    env_vars = None
    if environment_variables:
        try:
            env_vars = json.loads(environment_variables)
        except json.JSONDecodeError:
            env_vars = None
    
    # Parse tags if provided
    tags_list = None
    if tags:
        try:
            tags_list = json.loads(tags)
        except json.JSONDecodeError:
            tags_list = None
    
    result = sagemaker_service.create_sagemaker_model(
        model_name, algorithm, model_data_url or None, env_vars, tags_list
    )
    return json.dumps(result, indent=2)

@tool
def describe_sagemaker_model(model_name: str) -> str:
    """
    Describe a SageMaker model and verify it exists.
    
    Args:
        model_name: Name of the SageMaker model to describe
        
    Returns:
        JSON string with model description and verification details
    """
    sagemaker_service = SageMakerService()
    result = sagemaker_service.describe_sagemaker_model(model_name)
    return json.dumps(result, indent=2)

@tool
def delete_sagemaker_model(model_name: str, delete_role: bool = True) -> str:
    """
    Delete a SageMaker model and optionally its IAM role.
    
    Args:
        model_name: Name of the SageMaker model to delete
        delete_role: Whether to delete the associated IAM role
        
    Returns:
        JSON string with deletion result and details
    """
    sagemaker_service = SageMakerService()
    result = sagemaker_service.delete_sagemaker_model(model_name, delete_role)
    return json.dumps(result, indent=2)

@tool
def list_sagemaker_models() -> str:
    """
    List all SageMaker models in the account.
    
    Returns:
        JSON string with list of all SageMaker models
    """
    sagemaker_service = SageMakerService()
    result = sagemaker_service.list_sagemaker_models()
    return json.dumps(result, indent=2)

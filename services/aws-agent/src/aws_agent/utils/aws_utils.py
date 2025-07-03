import boto3
import json
import tempfile
import zipfile
import os
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError

def get_aws_account_info() -> Dict[str, str]:
    """Get AWS account information"""
    try:
        sts = boto3.client('sts')
        account_info = sts.get_caller_identity()
        region = boto3.Session().region_name or 'us-east-1'
        
        return {
            'account_id': account_info['Account'],
            'user_id': account_info['UserId'],
            'arn': account_info['Arn'],
            'region': region
        }
    except Exception as e:
        return {
            'error': str(e),
            'account_id': 'unknown',
            'region': 'us-east-1'
        }

def create_lambda_deployment_package(code: str, handler_file: str = "lambda_function.py") -> str:
    """Create a Lambda deployment package from code string"""
    temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    temp_zip.close()
    
    with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
        zip_file.writestr(handler_file, code)
    
    return temp_zip.name

def create_iam_role_for_lambda(role_name: str) -> str:
    """Create an IAM role for Lambda execution"""
    iam = boto3.client('iam')
    
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
        # Create role
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"Execution role for Lambda function {role_name}"
        )
        
        role_arn = response['Role']['Arn']
        
        # Attach basic execution policy
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        
        return role_arn
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            # Role already exists, get its ARN
            response = iam.get_role(RoleName=role_name)
            return response['Role']['Arn']
        else:
            raise e

def create_iam_role_for_sagemaker(role_name: str) -> str:
    """Create an IAM role for SageMaker execution"""
    iam = boto3.client('iam')
    
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
                "Resource": ["arn:aws:s3:::*"]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            }
        ]
    }
    
    try:
        # Create role
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"Execution role for SageMaker model {role_name}"
        )
        
        role_arn = response['Role']['Arn']
        
        # Create and attach custom policy
        policy_name = f"{role_name}-policy"
        try:
            iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(sagemaker_policy),
                Description=f"Custom policy for {role_name}"
            )
            
            account_id = get_aws_account_info()['account_id']
            policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
            
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'EntityAlreadyExists':
                raise e
        
        return role_arn
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            # Role already exists, get its ARN
            response = iam.get_role(RoleName=role_name)
            return response['Role']['Arn']
        else:
            raise e

def delete_iam_role(role_name: str):
    """Delete an IAM role and its attached policies"""
    iam = boto3.client('iam')
    
    try:
        # Detach all policies
        attached_policies = iam.list_attached_role_policies(RoleName=role_name)
        for policy in attached_policies['AttachedPolicies']:
            iam.detach_role_policy(
                RoleName=role_name,
                PolicyArn=policy['PolicyArn']
            )
        
        # Delete inline policies
        inline_policies = iam.list_role_policies(RoleName=role_name)
        for policy_name in inline_policies['PolicyNames']:
            iam.delete_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
        
        # Delete role
        iam.delete_role(RoleName=role_name)
        
    except ClientError:
        pass  # Role might not exist

def get_sagemaker_container_uri(algorithm: str, region: str) -> str:
    """Get SageMaker container URI for a specific algorithm and region"""
    
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
        'ap-northeast-1': '501404015308'
    }
    
    if algorithm.lower() == 'xgboost':
        account_id = xgboost_mapping.get(region, '683313688378')  # Default to us-east-1
        return f"{account_id}.dkr.ecr.{region}.amazonaws.com/xgboost:latest"
    
    # Fallback to us-east-1 XGBoost
    return f"683313688378.dkr.ecr.us-east-1.amazonaws.com/xgboost:latest"

def ensure_unique_name(base_name: str, service_type: str = "gremory-test") -> str:
    """Ensure AWS resource names are unique"""
    if not base_name.endswith(f'-{service_type}'):
        return f"{base_name}-{service_type}"
    return base_name

def parse_environment_variables(env_vars_str: str) -> Optional[Dict[str, str]]:
    """Parse environment variables from string"""
    if not env_vars_str:
        return None
    
    try:
        return json.loads(env_vars_str)
    except json.JSONDecodeError:
        # Try to parse as comma-separated key=value pairs
        env_vars = {}
        for pair in env_vars_str.split(','):
            if '=' in pair:
                key, value = pair.split('=', 1)
                env_vars[key.strip()] = value.strip()
        return env_vars if env_vars else None

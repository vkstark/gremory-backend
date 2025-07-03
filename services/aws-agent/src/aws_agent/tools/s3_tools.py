import boto3
import json
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from langchain_core.tools import tool

from ..utils.aws_utils import get_aws_account_info, ensure_unique_name

@tool
def create_s3_bucket(
    bucket_name: str,
    enable_versioning: bool = False,
    enable_encryption: bool = True,
    create_folders: Optional[List[str]] = None,
    add_policy: bool = False
) -> str:
    """
    Create an S3 bucket with optional configurations.
    
    Args:
        bucket_name: Name of the S3 bucket to create
        enable_versioning: Whether to enable versioning on the bucket
        enable_encryption: Whether to enable server-side encryption
        create_folders: List of folder paths to create in the bucket
        add_policy: Whether to add a secure transport policy
        
    Returns:
        JSON string with creation result and bucket details
    """
    s3 = boto3.client('s3')
    account_info = get_aws_account_info()
    region = account_info['region']
    
    # Ensure unique bucket name
    full_bucket_name = ensure_unique_name(bucket_name)
    
    try:
        # Create bucket
        if region == 'us-east-1':
            response = s3.create_bucket(Bucket=full_bucket_name)
        else:
            response = s3.create_bucket(
                Bucket=full_bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        
        bucket_location = response['Location']
        
        # Configure versioning if requested
        if enable_versioning:
            s3.put_bucket_versioning(
                Bucket=full_bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
        
        # Configure encryption if requested
        if enable_encryption:
            s3.put_bucket_encryption(
                Bucket=full_bucket_name,
                ServerSideEncryptionConfiguration={
                    'Rules': [
                        {
                            'ApplyServerSideEncryptionByDefault': {
                                'SSEAlgorithm': 'AES256'
                            }
                        }
                    ]
                }
            )
        
        # Add secure transport policy if requested
        if add_policy:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyInsecureConnections",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"arn:aws:s3:::{full_bucket_name}",
                            f"arn:aws:s3:::{full_bucket_name}/*"
                        ],
                        "Condition": {
                            "Bool": {
                                "aws:SecureTransport": "false"
                            }
                        }
                    }
                ]
            }
            s3.put_bucket_policy(
                Bucket=full_bucket_name,
                Policy=json.dumps(policy)
            )
        
        # Create folders if specified
        created_folders = []
        if create_folders:
            for folder_path in create_folders:
                if not folder_path.endswith('/'):
                    folder_path += '/'
                s3.put_object(Bucket=full_bucket_name, Key=folder_path)
                created_folders.append(folder_path)
        
        result = {
            'success': True,
            'bucket_name': full_bucket_name,
            'bucket_location': bucket_location,
            'region': region,
            'versioning_enabled': enable_versioning,
            'encryption_enabled': enable_encryption,
            'policy_applied': add_policy,
            'folders_created': created_folders,
            'message': f'S3 bucket {full_bucket_name} created successfully'
        }
        
        return json.dumps(result, indent=2)
        
    except ClientError as e:
        error_result = {
            'success': False,
            'error_code': e.response['Error']['Code'],
            'error_message': e.response['Error']['Message'],
            'message': f'Failed to create S3 bucket {full_bucket_name}'
        }
        return json.dumps(error_result, indent=2)

@tool
def verify_s3_bucket(bucket_name: str, check_contents: bool = True) -> str:
    """
    Verify that an S3 bucket exists and check its configuration.
    
    Args:
        bucket_name: Name of the S3 bucket to verify
        check_contents: Whether to list and return bucket contents
        
    Returns:
        JSON string with verification result and bucket details
    """
    s3 = boto3.client('s3')
    
    # Ensure full bucket name
    full_bucket_name = ensure_unique_name(bucket_name)
    
    try:
        # Check if bucket exists
        s3.head_bucket(Bucket=full_bucket_name)
        
        # Get bucket location
        location_response = s3.get_bucket_location(Bucket=full_bucket_name)
        region = location_response['LocationConstraint'] or 'us-east-1'
        
        # Check versioning
        versioning_response = s3.get_bucket_versioning(Bucket=full_bucket_name)
        versioning_enabled = versioning_response.get('Status') == 'Enabled'
        
        # Check encryption
        encryption_enabled = False
        try:
            s3.get_bucket_encryption(Bucket=full_bucket_name)
            encryption_enabled = True
        except ClientError:
            pass
        
        # Get contents if requested
        contents = []
        if check_contents:
            try:
                response = s3.list_objects_v2(Bucket=full_bucket_name, MaxKeys=10)
                if 'Contents' in response:
                    contents = [
                        {
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat()
                        }
                        for obj in response['Contents']
                    ]
            except ClientError:
                pass
        
        result = {
            'success': True,
            'bucket_name': full_bucket_name,
            'exists': True,
            'region': region,
            'versioning_enabled': versioning_enabled,
            'encryption_enabled': encryption_enabled,
            'contents': contents,
            'object_count': len(contents),
            'message': f'S3 bucket {full_bucket_name} verified successfully'
        }
        
        return json.dumps(result, indent=2)
        
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            result = {
                'success': False,
                'bucket_name': full_bucket_name,
                'exists': False,
                'message': f'S3 bucket {full_bucket_name} does not exist'
            }
        else:
            result = {
                'success': False,
                'error_code': e.response['Error']['Code'],
                'error_message': e.response['Error']['Message'],
                'message': f'Failed to verify S3 bucket {full_bucket_name}'
            }
        
        return json.dumps(result, indent=2)

@tool
def delete_s3_bucket(bucket_name: str, force_delete: bool = False) -> str:
    """
    Delete an S3 bucket and optionally all its contents.
    
    Args:
        bucket_name: Name of the S3 bucket to delete
        force_delete: Whether to delete all objects before deleting bucket
        
    Returns:
        JSON string with deletion result
    """
    s3 = boto3.client('s3')
    
    # Ensure full bucket name
    full_bucket_name = ensure_unique_name(bucket_name)
    
    try:
        deleted_objects = []
        
        if force_delete:
            # Delete all objects and versions
            try:
                # List and delete all objects
                response = s3.list_objects_v2(Bucket=full_bucket_name)
                if 'Contents' in response:
                    objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
                    s3.delete_objects(
                        Bucket=full_bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
                    deleted_objects.extend([obj['Key'] for obj in objects_to_delete])
                
                # List and delete all versions
                versions_response = s3.list_object_versions(Bucket=full_bucket_name)
                versions_to_delete = []
                
                if 'Versions' in versions_response:
                    versions_to_delete.extend([
                        {'Key': version['Key'], 'VersionId': version['VersionId']}
                        for version in versions_response['Versions']
                    ])
                
                if 'DeleteMarkers' in versions_response:
                    versions_to_delete.extend([
                        {'Key': marker['Key'], 'VersionId': marker['VersionId']}
                        for marker in versions_response['DeleteMarkers']
                    ])
                
                if versions_to_delete:
                    s3.delete_objects(
                        Bucket=full_bucket_name,
                        Delete={'Objects': versions_to_delete}
                    )
                    
            except ClientError:
                pass  # Continue with bucket deletion
        
        # Delete bucket
        s3.delete_bucket(Bucket=full_bucket_name)
        
        result = {
            'success': True,
            'bucket_name': full_bucket_name,
            'deleted_objects': deleted_objects,
            'object_count': len(deleted_objects),
            'message': f'S3 bucket {full_bucket_name} deleted successfully'
        }
        
        return json.dumps(result, indent=2)
        
    except ClientError as e:
        error_result = {
            'success': False,
            'error_code': e.response['Error']['Code'],
            'error_message': e.response['Error']['Message'],
            'message': f'Failed to delete S3 bucket {full_bucket_name}'
        }
        return json.dumps(error_result, indent=2)

# List of S3 tools
S3_TOOLS = [create_s3_bucket, verify_s3_bucket, delete_s3_bucket]

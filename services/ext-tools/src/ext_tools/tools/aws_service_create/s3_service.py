#!/usr/bin/env python3
"""
S3 Service Operations for AWS
Provides create, verify, and delete operations for S3 buckets
"""

import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Any

from langchain_core.tools import tool

class S3Service:
    def __init__(self):
        """Initialize S3 service client and get AWS account information."""
        self.s3 = boto3.client('s3')
        self.sts = boto3.client('sts')
        
        self.account_id = self.sts.get_caller_identity()['Account']
        self.region = boto3.Session().region_name or 'us-east-1'
    
    def create_s3_bucket(
        self, 
        bucket_name: str,
        enable_versioning: bool = False,
        enable_encryption: bool = True,
        create_folders: Optional[List[str]] = None,
        add_policy: bool = False
    ) -> Dict[str, Any]:
        """
        Create an S3 bucket with optional configurations.
        
        Args:
            bucket_name (str): Name of the S3 bucket to create
            enable_versioning (bool): Whether to enable versioning on the bucket
            enable_encryption (bool): Whether to enable server-side encryption
            create_folders (List[str], optional): List of folder paths to create in the bucket
            add_policy (bool): Whether to add a secure transport policy
            
        Returns:
            Dict[str, Any]: Result containing bucket details and status
            
        Example:
            result = s3_service.create_s3_bucket(
                bucket_name="my-data-bucket",
                enable_versioning=True,
                create_folders=["data/raw/", "data/processed/", "logs/"]
            )
        """
        # Ensure bucket name is unique by adding account ID if not already present
        # if self.account_id not in bucket_name:
        #     # full_bucket_name = f"{bucket_name}-{self.account_id}"
        #     full_bucket_name = f"{bucket_name}-GREMORY-TEST"
        # else:
        #     full_bucket_name = bucket_name
        full_bucket_name = bucket_name
        if not full_bucket_name.endswith('-gremory-test'):
            full_bucket_name = f"{bucket_name}-gremory-test"
        try:
            
            # Create bucket
            if self.region == 'us-east-1':
                response = self.s3.create_bucket(Bucket=full_bucket_name)
            else:
                response = self.s3.create_bucket(
                    Bucket=full_bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            bucket_location = response['Location']
            
            # Configure versioning if requested
            if enable_versioning:
                self.s3.put_bucket_versioning(
                    Bucket=full_bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
            
            # Configure encryption if requested
            if enable_encryption:
                self.s3.put_bucket_encryption(
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
                bucket_policy = {
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
                
                self.s3.put_bucket_policy(
                    Bucket=full_bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
            
            # Create folders if specified
            created_folders = []
            if create_folders:
                for folder in create_folders:
                    if not folder.endswith('/'):
                        folder += '/'
                    self.s3.put_object(Bucket=full_bucket_name, Key=folder, Body='')
                    created_folders.append(folder)
            
            return {
                'success': True,
                'bucket_name': full_bucket_name,
                'bucket_location': bucket_location,
                'region': self.region,
                'versioning_enabled': enable_versioning,
                'encryption_enabled': enable_encryption,
                'policy_applied': add_policy,
                'folders_created': created_folders,
                'message': f'S3 bucket {full_bucket_name} created successfully'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyOwnedByYou':
                return {
                    'success': True,
                    'bucket_name': full_bucket_name,
                    'message': f'S3 bucket {full_bucket_name} already exists and is owned by you'
                }
            else:
                return {
                    'success': False,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to create S3 bucket {bucket_name}'
                }
    
    def verify_s3_bucket(self, bucket_name: str, check_contents: bool = True) -> Dict[str, Any]:
        """
        Verify that an S3 bucket exists and optionally check its contents.
        
        Args:
            bucket_name (str): Name of the S3 bucket to verify
            check_contents (bool): Whether to list and return bucket contents
            
        Returns:
            Dict[str, Any]: Result containing bucket verification status and details
            
        Example:
            result = s3_service.verify_s3_bucket("my-data-bucket", check_contents=True)
        """
        # Ensure bucket name includes account ID if not already present
        # if self.account_id not in bucket_name:
        #     # full_bucket_name = f"{bucket_name}-{self.account_id}"
        #     full_bucket_name = f"{bucket_name}-GREMORY-TEST"
        # else:
        #     full_bucket_name = bucket_name
        
        full_bucket_name = bucket_name
        if not full_bucket_name.endswith('-gremory-test'):
            full_bucket_name = f"{bucket_name}-gremory-test"
            
        try:
            
            # Check if bucket exists
            self.s3.head_bucket(Bucket=full_bucket_name)
            
            # Get bucket location
            location_response = self.s3.get_bucket_location(Bucket=full_bucket_name)
            bucket_region = location_response['LocationConstraint'] or 'us-east-1'
            
            # Check versioning status
            versioning_response = self.s3.get_bucket_versioning(Bucket=full_bucket_name)
            versioning_status = versioning_response.get('Status', 'Suspended')
            
            # Check encryption status
            try:
                encryption_response = self.s3.get_bucket_encryption(Bucket=full_bucket_name)
                encryption_enabled = True
                encryption_algorithm = encryption_response['ServerSideEncryptionConfiguration']['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']
            except ClientError:
                encryption_enabled = False
                encryption_algorithm = None
            
            result = {
                'success': True,
                'bucket_name': full_bucket_name,
                'exists': True,
                'region': bucket_region,
                'versioning_status': versioning_status,
                'encryption_enabled': encryption_enabled,
                'encryption_algorithm': encryption_algorithm,
                'message': f'S3 bucket {full_bucket_name} exists and is accessible'
            }
            
            # Check contents if requested
            if check_contents:
                try:
                    objects_response = self.s3.list_objects_v2(Bucket=full_bucket_name)
                    
                    if 'Contents' in objects_response:
                        objects = []
                        total_size = 0
                        for obj in objects_response['Contents']:
                            objects.append({
                                'key': obj['Key'],
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'].isoformat()
                            })
                            total_size += obj['Size']
                        
                        result.update({
                            'object_count': len(objects),
                            'total_size_bytes': total_size,
                            'objects': objects[:10],  # Return first 10 objects
                            'has_more_objects': len(objects_response.get('Contents', [])) > 10
                        })
                    else:
                        result.update({
                            'object_count': 0,
                            'total_size_bytes': 0,
                            'objects': []
                        })
                        
                except ClientError as e:
                    result['content_check_error'] = str(e)
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                return {
                    'success': False,
                    'bucket_name': full_bucket_name,
                    'exists': False,
                    'error_code': error_code,
                    'message': f'S3 bucket {full_bucket_name} does not exist'
                }
            else:
                return {
                    'success': False,
                    'bucket_name': full_bucket_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to verify S3 bucket {full_bucket_name}'
                }
    
    def delete_s3_bucket(self, bucket_name: str, force_delete: bool = False) -> Dict[str, Any]:
        """
        Delete an S3 bucket and optionally all its contents.
        
        Args:
            bucket_name (str): Name of the S3 bucket to delete
            force_delete (bool): Whether to delete all objects and versions before deleting bucket
            
        Returns:
            Dict[str, Any]: Result containing deletion status and details
            
        Example:
            result = s3_service.delete_s3_bucket("my-data-bucket", force_delete=True)
        """
        # Ensure bucket name includes account ID if not already present
        # if self.account_id not in bucket_name:
        #     # full_bucket_name = f"{bucket_name}-{self.account_id}"
        #     full_bucket_name = f"{bucket_name}-GREMORY-TEST"
        # else:
        #     full_bucket_name = bucket_name
        full_bucket_name = bucket_name
        if not full_bucket_name.endswith('-gremory-test'):
            full_bucket_name = f"{bucket_name}-gremory-test"
        try:
            
            deleted_objects = 0
            deleted_versions = 0
            
            # If force delete is enabled, delete all objects and versions first
            if force_delete:
                # Delete all object versions and delete markers
                paginator = self.s3.get_paginator('list_object_versions')
                for page in paginator.paginate(Bucket=full_bucket_name):
                    # Delete object versions
                    if 'Versions' in page:
                        for version in page['Versions']:
                            self.s3.delete_object(
                                Bucket=full_bucket_name,
                                Key=version['Key'],
                                VersionId=version['VersionId']
                            )
                            deleted_versions += 1
                    
                    # Delete delete markers
                    if 'DeleteMarkers' in page:
                        for marker in page['DeleteMarkers']:
                            self.s3.delete_object(
                                Bucket=full_bucket_name,
                                Key=marker['Key'],
                                VersionId=marker['VersionId']
                            )
                            deleted_objects += 1
                
                # Also delete any regular objects that might not have versions
                objects_paginator = self.s3.get_paginator('list_objects_v2')
                for page in objects_paginator.paginate(Bucket=full_bucket_name):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            self.s3.delete_object(
                                Bucket=full_bucket_name,
                                Key=obj['Key']
                            )
                            deleted_objects += 1
            
            # Delete the bucket
            self.s3.delete_bucket(Bucket=full_bucket_name)
            
            return {
                'success': True,
                'bucket_name': full_bucket_name,
                'deleted_objects': deleted_objects,
                'deleted_versions': deleted_versions,
                'force_delete_used': force_delete,
                'message': f'S3 bucket {full_bucket_name} deleted successfully'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NoSuchBucket':
                return {
                    'success': True,
                    'bucket_name': full_bucket_name,
                    'message': f'S3 bucket {full_bucket_name} does not exist (already deleted)'
                }
            elif error_code == 'BucketNotEmpty':
                return {
                    'success': False,
                    'bucket_name': full_bucket_name,
                    'error_code': error_code,
                    'message': f'S3 bucket {full_bucket_name} is not empty. Use force_delete=True to delete all contents first.'
                }
            else:
                return {
                    'success': False,
                    'bucket_name': full_bucket_name,
                    'error': str(e),
                    'error_code': error_code,
                    'message': f'Failed to delete S3 bucket {full_bucket_name}'
                }

@tool
def create_s3_bucket_tool(
    bucket_name: str,
    enable_versioning: bool = False,
    enable_encryption: bool = True,
    create_folders: str = "",
    add_policy: bool = False
) -> str:
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
    s3_service = S3Service()
    folders = [f.strip() for f in create_folders.split(',')] if create_folders else None
    result = s3_service.create_s3_bucket(bucket_name, enable_versioning, enable_encryption, folders, add_policy)
    return json.dumps(result, indent=2)

@tool
def verify_s3_bucket_tool(bucket_name: str, check_contents: bool = True) -> str:
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
    s3_service = S3Service()
    result = s3_service.verify_s3_bucket(bucket_name, check_contents)
    return json.dumps(result, indent=2)

@tool
def delete_s3_bucket_tool(bucket_name: str, force_delete: bool = False) -> str:
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
    s3_service = S3Service()
    result = s3_service.delete_s3_bucket(bucket_name, force_delete)
    return json.dumps(result, indent=2)

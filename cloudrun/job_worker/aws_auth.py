"""AWS authentication utilities for Cloud Run Job worker using Workload Identity."""

import os
import logging
from typing import Optional, Dict, Any
from .config import JobWorkerConfig

logger = logging.getLogger(__name__)


def get_aws_credentials(config: JobWorkerConfig) -> Optional[Dict[str, str]]:
    """
    Get AWS credentials using Workload Identity.
    
    Returns:
        Dict with AWS credentials or None if failed
    """
    try:
        # Import required libraries
        from google.auth import default
        from google.auth.transport.requests import Request
        import requests
        
        # Get GCP credentials
        credentials, project_id = default()
        
        # Create OIDC token
        oidc_token = credentials.token
        
        # Prepare the request to AWS STS
        sts_url = f"https://sts.{config.aws_region}.amazonaws.com/"
        
        # Create the AssumeRoleWithWebIdentity request
        assume_role_data = {
            "Action": "AssumeRoleWithWebIdentity",
            "Version": "2011-06-15",
            "RoleArn": config.aws_role_arn,
            "RoleSessionName": "cloudrun-job-worker",
            "WebIdentityToken": oidc_token,
        }
        
        # Make the request
        response = requests.post(sts_url, data=assume_role_data)
        response.raise_for_status()
        
        # Parse the XML response (AWS STS returns XML)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        
        # Extract credentials from XML response
        credentials_elem = root.find(".//{https://sts.amazonaws.com/doc/2011-06-15/}Credentials")
        if credentials_elem is None:
            logger.error("No credentials found in STS response")
            return None
            
        access_key = credentials_elem.find("{https://sts.amazonaws.com/doc/2011-06-15/}AccessKeyId")
        secret_key = credentials_elem.find("{https://sts.amazonaws.com/doc/2011-06-15/}SecretAccessKey")
        session_token = credentials_elem.find("{https://sts.amazonaws.com/doc/2011-06-15/}SessionToken")
        
        if access_key is None or secret_key is None or session_token is None:
            logger.error("Incomplete credentials in STS response")
            return None
            
        return {
            "aws_access_key_id": access_key.text,
            "aws_secret_access_key": secret_key.text,
            "aws_session_token": session_token.text,
            "region": config.aws_region,
        }
        
    except Exception as exc:
        logger.error(f"Failed to get AWS credentials via Workload Identity: {exc}")
        return None


def create_dynamodb_client(config: JobWorkerConfig):
    """
    Create a DynamoDB client using Workload Identity credentials.
    
    Returns:
        boto3 DynamoDB resource or None if failed
    """
    try:
        import boto3
        
        # Get AWS credentials
        aws_creds = get_aws_credentials(config)
        if not aws_creds:
            logger.error("Failed to get AWS credentials")
            return None
            
        # Create DynamoDB client with temporary credentials
        dynamodb = boto3.resource(
            'dynamodb',
            region_name=aws_creds['region'],
            aws_access_key_id=aws_creds['aws_access_key_id'],
            aws_secret_access_key=aws_creds['aws_secret_access_key'],
            aws_session_token=aws_creds['aws_session_token']
        )
        
        logger.info("Successfully created DynamoDB client with Workload Identity")
        return dynamodb
        
    except Exception as exc:
        logger.error(f"Failed to create DynamoDB client: {exc}")
        return None

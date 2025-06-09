#!/usr/bin/env python3
"""
Test script to verify all user history API fixes
Tests error handling, type conversions, and proper JSON responses
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
USER_HISTORY_URL = f"{BASE_URL}/api/v1"

def api_endpoint(method, url, data=None, params=None, expected_status=200, test_name=""):
    """Test an API endpoint and return the response"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Method: {method}")
    print(f"URL: {url}")
    if params:
        print(f"Params: {json.dumps(params, indent=2)}")
    if data:
        print(f"Data: {json.dumps(data, indent=2)}")
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, params=params)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, params=params)
        elif method.upper() == "DELETE":
            response = requests.delete(url, params=params)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        print(f"\nResponse Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2, default=str)}")
        except:
            print(f"Response Text: {response.text}")
        
        # Check if status matches expected
        if response.status_code == expected_status:
            print(f"✅ SUCCESS: Expected status {expected_status}")
        else:
            print(f"❌ FAILED: Expected {expected_status}, got {response.status_code}")
        
        return response
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return None

def run_comprehensive_tests():
    """Run comprehensive tests for user history API"""
    
    print("🚀 Starting User History API Comprehensive Tests")
    print(f"Testing against: {BASE_URL}")
    
    # Test 1: Health check
    api_endpoint(
        "GET", 
        f"{USER_HISTORY_URL}/user-history/health",
        test_name="Health Check"
    )
    
    # Test 2: Create new conversation
    conversation_data = {
        "user_id": 1,
        "title": "Test Conversation",
        "conversation_type": "direct",
        "description": "A test conversation for API testing"
    }
    
    create_response = api_endpoint(
        "POST",
        f"{USER_HISTORY_URL}/user/history",
        data=conversation_data,
        expected_status=200,
        test_name="Create New Conversation"
    )
    
    conversation_id = None
    if create_response and create_response.status_code == 200:
        try:
            data = create_response.json()
            if data.get("success") and data.get("data"):
                conversation_id = data["data"].get("id")  # Fixed: use "id" instead of "conversation_id"
                print(f"Created conversation ID: {conversation_id}")
        except:
            pass
    
    if not conversation_id:
        print("❌ Could not create conversation, skipping dependent tests")
        return
    
    # Test 3: Send message to conversation
    message_data = {
        "conversation_id": conversation_id,
        "sender_id": 1,
        "content": "Hello, this is a test message!",
        "message_type": "text"
    }
    
    api_endpoint(
        "POST",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}/messages",
        data=message_data,
        expected_status=200,
        test_name="Send Message to Conversation"
    )
    
    # Test 4: Get user history with filters and enum conversion
    api_endpoint(
        "GET",
        f"{USER_HISTORY_URL}/user/1/history",
        params={
            "page": 1,
            "per_page": 10,
            "sort_order": "desc",
            "conversation_type": "direct",  # Test enum conversion
            "conversation_state": "active"  # Test enum conversion
        },
        test_name="Get User History with Enum Filters"
    )
    
    # Test 5: Get conversation messages with filters
    api_endpoint(
        "GET",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}/messages",
        params={
            "user_id": 1,
            "page": 1,
            "per_page": 20,
            "sort_order": "asc",
            "message_type": "text",  # Test enum conversion
            "include_deleted": False
        },
        test_name="Get Conversation Messages with Enum Filters"
    )
    
    # Test 6: Get conversation details
    api_endpoint(
        "GET",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}",
        params={"user_id": 1},
        test_name="Get Conversation Details"
    )
    
    # Test 7: Update conversation
    update_data = {
        "title": "Updated Test Conversation",
        "description": "Updated description for testing"
    }
    
    api_endpoint(
        "PUT",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}",
        data=update_data,
        params={"user_id": 1},
        test_name="Update Conversation"
    )
    
    # Test 8: Continue conversation
    api_endpoint(
        "PUT",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}/continue",
        params={"user_id": 1},
        test_name="Continue Conversation"
    )
    
    # Test 9: Archive conversation
    api_endpoint(
        "PUT",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}/archive",
        params={"user_id": 1},
        test_name="Archive Conversation"
    )
    
    # Test 10: Error handling - Invalid conversation ID
    api_endpoint(
        "GET",
        f"{USER_HISTORY_URL}/conversation/99999",
        params={"user_id": 1},
        expected_status=500,  # Might be 404 or 500 depending on service
        test_name="Error Handling - Invalid Conversation ID"
    )
    
    # Test 11: Error handling - Invalid enum values
    api_endpoint(
        "GET",
        f"{USER_HISTORY_URL}/user/1/history",
        params={
            "conversation_type": "invalid_type",  # Should be handled gracefully
            "conversation_state": "invalid_state"  # Should be handled gracefully
        },
        test_name="Error Handling - Invalid Enum Values"
    )
    
    # Test 12: Error handling - Validation errors
    invalid_message_data = {
        "conversation_id": conversation_id,
        "sender_id": 1,
        "content": "",  # Empty content should fail validation
        "message_type": "text"
    }
    
    api_endpoint(
        "POST",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}/messages",
        data=invalid_message_data,
        expected_status=422,  # Validation error
        test_name="Error Handling - Validation Errors"
    )
    
    # Test 13: Query parameter validation
    api_endpoint(
        "GET",
        f"{USER_HISTORY_URL}/user/1/history",
        params={
            "sort_order": "invalid_order"  # Should fail pattern validation
        },
        expected_status=422,  # Validation error
        test_name="Query Parameter Validation - Invalid Sort Order"
    )
    
    # Test 14: Delete conversation (final test)
    api_endpoint(
        "DELETE",
        f"{USER_HISTORY_URL}/conversation/{conversation_id}",
        params={"user_id": 1},
        test_name="Delete Conversation"
    )
    
    print(f"\n{'='*60}")
    print("🎉 ALL TESTS COMPLETED!")
    print(f"{'='*60}")

if __name__ == "__main__":
    run_comprehensive_tests()

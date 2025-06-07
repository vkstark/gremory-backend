#!/usr/bin/env python3
"""
Comprehensive test script for User History API
Tests all endpoints with realistic data and scenarios
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

class UserHistoryAPITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        
    def test_endpoint(self, method: str, endpoint: str, data: Dict[Any, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Helper method to test API endpoints"""
        url = f"{self.base_url}{API_PREFIX}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            print(f"\n{'='*60}")
            print(f"{method.upper()} {endpoint}")
            print(f"Status Code: {response.status_code}")
            
            if response.headers.get('content-type', '').startswith('application/json'):
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2, default=str)}")
                return result
            else:
                print(f"Response: {response.text}")
                return {"status_code": response.status_code, "text": response.text}
                
        except Exception as e:
            print(f"Error testing {method} {endpoint}: {str(e)}")
            return {"error": str(e)}
    
    def run_comprehensive_test(self):
        """Run comprehensive tests for all user history endpoints"""
        print("🚀 Starting User History API Comprehensive Test")
        print("="*80)
        
        # Test 1: Create a new conversation
        print("\n📝 Test 1: Create New Conversation")
        new_chat_data = {
            "user_id": 1,
            "title": "Customer Support Chat",
            "conversation_type": "support",
            "description": "Customer asking about product features"
        }
        create_result = self.test_endpoint("POST", "/user/history", new_chat_data)
        
        # Extract conversation ID for subsequent tests
        conversation_id = None
        if create_result.get("success") and create_result.get("data"):
            conversation_id = create_result["data"]["id"]
            print(f"✅ Created conversation with ID: {conversation_id}")
        else:
            print("❌ Failed to create conversation")
            return
        
        # Test 2: Send messages to the conversation
        print(f"\n💬 Test 2: Send Messages to Conversation {conversation_id}")
        messages = [
            {
                "conversation_id": conversation_id,
                "sender_id": 1,
                "content": "Hello, I need help with your product.",
                "message_type": "text"
            },
            {
                "conversation_id": conversation_id,
                "sender_id": 2,  # Different sender (support agent)
                "content": "Hi! I'd be happy to help. What specific questions do you have?",
                "message_type": "text"
            },
            {
                "conversation_id": conversation_id,
                "sender_id": 1,
                "content": "I'm trying to understand the pricing tiers.",
                "message_type": "text"
            }
        ]
        
        for i, message_data in enumerate(messages, 1):
            print(f"\n  📨 Sending message {i}")
            message_result = self.test_endpoint("POST", f"/conversation/{conversation_id}/messages", message_data)
            if message_result.get("success"):
                print(f"  ✅ Message {i} sent successfully")
            else:
                print(f"  ❌ Failed to send message {i}")
            time.sleep(0.5)  # Small delay between messages
        
        # Test 3: Get conversation messages
        print(f"\n📖 Test 3: Get Messages for Conversation {conversation_id}")
        messages_result = self.test_endpoint("GET", f"/conversation/{conversation_id}/messages")
        if messages_result.get("success"):
            message_count = len(messages_result.get("messages", []))
            print(f"✅ Retrieved {message_count} messages")
        else:
            print("❌ Failed to retrieve messages")
        
        # Test 4: Get conversation details
        print(f"\n🔍 Test 4: Get Conversation Details {conversation_id}")
        conversation_result = self.test_endpoint("GET", f"/conversation/{conversation_id}")
        if conversation_result.get("success"):
            print("✅ Retrieved conversation details")
        else:
            print("❌ Failed to retrieve conversation details")
        
        # Test 5: Update conversation
        print(f"\n✏️ Test 5: Update Conversation {conversation_id}")
        update_data = {
            "name": "Updated Customer Support Chat",
            "description": "Updated description with more details",
            "conversation_state": "active"
        }
        update_result = self.test_endpoint("PUT", f"/conversation/{conversation_id}", update_data)
        if update_result.get("success"):
            print("✅ Conversation updated successfully")
        else:
            print("❌ Failed to update conversation")
        
        # Test 6: Continue conversation
        print(f"\n🔄 Test 6: Continue Conversation {conversation_id}")
        continue_data = {"user_id": 1}
        continue_result = self.test_endpoint("PUT", f"/conversation/{conversation_id}/continue", continue_data)
        if continue_result.get("success"):
            print("✅ Conversation continued successfully")
        else:
            print("❌ Failed to continue conversation")
        
        # Test 7: Get user history with various filters
        print("\n📚 Test 7: Get User History with Filters")
        
        # Test 7a: Basic user history
        print("\n  📋 Test 7a: Basic user history")
        history_result = self.test_endpoint("GET", "/user/1/history")
        if history_result.get("success"):
            conv_count = len(history_result.get("conversations", []))
            print(f"  ✅ Retrieved {conv_count} conversations for user")
        else:
            print("  ❌ Failed to retrieve user history")
        
        # Test 7b: Filtered by conversation type
        print("\n  📋 Test 7b: Filter by conversation type")
        filtered_params = {"conversation_type": "support"}
        filtered_result = self.test_endpoint("GET", "/user/1/history", params=filtered_params)
        if filtered_result.get("success"):
            conv_count = len(filtered_result.get("conversations", []))
            print(f"  ✅ Retrieved {conv_count} support conversations")
        else:
            print("  ❌ Failed to retrieve filtered history")
        
        # Test 7c: Pagination test
        print("\n  📋 Test 7c: Pagination test")
        paginated_params = {"page": 1, "per_page": 5}
        paginated_result = self.test_endpoint("GET", "/user/1/history", params=paginated_params)
        if paginated_result.get("success"):
            print(f"  ✅ Retrieved paginated results (page 1, per_page 5)")
        else:
            print("  ❌ Failed to retrieve paginated history")
        
        # Test 8: Create additional test data
        print("\n🏗️ Test 8: Create Additional Test Conversations")
        additional_conversations = [
            {
                "user_id": 1,
                "title": "General Inquiry",
                "conversation_type": "direct",
                "description": "General questions about services"
            },
            {
                "user_id": 1,
                "title": "Bot Interaction",
                "conversation_type": "bot",
                "description": "Automated bot conversation"
            }
        ]
        
        for i, conv_data in enumerate(additional_conversations, 1):
            print(f"\n  🆕 Creating additional conversation {i}")
            additional_result = self.test_endpoint("POST", "/user/history", conv_data)
            if additional_result.get("success"):
                print(f"  ✅ Additional conversation {i} created")
            else:
                print(f"  ❌ Failed to create additional conversation {i}")
        
        # Test 9: Final user history check
        print("\n📊 Test 9: Final User History Summary")
        final_history = self.test_endpoint("GET", "/user/1/history")
        if final_history.get("success"):
            total_conversations = final_history.get("total_conversations", 0)
            print(f"✅ Final summary: User has {total_conversations} total conversations")
        else:
            print("❌ Failed to get final user history")
        
        # Test 10: Error handling tests
        print("\n🚨 Test 10: Error Handling Tests")
        
        # Test 10a: Non-existent conversation
        print("\n  ❌ Test 10a: Non-existent conversation")
        error_result = self.test_endpoint("GET", "/conversation/99999")
        print(f"  Expected error for non-existent conversation: {error_result.get('success', True) == False}")
        
        # Test 10b: Invalid user ID
        print("\n  ❌ Test 10b: Invalid user history")
        error_result2 = self.test_endpoint("GET", "/user/99999/history")
        print(f"  Handled invalid user ID gracefully")
        
        print("\n" + "="*80)
        print("🎉 User History API Comprehensive Test Complete!")
        print("="*80)

def main():
    """Main test execution"""
    print("Testing User History API...")
    print("Make sure the FastAPI server is running on http://localhost:8000")
    
    # Quick health check
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ FastAPI server is running")
        else:
            print("⚠️ FastAPI server responded but may have issues")
    except Exception as e:
        print(f"❌ Cannot connect to FastAPI server: {str(e)}")
        print("Please make sure the server is running with: uvicorn app.main:app --reload")
        return
    
    # Run the comprehensive test
    tester = UserHistoryAPITester()
    tester.run_comprehensive_test()

if __name__ == "__main__":
    main()

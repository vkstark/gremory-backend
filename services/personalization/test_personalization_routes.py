#!/usr/bin/env python3
"""
Comprehensive test suite for Personalization Service Routes
Tests all endpoints with various scenarios including success and error cases.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, date
from typing import Dict, Any, List, Optional
import httpx
import pytest
from pydantic import BaseModel

# Test configuration
BASE_URL = "http://localhost:8004"
TEST_USER_ID = 1
TIMEOUT = 10.0

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TestResult:
    """Test result container"""
    def __init__(self, name: str, passed: bool, message: str, response_data: Any = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.response_data = response_data
        self.timestamp = datetime.now()

class PersonalizationTester:
    """Comprehensive personalization service tester"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.results: List[TestResult] = []
        self.test_data = {}
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    def log_result(self, name: str, passed: bool, message: str, response_data: Any = None):
        """Log test result"""
        result = TestResult(name, passed, message, response_data)
        self.results.append(result)
        
        status_color = Colors.GREEN if passed else Colors.RED
        status_text = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"{status_color}{status_text}{Colors.END} {Colors.BOLD}{name}{Colors.END}")
        print(f"    {message}")
        if response_data and not passed:
            print(f"    Response: {json.dumps(response_data, indent=2, default=str)[:200]}...")
        print()
        
    async def test_service_availability(self) -> bool:
        """Test if the service is running and accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.log_result(
                    "Service Health Check", 
                    True, 
                    f"Service is healthy: {data}",
                    data
                )
                return True
            else:
                self.log_result(
                    "Service Health Check", 
                    False, 
                    f"Service returned status {response.status_code}",
                    response.text
                )
                return False
        except Exception as e:
            self.log_result(
                "Service Health Check", 
                False, 
                f"Service is not accessible: {str(e)}"
            )
            return False
            
    async def test_root_endpoint(self):
        """Test root endpoint"""
        try:
            response = await self.client.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                expected_fields = ['service', 'status', 'endpoints']
                has_fields = all(field in data for field in expected_fields)
                
                self.log_result(
                    "Root Endpoint", 
                    has_fields, 
                    f"Root endpoint returned expected structure" if has_fields else "Missing expected fields",
                    data
                )
            else:
                self.log_result(
                    "Root Endpoint", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text
                )
        except Exception as e:
            self.log_result("Root Endpoint", False, f"Error: {str(e)}")
            
    async def test_test_endpoint(self):
        """Test the /test endpoint"""
        try:
            response = await self.client.get(f"{self.base_url}/test")
            if response.status_code == 200:
                data = response.json()
                has_message = 'message' in data
                has_data = 'data' in data
                
                self.log_result(
                    "Test Endpoint", 
                    has_message and has_data, 
                    "Test endpoint working correctly" if (has_message and has_data) else "Missing expected response structure",
                    data
                )
            else:
                self.log_result(
                    "Test Endpoint", 
                    False, 
                    f"Unexpected status code: {response.status_code}",
                    response.text
                )
        except Exception as e:
            self.log_result("Test Endpoint", False, f"Error: {str(e)}")
            
    async def test_create_user_profile(self):
        """Test creating a user profile"""
        profile_data = {
            "user_id": TEST_USER_ID,
            "name": "Test User",
            "email": "test@example.com",
            "language_preference": "en",
            "timezone": "UTC",
            "long_term_goals": {"career": "AI Engineer", "skills": ["Python", "ML"]},
            "immutable_preferences": {"theme": "dark", "notifications": True}
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/profile",
                json=profile_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.test_data['profile'] = data.get('data', {})
                
                self.log_result(
                    "Create User Profile", 
                    True, 
                    f"Profile created successfully for user {TEST_USER_ID}",
                    data
                )
            else:
                self.log_result(
                    "Create User Profile", 
                    False, 
                    f"Failed with status {response.status_code}: {response.text}",
                    response.text
                )
        except Exception as e:
            self.log_result("Create User Profile", False, f"Error: {str(e)}")
            
    async def test_get_user_profile(self):
        """Test getting a user profile"""
        try:
            response = await self.client.get(f"{self.base_url}/profile/{TEST_USER_ID}")
            
            if response.status_code == 200:
                data = response.json()
                has_required_fields = all(field in data for field in ['user_id'])
                
                self.log_result(
                    "Get User Profile", 
                    has_required_fields, 
                    f"Profile retrieved successfully" if has_required_fields else "Missing required fields",
                    data
                )
            elif response.status_code == 404:
                self.log_result(
                    "Get User Profile", 
                    True,  # 404 is expected if profile doesn't exist yet
                    "Profile not found (expected if not created yet)",
                    response.text
                )
            else:
                self.log_result(
                    "Get User Profile", 
                    False, 
                    f"Unexpected status {response.status_code}: {response.text}",
                    response.text
                )
        except Exception as e:
            self.log_result("Get User Profile", False, f"Error: {str(e)}")
            
    async def test_update_user_profile(self):
        """Test updating a user profile"""
        update_data = {
            "name": "Updated Test User",
            "timezone": "America/New_York",
            "long_term_goals": {"career": "Senior AI Engineer", "skills": ["Python", "ML", "NLP"]}
        }
        
        try:
            response = await self.client.put(
                f"{self.base_url}/profile/{TEST_USER_ID}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_result(
                    "Update User Profile", 
                    True, 
                    f"Profile updated successfully",
                    data
                )
            elif response.status_code == 404:
                self.log_result(
                    "Update User Profile", 
                    True,  # Expected if profile doesn't exist
                    "Profile not found for update (expected if not created)",
                    response.text
                )
            else:
                self.log_result(
                    "Update User Profile", 
                    False, 
                    f"Failed with status {response.status_code}: {response.text}",
                    response.text
                )
        except Exception as e:
            self.log_result("Update User Profile", False, f"Error: {str(e)}")
            
    async def test_track_user_activity(self):
        """Test tracking user activity"""
        activity_data = {
            "user_id": TEST_USER_ID,
            "session_message_count": 10,
            "daily_activity_count": 25,
            "recent_topics": ["AI", "Machine Learning", "Python", "FastAPI"],
            "real_time_feedback": {"satisfaction": 4.5, "difficulty": "medium"},
            "session_metrics": {
                "session_duration": 1800,
                "avg_response_time": 2.3,
                "questions_asked": 5,
                "engagement_score": 0.85
            }
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/activity",
                json=activity_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_result(
                    "Track User Activity", 
                    True, 
                    f"Activity tracked successfully",
                    data
                )
            else:
                self.log_result(
                    "Track User Activity", 
                    False, 
                    f"Failed with status {response.status_code}: {response.text}",
                    response.text
                )
        except Exception as e:
            self.log_result("Track User Activity", False, f"Error: {str(e)}")
            
    async def test_set_user_feature(self):
        """Test setting user features"""
        features_to_test = [
            {
                "user_id": TEST_USER_ID,
                "feature_name": "ui_theme",
                "feature_value": {"theme": "dark", "compact_mode": True},
                "feature_version": "1.0",
                "change_frequency": "static"
            },
            {
                "user_id": TEST_USER_ID,
                "feature_name": "ai_personality",
                "feature_value": {"formality": "casual", "detail_level": "high", "humor": True},
                "feature_version": "2.0",
                "change_frequency": "slow"
            },
            {
                "user_id": TEST_USER_ID,
                "feature_name": "experimental_features",
                "feature_value": {"beta_ui": True, "advanced_search": False},
                "feature_version": "1.0",
                "change_frequency": "dynamic"
            }
        ]
        
        for i, feature_data in enumerate(features_to_test):
            try:
                response = await self.client.post(
                    f"{self.base_url}/feature",
                    json=feature_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_result(
                        f"Set User Feature {i+1} ({feature_data['feature_name']})", 
                        True, 
                        f"Feature '{feature_data['feature_name']}' set successfully",
                        data
                    )
                else:
                    self.log_result(
                        f"Set User Feature {i+1} ({feature_data['feature_name']})", 
                        False, 
                        f"Failed with status {response.status_code}: {response.text}",
                        response.text
                    )
            except Exception as e:
                self.log_result(f"Set User Feature {i+1}", False, f"Error: {str(e)}")
                
    async def test_get_user_features(self):
        """Test getting user features"""
        try:
            # Test getting all features
            response = await self.client.get(f"{self.base_url}/feature/{TEST_USER_ID}")
            
            if response.status_code == 200:
                data = response.json()
                features = data.get('data', {}).get('features', [])
                
                self.log_result(
                    "Get All User Features", 
                    True, 
                    f"Retrieved {len(features)} features",
                    data
                )
                
                # Test getting specific feature
                if features:
                    feature_name = "ui_theme"  # From our test data
                    response = await self.client.get(
                        f"{self.base_url}/feature/{TEST_USER_ID}?feature_name={feature_name}"
                    )
                    
                    if response.status_code == 200:
                        filtered_data = response.json()
                        filtered_features = filtered_data.get('data', {}).get('features', [])
                        
                        self.log_result(
                            "Get Specific User Feature", 
                            True, 
                            f"Retrieved {len(filtered_features)} features for '{feature_name}'",
                            filtered_data
                        )
                    else:
                        self.log_result(
                            "Get Specific User Feature", 
                            False, 
                            f"Failed with status {response.status_code}",
                            response.text
                        )
            else:
                self.log_result(
                    "Get All User Features", 
                    False, 
                    f"Failed with status {response.status_code}: {response.text}",
                    response.text
                )
        except Exception as e:
            self.log_result("Get User Features", False, f"Error: {str(e)}")
            
    async def test_get_personalization_data(self):
        """Test getting comprehensive personalization data"""
        try:
            response = await self.client.get(f"{self.base_url}/personalization/{TEST_USER_ID}")
            
            if response.status_code == 200:
                data = response.json()
                has_data = 'data' in data
                
                self.log_result(
                    "Get Personalization Data", 
                    has_data, 
                    f"Comprehensive data retrieved successfully" if has_data else "Missing data field",
                    data
                )
            else:
                self.log_result(
                    "Get Personalization Data", 
                    False, 
                    f"Failed with status {response.status_code}: {response.text}",
                    response.text
                )
        except Exception as e:
            self.log_result("Get Personalization Data", False, f"Error: {str(e)}")
            
    async def test_error_handling(self):
        """Test error handling scenarios"""
        
        # Test invalid user ID
        try:
            response = await self.client.get(f"{self.base_url}/profile/99999")
            expected_404 = response.status_code == 404
            
            self.log_result(
                "Error Handling - Invalid User ID", 
                expected_404, 
                "Returns 404 for non-existent user" if expected_404 else f"Unexpected status: {response.status_code}"
            )
        except Exception as e:
            self.log_result("Error Handling - Invalid User ID", False, f"Error: {str(e)}")
            
        # Test invalid JSON
        try:
            response = await self.client.post(
                f"{self.base_url}/profile",
                content='{"invalid": json}',  # Invalid JSON
                headers={"Content-Type": "application/json"}
            )
            expected_error = response.status_code in [400, 422]
            
            self.log_result(
                "Error Handling - Invalid JSON", 
                expected_error, 
                "Returns 400/422 for invalid JSON" if expected_error else f"Unexpected status: {response.status_code}"
            )
        except Exception as e:
            self.log_result("Error Handling - Invalid JSON", False, f"Error: {str(e)}")
            
        # Test missing required fields
        try:
            response = await self.client.post(
                f"{self.base_url}/profile",
                json={},  # Missing required user_id
                headers={"Content-Type": "application/json"}
            )
            expected_error = response.status_code == 422
            
            self.log_result(
                "Error Handling - Missing Required Fields", 
                expected_error, 
                "Returns 422 for missing required fields" if expected_error else f"Unexpected status: {response.status_code}"
            )
        except Exception as e:
            self.log_result("Error Handling - Missing Required Fields", False, f"Error: {str(e)}")
            
    async def test_api_documentation(self):
        """Test API documentation endpoints"""
        try:
            # Test OpenAPI docs
            response = await self.client.get(f"{self.base_url}/docs")
            docs_available = response.status_code == 200
            
            self.log_result(
                "API Documentation - OpenAPI", 
                docs_available, 
                "OpenAPI documentation is accessible" if docs_available else f"Docs not available: {response.status_code}"
            )
            
            # Test OpenAPI JSON schema
            response = await self.client.get(f"{self.base_url}/openapi.json")
            schema_available = response.status_code == 200
            
            if schema_available:
                schema = response.json()
                has_paths = 'paths' in schema
                has_components = 'components' in schema
                
                self.log_result(
                    "API Documentation - Schema", 
                    has_paths and has_components, 
                    "OpenAPI schema is valid" if (has_paths and has_components) else "Schema missing required sections"
                )
            else:
                self.log_result(
                    "API Documentation - Schema", 
                    False, 
                    f"Schema not available: {response.status_code}"
                )
                
        except Exception as e:
            self.log_result("API Documentation", False, f"Error: {str(e)}")
            
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}🧪 PERSONALIZATION SERVICE TEST SUMMARY{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")
        
        print(f"\n📊 {Colors.BOLD}Results:{Colors.END}")
        print(f"   {Colors.GREEN}✅ Passed: {passed_tests}{Colors.END}")
        print(f"   {Colors.RED}❌ Failed: {failed_tests}{Colors.END}")
        print(f"   📝 Total: {total_tests}")
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"   🎯 Success Rate: {success_rate:.1f}%")
        
        if failed_tests > 0:
            print(f"\n{Colors.RED}❌ Failed Tests:{Colors.END}")
            for result in self.results:
                if not result.passed:
                    print(f"   • {result.name}: {result.message}")
        
        print(f"\n{Colors.BOLD}🔧 Service Status:{Colors.END}")
        if passed_tests > 0:
            print(f"   {Colors.GREEN}✅ Service is responding{Colors.END}")
        else:
            print(f"   {Colors.RED}❌ Service may not be running{Colors.END}")
            print(f"   💡 Try: cd services/personalization && ./start.sh")
            
        print(f"\n{Colors.BOLD}📚 Next Steps:{Colors.END}")
        if success_rate >= 80:
            print(f"   {Colors.GREEN}🎉 Service is working well!{Colors.END}")
            print(f"   • View API docs: {BASE_URL}/docs")
            print(f"   • Integration: Add to API gateway")
        else:
            print(f"   {Colors.YELLOW}⚠️  Some issues detected{Colors.END}")
            print(f"   • Check service logs: tail -f logs/service.log")
            print(f"   • Verify database setup: ./setup_personalization_db.sh")
            
        print(f"\n{Colors.CYAN}📋 Test completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print()

async def run_comprehensive_tests():
    """Run all personalization service tests"""
    print(f"{Colors.BOLD}🚀 Starting Personalization Service Tests{Colors.END}")
    print(f"Target: {BASE_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print(f"{'='*60}\n")
    
    async with PersonalizationTester(BASE_URL) as tester:
        # Check if service is available first
        is_available = await tester.test_service_availability()
        
        if not is_available:
            print(f"{Colors.RED}❌ Service is not available. Please start the service first:{Colors.END}")
            print(f"   cd services/personalization && ./start.sh")
            return
            
        # Run all tests
        test_functions = [
            tester.test_root_endpoint,
            tester.test_test_endpoint,
            tester.test_create_user_profile,
            tester.test_get_user_profile,
            tester.test_update_user_profile,
            tester.test_track_user_activity,
            tester.test_set_user_feature,
            tester.test_get_user_features,
            tester.test_get_personalization_data,
            tester.test_error_handling,
            tester.test_api_documentation,
        ]
        
        for test_func in test_functions:
            try:
                await test_func()
                # Small delay between tests
                await asyncio.sleep(0.1)
            except Exception as e:
                tester.log_result(
                    f"Test Function {test_func.__name__}", 
                    False, 
                    f"Test function failed: {str(e)}"
                )
        
        # Print summary
        tester.print_summary()

def main():
    """Main function"""
    try:
        asyncio.run(run_comprehensive_tests())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Tests interrupted by user{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Test execution failed: {str(e)}{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()

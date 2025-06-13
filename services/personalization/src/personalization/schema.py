"""
Personalization API Schema definitions for request/response models
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import date, datetime
from enum import Enum

# Base response models
class PersonalizationBaseResponse(BaseModel):
    success: bool = True
    message: str = "Success"
    
class PersonalizationDataResponse(PersonalizationBaseResponse):
    data: Optional[Dict[str, Any]] = None

# User Profile Models
class CreateUserProfileRequest(BaseModel):
    user_id: int = Field(..., description="User ID from main users table")
    name: Optional[str] = None
    email: Optional[str] = None
    birthdate: Optional[date] = None
    signup_source: Optional[str] = None
    language_preference: str = Field(default="en", description="Language preference code")
    timezone: Optional[str] = Field(default="UTC", description="User timezone")
    preferences: Optional[Dict[str, Any]] = None

class UpdateUserProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    birthdate: Optional[date] = None
    language_preference: Optional[str] = None
    timezone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class UserProfileResponse(BaseModel):
    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    birthdate: Optional[date] = None
    signup_source: Optional[str] = None
    language_preference: str
    timezone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    last_login_at: Optional[datetime] = None
    activity_summary: Optional[Dict[str, Any]] = None
    recent_interactions: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# User Activity Models
class UserActivityRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    session_message_count: Optional[int] = None
    daily_activity_count: Optional[int] = None
    recent_topics: Optional[List[str]] = None
    real_time_feedback: Optional[Dict[str, Any]] = None
    session_metrics: Optional[Dict[str, Any]] = None

# User Feature Models
class UserFeatureRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    feature_name: str = Field(..., description="Name of the feature")
    feature_value: Dict[str, Any] = Field(..., description="Feature value as JSON")
    expires_at: Optional[datetime] = None

class UserFeatureResponse(BaseModel):
    user_id: int
    config_type: str
    config_key: str  # This is the feature_name in the old schema
    config_value: Dict[str, Any]  # This is the feature_value in the old schema
    meta_data: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# User Experiment Models
class UserExperimentResponse(BaseModel):
    user_id: int
    experiment_name: str  # This maps to config_key 
    variant: str  # This comes from config_value
    assigned_at: datetime  # This maps to created_at
    status: str
    meta_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# Comprehensive user personalization data
class UserPersonalizationData(BaseModel):
    profile: Optional[UserProfileResponse] = None
    features: List[UserFeatureResponse] = []
    recent_activity: Optional[Dict[str, Any]] = None
    preferences_summary: Optional[Dict[str, Any]] = None

# API Response models
class UserProfileCreatedResponse(PersonalizationBaseResponse):
    data: UserProfileResponse

class UserProfileUpdatedResponse(PersonalizationBaseResponse):
    data: UserProfileResponse

class UserFeatureSetResponse(PersonalizationBaseResponse):
    data: UserFeatureResponse

class UserPersonalizationResponse(PersonalizationBaseResponse):
    data: UserPersonalizationData

# Health check models
class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    service: str = "personalization-service"
    timestamp: datetime = Field(default_factory=datetime.now)

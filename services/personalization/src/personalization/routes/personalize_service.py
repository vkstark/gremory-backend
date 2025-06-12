from typing import Optional, Dict, Any, List
from enum import Enum
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime, date

from common_utils.schema.response_schema import APIResponse
from common_utils.logger import logger
from personalization.database.db_conn import PersonalizationService, create_personalization_db_manager
from personalization.database.orm_tables import ConfigType, ConfigStatus, EmbeddingType, UserProfile, UserConfiguration
from personalization.schema import (
    UserProfileResponse, CreateUserProfileRequest, UpdateUserProfileRequest,
    UserActivityRequest, UserFeatureRequest, UserFeatureResponse,
    UserExperimentResponse, PersonalizationDataResponse, UserProfileCreatedResponse, 
    UserProfileUpdatedResponse, UserFeatureSetResponse, UserPersonalizationResponse, 
    HealthCheckResponse, UserPersonalizationData
)

# Create router instead of FastAPI app
router = APIRouter()

# Global personalization service instance for this router
personalization_service: Optional[PersonalizationService] = None

def get_personalization_service() -> PersonalizationService:
    """Get personalization service instance"""
    if personalization_service is None:
        raise HTTPException(status_code=500, detail="Personalization service not initialized")
    return personalization_service

# Initialize personalization service for this router (called from main.py)
async def initialize_personalization_service():
    """Initialize personalization service"""
    global personalization_service
    if personalization_service is None:
        try:
            from common_utils.main_setting import settings
            db_manager = create_personalization_db_manager(settings)
            personalization_service = PersonalizationService(db_manager)
            logger.info("Personalization service initialized for router")
        except Exception as e:
            logger.error(f"Failed to initialize personalization service: {str(e)}")
            raise

# Cleanup personalization service (called from main.py)
async def cleanup_personalization_service():
    """Cleanup personalization service"""
    global personalization_service
    if personalization_service:
        try:
            # Add cleanup logic if needed
            personalization_service = None
            logger.info("Personalization service cleaned up for router")
        except Exception as e:
            logger.error(f"Failed to cleanup personalization service: {str(e)}")

# Root endpoint
@router.get("/")
def read_personalization_root():
    return {
        "message": "Personalization API",
        "status": "healthy",
        "endpoints": [
            "/profile", "/profile/{user_id}", "/activity", 
            "/feature/{user_id}", "/experiments/{user_id}", "/personalization/{user_id}", "/health"
        ],
        "description": "User personalization and preferences management"
    }

@router.get("/health", response_model=HealthCheckResponse)
def health_check():
    return HealthCheckResponse()

# Test endpoint for MVP1 setup verification
@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify service is working"""
    return PersonalizationDataResponse(
        message="Personalization service is working correctly",
        data={
            "service": "personalization-service",
            "version": "1.0.0",
            "status": "operational",
            "endpoints_available": [
                "/profile", "/profile/{user_id}", "/activity", 
                "/feature", "/personalization/{user_id}", "/health", "/test"
            ]
        }
    )

# ==== CORE MVP1 ENDPOINTS ====

@router.post("/profile", response_model=UserProfileCreatedResponse)
async def create_user_profile(
    request: CreateUserProfileRequest,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Create a new user profile for personalization"""
    try:
        logger.info(f"Creating profile for user {request.user_id}")
        
        # Use the UserProfileRepository directly through the service
        with service.db_manager.get_session() as session:
            from personalization.database.db_conn import UserProfileRepository
            from personalization.database.orm_tables import UserProfile
            repo = UserProfileRepository(session, UserProfile)
            
            profile_data = repo.create_or_update_profile(
                user_id=request.user_id,
                name=request.name,
                email=request.email,
                birthdate=request.birthdate,
                signup_source=request.signup_source,
                language_preference=request.language_preference,
                timezone=request.timezone,
                preferences=getattr(request, 'preferences', {})
            )
        
        if not profile_data:
            raise HTTPException(status_code=400, detail="Failed to create user profile")
        
        response_data = UserProfileResponse.model_validate(profile_data)
        return UserProfileCreatedResponse(
            message=f"User profile created successfully for user {request.user_id}",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error creating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: int,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Get user profile by user ID"""
    try:
        logger.info(f"Getting profile for user {user_id}")
        
        profile = service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"User profile not found for user {user_id}")
        
        return UserProfileResponse.model_validate(profile)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/profile/{user_id}", response_model=UserProfileUpdatedResponse)
async def update_user_profile(
    user_id: int,
    request: UpdateUserProfileRequest,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Update user profile"""
    try:
        logger.info(f"Updating profile for user {user_id}")
        
        # Build update data dict from request
        update_data = {}
        for field, value in request.model_dump(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Use the UserProfileRepository directly
        with service.db_manager.get_session() as session:
            from personalization.database.db_conn import UserProfileRepository
            from personalization.database.orm_tables import UserProfile
            repo = UserProfileRepository(session, UserProfile)
            
            updated_profile = repo.create_or_update_profile(user_id, **update_data)
            
        if not updated_profile:
            raise HTTPException(status_code=404, detail=f"User profile not found for user {user_id}")
        
        response_data = UserProfileResponse.model_validate(updated_profile)
        return UserProfileUpdatedResponse(
            message=f"User profile updated successfully for user {user_id}",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/activity")
async def track_user_activity(
    request: UserActivityRequest,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Track user activity for personalization"""
    try:
        logger.info(f"Tracking activity for user {request.user_id}")
        
        activity_data = {
            "session_message_count": request.session_message_count,
            "daily_activity_count": request.daily_activity_count,
            "recent_topics": request.recent_topics,
            "real_time_feedback": request.real_time_feedback,
            "session_metrics": request.session_metrics
        }
        
        # Remove None values
        activity_data = {k: v for k, v in activity_data.items() if v is not None}
        
        result = service.update_user_activity(request.user_id, activity_data)
        
        return PersonalizationDataResponse(
            message=f"Activity tracked successfully for user {request.user_id}",
            data={"activity_updated": True, "user_id": request.user_id}
        )
        
    except Exception as e:
        logger.error(f"Error tracking user activity: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/feature", response_model=UserFeatureSetResponse)
async def set_user_feature(
    request: UserFeatureRequest,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Set a user feature for personalization"""
    try:
        logger.info(f"Setting feature '{request.feature_name}' for user {request.user_id}")
        
        feature = service.set_user_feature(
            user_id=request.user_id,
            feature_name=request.feature_name,
            feature_value=request.feature_value,
            expires_at=getattr(request, 'expires_at', None)
        )
        
        if not feature:
            raise HTTPException(status_code=400, detail="Failed to set user feature")
        
        response_data = UserFeatureResponse.model_validate(feature)
        return UserFeatureSetResponse(
            message=f"Feature '{request.feature_name}' set successfully for user {request.user_id}",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error setting user feature: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/feature/{user_id}")
async def get_user_features(
    user_id: int,
    feature_name: Optional[str] = Query(None, description="Filter by feature name"),
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Get user features"""
    try:
        logger.info(f"Getting features for user {user_id}")
        
        features = service.get_user_features(user_id)
        
        features_data = [UserFeatureResponse.model_validate(f) for f in features]
        
        return PersonalizationDataResponse(
            message=f"Retrieved {len(features_data)} features for user {user_id}",
            data={"features": [f.model_dump() for f in features_data]}
        )
        
    except Exception as e:
        logger.error(f"Error getting user features: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/experiments/{user_id}")
async def get_user_experiments(
    user_id: int,
    status: Optional[str] = Query(None, description="Filter by experiment status"),
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Get user experiments"""
    try:
        logger.info(f"Getting experiments for user {user_id}")
        
        # Get experiments from configurations table
        with service.db_manager.get_session() as session:
            from personalization.database.db_conn import UserConfigurationRepository
            from personalization.database.orm_tables import UserConfiguration
            repo = UserConfigurationRepository(session, UserConfiguration)
            
            experiments = repo.get_user_configurations(user_id, config_type='experiment')
        
        # Convert UserConfiguration objects to UserExperimentResponse objects
        experiments_data = []
        for exp in experiments:
            experiment_dict = {
                "user_id": exp.user_id,
                "experiment_name": exp.config_key,
                "variant": exp.config_value.get('variant', 'unknown') if exp.config_value is not None else 'unknown',
                "assigned_at": exp.created_at,
                "status": exp.status,
                "meta_data": exp.meta_data
            }
            experiment_response = UserExperimentResponse(**experiment_dict)
            experiments_data.append(experiment_response)
        
        return PersonalizationDataResponse(
            message=f"Retrieved {len(experiments_data)} experiments for user {user_id}",
            data={"experiments": [e.model_dump() for e in experiments_data]}
        )
        
    except Exception as e:
        logger.error(f"Error getting user experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/personalization/{user_id}", response_model=UserPersonalizationResponse)
async def get_user_personalization_data(
    user_id: int,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Get comprehensive personalization data for a user"""
    try:
        logger.info(f"Getting personalization data for user {user_id}")
        
        # Use the service method that exists
        personalization_data = service.get_personalization_data(user_id)
        
        # Convert to response format
        from personalization.schema import UserPersonalizationData
        
        profile_data = None
        if personalization_data.get('profile'):
            profile_data = UserProfileResponse.model_validate(personalization_data['profile'])
        
        # Features and experiments are now in dict format from the service
        features_data = []
        if personalization_data.get('features'):
            # Convert dict back to list format for response
            for feature_name, feature_value in personalization_data['features'].items():
                # Create a mock UserConfiguration object for validation
                feature_config = {
                    'user_id': user_id,
                    'config_type': 'feature',
                    'config_key': feature_name,
                    'config_value': feature_value,
                    'status': 'active',
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                features_data.append(feature_config)
        
        response_data = UserPersonalizationData(
            profile=profile_data,
            features=features_data,
            recent_activity=personalization_data.get('recent_activity'),
            preferences_summary=personalization_data.get('preferences_summary')
        )
        
        return UserPersonalizationResponse(
            message=f"Personalization data retrieved for user {user_id}",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error getting personalization data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/experiment")
async def assign_user_experiment(
    user_id: int = Query(..., description="User ID"),
    experiment_name: str = Query(..., description="Experiment name"),
    variant: str = Query(..., description="Experiment variant"),
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Assign user to an A/B test experiment"""
    try:
        logger.info(f"Assigning user {user_id} to experiment '{experiment_name}' with variant '{variant}'")
        
        experiment = service.assign_experiment(
            user_id=user_id,
            experiment_name=experiment_name,
            variant=variant
        )
        
        if not experiment:
            raise HTTPException(status_code=400, detail="Failed to assign user to experiment")
        
        return PersonalizationDataResponse(
            message=f"User {user_id} assigned to experiment '{experiment_name}' with variant '{variant}'",
            data={
                "user_id": user_id,
                "experiment_name": experiment_name,
                "variant": variant,
                "assigned_at": experiment.created_at.isoformat() if experiment.created_at is not None else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error assigning user to experiment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/event")
async def log_user_event(
    user_id: int = Query(..., description="User ID"),
    event_type: str = Query(..., description="Event type"),
    event_data: Optional[Dict[str, Any]] = None,
    service: PersonalizationService = Depends(get_personalization_service)
):
    """Log a user event for analytics and personalization"""
    try:
        logger.info(f"Logging event '{event_type}' for user {user_id}")
        
        event = service.log_event(
            user_id=user_id,
            event_type=event_type,
            event_data=event_data
        )
        
        if not event:
            raise HTTPException(status_code=400, detail="Failed to log user event")
        
        return PersonalizationDataResponse(
            message=f"Event '{event_type}' logged successfully for user {user_id}",
            data={
                "user_id": user_id,
                "event_type": event_type,
                "event_id": event.id,
                "created_at": event.created_at.isoformat() if event.created_at is not None else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error logging user event: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

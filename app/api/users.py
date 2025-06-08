from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.utils.database.db_conn_updated import DatabaseManager
from app.utils.database.ORM_models.orm_tables import User
from app.logger import logger

router = APIRouter()

# User creation and management schemas
class CreateUserRequest(BaseModel):
    username: Optional[str] = Field(None, description="Username (optional for guests)")
    email: Optional[str] = Field(None, description="Email (optional for guests)")
    display_name: Optional[str] = Field(None, description="Display name")
    user_type: str = Field("registered", description="User type: registered, guest, bot")
    phone_number: Optional[str] = Field(None, description="Phone number")
    timezone: Optional[str] = Field("UTC", description="User timezone")
    language_preference: Optional[str] = Field("en", description="Language preference")

class UserResponse(BaseModel):
    id: int
    username: Optional[str]
    email: Optional[str]
    display_name: Optional[str]
    user_type: str
    status: str
    timezone: Optional[str]
    language_preference: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserCreatedResponse(BaseModel):
    success: bool = True
    message: str = "User created successfully"
    data: Optional[UserResponse] = None

class UsersListResponse(BaseModel):
    success: bool = True
    message: str = "Users retrieved successfully"
    users: List[UserResponse] = []
    total_count: int = 0

def get_db_manager():
    """Get database manager instance"""
    from app.config import settings
    return DatabaseManager(settings)

def create_error_response(status_code: int, message: str, details: Optional[str] = None):
    """Create standardized error response"""
    error_data = {
        "success": False,
        "message": message,
        "data": None
    }
    if details:
        error_data["details"] = details
    return JSONResponse(status_code=status_code, content=error_data)

@router.post("/users", response_model=UserCreatedResponse)
async def create_user(request: CreateUserRequest):
    """Create a new user"""
    try:
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            # Check if username or email already exists (if provided)
            if request.username:
                existing_user = session.query(User).filter(User.username == request.username).first()
                if existing_user:
                    return create_error_response(400, f"Username '{request.username}' already exists")
            
            if request.email:
                existing_user = session.query(User).filter(User.email == request.email).first()
                if existing_user:
                    return create_error_response(400, f"Email '{request.email}' already exists")
            
            # Create new user with all attributes
            user_kwargs = {
                'username': request.username,
                'email': request.email,
                'display_name': request.display_name or request.username or f"User_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'user_type': request.user_type,
                'phone_number': request.phone_number,
                'status': 'active',
                'timezone': request.timezone,
                'language_preference': request.language_preference,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # For guest users, generate a guest session ID
            if request.user_type == 'guest':
                import uuid
                user_kwargs['guest_session_id'] = str(uuid.uuid4())
            
            user = User(**user_kwargs)
            
            session.add(user)
            session.commit()
            session.refresh(user)
            
            user_response = UserResponse.model_validate(user)
            
            logger.info(f"Created user with ID {user.id}, username: {user.username}, type: {user.user_type}")
            
            return UserCreatedResponse(
                success=True,
                message="User created successfully",
                data=user_response
            )
            
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    """Get user by ID"""
    try:
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return create_error_response(404, f"User with ID {user_id} not found")
            
            return UserResponse.model_validate(user)
            
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.get("/users", response_model=UsersListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    user_type: Optional[str] = Query(None, description="Filter by user type"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List users with pagination and filtering"""
    try:
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            query = session.query(User)
            
            # Apply filters
            if user_type:
                query = query.filter(User.user_type == user_type)
            if status:
                query = query.filter(User.status == status)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            users = query.offset(offset).limit(per_page).all()
            
            user_responses = [UserResponse.model_validate(user) for user in users]
            
            return UsersListResponse(
                success=True,
                message="Users retrieved successfully",
                users=user_responses,
                total_count=total_count
            )
            
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.post("/users/seed-test-data")
async def seed_test_users():
    """Create test users for development and testing"""
    try:
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            # Check if test users already exist
            existing_user = session.query(User).filter(User.id == 1).first()
            if existing_user:
                return {
                    "success": True,
                    "message": "Test users already exist",
                    "data": {"users_created": 0}
                }
            
            # Create test users
            test_users = [
                User(
                    username="test_user_1",
                    email="test1@example.com",
                    display_name="Test User 1",
                    user_type="registered",
                    status="active",
                    timezone="UTC",
                    language_preference="en",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                User(
                    username="test_user_2",
                    email="test2@example.com",
                    display_name="Test User 2",
                    user_type="registered",
                    status="active",
                    timezone="UTC",
                    language_preference="en",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                User(
                    username="support_agent",
                    email="support@example.com",
                    display_name="Support Agent",
                    user_type="registered",
                    status="active",
                    timezone="UTC",
                    language_preference="en",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                User(
                    username="guest_user",
                    email=None,
                    display_name="Guest User",
                    user_type="guest",
                    guest_session_id="guest_123456",
                    status="active",
                    timezone="UTC",
                    language_preference="en",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                User(
                    username="ai_bot",
                    email=None,
                    display_name="AI Assistant",
                    user_type="bot",
                    status="active",
                    timezone="UTC",
                    language_preference="en",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            ]
            
            for user in test_users:
                session.add(user)
            
            session.commit()
            
            # Get the created user IDs
            session.refresh(test_users[0])  # Refresh to get the assigned IDs
            created_ids = [user.id for user in test_users]
            
            logger.info(f"Created test users with IDs: {created_ids}")
            
            return {
                "success": True,
                "message": f"Created {len(test_users)} test users",
                "data": {
                    "users_created": len(test_users),
                    "user_ids": created_ids
                }
            }
            
    except Exception as e:
        logger.error(f"Error seeding test users: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.delete("/users/{user_id}")
async def delete_user(user_id: int):
    """Delete a user (soft delete by setting status to 'deleted')"""
    try:
        db_manager = get_db_manager()
        
        with db_manager.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return create_error_response(404, f"User with ID {user_id} not found")
            
            # Update user status and timestamp using update() method
            session.query(User).filter(User.id == user_id).update({
                'status': 'deleted',
                'updated_at': datetime.now()
            })
            session.commit()
            
            logger.info(f"Soft deleted user with ID {user_id}")
            
            return {
                "success": True,
                "message": f"User {user_id} deleted successfully"
            }
            
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return create_error_response(500, "Internal server error", str(e))

@router.get("/users-health")
async def users_health_check():
    """Health check endpoint for users service"""
    return {"status": "healthy", "service": "users-api"}

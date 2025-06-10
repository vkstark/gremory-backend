from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import routers
from app.api import chat, user_history, users
from libs.common_utils.logger import logger

# # Store initialization functions for all routers
router_initializers = {
    "chat": {
        "init": chat.initialize_chat_service,
        "cleanup": chat.cleanup_chat_service
    },
    "user_history": {
        "init": user_history.initialize_user_history_service,
        "cleanup": user_history.cleanup_user_history_service
    },
    "users": {
        "init": None,  # Users API doesn't need special initialization
        "cleanup": None
    }
    # Add other routers here as you create them
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Initialize all services
    logger.info("Starting up application...")
    
    for router_name, funcs in router_initializers.items():
        try:
            if funcs["init"]:
                await funcs["init"]()
                logger.info(f"Initialized {router_name} router")
        except Exception as e:
            logger.error(f"Failed to initialize {router_name} router: {str(e)}")
    
    yield
    
    # Shutdown - Cleanup all services
    logger.info("Shutting down application...")
    
    for router_name, funcs in router_initializers.items():
        try:
            if funcs["cleanup"]:
                await funcs["cleanup"]()
                logger.info(f"Cleaned up {router_name} router")
        except Exception as e:
            logger.error(f"Failed to cleanup {router_name} router: {str(e)}")

app = FastAPI(
    title="My API Collection",
    description="Collection of all APIs including AI Chat",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": "Welcome to My API Collection",
        "docs": "/docs",
        "available_apis": {
            "chat": "/api/v1/chat",
            "user_history": "/api/v1/user",
            "users": "/api/v1/users",
            "models": "/api/v1/models",
            "health": "/health"
        }
    }

@app.get("/health")
def main_health_check():
    return {"status": "healthy", "service": "main-api-collection"}

# Include the chat router
app.include_router(
    chat.router, 
    prefix="/api/v1", 
    tags=["chat"]
)

# Include the user history router
app.include_router(
    user_history.router, 
    prefix="/api/v1", 
    tags=["user_history"]
)

# Include the users router
app.include_router(
    users.router, 
    prefix="/api/v1", 
    tags=["users"]
)

# Add other routers here as you create them
# app.include_router(other_router.router, prefix="/api/v1", tags=["other"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )

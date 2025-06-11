from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from user_history.routes.user_history import router as user_history_router, initialize_user_history_service, cleanup_user_history_service
from common_utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting User History Service...")
    try:
        await initialize_user_history_service()
        logger.info("User History service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize user history service: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down User History Service...")
    try:
        await cleanup_user_history_service()
        logger.info("User History service cleaned up successfully")
    except Exception as e:
        logger.error(f"Failed to cleanup user history service: {str(e)}")

app = FastAPI(
    title="User History Service API",
    description="User conversation history management microservice",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint for this service
@app.get("/")
def read_root():
    return {
        "service": "User History Service",
        "status": "healthy",
        "endpoints": ["/user/{user_id}/history", "/conversation/{id}", "/health"],
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "user-history-service"}

# Include the user history router without prefix
app.include_router(user_history_router, tags=["user_history"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8002)),
        reload=True,
        log_level="info"
    )
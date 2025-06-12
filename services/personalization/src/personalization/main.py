from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

from common_utils.logger import logger

# Load environment variables
load_dotenv()

# Import the personalization router
from personalization.routes.personalize_service import router as personalization_router, initialize_personalization_service, cleanup_personalization_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Personalization Service...")
    try:
        await initialize_personalization_service()
        logger.info("Personalization service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Personalization service: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Personalization Service...")
    try:
        await cleanup_personalization_service()
        logger.info("Personalization service cleaned up successfully")
    except Exception as e:
        logger.error(f"Failed to cleanup Personalization service: {str(e)}")

app = FastAPI(
    title="Personalization Service API",
    description="AI Personalization functionality microservice",
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
        "service": "Personalization Service",
        "status": "healthy",
        "endpoints": [
            "/profile", "/profile/{user_id}", "/activity", 
            "/feature/{user_id}", "/experiments/{user_id}", "/personalization/{user_id}", "/health"
        ],
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "personalization-service"}

# Include the personalization router without prefix since this is a dedicated service
app.include_router(personalization_router, tags=["personalization"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "personalization.main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8004)),
        reload=True,
        log_level="info"
    )

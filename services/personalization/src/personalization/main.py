from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

from common_utils.logger import logger

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Personalize Service...")
    try:
        await initialize_chat_service()
        logger.info("Personalize service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Personalize service: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Chat Service...")
    try:
        await cleanup_chat_service()
        logger.info("Personalize service cleaned up successfully")
    except Exception as e:
        logger.error(f"Failed to cleanup Personalize service: {str(e)}")

app = FastAPI(
    title="Chat Service API",
    description="AI Personalize functionality microservice",
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
        "service": "Personalize Service",
        "status": "healthy",
        "endpoints": ["/chat", "/models", "/health"], # TODO
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "personalize-service"}

# Include the chat router without prefix since this is a dedicated service
app.include_router(personalise_router, tags=["chat"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8004)),
        reload=True,
        log_level="info"
    )
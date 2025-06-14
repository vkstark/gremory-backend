from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import your existing tools route, but modify the import path

from ext_tools.routes.tools import router as tools_router, initialize_tool_service, cleanup_tool_service
from common_utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Tool Service...")
    try:
        await initialize_tool_service()
        logger.info("Tool service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Tool service: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tool Service...")
    try:
        await cleanup_tool_service()
        logger.info("Tool service cleaned up successfully")
    except Exception as e:
        logger.error(f"Failed to cleanup Tool service: {str(e)}")

app = FastAPI(
    title="Tool Service API",
    description="AI Tool functionality microservice",
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
        "service": "Tool Service",
        "status": "healthy",
        "endpoints": ["/tools", "/execute", "/info", "/health"],
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ext-tool-service"}

# Include the tool router without prefix since this is a dedicated service
app.include_router(tools_router, tags=["ext_tools"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8005)),
        reload=True,
        log_level="info"
    )

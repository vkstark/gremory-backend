from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from user_profile.routes.users import router as users_router
from common_utils.logger import logger

app = FastAPI(
    title="Users Service API",
    description="User management microservice",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
        "service": "Users Service",
        "status": "healthy",
        "endpoints": ["/users", "/users/{user_id}", "/health"],
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "users-service"}

# Include the users router without prefix
app.include_router(users_router, tags=["users"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8003)),
        reload=True,
        log_level="info"
    )
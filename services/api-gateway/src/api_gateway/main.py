from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

from common_utils.logger import logger

app = FastAPI(
    title="API Gateway",
    description="Gateway routing requests to microservices",
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

# Service URLs - Configure these based on your deployment
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://chat-inference:8002")
USER_HISTORY_SERVICE_URL = os.getenv("USER_HISTORY_SERVICE_URL", "http://user-history:8001")
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://user-profile:8003")
PERSONALIZATION_SERVICE_URL = os.getenv("PERSONALIZATION_SERVICE_URL", "http://personalization:8004")

# Timeout configuration
REQUEST_TIMEOUT = 60.0

async def proxy_request(request: Request, target_url: str):
    """Proxy HTTP requests to target microservice"""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # Prepare request data
            url = f"{target_url}{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"
            
            # Get request body if present
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Forward headers (exclude host and content-length)
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in ["host", "content-length"]
            }
            
            # Make request to microservice
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body
            )
            
            # Return response
            return JSONResponse(
                content=response.json() if response.text else {},
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
    except httpx.TimeoutException:
        logger.error(f"Timeout while calling {target_url}")
        raise HTTPException(status_code=504, detail="Service timeout")
    except httpx.ConnectError:
        logger.error(f"Connection error while calling {target_url}")
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        logger.error(f"Error proxying request to {target_url}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": "API Gateway - Microservices Architecture",
        "docs": "/docs",
        "available_apis": {
            "chat": "/api/v1/chat",
            "user_history": "/api/v1/user",
            "users": "/api/v1/users",
            "personalization": "/api/v1/personalization",
            "models": "/api/v1/models",
            "health": "/health"
        },
        "services": {
            "chat-inference": CHAT_SERVICE_URL,
            "user-history": USER_HISTORY_SERVICE_URL,
            "user-profile": USERS_SERVICE_URL,
            "personalization": PERSONALIZATION_SERVICE_URL
        }
    }

@app.get("/health")
async def gateway_health_check():
    """Health check that also checks all microservices"""
    services_health = {}
    overall_healthy = True
    
    services = {
        "chat-service": f"{CHAT_SERVICE_URL}/health",
        "user-history-service": f"{USER_HISTORY_SERVICE_URL}/health",
        "users-service": f"{USERS_SERVICE_URL}/users-health",
        "personalization-service": f"{PERSONALIZATION_SERVICE_URL}/health"
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, health_url in services.items():
            try:
                response = await client.get(health_url)
                services_health[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response.elapsed.total_seconds()
                }
            except Exception as e:
                services_health[service_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                overall_healthy = False
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "service": "api-gateway",
        "services": services_health
    }

# Chat service routes
@app.post("/api/v1/chat", tags=["chat"], operation_id="send_chat_message")
async def send_chat_message(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, CHAT_SERVICE_URL)

@app.get("/api/v1/models", tags=["chat"], operation_id="get_supported_models")
async def get_supported_models(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, CHAT_SERVICE_URL)

# User history service routes
@app.get("/api/v1/user/{user_id}/history", tags=["user_history"], operation_id="get_user_history")
async def get_user_history_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

@app.post("/api/v1/user/history", tags=["user_history"], operation_id="create_new_chat_history")
async def create_chat_history_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

@app.get("/api/v1/conversation/{conversation_id}", tags=["user_history"], operation_id="get_conversation_details")
async def get_conversation_details_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

@app.get("/api/v1/conversation/{conversation_id}/messages", tags=["user_history"], operation_id="get_conversation_messages")
async def get_conversation_messages_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

@app.post("/api/v1/conversation/{conversation_id}/messages", tags=["user_history"], operation_id="send_message_to_conversation")
async def send_message_to_conversation_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

@app.put("/api/v1/conversation/{conversation_id}", tags=["user_history"], operation_id="update_conversation")
async def update_conversation_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

@app.delete("/api/v1/conversation/{conversation_id}", tags=["user_history"], operation_id="delete_conversation")
async def delete_conversation_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USER_HISTORY_SERVICE_URL)

# Users service routes
@app.get("/api/v1/users", tags=["users"], operation_id="list_users")
async def list_users_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USERS_SERVICE_URL)

@app.post("/api/v1/users", tags=["users"], operation_id="create_user")
async def create_user_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USERS_SERVICE_URL)

@app.get("/api/v1/users/{user_id}", tags=["users"], operation_id="get_user_by_id")
async def get_user_by_id_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USERS_SERVICE_URL)

@app.delete("/api/v1/users/{user_id}", tags=["users"], operation_id="delete_user")
async def delete_user_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USERS_SERVICE_URL)

@app.post("/api/v1/users/seed-test-data", tags=["users"], operation_id="seed_test_users")
async def seed_test_users_proxy(request: Request):
    path = request.url.path.replace("/api/v1", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, USERS_SERVICE_URL)

# Personalization service routes
@app.post("/api/v1/personalization/profile", tags=["personalization"], operation_id="create_user_profile")
async def create_user_profile_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

@app.get("/api/v1/personalization/profile/{user_id}", tags=["personalization"], operation_id="get_user_profile")
async def get_user_profile_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

@app.put("/api/v1/personalization/profile/{user_id}", tags=["personalization"], operation_id="update_user_profile")
async def update_user_profile_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

@app.post("/api/v1/personalization/activity", tags=["personalization"], operation_id="track_user_activity")
async def track_user_activity_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

@app.post("/api/v1/personalization/feature", tags=["personalization"], operation_id="set_user_feature")
async def set_user_feature_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

@app.get("/api/v1/personalization/feature/{user_id}", tags=["personalization"], operation_id="get_user_features")
async def get_user_features_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

@app.get("/api/v1/personalization/personalization/{user_id}", tags=["personalization"], operation_id="get_user_personalization_data")
async def get_user_personalization_data_proxy(request: Request):
    path = request.url.path.replace("/api/v1/personalization", "")
    new_request = request
    new_request._url = request.url.replace(path=path)
    return await proxy_request(new_request, PERSONALIZATION_SERVICE_URL)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 80)),
        reload=True,
        log_level="info"
    )
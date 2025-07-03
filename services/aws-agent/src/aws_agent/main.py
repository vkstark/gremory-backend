from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from .schemas.request_schemas import AWSTaskRequest, S3TaskRequest, LambdaTaskRequest, SageMakerTaskRequest, TaskResponse
from .graph.aws_multi_agent_graph import aws_multi_agent_graph
from .utils.model_utils import get_supported_models, validate_model_config
from .schemas.request_schemas import ModelProvider

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 Starting AWS Multi-Agent Service...")
    print("🔧 Initializing agents and tools...")
    
    # Validate environment
    required_env_vars = ["OPENAI_API_KEY", "GOOGLE_API_KEY"]
    for var in required_env_vars:
        if not os.getenv(var):
            print(f"⚠️  Warning: {var} not set - related models will not work")
    
    print("✅ AWS Multi-Agent Service ready!")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AWS Multi-Agent Service...")

app = FastAPI(
    title="AWS Multi-Agent Service",
    description="Multi-agent system for AWS operations using LangGraph",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AWS Multi-Agent Service",
        "version": "1.0.0",
        "description": "Multi-agent system for AWS operations",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "aws-agent"}

@app.get("/system/info")
async def get_system_info():
    """Get information about the multi-agent system"""
    return aws_multi_agent_graph.get_system_info()

@app.get("/models/supported")
async def get_supported_models_endpoint():
    """Get information about supported models"""
    return get_supported_models()

@app.post("/tasks/general", response_model=TaskResponse)
async def process_general_task(request: AWSTaskRequest):
    """
    Process a general AWS task through the multi-agent system.
    The orchestrator will analyze the task and route to appropriate specialists.
    """
    try:
        # Validate model configuration
        if not validate_model_config(request.model_name, ModelProvider(request.model_provider)):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model configuration: {request.model_provider}:{request.model_name}"
            )
        
        # Process task through multi-agent system
        result = await aws_multi_agent_graph.process_task(
            task_description=request.task_description,
            model_name=request.model_name,
            model_provider=request.model_provider.value,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 1000,
            service_preferences=[s.value for s in request.service_preferences] if request.service_preferences else None,
            additional_context=request.additional_context
        )
        
        # Convert to response format
        response = TaskResponse(
            success=result["success"],
            message=result.get("message", "Task processed successfully"),
            data=result,
            execution_path=result.get("execution_path", []),
            model_used=result.get("model_used"),
            total_execution_time=result.get("total_execution_time")
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/s3", response_model=TaskResponse)
async def process_s3_task(request: S3TaskRequest):
    """
    Process an S3-specific task directly through the S3 specialist.
    """
    try:
        # Validate model configuration
        if not validate_model_config(request.model_name, ModelProvider(request.model_provider)):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model configuration: {request.model_provider}:{request.model_name}"
            )
        
        # Create task description from S3 request
        task_description = f"S3 {request.action}"
        if request.bucket_name:
            task_description += f" bucket named {request.bucket_name}"
        if request.enable_versioning:
            task_description += " with versioning enabled"
        if request.create_folders:
            task_description += f" and create folders: {', '.join(request.create_folders)}"
        
        # Process task with S3 preference
        result = await aws_multi_agent_graph.process_task(
            task_description=task_description,
            model_name=request.model_name,
            model_provider=request.model_provider.value,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 1000,
            service_preferences=["s3"],
            additional_context={
                "action": request.action,
                "bucket_name": request.bucket_name,
                "enable_versioning": request.enable_versioning,
                "enable_encryption": request.enable_encryption,
                "create_folders": request.create_folders,
                "force_delete": request.force_delete
            }
        )
        
        # Convert to response format
        response = TaskResponse(
            success=result["success"],
            message=result.get("message", "S3 task processed successfully"),
            data=result,
            execution_path=result.get("execution_path", []),
            model_used=result.get("model_used"),
            total_execution_time=result.get("total_execution_time")
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/lambda", response_model=TaskResponse)
async def process_lambda_task(request: LambdaTaskRequest):
    """
    Process a Lambda-specific task directly through the Lambda specialist.
    """
    try:
        # Validate model configuration
        if not validate_model_config(request.model_name, ModelProvider(request.model_provider)):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model configuration: {request.model_provider}:{request.model_name}"
            )
        
        # Create task description from Lambda request
        task_description = f"Lambda {request.action}"
        if request.function_name:
            task_description += f" function named {request.function_name}"
        if request.code and request.action == "create":
            task_description += " with provided code"
        if request.payload and request.action == "invoke":
            task_description += " with payload"
        
        # Process task with Lambda preference
        result = await aws_multi_agent_graph.process_task(
            task_description=task_description,
            model_name=request.model_name,
            model_provider=request.model_provider.value,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 1000,
            service_preferences=["lambda"],
            additional_context={
                "action": request.action,
                "function_name": request.function_name,
                "code": request.code,
                "runtime": request.runtime,
                "handler": request.handler,
                "timeout": request.timeout,
                "memory_size": request.memory_size,
                "payload": request.payload
            }
        )
        
        # Convert to response format
        response = TaskResponse(
            success=result["success"],
            message=result.get("message", "Lambda task processed successfully"),
            data=result,
            execution_path=result.get("execution_path", []),
            model_used=result.get("model_used"),
            total_execution_time=result.get("total_execution_time")
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/sagemaker", response_model=TaskResponse)
async def process_sagemaker_task(request: SageMakerTaskRequest):
    """
    Process a SageMaker-specific task directly through the SageMaker specialist.
    """
    try:
        # Validate model configuration
        if not validate_model_config(request.model_name or "gpt-4o-mini", ModelProvider(request.model_provider)):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model configuration: {request.model_provider}:{request.model_name}"
            )
        
        # Create task description from SageMaker request
        task_description = f"SageMaker {request.action}"
        if request.model_name:
            task_description += f" model named {request.model_name}"
        if request.algorithm and request.action == "create":
            task_description += f" using {request.algorithm} algorithm"
        if request.model_data_url:
            task_description += f" with model data from {request.model_data_url}"
        
        # Process task with SageMaker preference
        result = await aws_multi_agent_graph.process_task(
            task_description=task_description,
            model_name=request.model_name or "gpt-4o-mini",
            model_provider=request.model_provider.value,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 1000,
            service_preferences=["sagemaker"],
            additional_context={
                "action": request.action,
                "model_name": request.model_name,
                "algorithm": request.algorithm,
                "model_data_url": request.model_data_url,
                "environment_variables": request.environment_variables
            }
        )
        
        # Convert to response format
        response = TaskResponse(
            success=result["success"],
            message=result.get("message", "SageMaker task processed successfully"),
            data=result,
            execution_path=result.get("execution_path", []),
            model_used=result.get("model_used"),
            total_execution_time=result.get("total_execution_time")
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "aws_agent.main:app",
        host="0.0.0.0",
        port=8006,
        reload=True
    )
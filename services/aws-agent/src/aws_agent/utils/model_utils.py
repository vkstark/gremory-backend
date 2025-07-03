"""
Model utilities for AWS Agent Service
"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from ..schemas.request_schemas import ModelProvider

class ModelFactory:
    """Factory class for creating LLM models"""
    
    @staticmethod
    def create_model(
        model_name: str,
        model_provider: str,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ):
        """Create a model instance based on provider and configuration"""
        if model_provider.lower() == "openai":
            return ChatOpenAI(
                model=model_name,
                temperature=temperature
            )
        elif model_provider.lower() == "google":
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        else:
            raise ValueError(f"Unsupported model provider: {model_provider}")

def get_supported_models() -> Dict[str, Any]:
    """Get information about supported models"""
    return {
        "providers": {
            "openai": {
                "models": ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4-turbo"],
                "description": "OpenAI GPT models"
            },
            "google": {
                "models": ["gemini-pro", "gemini-pro-vision"],
                "description": "Google Gemini models"
            }
        }
    }

def validate_model_config(model_name: str, model_provider: ModelProvider) -> bool:
    """Validate if the model configuration is supported"""
    supported = get_supported_models()
    provider_info = supported["providers"].get(model_provider.value)
    
    if not provider_info:
        return False
        
    return model_name in provider_info["models"]

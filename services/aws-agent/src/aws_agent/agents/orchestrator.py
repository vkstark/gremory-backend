from typing import Dict, Optional, Any, List, Union, Tuple
import os

from langchain_ollama.chat_models import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.base import BaseLanguageModel

from aws_agent.agents.prompt_management import AWS_ORCHESTRATOR_SYSTEM_PROMPT

class AWSOrchestrator:
    def __init__(self) -> None:
        self.models: Union[Dict[str, ChatGoogleGenerativeAI], Dict[str,ChatOllama], Dict[str,ChatOpenAI]] = {}
        self.system_prompt = self._get_system_prompt()
        # TODO

    def _get_system_prompt(self) -> str:
        """Define the system prompt for all models"""
        system_prompt = AWS_ORCHESTRATOR_SYSTEM_PROMPT
        return system_prompt
    
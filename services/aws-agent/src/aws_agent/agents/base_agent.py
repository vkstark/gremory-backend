from typing import Dict, Any, List, Optional
import json
from abc import ABC, abstractmethod
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models.base import BaseLanguageModel

from ..utils.model_utils import ModelFactory
from ..schemas.state_schemas import AWSMultiAgentState
from ..schemas.request_schemas import ModelProvider
from ..tools.all_aws_tools import ALL_AWS_TOOLS

class BaseAWSAgent(ABC):
    """
    Base class for AWS specialist agents that use proper tool binding.
    """
    
    def __init__(self, name: str, system_prompt: str, tools: List[Any]):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
    
    def _create_model_with_tools(self, state: AWSMultiAgentState) -> BaseLanguageModel:
        """Create a model instance bound with tools."""
        model = ModelFactory.create_model(
            model_name=state["model_name"],
            model_provider=state["model_provider"],
            temperature=state["temperature"],
            max_tokens=state["max_tokens"]
        )
        
        # Bind tools to the model (following the chat service pattern)
        try:
            return model.bind_tools(self.tools)  # type: ignore
        except AttributeError:
            # Fallback for models that don't support tool binding
            return model
    
    async def process_task(self, state: AWSMultiAgentState) -> Dict[str, Any]:
        """
        Process a task using the LangChain tool execution pattern.
        """
        try:
            # Create model with bound tools
            model_with_tools = self._create_model_with_tools(state)
            
            # Create the conversation with system prompt and task
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"""
Task: {state['task_description']}

Service Preferences: {state.get('service_preferences', 'None specified')}
Additional Context: {state.get('additional_context', 'None provided')}

Please analyze the task and use the appropriate tools to complete it. Provide a clear summary of what you accomplished.
""")
            ]
            
            # Initial model response
            response = await model_with_tools.ainvoke(messages)
            messages.append(response)
            
            # Check if the model made tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Execute tool calls and get results
                tool_results, tool_outputs = await self._execute_tool_calls(response.tool_calls)
                
                # Add tool messages to conversation
                for tool_result in tool_results:
                    messages.append(tool_result)
                
                # Get final response after tool execution
                final_response = await model_with_tools.ainvoke(messages)
                
                return {
                    'success': True,
                    'agent': self.name,
                    'tool_calls_made': len(response.tool_calls),
                    'tools_used': [tc.get('name', 'unknown') for tc in response.tool_calls],
                    'tool_results': tool_outputs,  # Preserve actual tool results
                    'final_response': final_response.content,
                    'conversation': [msg.content if hasattr(msg, 'content') else str(msg) for msg in messages],
                    'message': f"{self.name} completed task successfully with {len(response.tool_calls)} tool calls"
                }
            else:
                # No tools were called, return the response
                return {
                    'success': True,
                    'agent': self.name,
                    'tool_calls_made': 0,
                    'tools_used': [],
                    'final_response': response.content,
                    'conversation': [msg.content if hasattr(msg, 'content') else str(msg) for msg in messages],
                    'message': f"{self.name} completed task without tool calls"
                }
            
        except Exception as e:
            return {
                'success': False,
                'agent': self.name,
                'error': str(e),
                'message': f"{self.name} failed to process task: {str(e)}"
            }
    
    async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> tuple[List[ToolMessage], List[Any]]:
        """Execute tool calls and return ToolMessage objects and actual tool results."""
        tool_messages = []
        tool_outputs = []
        
        # Create tools dict for lookup
        tools_dict = {tool.name.lower(): tool for tool in self.tools}
        
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get('name', '').lower()
                tool_args = tool_call.get('args', {})
                tool_call_id = tool_call.get('id', f'call_{len(tool_messages)}')
                
                if tool_name in tools_dict:
                    # Execute the tool
                    tool = tools_dict[tool_name]
                    result = await tool.ainvoke(tool_args) if hasattr(tool, 'ainvoke') else tool.invoke(tool_args)
                    
                    # Store the actual result
                    tool_outputs.append({
                        'tool_name': tool_name,
                        'result': result
                    })
                    
                    # Create ToolMessage
                    tool_message = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(tool_message)
                else:
                    # Tool not found
                    error_message = ToolMessage(
                        content=f"Error: Tool '{tool_name}' not found. Available tools: {list(tools_dict.keys())}",
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(error_message)
                    tool_outputs.append({
                        'tool_name': tool_name,
                        'error': f"Tool not found"
                    })
                    
            except Exception as e:
                # Tool execution failed
                error_message = ToolMessage(
                    content=f"Error executing tool '{tool_call.get('name', 'unknown')}': {str(e)}",
                    tool_call_id=tool_call.get('id', f'call_{len(tool_messages)}')
                )
                tool_messages.append(error_message)
                tool_outputs.append({
                    'tool_name': tool_call.get('name', 'unknown'),
                    'error': str(e)
                })
        
        return tool_messages, tool_outputs
    
    def get_capabilities(self) -> List[str]:
        """Get the capabilities of this agent (tool names)."""
        return [tool.name for tool in self.tools]

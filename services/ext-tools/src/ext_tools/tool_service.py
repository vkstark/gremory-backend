from typing import Dict, List, Any, Optional
from langchain.tools import tool
from langchain_core.messages import ToolMessage

from common_utils.schema.response_schema import APIResponse
from common_utils.logger import logger

# Import all available tools
from ext_tools.tools.all_tools import ALL_TOOLS

class ToolService:
    def __init__(self):
        self.tools: List[Any] = []
        self.tools_dict: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize the tool service with available tools"""
        logger.info("Initializing tool service...")
        
        # Register all available tools
        self.tools = ALL_TOOLS
        self.tools_dict = {tool.name.lower(): tool for tool in self.tools}
        
        logger.info(f"Tool service initialized with {len(self.tools)} tools: {list(self.tools_dict.keys())}")
    
    async def cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info("Cleaning up tool service...")
        self.tools.clear()
        self.tools_dict.clear()
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with their information"""
        tool_info = []
        for tool in self.tools:
            tool_info.append({
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') and tool.args_schema else None
            })
        return tool_info
    
    def get_tools_dict(self) -> Dict[str, Any]:
        """Get the tools dictionary for external use"""
        return self.tools_dict.copy()
    
    def get_tools_list(self) -> List[Any]:
        """Get the tools list for external use"""
        return self.tools.copy()
    
    async def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> APIResponse:
        """
        Execute a list of tool calls and return the results
        
        Args:
            tool_calls: List of tool call dictionaries with 'name' and other parameters
            
        Returns:
            APIResponse containing the list of tool messages
        """
        api_response = APIResponse()
        
        try:
            tool_messages = []
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "").lower()
                
                if tool_name not in self.tools_dict:
                    error_msg = f"Tool '{tool_name}' not found. Available tools: {list(self.tools_dict.keys())}"
                    logger.error(error_msg)
                    # Create error tool message
                    tool_message = ToolMessage(
                        content=f"Error: {error_msg}",
                        tool_call_id=tool_call.get("id", "unknown")
                    )
                    tool_messages.append(tool_message)
                    continue
                
                try:
                    # Get the selected tool
                    selected_tool = self.tools_dict[tool_name]
                    
                    # Invoke the tool with the tool call
                    tool_result = selected_tool.invoke(tool_call)
                    
                    # Convert to ToolMessage if it's not already
                    if isinstance(tool_result, ToolMessage):
                        tool_message = tool_result
                    else:
                        # Create ToolMessage from result
                        tool_message = ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call.get("id", "unknown")
                        )
                    
                    tool_messages.append(tool_message)
                    logger.info(f"Successfully executed tool: {tool_name}")
                    
                except Exception as e:
                    error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                    logger.error(error_msg)
                    
                    # Create error tool message
                    tool_message = ToolMessage(
                        content=f"Error: {error_msg}",
                        tool_call_id=tool_call.get("id", "unknown")
                    )
                    tool_messages.append(tool_message)
            
            # Convert tool messages to serializable format
            serializable_messages = []
            for msg in tool_messages:
                serializable_messages.append({
                    "type": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                    "name": getattr(msg, 'name', None)
                })
            
            api_response.code = 200
            api_response.msg = f"Successfully executed {len(tool_calls)} tool calls"
            api_response.data = {
                "tool_messages": serializable_messages,
                "total_calls": len(tool_calls),
                "successful_calls": len([msg for msg in tool_messages if not msg.content.startswith("Error:")])
            }
            
            logger.info(f"Tool execution completed. {len(tool_calls)} calls processed")
            
        except Exception as e:
            error_msg = f"Unexpected error executing tool calls: {str(e)}"
            logger.error(error_msg)
            api_response.code = 500
            api_response.msg = error_msg
            api_response.data = {"error": error_msg}
        
        return api_response
    
    async def get_tool_info(self, tool_name: str) -> APIResponse:
        """Get detailed information about a specific tool"""
        api_response = APIResponse()
        
        try:
            tool_name_lower = tool_name.lower()
            
            if tool_name_lower not in self.tools_dict:
                api_response.code = 404
                api_response.msg = f"Tool '{tool_name}' not found"
                api_response.data = {"available_tools": list(self.tools_dict.keys())}
                return api_response
            
            tool = self.tools_dict[tool_name_lower]
            
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') and tool.args_schema else None
            }
            
            api_response.code = 200
            api_response.msg = f"Tool information for '{tool_name}'"
            api_response.data = tool_info
            
        except Exception as e:
            error_msg = f"Error getting tool info for '{tool_name}': {str(e)}"
            logger.error(error_msg)
            api_response.code = 500
            api_response.msg = error_msg
            api_response.data = {"error": error_msg}
        
        return api_response

from typing import Dict, Any, List, Optional
import time
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.state import CompiledStateGraph

from ..schemas.state_schemas import AWSMultiAgentState
from ..agents.specialists.orchestrator_agent import OrchestratorAgent
from ..agents.specialists.s3_agent import S3Agent
from ..agents.specialists.lambda_agent import LambdaAgent
from ..agents.specialists.sagemaker_agent import SageMakerAgent

class AWSMultiAgentGraph:
    """
    LangGraph implementation of the AWS Multi-Agent System.
    """
    
    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.s3_agent = S3Agent()
        self.lambda_agent = LambdaAgent()
        self.sagemaker_agent = SageMakerAgent()
        
        self.graph = self._build_graph()
    
    def _build_graph(self) -> CompiledStateGraph:
        """
        Build the LangGraph workflow for the multi-agent system.
        """
        workflow = StateGraph(AWSMultiAgentState)
        
        # Add nodes
        workflow.add_node("orchestrator", self._orchestrator_node)
        workflow.add_node("s3_specialist", self._s3_specialist_node)
        workflow.add_node("lambda_specialist", self._lambda_specialist_node)
        workflow.add_node("sagemaker_specialist", self._sagemaker_specialist_node)
        workflow.add_node("summarizer", self._summarizer_node)
        
        # Define edges
        workflow.add_edge(START, "orchestrator")
        workflow.add_conditional_edges(
            "orchestrator",
            self._route_to_specialist,
            ["s3_specialist", "lambda_specialist", "sagemaker_specialist"]
        )
        workflow.add_edge("s3_specialist", "summarizer")
        workflow.add_edge("lambda_specialist", "summarizer")
        workflow.add_edge("sagemaker_specialist", "summarizer")
        workflow.add_edge("summarizer", END)
        
        return workflow.compile()
    
    async def _orchestrator_node(self, state: AWSMultiAgentState) -> AWSMultiAgentState:
        """
        Orchestrator node that analyzes tasks and determines routing.
        """
        # Update execution path
        state["execution_path"].append("Orchestrator")
        state["current_agent"] = "Orchestrator"
        
        # Analyze the task
        analysis_result = await self.orchestrator.analyze_task(state)
        
        print(f"DEBUG: Orchestrator analysis result: {analysis_result}")
        
        if analysis_result["success"]:
            analysis = analysis_result["analysis"]
            state["task_analysis"] = analysis
            state["assigned_specialist"] = analysis["recommended_specialist"]
            state["specialist_recommendations"] = [analysis["recommended_specialist"]]
            print(f"DEBUG: Assigned specialist: {analysis['recommended_specialist']}")
        else:
            # Fallback if analysis fails
            state["assigned_specialist"] = "s3"  # Default to S3
            state["specialist_recommendations"] = ["s3"]
            print("DEBUG: Using fallback assignment - S3")
        
        return state
    
    async def _s3_specialist_node(self, state: AWSMultiAgentState) -> AWSMultiAgentState:
        """
        S3 specialist node that handles S3 operations.
        """
        # Update execution path
        state["execution_path"].append("S3_Agent")
        state["current_agent"] = "S3_Agent"
        
        # Process S3 task
        result = await self.s3_agent.process_s3_task(state)
        
        # Update state with results
        state["s3_result"] = result
        if result.get("success"):
            state["final_result"] = result
            state["completed"] = True
        
        return state
    
    async def _lambda_specialist_node(self, state: AWSMultiAgentState) -> AWSMultiAgentState:
        """
        Lambda specialist node that handles Lambda operations.
        """
        # Update execution path
        state["execution_path"].append("Lambda_Agent")
        state["current_agent"] = "Lambda_Agent"
        
        # Process Lambda task
        result = await self.lambda_agent.process_lambda_task(state)
        
        # Update state with results
        state["lambda_result"] = result
        if result.get("success"):
            state["final_result"] = result
            state["completed"] = True
        
        return state
    
    async def _sagemaker_specialist_node(self, state: AWSMultiAgentState) -> AWSMultiAgentState:
        """
        SageMaker specialist node that handles SageMaker operations.
        """
        # Update execution path
        state["execution_path"].append("SageMaker_Agent")
        state["current_agent"] = "SageMaker_Agent"
        
        # Process SageMaker task
        result = await self.sagemaker_agent.process_sagemaker_task(state)
        
        # Update state with results
        state["sagemaker_result"] = result
        if result.get("success"):
            state["final_result"] = result
            state["completed"] = True
        
        return state
    
    async def _summarizer_node(self, state: AWSMultiAgentState) -> AWSMultiAgentState:
        """
        Summarizer node that creates final task summary.
        """
        # Update execution path
        state["execution_path"].append("Summarizer")
        state["current_agent"] = "Summarizer"
        
        # Create task summary using orchestrator
        summary = await self.orchestrator.create_task_summary(state)
        
        # Update final result with summary
        if "final_result" not in state:
            state["final_result"] = {}
        
        if isinstance(state["final_result"], dict):
            state["final_result"]["task_summary"] = summary
        
        state["completed"] = True
        
        return state
    
    def _route_to_specialist(self, state: AWSMultiAgentState) -> List[str]:
        """
        Route to the appropriate specialist based on orchestrator analysis.
        """
        assigned_specialist = state.get("assigned_specialist") or []
        task_description = state.get("task_description", "")
        
        print(f"DEBUG: Routing - assigned_specialist: {assigned_specialist}")
        print(f"DEBUG: Routing - task_description: {task_description}")
        
        # Normalize the specialist name to handle different formats
        specialist_lower = str(assigned_specialist).lower()
        return assigned_specialist
        print(f"DEBUG: Routing - specialist_lower: {specialist_lower}")
        
        func_to_call = []
        if "lambda" in specialist_lower:
            print("DEBUG: Routing to lambda_specialist")
            # return "lambda_specialist"
            func_to_call.append("lambda_specialist")
        elif "sagemaker" in specialist_lower:
            print("DEBUG: Routing to sagemaker_specialist")
            # return "sagemaker_specialist"
            func_to_call.append("sagemaker_specialist")
        elif "s3" in specialist_lower:
            print("DEBUG: Routing to s3_specialist")
            # return "s3_specialist"
            func_to_call.append("s3_specialist")
        return func_to_call
        # else:
        #     # Try to determine from task analysis if available
        #     task_analysis = state.get("task_analysis")
        #     if task_analysis:
        #         primary_service = task_analysis.get("primary_service", "").lower()
        #         print(f"DEBUG: Routing fallback - primary_service: {primary_service}")
        #         if primary_service == "lambda":
        #             print("DEBUG: Routing to lambda_specialist (from task_analysis)")
        #             return "lambda_specialist"
        #         elif primary_service == "sagemaker":
        #             print("DEBUG: Routing to sagemaker_specialist (from task_analysis)")
        #             return "sagemaker_specialist"
        #         elif primary_service == "s3":
        #             print("DEBUG: Routing to s3_specialist (from task_analysis)")
        #             return "s3_specialist"
            
        #     # Final fallback - determine from task description
        #     task_description_lower = task_description.lower()
        #     if any(keyword in task_description_lower for keyword in ['lambda', 'function', 'serverless']):
        #         print("DEBUG: Routing to lambda_specialist (from task_description)")
        #         return "lambda_specialist"
        #     elif any(keyword in task_description_lower for keyword in ['sagemaker', 'model', 'ml']):
        #         print("DEBUG: Routing to sagemaker_specialist (from task_description)")
        #         return "sagemaker_specialist"
        #     else:
        #         print("DEBUG: Routing to s3_specialist (final fallback)")
        #         return "s3_specialist"  # Default to S3
    
    async def process_task(
        self,
        task_description: str,
        model_name: str = "gpt-4o-mini",
        model_provider: str = "openai",
        temperature: float = 0.1,
        max_tokens: int = 1000,
        service_preferences: Optional[List[str]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a task through the multi-agent system.
        """
        start_time = time.time()
        
        # Initialize state
        initial_state: AWSMultiAgentState = {
            "messages": [HumanMessage(content=task_description)],
            "model_name": model_name,
            "model_provider": model_provider,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "current_agent": None,
            "execution_path": [],
            "task_description": task_description,
            "service_preferences": service_preferences,
            "additional_context": additional_context,
            
            # Orchestrator state
            "assigned_specialist": None,
            "task_analysis": None,
            "specialist_recommendations": None,
            
            # Agent-specific states
            "s3_action": None,
            "bucket_name": None,
            "bucket_config": None,
            "s3_result": None,
            
            "lambda_action": None,
            "function_name": None,
            "function_code": None,
            "function_config": None,
            "lambda_result": None,
            
            "sagemaker_action": None,
            "sagemaker_model_name": None,
            "model_config": None,
            "sagemaker_result": None,
            
            # Final results
            "final_result": None,
            "completed": False
        }
        
        try:
            # Execute the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            execution_time = time.time() - start_time
            
            # Prepare response
            response = {
                "success": True,
                "task_description": task_description,
                "execution_path": final_state["execution_path"],
                "model_used": f"{model_provider}:{model_name}",
                "total_execution_time": execution_time,
                "final_result": final_state.get("final_result"),
                "task_analysis": final_state.get("task_analysis"),
                "specialist_used": final_state.get("assigned_specialist"),
                "completed": final_state.get("completed", False)
            }
            
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            return {
                "success": False,
                "error": str(e),
                "task_description": task_description,
                "execution_path": initial_state["execution_path"],
                "total_execution_time": execution_time,
                "message": f"Failed to process task: {str(e)}"
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get information about the multi-agent system.
        """
        return {
            "system_name": "AWS Multi-Agent System",
            "agents": [
                self.orchestrator.name,
                self.s3_agent.name,
                self.lambda_agent.name,
                self.sagemaker_agent.name
            ],
            "capabilities": {
                "s3": self.s3_agent.get_capabilities(),
                "lambda": self.lambda_agent.get_capabilities(),
                "sagemaker": self.sagemaker_agent.get_capabilities()
            },
            "supported_services": ["S3", "Lambda", "SageMaker"],
            "workflow": "Orchestrator -> Specialist -> Summarizer"
        }

# Global instance
aws_multi_agent_graph = AWSMultiAgentGraph()

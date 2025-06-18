from chat_inference.ext_tools_init.tool_def import (
    get_weather, add
)
from chat_inference.ext_tools_init.aws_tool_def import (
    create_s3_bucket_tool, verify_s3_bucket_tool, delete_s3_bucket_tool,
    create_lambda_function_tool, delete_lambda_function_tool, invoke_lambda_function_tool,
    create_sagemaker_model_tool, delete_sagemaker_model_tool, describe_sagemaker_model_tool
)
ALL_TOOLS = [
    get_weather, 
    add,
    create_s3_bucket_tool, verify_s3_bucket_tool, delete_s3_bucket_tool,
    create_lambda_function_tool, delete_lambda_function_tool, invoke_lambda_function_tool,
    create_sagemaker_model_tool, delete_sagemaker_model_tool, describe_sagemaker_model_tool

]
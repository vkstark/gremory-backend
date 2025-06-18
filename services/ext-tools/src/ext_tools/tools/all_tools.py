from ext_tools.tools.get_weather.get_weather import get_weather
from ext_tools.tools.calculator.calc import add
from ext_tools.tools.aws_service_create.s3_service import (
    create_s3_bucket_tool, verify_s3_bucket_tool, delete_s3_bucket_tool
)
from ext_tools.tools.aws_service_create.lambda_service import (
    create_lambda_function_tool, delete_lambda_function_tool, invoke_lambda_function_tool
)
from ext_tools.tools.aws_service_create.sagemaker_service import (
    create_sagemaker_model_tool, delete_sagemaker_model_tool, describe_sagemaker_model_tool
)

ALL_TOOLS = [
    get_weather, add,
    create_s3_bucket_tool, verify_s3_bucket_tool, delete_s3_bucket_tool,
    create_lambda_function_tool, delete_lambda_function_tool, invoke_lambda_function_tool,
    create_sagemaker_model_tool, delete_sagemaker_model_tool, describe_sagemaker_model_tool
    ]

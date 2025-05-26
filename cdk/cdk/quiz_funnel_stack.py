from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigateway,
    Duration,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="../.env")  # Load API key from root .env

class QuizFunnelStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Lambda Layer with third-party Python packages
        python_deps_layer = _lambda.LayerVersion(
            self, "QuizFunnelPythonDepsLayer",
            code=_lambda.Code.from_asset("../lambda_layers/generate_results_layer/layer.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            description="Python dependencies for Quiz Funnel Lambda functions"
        )

        # DynamoDB Table to store quiz results
        quiz_results_table = dynamodb.Table(
            self, "QuizResultsTable",
            partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Main Lambda function
        generate_results_fn = _lambda.Function(
            self, "QuizFunnelGenerateResultsFn",
            runtime=_lambda.Runtime.PYTHON_3_11,
            architecture=_lambda.Architecture.ARM_64,
            handler="generate_results_lambda.lambda_handler",
            code=_lambda.Code.from_asset("../lambda/generate_results_lambda"),
            timeout=Duration.seconds(30),
            layers=[python_deps_layer],
            environment={
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                "DYNAMODB_TABLE_NAME": quiz_results_table.table_name
            },
            description="Handles quiz input, generates AI stack, and B2B assessment"
        )

        # Grant Lambda function read/write permissions to the DynamoDB table
        quiz_results_table.grant_read_write_data(generate_results_fn)

        # API Gateway to trigger the Lambda function
        api = apigateway.RestApi(
            self, "QuizFunnelApi",
            rest_api_name="QuizFunnelServiceApi",
            description="API for Quiz Funnel Chatbot",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS, # Adjust for production
                allow_methods=apigateway.Cors.ALL_METHODS # Adjust for production, e.g., ["POST"]
            )
        )

        # Lambda integration
        lambda_integration = apigateway.LambdaIntegration(generate_results_fn)

        # Add a resource and POST method (no API key required)
        quiz_resource = api.root.add_resource("submit") # e.g., /submit endpoint
        quiz_resource.add_method("POST", lambda_integration,
            api_key_required=False # API key is not required
        )

        # Output the API Endpoint URL
        CfnOutput(self, "ApiEndpoint",
            value=api.url_for_path(quiz_resource.path),
            description="Endpoint URL for the /submit POST method"
        )

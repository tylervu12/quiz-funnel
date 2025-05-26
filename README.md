# Quiz Funnel Chatbot Backend

This project implements the backend for a quiz funnel chatbot. It uses AWS Lambda for processing, OpenAI GPT-4o for AI-driven responses, API Gateway for exposing an endpoint, and DynamoDB for data storage. The primary goal is to provide users with tailored AI tool recommendations based on their quiz inputs.

## Project Structure

```
quiz-chatbot/
├── cdk/                     # AWS CDK infrastructure code
│   ├── app.py               # CDK app entry point
│   ├── cdk/                 # Stack definitions (quiz_funnel_stack.py)
│   ├── requirements.txt     # CDK Python dependencies
│   └── cdk.json             # CDK configuration
│   └── ...
├── lambda/
│   └── generate_results_lambda/ # Source for the main quiz processing Lambda
│       ├── generate_results_lambda.py
│       └── models.py
├── lambda_layers/
│   └── generate_results_layer/ # Dockerfile & requirements to build Lambda layer
│       ├── Dockerfile
│       ├── requirements.txt
│       └── layer.zip          # (This is built using the Dockerfile)
├── .env.example             # Example environment file (copy to .env)
├── .gitignore
└── README.md
```

## Features

*   Receives quiz data (primary goal, tech skill, current tools, budget) via an API Gateway endpoint.
*   Performs a relevance check on user input using GPT-4o.
*   Generates a custom AI tool stack and summary using GPT-4o if input is relevant.
*   Assesses B2B client qualification using GPT-4o.
*   Applies a budget-based filter to the B2B qualification.
*   Stores quiz inputs and full AI summary in DynamoDB.
*   Returns a truncated preview summary and a `user_id` to the client (e.g., Landbot).

## Prerequisites

*   Python 3.11 or later
*   Node.js (for AWS CDK)
*   AWS CLI configured with appropriate credentials and AWS region
*   Docker (for building the Lambda layer)
*   An OpenAI API Key

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/tylervu12/quiz-funnel
    cd quiz-chatbot
    ```

2.  **Create and Activate Python Virtual Environment (Project Root):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install CDK Dependencies:**
    Navigate to the CDK directory and install its requirements:
    ```bash
    cd cdk
    pip install -r requirements.txt
    cd ..
    ```

4.  **Set Up Environment Variables:**
    Copy `env.example` to `.env` in the project root and add your OpenAI API Key:
    ```bash
    cp env.example .env
    ```
    Edit `.env` to look like this:
    ```
    OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    ```

## Local Testing (`generate_results_lambda`)

1.  Ensure your `.env` file in the project root is configured with your `OPENAI_API_KEY`.
2.  The Lambda function is designed to skip DynamoDB operations if the `DYNAMODB_TABLE_NAME` environment variable is not set, which is helpful for local testing focused on LLM calls.
3.  To run the Lambda function locally, execute its `if __name__ == '__main__':` block from the project root directory:
    ```bash
    python -m lambda.generate_results_lambda.generate_results_lambda
    ```
    This will use the mock event data defined within that block to simulate an API call.

## AWS Deployment with CDK

1.  **Bootstrap CDK (One-time per AWS Account/Region):**
    If you haven't used CDK in your target AWS account and region before, bootstrap it:
    ```bash
    cd cdk
    cdk bootstrap aws://<YOUR_AWS_ACCOUNT_ID>/<YOUR_AWS_REGION>
    ```

2.  **Build the Lambda Layer (`layer.zip`):**
    The Lambda function relies on a layer for its Python dependencies. This layer needs to be built using Docker.
    Navigate to the layer's directory:
    ```bash
    cd ../lambda_layers/generate_results_layer/
    ```
    Build the Docker image and extract `layer.zip`:
    ```bash
    docker build -t quiz-lambda-layer .
    # Create a dummy container from the image
    docker create --name temp_lambda_layer_container quiz-lambda-layer
    # Copy layer.zip from the container to your current directory (the layer directory)
    docker cp temp_lambda_layer_container:/lambda/layer.zip .
    # Remove the dummy container
    docker rm temp_lambda_layer_container
    ```
    After these steps, `layer.zip` will be in the `lambda_layers/generate_results_layer/` directory.
    Return to the CDK directory:
    ```bash
    cd ../../cdk
    ```

3.  **Synthesize and Deploy the CDK Stack:**
    From within the `cdk` directory:
    ```bash
    cdk synth  # Optional: to see the CloudFormation template
    cdk deploy
    ```
    This command will provision all AWS resources: API Gateway, Lambda function, DynamoDB table, and necessary IAM roles/permissions.
    Take note of the `ApiEndpoint` URL output at the end of the deployment.

## API Endpoint: Quiz Submission

*   **URL**: `[ApiEndpoint]/submit` (The `ApiEndpoint` is provided in the `cdk deploy` output)
*   **Method**: `POST`
*   **Request Body** (JSON):
    ```json
    {
      "primary_goal": "User's primary goal with AI",
      "tech_skill": "Beginner/Intermediate/Expert" 
      "tools": "User's current tech stack",
      "budget": "$0-100" 
    }
    ```
*   **Response Body** (JSON on success - status 200):
    ```json
    {
      "message": "[Truncated preview of the AI stack summary]",
      "user_id": "[UUID generated for the user's record]"
    }
    ```
*   **Error Responses**:
    *   `400 Bad Request`: Input validation failed or query out of scope.
    *   `500 Internal Server Error`: Error during LLM processing or other unexpected issues.

### Example `curl` Command for Testing Deployed API:

```bash
curl -X POST \
  YOUR_API_ENDPOINT_URL/submit \
  -H 'Content-Type: application/json' \
  -d '{ 
    "primary_goal": "Learn to build AI applications", 
    "tech_skill": "Intermediate", 
    "tools": "Python, VS Code", 
    "budget": "$0-100" 
  }'
```
(Replace `YOUR_API_ENDPOINT_URL` with the actual endpoint from `cdk deploy` output.) . 

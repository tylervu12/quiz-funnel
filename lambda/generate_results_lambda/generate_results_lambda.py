import json
import os
import uuid # Added for user_id
from datetime import datetime # Added for timestamp
import boto3 # Added for DynamoDB
from openai import OpenAI
from dotenv import load_dotenv
from models import QuizInput, AIStackOutput, B2BAssessment, RelevanceAssessmentOutput

# Load environment variables from .env file for local development
load_dotenv()

# Initialize OpenAI client
# It's good practice to check if the API key is available
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    # This will cause an error if the key is not found, 
    # which is good for early detection of configuration issues.
    # In a production Lambda, ensure OPENAI_API_KEY is set in environment variables.
    raise ValueError("OPENAI_API_KEY not found in environment variables.")
client = OpenAI(api_key=api_key)

MODEL_NAME = "gpt-4o"

# Initialize DynamoDB client
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME")
dynamodb_client = None
if DYNAMODB_TABLE_NAME:
    dynamodb_client = boto3.resource("dynamodb")
    quiz_table = dynamodb_client.Table(DYNAMODB_TABLE_NAME)
else:
    # This allows local testing without DynamoDB if table name is not set
    print("Warning: DYNAMODB_TABLE_NAME not set. DynamoDB operations will be skipped.")
    quiz_table = None 

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        quiz_input = QuizInput(**body)
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e), 'message': 'Input validation failed'})
        }

    try:
        # LLM Call #0 - Relevance Check
        relevance_check_messages = [
            {"role": "system", "content": "You are a highly proficient AI assistant. Your task is to determine if a user's stated goals and current tools indicate a genuine interest in exploring, learning about, or utilizing AI tools and technologies for personal development, productivity, business solutions, or general tech-related improvements. Be permissive if the user expresses a desire to learn or explore AI, even if the goal isn't highly specific yet."},
            {"role": "user", "content": f"""A user was asked the following questions:
1. What is your primary goal with using AI? (User's answer: '{quiz_input.primary_goal}')
2. What tools are in your current tech stack? (User's answer: '{quiz_input.tools}')

Based *only* on these answers, assess if the user's intent is relevant to seeking information, recommendations, or solutions related to AI or technology. Consider goals about learning AI, exploring AI tools, or applying AI for any purpose (personal, educational, business) as RELEVANT.

Respond strictly with a JSON object containing two keys: 'is_relevant' (boolean) and 'reasoning' (a concise explanation for your decision, especially if flagging as irrelevant, or to confirm relevance for ambiguous cases).

Example of a RELEVANT query (learning focus):
User's primary goal with using AI: "just trying to learn"
User's current tech stack: "none"
Output:
{{
  \"is_relevant\": true,
  \"reasoning\": \"User explicitly stated a goal to learn, which is relevant for AI tool exploration and recommendations.\"
}}

Example of a RELEVANT query (business focus):
User's primary goal with using AI: "Improve customer support for my ecommerce site"
User's current tech stack: "Shopify, Zendesk"
Output:
{{
  \"is_relevant\": true,
  \"reasoning\": \"User has a clear business goal where AI can be applied and is seeking solutions.\"
}}

Example of an IRRELEVANT query:
User's primary goal with using AI: "I want to bake a cake"
User's current tech stack: "oven, mixer"
Output:
{{
  \"is_relevant\": false,
  \"reasoning\": \"User's goal is unrelated to AI or technology exploration and is focused on a non-tech hobby.\"
}}

User's actual input:
Primary Goal with using AI: '{quiz_input.primary_goal}'
Current Tech Stack: '{quiz_input.tools}'

Now, provide your assessment:
"""}
        ]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=relevance_check_messages,
            response_format={"type": "json_object"}
        )
        relevance_response_content = response.choices[0].message.content
        relevance_output = RelevanceAssessmentOutput(**json.loads(relevance_response_content))

        if not relevance_output.is_relevant:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Query out of scope', 
                    'message': f"Your request about '{quiz_input.primary_goal}' appears to be outside the scope of AI tool recommendations. {relevance_output.reasoning}"
                })
            }

        # LLM Call #1 - Generate AI Tool Stack
        ai_stack_prompt_messages = [
            {"role": "system", "content": "You are an expert AI solutions architect with deep knowledge of a wide array of AI tools and technologies. Your primary function is to analyze a user's specific goals, technical background, and current toolset to recommend a tailored stack of AI tools. Focus on providing practical, actionable recommendations that directly address the user's stated objectives."},
            {"role": "user", "content": f"""A user has provided the following information in response to a quiz:

1.  **What is your primary goal with using AI?**
    User's Answer: '{quiz_input.primary_goal}'

2.  **How tech-savvy are you?**
    User's Answer: '{quiz_input.tech_skill}'

3.  **What tools are in your current tech stack?**
    User's Answer: '{quiz_input.tools}'

Based *exclusively* on this user profile, please generate the following:

A.  **Custom AI Tool Recommendations:** A list of specific AI tools or platforms that are highly relevant to achieving the user's 'Primary Goal'.
B.  **Detailed Explanation for Each Tool:** For every tool recommended, provide:
    *   A brief description of the tool and its core functionality.
    *   Key features that make it suitable for the user's specific 'Primary Goal' and 'Tech Skill' level.
    *   Why this tool is a good fit for someone with their 'Current Tools' (if relevant, or how it complements/integrates).
C.  **Practical Use Cases:** Illustrate with 1-2 concise examples how each recommended tool can be practically applied to help the user achieve their 'Primary Goal'.

Your entire response must be a single JSON object with one key: "ai_stack_summary".
The value of "ai_stack_summary" should be a well-formatted string (e.g., using markdown for readability if appropriate) containing all the information requested above (A, B, and C).

Example JSON output structure:
{{
  \"ai_stack_summary\": \"### Your Custom AI Tool Stack\n\n**Goal:** [User's Primary Goal Here]\n\n**1. Tool Name A**\n   - **Description:** ...\n   - **Key Features for You:** ...\n   - **Fit with Your Profile:** ...\n   - **Use Case Example:** ...\n\n**2. Tool Name B**\n   - **Description:** ...\n   - **Key Features for You:** ...\n   - **Fit with Your Profile:** ...\n   - **Use Case Example:** ...\n\n[...more tools as appropriate...]\"
}}

Ensure the recommendations are directly applicable to the user's stated 'Primary Goal'.
"""}
        ]
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=ai_stack_prompt_messages,
            response_format={"type": "json_object"} # Ensure JSON mode
        )
        ai_stack_response_content = response.choices[0].message.content
        ai_stack_output = AIStackOutput(**json.loads(ai_stack_response_content))

        # LLM Call #2 - Assess B2B Qualification
        b2b_assessment_prompt_messages = [
            {"role": "system", "content": "You are an astute business analyst. Your task is to evaluate if a user's stated goal suggests they might be a suitable B2B client for an AI consulting and software development firm. A B2B client is defined as someone who owns/represents a business OR is looking to have custom software (MVP, tool, application) developed."},
            {"role": "user", "content": f"""A user was asked: 'What is your primary goal with using AI?'
User's Answer: '{quiz_input.primary_goal}'

Based *solely* on the user's answer to this question, determine if they meet the criteria for a B2B client. The criteria are:
1.  The user expresses intent to build or have software developed (e.g., an app, a SaaS product, an MVP, a custom tool).
OR
2.  The user represents a business and is looking to implement or integrate AI solutions into their operations or products.

Learning about AI for personal use or general curiosity does NOT qualify as B2B unless explicitly tied to a business or software development goal.

Respond strictly with a JSON object containing a single boolean key 'b2b_qualified'.

Example of a QUALIFIED B2B client (software development focus):
User's Answer: "I want to build an AI tool to automate my customer service emails."
Output:
{{
  \"b2b_qualified\": true
}}

Example of a QUALIFIED B2B client (business implementation focus):
User's Answer: "As a small business owner, I need to understand how AI can improve my marketing efforts."
Output:
{{
  \"b2b_qualified\": true
}}

Example of a NON-QUALIFIED B2B client (personal learning):
User's Answer: "I'm just trying to learn Python for AI."
Output:
{{
  \"b2b_qualified\": false
}}

Example of a NON-QUALIFIED B2B client (unrelated hobby):
User's Answer: "I want to use AI to make better paintings."
Output:
{{
  \"b2b_qualified\": false
}}

User's actual answer to 'What is your primary goal with using AI?': '{quiz_input.primary_goal}'

Now, provide your assessment:
"""}
        ]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=b2b_assessment_prompt_messages,
            response_format={"type": "json_object"} # Ensure JSON mode
        )
        b2b_assessment_response_content = response.choices[0].message.content
        b2b_assessment_output = B2BAssessment(**json.loads(b2b_assessment_response_content))

    except Exception as e:
        # Handle LLM call or parsing errors
        # You might want to log the specific error (e) for debugging
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e), 
                'message': 'An error occurred during LLM processing. Please try again.',
                # Fallback message as per instructions
                'preview_summary': 'We encountered an issue generating your personalized AI stack. Please try again later.',
                'b2b_qualified': False # Default to False on error
            })
        }

    # Additional B2B qualification based on budget
    if b2b_assessment_output.b2b_qualified:
        if quiz_input.budget not in ["$2000-5000", "$5000+"]:
            b2b_assessment_output.b2b_qualified = False

    # Step 3: PREVIEW CUTTING LOGIC
    preview_summary = truncate_preview(ai_stack_output.ai_stack_summary).replace("\\n", "\n")


    # Step 4: DYNAMODB STORAGE
    if quiz_table:
        user_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        item_to_save = {
            "user_id": user_id,
            "primary_goal": quiz_input.primary_goal,
            "tech_skill": quiz_input.tech_skill,
            "tools": quiz_input.tools,
            "budget": quiz_input.budget,
            "ai_stack_summary": ai_stack_output.ai_stack_summary, # Full version
            "preview_summary": preview_summary, # Truncated version
            "b2b_qualified": b2b_assessment_output.b2b_qualified,
            "created_at": timestamp
        }

        try:
            quiz_table.put_item(Item=item_to_save)
            print(f"Successfully saved item to DynamoDB for user_id: {user_id}")
        except Exception as db_error:
            # Log DynamoDB error but don't fail the whole request to Landbot
            # Landbot still needs its response. Consider more robust error logging/alarming here.
            print(f"Error saving to DynamoDB: {str(db_error)}. Item: {json.dumps(item_to_save)}")
            # Optionally, you could modify the response to Landbot or raise an alert

    # Step 5 (Return to Landbot) - this is the structure
    return {
        'statusCode': 200,
        'body': json.dumps({
        'message': preview_summary.replace("\\n", "\n"),
        'user_id': user_id,
        'b2b_qualified': b2b_assessment_output.b2b_qualified,
        'stack_summary': ai_stack_output.ai_stack_summary.replace("\\n", "\n")
    })
    }

def truncate_preview(text: str) -> str:
    mid = len(text) // 2
    while mid < len(text) and not text[mid].isspace():
        mid += 1
    return text[:mid]

# Example usage (for local testing, not part of Lambda deployment package)
if __name__ == '__main__':
    # Ensure OPENAI_API_KEY is in your .env file for this to work
    mock_event = {
        'body': json.dumps({
            'primary_goal': 'build a SaaS for project management',
            'tech_skill': 'Intermediate',
            'tools': 'Jira, Slack',
            'budget': '$5000+'
        })
    }
    response = lambda_handler(mock_event, None)
    print(json.dumps(json.loads(response['body']), indent=2) if response['statusCode'] == 200 else response)

    mock_event_fail_llm = {
        'body': json.dumps({
            'primary_goal': 'break the internet with my genius idea',
            'tech_skill': 'Expert',
            'tools': 'Vim, coffee',
            'budget': '$0-100' # This will make b2b false after budget check
        })
    }
    # To test LLM error, you could temporarily invalidate the API key or model name
    # Or simulate a malformed response if the LLM doesn't adhere to JSON output
    print("\nTesting B2B qualification (should be False due to budget):")
    response = lambda_handler(mock_event_fail_llm, None)
    print(json.dumps(json.loads(response['body']), indent=2) if response['statusCode'] == 200 else response)

    mock_event_irrelevant = {
        'body': json.dumps({
            'primary_goal': 'I want to go snowboarding',
            'tech_skill': 'Beginner',
            'tools': 'Snowboard, Goggles',
            'budget': '$0-100'
        })
    }
    print("\nTesting Irrelevant Query:")
    response = lambda_handler(mock_event_irrelevant, None)
    print(json.dumps(json.loads(response['body']), indent=2) if response['statusCode'] == 200 else response) 
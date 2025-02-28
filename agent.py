"""
Code initially to run an agent that can handle cloud functions.
"""

import os
from mistralai import Mistral
import discord
import asyncio  # Import asyncio for running async code
import json
from tools.aws import start_instance, run_command
import time
from prompts import EXTRACT_TOOL_PROMPT, ALL_TOOLS
import boto3
from dotenv import load_dotenv
from tools.session import PersistentSSMSession

# Load environment variables from .env file
load_dotenv()

# Retrieve AWS credentials and instance ID from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
INSTANCE_ID = os.getenv("INSTANCE_ID")

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant."

from dotenv import load_dotenv

load_dotenv()

EXTRACT_PLAN_PROMPT = f"""
Analyze the given message and determine whether it is related to managing AWS infrastructure.  
If it is **not** related to AWS infrastructure, return an empty list: `[]`.  

If it **is** related to AWS infrastructure, generate a structured plan using the following tools:  
{ALL_TOOLS}  

Each tool may require specific parameters. If parameters are necessary, extract and specify them in the response.  

### **Response Format:**
Return a JSON list of objects. Each object must have:  
- `"tool"`: The exact tool name (string).  
- `"parameters"`: A dictionary of required parameters (if applicable).  
- `"description"`: A description of the action you are taking.

### **Examples:**  

#### **AWS-related message:**  
**Message:** "Can you please boot up my AWS Instance?"  
**Response:** `[{{"tool": "start_instance", "description": "Starting the instance."}}]`  

#### **Non-AWS message:**  
**Message:** "Can you run the `main.py` file?"  
**Response:** `[{{"tool": "run_command", "command": "python3 main.py", "description": "Running the `main.py` file."}}]`  

#### **Complex multi-step command:**  
**Message:** "Can you navigate into the `home` directory, make a directory called `test`, and enter that directory?"  
**Response:** `[  
    {{"tool": "run_command", "command": "cd home", "description": "Navigating into the home directory."}},  
    {{"tool": "run_command", "command": "mkdir test", "description": "Making the test directory."}},  
    {{"tool": "run_command", "command": "cd test", "description": "Navigating into the created test directory."}}  
]`  
"""

TOOLS_PROMPT = """
You are a helpful AWS infrastructure assistant.
Given the name of a function to use, use your tools fulfill the request. In addition, using the tool parameters, explain how you completed the request.
Only use tools if needed. Pass in the proper parameters as stated by the request, as well! Lastly, return in Markdown.
"""


class AWSAgent:
    def __init__(self):
        """
        Initialize agent with API key
        """
        # Check for API key
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        if not MISTRAL_API_KEY:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")


        # Define clients and tools
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.ssm = PersistentSSMSession()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "start_instance",
                    "description": "Check if AWS instance is not started; if not, start it.",
                    "parameters": {
                        "type": "object",
                        "properties": {},  # Explicitly define empty properties
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a command within an AWS instance.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                        },
                        "required": ["command"],
                    },
                },
            },
        ]
        self.tools_to_functions = {
            "start_instance": start_instance,
            "run_command": self.ssm.execute_command,
        }

    async def extract_plan(self, message: str) -> dict:
        """
        Extract plan instead of singular tool.
        """
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_PLAN_PROMPT},
                {"role": "user", "content": f"Discord message: {message}\nOutput:"},
            ],
            response_format={"type": "json_object"},
        )

        message = response.choices[0].message.content

        # obj = json.loads(message)
        if not len(message):
            return None

        return message

    async def extract_tool(self, message: str) -> dict:
        """
        Working demo: extract the correct tool call from the message.
        """
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_TOOL_PROMPT},
                {"role": "user", "content": f"Discord message: {message}\nOutput:"},
            ],
            response_format={"type": "json_object"},
        )

        message = response.choices[0].message.content

        obj = json.loads(message)
        if obj["tool"] == "none":
            return None

        return obj

    async def get_data_with_tools(self, tool: dict, request: str):
        """
        Working demo: run the right call, return a summary to the user.
        """
        # Check which tool to use
        full_tool_str = f"Request: {request}\nFunction: {tool["tool"]}\n"
        for key in tool:
            if key != "tool":
                full_tool_str += f"{key}: {tool[key]}\n"

        messages = [
            {"role": "system", "content": TOOLS_PROMPT},
            {"role": "user", "content": f"Function: {tool}"},
        ]

        # Require the agent to use a tool with the "any" tool choice.
        tool_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
            tools=self.tools,
            tool_choice="any",
        )

        # print(f"Tool response message: {tool_response.choices[0].message}")
        messages.append(tool_response.choices[0].message)

        # Perform tool call
        tool_call = tool_response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_params = {}
        if tool_call.function.arguments:
            function_params = json.loads(tool_call.function.arguments)

        # Ensure function_result is a string before appending
        function_result = self.tools_to_functions[function_name](**function_params)
        if not isinstance(function_result, str):
            function_result = json.dumps(function_result)

        # Append the tool call and its result to the messages.
        messages.append(
            {
                "role": "tool",
                "name": function_name,
                "content": function_result,
                "tool_call_id": tool_call.id,
            }
        )

        # Run the model again to generate the summary.
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        return response.choices[0].message.content

    async def run(self, message: discord.Message):
        """
        Extract the proper tool, create a thread, perform all functions in the plan, and return responses.
        """
        # Extract a plan (which may contain multiple tool calls)
        plan = await self.extract_plan(message.content)
        if not plan or plan == "[]":
            await message.reply(
                "I couldn't find any AWS-related tasks in your request."
            )
            return

        # Parse JSON into a list of tool calls, create thread
        tool_calls = json.loads(plan)
        thread = await message.create_thread(name=f"AWS Task - {message.author.name}")
        await thread.send(f"Processing {len(tool_calls)} steps...")

        # Iterate over each tool call and execute
        final_response = ""
        for i, tool in enumerate(tool_calls):
            await thread.send(f"Step {i+1}/{len(tool_calls)}: {tool['description']}...")
            tool_response = await self.get_data_with_tools(tool, message.content)
            
            # Show plan messages
            if i < len(tool_calls) - 1:
                await thread.send(f"**✅ Step {i+1}**:\n{tool_response}")
            else:
                final_response = tool_response

            # Sleep to give agent a bit of time
            await asyncio.sleep(2)

        # Send final response in thread
        if len(final_response) > 1900:
            final_response = final_response[:1900] + "..."
        await message.reply(
            f"**Task completed!** 🎉\n\n{final_response if final_response else '✅ All steps completed successfully.'}\n\n"
            f"**Want more details?** View the agent's thread [here]({thread.jump_url})."
        )

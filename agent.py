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
from prompts import (
    EXTRACT_TOOL_PROMPT,
    ALL_TOOLS,
    EXTRACT_PLAN_PROMPT,
    TOOLS_PROMPT,
    FINAL_SUMMARY_PROMPT,
    SUMMARIZE_TOOL_USE_PROMPT,
)
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

# Model and env variable config
MISTRAL_MODEL = "mistral-large-latest"
from dotenv import load_dotenv

load_dotenv()


class AWSAgent:
    """
    Agent class to deal with and interact with AWS instance.
    """

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

        # Create a tool string
        def create_tool_str(tool: dict):
            full_tool_str = f"Function: {tool["tool"]}\n"
            for key in tool:
                if key != "tool":
                    full_tool_str += f"{key}: {tool[key]}\n"
            return full_tool_str

        # Check which tool to use
        full_tool_str = create_tool_str(tool)
        messages = [
            {"role": "system", "content": TOOLS_PROMPT},
            {"role": "user", "content": full_tool_str},
        ]

        # Require the agent to use a tool with the "any" tool choice.
        tool_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
            tools=self.tools,
            tool_choice="any",
        )
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

        # Format tool call record for the prompt
        tool["content"] = function_result
        final_tool_str = create_tool_str(tool)

        # Run the model again to generate the summary.
        summary_messages = [
            {
                "role": "system",
                "content": f"{SUMMARIZE_TOOL_USE_PROMPT}\n\n{final_tool_str}",
            },
        ]
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=summary_messages,
        )

        return response.choices[0].message.content, final_tool_str

    async def summarize_actions(self, request: str, messages: list[str]):
        """
        Prompt a model to summarize all of the messages.
        """

        # Create a string from messages
        def format_as_bulleted_list(strings: list[str]):
            return "\n".join(f"- {s}" for s in strings)

        formatted_steps = format_as_bulleted_list(messages)

        # Prompt model to summarize
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"{FINAL_SUMMARY_PROMPT}\n\n{formatted_steps}",
                },
                {"role": "user", "content": request},
            ],
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
        step_summaries = []
        for i, tool in enumerate(tool_calls):
            await thread.send(
                f"**⏳ Step {i+1}/{len(tool_calls)}:** {tool['description']}..."
            )
            tool_response, tool_string = await self.get_data_with_tools(
                tool, message.content
            )

            # Show plan messages, give agent a bit of time
            await thread.send(f"**✅ Step {i+1}**:\n{tool_response}")
            step_summaries.append(tool_string)
            step_summaries.append(tool_response)
            await asyncio.sleep(2)

        # Send final response in thread
        final_response = await self.summarize_actions(message.content, step_summaries)
        if len(final_response) > 1500:
            final_response = final_response[:1500] + "..."
        await message.reply(
            f"**Task completed!** 🎉\n\n{final_response if final_response else '✅ All steps completed successfully.'}\n\n"
            f"**Want more details?** View the agent's thread [here]({thread.jump_url})."
        )

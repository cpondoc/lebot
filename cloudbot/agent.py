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

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant."

from dotenv import load_dotenv

load_dotenv()

EXTRACT_TOOL_PROMPT = """
Given the below message, check if it is talking about managing AWS infrastructure. If so, find the corresponding tool, from the following options.
Each tool may also have a set of parameters. If the set of parameters is listed, also specify what parameters are needed for the function call. 

Function: start_instance = Function to start an AWS instance.
Function: run_command = Run a command within the AWS instance.
    - Parameter: command (string) = what command to run within the AWS instane. 

If there is no tool, return {"tool": "none"}.

Otherwise, return the full name of the tool and the corresponding parameters in JSON format.

Example:
Message: Can you please boot up my AWS Instance?
Response: {"tool": "start_instance"}

Example:
Message: Can you run the main.py file?
Response: {"tool": "run_command", "command": "python3 main.py"}
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

        # Define client and tools
        self.client = Mistral(api_key=MISTRAL_API_KEY)
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
            "run_command": run_command,
        }

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
        # print(f"Tool Call: \n{full_tool_str}")
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
        Extract the proper tool, perform the function, and return response
        """
        # Extract the tool from the message to verify that the user is asking about something related to cloud infrastructure.
        tool = await self.extract_tool(message.content)
        if tool is None:
            return None

        # Send a message to the user that we are fetching weather data.
        res_message = await message.reply(f"Sure! We're now running `{tool["tool"]}`.")

        # Use a second prompt chain to get the weather data and response.
        time.sleep(2)
        tool_response = await self.get_data_with_tools(tool, message.content)

        # Edit the message to show the tool data.
        if len(tool_response) > 1900:
            tool_response = tool_response[i : i + 1900]
        await res_message.edit(content=tool_response)

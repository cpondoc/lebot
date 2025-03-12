"""
Code initially to run an agent that can handle cloud functions.
"""

import os
from mistralai import Mistral
import discord
import asyncio
import json
from tools.aws import start_instance
from tools.github import setup_github_project, run_github_project
import time
from helpers.prompts import (
    EXTRACT_TOOL_PROMPT,
    ALL_TOOLS,
    EXTRACT_PLAN_PROMPT,
    TOOLS_PROMPT,
    FINAL_SUMMARY_PROMPT,
    SUMMARIZE_TOOL_USE_PROMPT,
    TOOL_SUCCESS_PROMPT,
    SUMMARIZE_TOOL_FAILURE_PROMPT,
    UNDO_STEP_PROMPT,
    FAILURE_FINAL_SUMMARY_PROMPT
)
import boto3
from dotenv import load_dotenv
from tools.session import PersistentSSMSession
import logging

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

# Set up logging
logger = logging.getLogger("discord")


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

        # Set up client + user-specific information
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.user_state_dict = {}

        # Define tools
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
            {
                "type": "function",
                "function": {
                    "name": "setup_github_project",
                    "description": "Set up a GitHub project with dependencies and environment and run the repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo_directory": {"type": "string"},
                        },
                        "required": ["repo_directory"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_github_project",
                    "description": "Run a GitHub project that has been set up.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo_directory": {"type": "string"},
                        },
                        "required": ["repo_directory"],
                    },
                },
            },
        ]

    async def extract_plan(self, message: str, memories: list) -> dict:
        """
        Extract plan instead of singular tool.
        """
        # Add memory to prompt for plan
        str_memory = "None"
        if memories:
            str_memory = "\n".join(memories)
        logger.info(f"Memory: {str_memory}")

        # Prompt new model to extract a plan
        new_extract_plan_prompt = EXTRACT_PLAN_PROMPT.replace("memory", str_memory)
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": new_extract_plan_prompt},
                {"role": "user", "content": f"Discord message: {message}\nOutput:"},
            ],
            response_format={"type": "json_object"},
        )
        message = response.choices[0].message.content

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

    async def get_data_with_tools(
        self, tool: dict, request: str, user_session: PersistentSSMSession
    ):
        """
        Working demo: run the right call, return a summary to the user.
        """

        # Define user-specific tools to functions mapping
        tools_to_functions = {
            "start_instance": start_instance,
            "run_command": user_session.execute_command,
            "setup_github_project": lambda **kwargs: setup_github_project(
                kwargs.get("repo_directory"), user_session
            ),
            "run_github_project": lambda **kwargs: run_github_project(
                kwargs.get("repo_directory"), user_session
            ),
        }

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

        await asyncio.sleep(2)

        messages.append(tool_response.choices[0].message)

        # Perform tool call
        tool_call = tool_response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_params = {}
        if tool_call.function.arguments:
            function_params = json.loads(tool_call.function.arguments)

        # Ensure function_result is a string before appending
        function_result = tools_to_functions[function_name](**function_params)

        if not isinstance(function_result, str):
            function_result = json.dumps(function_result)

        # Format tool call record for the prompt
        tool["request result"] = function_result

        final_tool_str = create_tool_str(tool)

        tool_success = True


        # Have the model determine if the tool execution was successful
        # We ignore git for errors, because the response doesn't provide enought
        # information (at least for git clone, we extrapolate to other git commands though
        # too for this)
        # if (tool["tool"] == "setup_github_project") or (tool["tool"] == "run_command" and "git" in tool["command"]):
        #     tool_success = True
        # else:
        tool_success_messages = [
            {
                "role": "system",
                "content": f"{TOOL_SUCCESS_PROMPT}",
            },
            {
                "role": "user",
                "content": f"Input JSON = {str(tool)}\nOutput JSON = ",
            },
        ]
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=tool_success_messages,
            response_format={"type": "json_object"},
        )
        await asyncio.sleep(2)
        tool_success = json.loads(response.choices[0].message.content)["successful"]
        if tool_success not in ["True", "False"]:
            raise Exception("The model did not return True or False for the successful field!")
        
        if tool_success == "False":
            tool_failure_message = [
                {
                    "role": "system",
                    "content": f"{SUMMARIZE_TOOL_FAILURE_PROMPT}\n\n{final_tool_str}",
                },
            ]
            response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=tool_failure_message,
            )
            await asyncio.sleep(2)
            return response.choices[0].message.content, final_tool_str, False

        await asyncio.sleep(2)
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
        await asyncio.sleep(2)

        return response.choices[0].message.content, final_tool_str, True

    async def summarize_actions(self, request: str, messages: list[str], success: bool):
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
        if not success:
            response = await self.client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"{FAILURE_FINAL_SUMMARY_PROMPT}\n\n{formatted_steps}",
                    },
                    {"role": "user", "content": request},
                ],
            )
        return response.choices[0].message.content


    async def run(self, message: discord.Message):
        """
        Extract the proper tool, create a thread, perform all functions in the plan, and return responses.
        """
        try:
            # First, handle the creation of a new user, if not created
            if message.author not in self.user_state_dict:
                self.user_state_dict[message.author] = (
                    PersistentSSMSession(message.author),
                    [],
                )

            # Extract a plan (which may contain multiple tool calls)
            current_user_state = self.user_state_dict[message.author]
            plan = await self.extract_plan(message.content, current_user_state[1])
            if not plan or plan == "[]":
                await message.reply(
                    "I couldn't find any AWS-related tasks in your request."
                )
                return
            tool_calls = json.loads(plan)

            # Create thread
            MAX_TITLE_LENGTH = 100
            prefix = "🧵 "
            max_content_length = MAX_TITLE_LENGTH - len(prefix)

            if len(message.content) > max_content_length:
                thread_name = f"{prefix}{message.content[:max_content_length - 3]}..."
            else:
                thread_name = f"{prefix}{message.content}"

            thread = await message.create_thread(name=thread_name)
            await thread.send(f"Processing {len(tool_calls)} steps...")
            await asyncio.sleep(2)

            # Iterate over each tool call and execute
            step_summaries = []
            step_memory = ""
            tool_success = True

            undo_failures = False
            for i, tool in enumerate(tool_calls):
                await thread.send(
                    f"**⏳ Step {i+1}/{len(tool_calls)}:** {tool['description']}..."
                )
                tool_response, tool_string, tool_success = await self.get_data_with_tools(
                    tool, message.content, current_user_state[0]
                )

                if not tool_success:
                    await thread.send(f"**Step❌ {i+1}**:\n{tool_response}")
                    step_memory += f"**❌ Step {i+1}**:\n{tool_response}\n"
                    await thread.send(f"🔄 We will now attempt to undo any altered state!")
                    for j in range(i, -1, -1):
                        await thread.send(
                            f"**⏳ Reversing Step {j+1}/{i+1}:** {tool_calls[j]['description']}..."
                        )
                        undo_steps_messages = [
                            {
                                "role": "system",
                                "content": f"{UNDO_STEP_PROMPT}",
                            },
                            {
                                "role": "user",
                                "content": f"Original Input JSON:{tool_calls[j]}\nOutput JSON to Undo the Original Input JSON:\n",
                            },
                        ] 

                        response = await self.client.chat.complete_async(
                            model=MISTRAL_MODEL,
                            messages=undo_steps_messages,
                            response_format={"type": "json_object"},          
                        )
                        await asyncio.sleep(2)

                        undo_tool = response.choices[0].message.content

                        if undo_tool == "{}":
                            await thread.send(f"**🔄✅ Reversing Step {j+1}**:\n{tool_calls[j]["description"][:len(tool_calls[j]["description"])-1]} did not alter any state!")
                            continue
                        undo_tool = json.loads(undo_tool)
                        undo_tool_response, _, undo_tool_success = await self.get_data_with_tools(
                            undo_tool, message.content, current_user_state[0]
                        )
                        if not undo_tool_success:
                            await thread.send(f"**🔄❌ Reversing Step {j+1} Failed**:\nWe're sorry, but reversing this command failed, and altered state may still persist from this step!")
                            undo_failures = True
                        else:
                            await thread.send(f"**🔄✅ Reversing Step {j+1} **:\n{undo_tool_response}")
                    if not undo_failures:
                        await thread.send(f"**🔄🎉** All altered state has been undone to the best of our ability!")
                    else:
                        await thread.send(f"**🔄🎉** We undid as much altered state as possible with our best efforts, but at least one error was identified!")
                    break
                
                if len(tool_response) > 1900:
                    for j in range(0, len(tool_response), 1900):
                        if j == 0:
                            await thread.send(f"**✅ Step {i+1}**:\n{tool_response[j : j + 1900]}")
                        else:
                            await thread.send(f"{tool_response[j : j + 1900]}")
                else:
                    await thread.send(f"**✅ Step {i+1}**:\n{tool_response}")
                step_memory += f"**✅ Step {i+1}**:\n{tool_response}"
                step_summaries.append(tool_string)
                step_summaries.append(tool_response)
                await asyncio.sleep(2)

            self.user_state_dict[message.author][1].append(step_memory)

            # Send final response in thread
            final_response = await self.summarize_actions(
                message.content, step_summaries, tool_success
            )
      
            if tool_success:
                if len(final_response) > 1900:
                    for j in range(0, len(final_response), 1900):
                        if j == 0:
                            await message.reply(
                                f"**Task completed!** 🎉\n\n{final_response[j : j + 1900] if final_response[j : j + 1900] else '✅ All steps completed successfully.'}\n\n"
                            )
                        else:
                            await message.reply(
                                f"{final_response[j : j + 1900] if final_response[j : j + 1900] else '✅ All steps completed successfully.'}\n\n"
                        )
                else:
                    await message.reply(
                        f"**Task completed!** 🎉\n\n{final_response if final_response else '✅ All steps completed successfully.'}\n\n"
                    )
                await message.reply(
                        f"**Want more details?** View the agent's thread [here]({thread.jump_url})."
                    )
              
            if not tool_success:
                if len(final_response) > 1900:
                    for j in range(0, len(final_response), 1900):
                        if j == 0:
                            await message.reply(
                                f"**Task failure! ** ❌\n{"Here is an explanation of why your request failed:\n\n" + final_response[j : j + 1900] if final_response[j : j + 1900] else 'All steps did NOT complete successfully.'}\n"
                            )
                        else:
                            await message.reply(
                                f"{final_response[j : j + 1900] if final_response[j : j + 1900] else 'All steps did NOT complete successfully.'}\n\n"
                            )
                    await message.reply(
                        f"**Want more details?** View the agent's thread [here]({thread.jump_url})."
                    )
                else:
                    await message.reply(
                        f"**Task failure! ** ❌\n{"Here is an explanation of why your request failed:\n\n" + final_response if final_response else 'All steps did NOT complete successfully.'}\n"
                    )
                if not undo_failures:
                    await message.reply(
                        f"Note that we also undid any altered state to the best of our ability.\n\n"
                        f"**Want more details?** View the agent's thread [here]({thread.jump_url})."
                    )
                else:
                    await message.reply(
                        f"Note that we also undid as much altered state as possible, but at least one error occurred in the process.\n\n"
                        f"**Want more details?** View the agent's thread [here]({thread.jump_url})."
                    )

        except Exception as e:
            await message.reply(
                f"**Error occurred ❌**: An error occurred while processing your request. Please try again!"
            )
            logger.error(f"Error in run function: {e}")

import os
import json
from mistralai import Mistral
import discord

from tools.nba import get_player_id

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant."

EXTRACT_PLAYER_PROMPT = """
Is this message explicitly requesting information about an NBA player?
If not, return {"player": "none"}.

Otherwise, return the full name of the city in JSON format.

Example:
Message: How many points did Nikola Jokic score last night?
Response: {"player": "Nikola Jokic"}

Message: Did LeBron James win or lose in his last game?
Response: {"player": "Lebron James"}

Message: How many assists is Chris Paul averaging this season?
Response: {"player": "Chris Paul"}

Message: I love Blake Griffin
Response: {"player": "none"}
"""

TOOLS_PROMPT = """
You are a helpful sports assistant.
Given a player's name and a user's request, use your tools to fulfill the request.
Only use tools if needed. If you use a tool, make sure the name is not an emptry string.
"""

class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_player_id",
                    "description": "Get the player ID given a certain player's name",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "player_name": {"type": "string"},
                        },
                        "required": ["player_name"],
                    },
                },
            }
        ]
        self.tools_to_functions = {
            "get_player_id": get_player_id,
        }

    async def test_run(self, message: str):
        """
        Sample test run, not within the Discord content.
        """
        # Extract the location from the message to verify that the user is asking about weather in a specific location.
        player = await self.extract_player(message)
        if player is None:
            return None

        # Use a second prompt chain to get the player data and response.
        player_response = await self.get_player_with_tools(player, message)

        # Edit the message to show the player data.
        return response

    async def extract_player(self, message: str) -> dict:
        """
        Extract player from the message.
        """
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_PLAYER_PROMPT},
                {"role": "user", "content": f"Discord message: {message}\nOutput:"},
            ],
            response_format={"type": "json_object"},
        )

        message = response.choices[0].message.content

        obj = json.loads(message)
        if obj["player"] == "none":
            return None

        return obj["player"]

    async def get_player_with_tools(self, player_name: str, request: str):
        """
        Extract player with tools.
        """
        messages = [
            {"role": "system", "content": TOOLS_PROMPT},
            {
                "role": "user",
                "content": f"Player: {player_name}\nRequest: {request}\nOutput:",
            },
        ]

        # Require the agent to use a tool with the "any" tool choice.
        tool_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
            tools=self.tools,
            tool_choice="any",
        )

        messages.append(tool_response.choices[0].message)

        tool_call = tool_response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_params = json.loads(tool_call.function.arguments)
        function_result = self.tools_to_functions[function_name](**function_params)

        # Append the tool call and its result to the messages.
        messages.append(
            {
                "role": "tool",
                "name": function_name,
                "content": function_result,
                "tool_call_id": tool_call.id,
            }
        )

        # Run the model again with the tool call and its result.
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content

    async def run(self, message: discord.Message):
        # The simplest form of an agent
        # Send the message's content to Mistral's API and return Mistral's response
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message.content},
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content

import os
import json
import discord
from mistralai import Mistral
from tools.web_search import get_relevant_github_repository_content

MISTRAL_MODEL = "mistral-large-latest"
SYSTEM_PROMPT = "You are a helpful assistant that returns relevant github repository urls given a natural language query."

TOOLS_PROMPT = (
    "You are a helpful search engine that finds github repositories.\n"
    "Given a user's query, use your tools to find relevant github repositories.\n"
    "Only use tools if needed. If you use a tool, make sure the name is not an empty string."
)

class MistralAgent:
    def __init__(self) -> None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable not set.")
        
        # Define available tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_relevant_github_repository_content",  # Set tool name to match the function mapping.
                    "description": "Get content of relevant github repositories from a natural language query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                },
            }
        ]
        
        # Map tool names to actual functions
        self.tools_to_functions = {
            "get_relevant_github_repository_content": get_relevant_github_repository_content,
        }
        
        self.client = Mistral(api_key=api_key)
    
    async def run(self, message: discord.Message) -> str:
        """
        Process a Discord message, use tools to extract websites, 
        and return the final result from the model.
        """
        # Use message.content to extract the text
        user_request = message.content
        
        messages = [
            {"role": "system", "content": TOOLS_PROMPT},
            {"role": "user", "content": f"Query: {user_request}\nOutput:"},
        ]
        
        # Call the model and require it to use a tool ("any" tool choice)
        tool_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
            tools=self.tools,
            tool_choice="any",
        )
        
        # Append the model's response to the conversation history
        messages.append(tool_response.choices[0].message)
        
        # Get the first tool call from the response
        tool_call = tool_response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        # Execute the corresponding tool function
        if function_name not in self.tools_to_functions:
            raise ValueError(f"Unknown tool function: {function_name}")
        function_result = self.tools_to_functions[function_name](**function_args)
        
        # Append the tool call and its result to the conversation
        messages.append({
            "role": "tool",
            "name": function_name,
            "content": function_result,
            "tool_call_id": tool_call.id,
        })
        
        # Run the model again with the updated conversation
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        
        return response.choices[0].message.content
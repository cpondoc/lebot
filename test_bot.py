import os
import discord
import logging

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent

# Set up environment variables
load_dotenv()

# Initialize Mistral agent
agent = MistralAgent()

async def process_message(message: str):
    """
    Processes a given message using the Mistral agent.
    """
    response = await agent.test_run(message)
    print(response)
    return response

# Example usage
if __name__ == "__main__":
    import asyncio
    message = "Can you explain basketball to me?"
    asyncio.run(process_message(message))
import os
import discord
import logging

from discord.ext import commands
from dotenv import load_dotenv
from agent import AWSAgent

PREFIX = "!"

# Setup logging
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
agent = AWSAgent()

# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")

# Set up team IDs
team_ids = ["458359284426866701"]


@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Process the message with the agent you wrote
    # Open up the agent.py file to customize the agent
    logger.info(f"Processing message from {message.author}: {message.content}")
    await agent.run(message)


# Commands


# This command is a general help command, and allows users to check on things the bot can do
@bot.command(name="about", help="Gives a description of what LeBot can do!")
async def about_command(ctx):
    team_mentions = ", ".join(f"<@{user_id}>" for user_id in team_ids)
    help_text = (
        "**Introducing LeBot!**\n"
        "LeBot helps you manage and use your cloud infrastructure using only natural language!"
        " Ask questions about your instance, create folders and files, and even clone and run GitHub repos!\n\n"
        "To get started, simply ask the bot a question or to do a task, and LeBot will take care of it for you.\n\n"
        "**Example Questions:**\n"
        "- *What files and folders are in my current directory?*\n"
        "- *Clone and set up this repository: <INSERT_REPOSITORY_URL>!*\n"
        "- *What is the CPU usage on my computer?*\n\n"
        "**For Support:**\n"
        f"Reach out to: {team_mentions}.\n\n"
        "**Available Commands:**\n"
        "`!about` - Displays this help message.\n"
        "`!lebron` - LeBron.\n"
    )
    await ctx.send(help_text)


# LeBron.
@bot.command(name="lebron", help="Sends a picture of LeBron James.")
async def lebron(ctx):
    lebron_image_url = "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png"  # Replace with an actual LeBron image URL
    await ctx.send(lebron_image_url)


# Start the bot, connecting it to the gateway
bot.run(token)

"""
Core of the bot, which sends queries over to the agent or handles ! commands.
"""

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
team_ids = ["458359284426866701", "1334071001041997866", "1035398837017260103"]


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
        "LeBot helps you manage and use your cloud infrastructure using only natural language! "
        "Ask questions about your instance, create folders and files, and even clone and run GitHub repos!\n\n"
        "To get started, simply ask the bot a question or to do a task, and LeBot will take care of it for you.\n\n"
        "**Example Questions:**\n"
        "- *What files and folders are in my current directory?*\n"
        "- *Clone and set up this repository: https://github.com/natalieg1/lebron-quote-generator!*\n"
        "- *What is the CPU usage on my instance?*\n\n"
        "**For Support:**\n"
        f"Reach out to: {team_mentions}.\n\n"
        "**Available Commands:**\n"
        "`!about` - Displays this help message.\n"
        "`!examples` - Gives example repositories to play around with. LeBot may not work with repos that are not listed.\n"
        "`!runbook` - Gives best practice tips on how to use LeBot\n"
        "`!lebron` - LeBron.\n\n"
        "**Project Info**\n"
        "- [LeBot Code](https://github.com/cpondoc/lebot)\n"
        "- [LeBot Video](https://www.youtube.com/watch?v=Cs7Up_YK6V4)\n"
    )
    await ctx.send(help_text)


# Provide a list of vetted repositories to use for playing around with the bot.
@bot.command(name="examples", help="More help with sample commands.")
async def examples_command(ctx):
    examples_text = (
        "**Example Repositories**\n"
        "Below are some example repositories you can use to try out LeBot!\n"
        "- [LeBron Text Printer (Bash)] https://github.com/natalieg1/bash-lebron-script\n"
        "- [Basketball ASCII Art (C++)] https://github.com/natalieg1/basketball-ascii-art\n"
        "- [LeBron Quote Generator (Python)] https://github.com/natalieg1/lebron-quote-generator\n"
    )
    await ctx.send(examples_text)


# This command is a command for best practice tips
@bot.command(name="runbook", help="Gives best practice tips on how to use LeBot!")
async def about_command(ctx):
    help_text = (
        "**Quick tips for using LeBot:**\n"
        "- Do not bombard LeBot with requests. Doing so will likely result in rate limiting errors from the Mistral API."
        ' Wait for your current command to finish, signaled by a message beginning with either "Task completed! 🎉" or "Task failure! ❌" in the main LeBot channel,'
        " before sending another request.\n"
        "- LeBot is meant to handle interacting with the cloud instance with Terminal commands like:\n"
        '   - Making files: Please make the file example_file.txt\n'
        '   - Adding text to files: Add the text "Hello World" to example_file.txt\n'
        '   - Creating directories: Please create the directory example_directory\n'
        '   - Asking about the current directory: What directory am I in right now?\n'
        'and so forth. LeBot can also set up simple Github repositories (these repositories can be seen by running the !examples command):\n'
        '   - Clone, set up, and run this repository: https://github.com/natalieg1/lebron-quote-generator\n'
        'LeBot is not meant to handle requests about altering or giving administrative information about the cloud instance itself.\n'
        '- You can also see examples of using LeBot in the examples section of the README: https://github.com/cpondoc/lebot'
    )
    await ctx.send(help_text)


# LeBron.
@bot.command(name="lebron", help="Sends a picture of LeBron James.")
async def lebron(ctx):
    lebron_image_url = "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png"
    await ctx.send(lebron_image_url)


# Start the bot, connecting it to the gateway
bot.run(token)

"""
A set of prompts for running our agent.
"""

# Prompt for simpler extract tool
EXTRACT_TOOL_PROMPT = """
Given the below message, check if it is talking about managing AWS infrastructure. If so, find the corresponding tool, from the following options.
Each tool may also have a set of parameters. If the set of parameters is listed, also specify what parameters are needed for the function call. 

Function: start_instance = Function to start an AWS instance.
Function: run_command = Run a command within the AWS instance.
    - Parameter: command (string) = what command to run within the AWS instance. 

If there is no tool, return {"tool": "none"}.

Otherwise, return the full name of the tool and the corresponding parameters in JSON format.

Example:
Message: Can you please boot up my AWS Instance?
Response: {"tool": "start_instance"}

Example:
Message: Can you run the main.py file?
Response: {"tool": "run_command", "command": "python3 main.py"}
"""

# Prompt to list all the tools
ALL_TOOLS = """
Function: start_instance = Function to start an AWS instance.
Function: run_command = Run a command within the AWS instance.
    - Parameter: command (string) = what command to run within the AWS instance. 
"""

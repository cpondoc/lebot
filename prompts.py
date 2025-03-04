"""
A set of prompts for running our agent.
"""

# Prompt for simpler extract tool
EXTRACT_TOOL_PROMPT = """
Given the below message, check if the message is talking about managing AWS infrastructure. If so, find the corresponding tool, from the following options.
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
Function: run_command = Run a command within the AWS instance.
    - Parameter: command (string) = what command to run within the AWS instance. 
"""

EXTRACT_PLAN_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, and Linux. Below, please analyze the given
message and the previous stepsand determine whether it is related to managing the user's AWS instance. The user may not specify the words "AWS" or
"instance," but will talk about activities such as opening a folder, creating a file, or running a script.

Please also take into account the previous steps you have executed. Each time you run a command, it is from the home directory; however, the user assumes 
they are in the directory specified in the previous steps, if there are any. Previous steps:
memory

If the message is **not** related to manging their AWS instance, return an empty list: `[]`.  

If the message **is** related to manging their AWS instance considering the previous steps, generate a structured plan using the following tools:  
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

**Message:** "Can you navigate into the `home` directory, make a directory called `test`, and enter that directory?"  
**Response:** `[  
    {{"tool": "run_command", "command": "cd home", "description": "Navigating into the home directory."}},  
    {{"tool": "run_command", "command": "mkdir test", "description": "Making the test directory."}},  
    {{"tool": "run_command", "command": "cd test", "description": "Navigating into the created test directory."}}  
]`  
"""

TOOLS_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, and Linux. In following messages, you will be prompted to fulfill a user
request related to someone's cloud instance. Specifically: given the name of a function to use, use the tools available to complete the request. If the
request contains parameters, please pass those into the function/tool, as well. 
"""

SUMMARIZE_TOOL_USE_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, and Linux. You have just completed a request to perform an action with a tool.

After using the tool and completing the user's request, provide the result and how you completed the user's request. Some guidelines:
- Please do not use the name of the tool in the answer, but instead describe what the tool does, based on the list of tools below. If your tool required specific parameters, describe, those, as well.
- If there is not output from running the command, the result will be "EMPTY." For instance, if there are no files after running `ls`, the result will be "EMPTY," so DO NOT MAKE UP FILES.
- USE MARKDOWN.
- FINALLY, DO NOT RETURN A LIST CONTAINING DIFFERENT TOOLS AND COMMANDS USED: use complete sentences.

List of tools:
{ALL_TOOLS}

Description of tool use:
"""

FINAL_SUMMARY_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, and Linux. You have just completed a user request around managing their AWS instance.

Below, you have a summary of the steps the agent took to fulfill the request. Given the original request and the list of steps, summarize the actions you took. If the 
user asked for a specific answer, be sure to provide the answer, as well. Some guidelines:
- You have already completed the steps below: you do not have to perform the actions again.
- Please do not use the name of the tool in the answer, but instead describe what the tool does, based on the list of tools below. If your tool required specific parameters, describe, those, as well.
- USE MARKDOWN.
- FINALLY, DO NOT RETURN A LIST CONTAINING DIFFERENT TOOLS AND COMMANDS USED: use complete sentences.

List of tools:
{ALL_TOOLS}

Steps you took:
"""

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
Function: setup_github_project = Set up a GitHub project with dependencies and environment.
    - Parameter: repo_directory (string) = Directory where the repository is cloned.
Function: run_github_project = Run a GitHub project that has been set up.
    - Parameter: repo_directory (string) = Directory where the repository is cloned.

If there is no tool, return {"tool": "none"}.

Otherwise, return the full name of the tool and the corresponding parameters in JSON format.

Example:
Message: Can you please boot up my AWS Instance?
Response: {"tool": "start_instance"}

Example:
Message: Can you run the main.py file?
Response: {"tool": "run_command", "command": "python3 main.py"}

Example:
Message: Can you download the repository at https://github.com/user/repo?
Response: {"tool": "clone_github_repo", "repo_url": "https://github.com/user/repo"}

Example:
Message: Can you set up the machine-learning-project repository I just cloned?
Response: {"tool": "setup_github_project", "repo_directory": "machine-learning-project"}

Example:
Message: git clone https://github.com/user/repo?
Response: {"tool": "clone_github_repo", "repo_url": "https://github.com/user/repo"}
"""

# Prompt to list all the tools
ALL_TOOLS = """
Function: start_instance = Function to start an AWS instance.
Function: run_command = Run a command within the AWS instance.
    - Parameter: command (string) = what command to run within the AWS instance.
Function: setup_github_project = Set up a GitHub project with dependencies and environment.
    - Parameter: repo_directory (string) = Directory where the repository is cloned.
Function: run_github_project = Run a GitHub project that has been set up.
    - Parameter: repo_directory (string) = Directory where the repository is cloned.
"""

EXTRACT_PLAN_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, and Linux. Below, please analyze the given
message and the previous steps and determine whether it is related to managing the user's AWS instance or GitHub repositories. 
The user may not specify the words "AWS" or "instance," but will talk about activities such as opening a folder, creating a file, 
running a script, or downloading a GitHub repo.

Please also take into account the previous steps you have executed. Each time you run a command, it is from the home directory; however, the user assumes 
they are in the directory specified in the previous steps, if there are any. Previous steps:
memory

If the message is **not** related to managing their AWS instance or working with code, return an empty list: `[]`.  

If the message **is** related to managing their AWS instance or working with code considering the previous steps, generate a structured plan using the following tools:  
{ALL_TOOLS}  

Each tool may require specific parameters. If parameters are necessary, extract and specify them in the response.

Some other rules:
- If we clone a repository and are asked to set it up, be sure to `cd` into the repository before running GitHub commands/functions.

### **Response Format:**
Return a JSON list of objects. Each object must have:  
- `"tool"`: The exact tool name (string).  
- Parameters required by the specific tool.
- `"description"`: A description of the action you are taking.

### **Examples:**  

#### **AWS-related message:**  
**Message:** "Can you please boot up my AWS Instance?"  
**Response:** `[{{"tool": "start_instance", "description": "Starting the instance."}}]`  

#### **GitHub-related message:**
**Message:** "Can you download the repository at https://github.com/user/repo and set it up?"  
**Response:** `[
{{"tool": "run_command", "command": "git clone https://github.com/user/repo.git", "description": "Cloning the repository."}}, 
{{"tool": "run_command", "command": "cd repo", "description": "Navigating to the cloned repository directory."}},
{{"tool": "setup_github_project", "repo_directory": "repo", "description": "Setting up the repository with all dependencies."}}
]`

#### **Command message:**  
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
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. In following messages, you will be prompted to fulfill a user
request related to someone's cloud instance. Specifically: given the name of a function to use, use the tools available to complete the request. If the
request contains parameters, please pass those into the function/tool, as well. 
"""

SUMMARIZE_TOOL_USE_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just completed a request to perform an action with a tool.

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
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just completed a user request around managing their AWS instance or working with GitHub repositories.

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

FAILURE_FINAL_SUMMARY_PROMPT = f"""
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just tried to complete a user request around managing their AWS instance or working with GitHub repositories,
but the last step in the process failed.

Below, you have a summary of the steps the agent took to fulfill the request. Note that only the last step failed. Given the original request and the list of steps, summarize the actions you took. 
Some guidelines:
- You have already completed the steps below: you do not have to perform the actions again.
- Please do not use the name of the tool in the answer, but instead describe what the tool does, based on the list of tools below. If your tool required specific parameters, describe, those, as well.
- USE MARKDOWN.
- FINALLY, DO NOT RETURN A LIST CONTAINING DIFFERENT TOOLS AND COMMANDS USED: use complete sentences.

List of tools:
{ALL_TOOLS}

Steps you took:
"""


TOOL_SUCCESS_PROMPT = """
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just completed a request to perform an action with a tool.
You are now tasked with determining if the execution of the success was successful in terms of what was asked of you. 

### **Input Format:**
You will be given a JSON corresponding to the request the was executed and the result. It will have the following format:

{'tool': 'request tool', 'command': 'request command', 'description': 'request description', 'output content': 'content given from executing the request.'}

The 'tool', 'command', and 'description' fields correspond to how the request was executed. The 'output content' field corresponds to what was outputted into the
console after request was executed.

### **Response Format:**
Return a JSON of the outcome. The JSON will be of the two following forms:
{'successful': 'True'} OR {'successful': 'False'}

A request is successfully completed if the desired outcome of the request is achieved, meaning that the response would be: {'successful': 'True'}
Otherwise, the desired outcome would not be achieved, so the response would be: {'successful': 'False'}

### **Examples:**

## **Example 1**
Input JSON = {'tool': 'run_command', 'command': 'ls', 'description': 'Listing the contents of the current directory.', 'request result': 'directory1, directory2, directory3, directory4'}
Output JSON = {'successful': 'True'}

## **Example 2**
Input JSON = {'tool': 'run_command', 'command': 'cd test_folder', 'description': 'Navigating into the test_folder directory.', 'request result': 'Directory not found'}
Output JSON = {'successful': 'False'}

## **Example 3**
Input JSON = {'tool': 'run_command', 'command': 'ls', 'description': 'Listing the contents of the current directory.', 'request result': ''}
Output JSON = {'successful': 'True'}

## **Example 4**
Input JSON = {'tool': 'run_command', 'command': 'python3 testing.py', 'description': 'Running the `testing.py` file.', 'output content': 'python3: can't open file '/home/user/testing.py': [Errno 2] No such file or directory\n\nERROR conda.cli.main_run:execute(125): `conda run bash -c cd '/home/user' && python3 testing.py` failed. (See above for error)\nfailed to run commands: exit status 2'}
Output JSON = {'successful': 'False'}
# """

SUMMARIZE_TOOL_FAILURE_PROMPT = """
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just tried to complete a request to perform an action with a tool, but the requestion execution did NOT succeed.

After having tried to use the tool and but unsuccessfully completing the user's request, provide the outcome and why the request execution was unsuccessful. Some guidelines:
- Please do not use the name of the tool in the answer, but instead describe what the tool was trying to do, based on the list of tools below. If your tool required specific parameters, describe, those, as well.
- If there is not output from running the command, the result will be "EMPTY." For instance, if there are no files after running `ls`, the result will be "EMPTY," so DO NOT MAKE UP FILES.
- USE MARKDOWN.
- FINALLY, DO NOT RETURN A LIST CONTAINING DIFFERENT TOOLS AND COMMANDS USED: use complete sentences.

List of tools:
{ALL_TOOLS}

Description of tool use:
"""

UNDO_STEP_PROMPT = """
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You are tasked with undoing any state changes that may have occurred after executing a tool.
To undo the state changes of executing the tool, you will provide a new tool plan to execute that will undo the state changes.

If there is nothing to do to undo the effects of the tool, return an empty json: {}  

Otherwise, to undo state changes from the steps an unsuccessful request exection, you MUST generate a structured plan using the following tools:  
{ALL_TOOLS}

Each tool may require specific parameters. If parameters are necessary, extract and specify them in the response.

### **Input Format:**
You will be inputted a JSON object. Each object will have:  
- `"tool"`: The exact tool name (string).
- Parameters that were required by the specific tool.
- `"description"`: A description of the action you was taken.

### **Response Format:**
Return a JSON object. Each object must have:  
- `"tool"`: The exact tool name (string).  
- Parameters required by the specific tool.
- `"description"`: A description of the action you are taking to undo the input.

### **Examples:**

## **Example 1**
Original Input JSON: {"tool": "run_command", "command": "mkdir new_directory", "description": "Creating the new_directory directory."}
Output JSON to Undo the Original Input JSON: {"tool": "run_command", "command": "rm -rf new_directory", "description": "Removing the new_directory directory."}

## **Example 2**
Original Input JSON: {"tool": "run_command", "command": "cd random", "description": "Navigating into the random directory."}
Output JSON to Undo the Original Input JSON: {}

## **Example 3**
Original Input JSON: {"tool": "run_command", "command": "echo hello > text.txt", "description": "Creating text.txt and putting 'hello' into the file."}
Output JSON to Undo the Original Input JSON: {"tool": "run_command", "command": "rm -f text.txt", "description": "Removing the text.txt file."}

## **Example 4**
Original Input JSON: {"tool": "run_command", "command": "python3 testing.py", "description": "Running the `testing.py` file."}
Output JSON to Undo the Original Input JSON: {}
"""
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



TOOL_SUCCESS_PROMPT = """
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just completed a request to perform an action with a tool.
You are now tasked with determining if the execution of the success was successful in terms of what was asked of you.

Based on the output of using the tool and trying to complete the request, you return one of "True" or "False" to denote if the request was successfully completed based on the provided context of the
executed request.

A request is successfully completed if the desired outcome of the request is achieved.

Here are some examples of determining if a command was successfully completed:

Example 1
Function: run_command
command: cd test_folder
description: Navigating into the test_folder directory.
output content: Directory not found
Completed: False

Example 2
Function: run_command
command: ls 
description: Listing the contents of the current directory.
output content: directory1, directory2, directory3, directory4
Completed: False

Example 3
Function: run_command
command: ls
description: Listing the contents of the current directory.
output content:
Completed: True

IMPORTANT NOTE: Your job is always to fill in "True" or "False" in the "Completed" field and nothing more. You should should NEVER
provide text for the Function:, command:, description:, or output content: fields. In other words, you are only able to give one
word responses of "True" or "False" based off the provided context!
""" 

SUMMARIZE_TOOL_FAILURE_PROMPT = """
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just tried to complete a request to perform an action with a tool, but the requestion execution did NOT succeed.

After trying to use the tool and but unsuccessfully completing the user's request, now provide the outcome and why the request execution was unsuccessful. Some guidelines:
- Please do not use the name of the tool in the answer, but instead describe what the tool was trying to do, based on the list of tools below. If your tool required specific parameters, describe, those, as well.
- If there is not output from running the command, the result will be "EMPTY." For instance, if there are no files after running `ls`, the result will be "EMPTY," so DO NOT MAKE UP FILES.
- USE MARKDOWN.
- FINALLY, DO NOT RETURN A LIST CONTAINING DIFFERENT TOOLS AND COMMANDS USED: use complete sentences.

List of tools:
{ALL_TOOLS}

Description of tool use:
"""


UNDO_STEPS_PROMPT = """
You are a helpful assistant that is knowledgeable about cloud instances, AWS, Linux, and working with code from GitHub repositories. You have just tried to complete a request to perform an action with a tool, but the requestion execution did NOT succeed.

Since the execution of the request failed, you now want to undo ALL state changes that were done in order to carry out the request. You carried out the request in steps, and you now want to undo ALL state changes that were made in the unsuccessful
execution of the request.

If there is nothing to do to undo the steps, return an empty list: `[]`.  

Otherwise, to undo state changes from the steps an unsuccessful request exection, you MUST generate a structured plan using the following tools:  
{ALL_TOOLS}

### **Response Format:**
Return a JSON list of objects. Each object must have:  
- `"tool"`: The exact tool name (string).  
- Parameters required by the specific tool.
- `"description"`: A description of the action you are taking.

### **Examples:**  
Example 1:
STEPS
Step❌ 1:
The request execution was unsuccessful because the process attempted to display the contents of a file named "testing," but the file was not found in the directory. The specific error message was "cat: testing: No such file or directory," indicating that the file does not exist in the specified location. This suggests that either the file was not created, was deleted, or is located in a different directory.
RESPONSE TO UNDO THESE STEPS
`[]`

Example 2:
STEPS
Step✅ 1:
To complete the user's request, a command was run within the AWS instance to create a new directory. The command mkdir new_directory was used, which creates a directory named "new_directory." There was no output from running this command, so the result is "EMPTY."
Step❌ 2:
The request to navigate into the other_directory directory was unsuccessful because the directory does not exist. The output received was:
Directory not found
This indicates that there is no directory named random in the current path, which is why the attempt to change into it failed.
RESPONSE TO UNDO THESE STEPS
`[{{"tool": "run_command", "command": "rm -rf new_directory", "description": "Removing the new_directory directory."}}]`

Example 3:
STEPS
✅ Step 1:
To complete the request of creating a new file, I used a tool that runs commands within an AWS instance. The specific command I utilized was touch new_file.txt, which creates an empty file named new_file.txt.
The result of running this command is "EMPTY," as the touch command does not produce any output; it simply ensures the file exists.
✅ Step 2:
To complete the user's request, the command to add the text 'hello' to new_file.txt was executed within the AWS instance.
The result of running this command is:
EMPTY
This is because the command does not produce any output to the terminal; it simply writes the text to the file.
Step❌ 3:
The attempt to run a Python script named testing.py was unsuccessful. The error occurred because the file testing.py could not be found in the specified directory /home/joey_obrien/. This resulted in a FileNotFoundError, specifically [Errno 2] No such file or directory. Consequently, the command to execute the script failed with an exit status of 2.

Here is the error output:
python3: can't open file '/home/joey_obrien/testing.py': [Errno 2] No such file or directory
ERROR conda.cli.main_run:execute(125): `conda run bash -c cd '/home/joey_obrien' && python3 testing.py` failed. (See above for error)
failed to run commands: exit status 2

Please ensure that the testing.py file exists in the specified directory or provide the correct path to the file.
RESPONSE TO UNDO THESE STEPS
`[{{"tool": "run_command", "command": "rm new_file.txt", "description": "Removing the new_file.txt directory."}}]`
"""
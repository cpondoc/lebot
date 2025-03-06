"""
Tools for setting up GitHub repositories on an AWS instance, ensuring only conda environments are used.
"""

import json
import os
from dotenv import load_dotenv
from tools.session import PersistentSSMSession

# Load environment variables from .env file
load_dotenv()

# Retrieve AWS credentials and instance ID from environment variables
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Initialize Mistral client for understanding READMEs
from mistralai import Mistral
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
# Model and env variable config
MISTRAL_MODEL = "mistral-large-latest"

# Set conda path 
conda_path = "/home/ec2-user/miniconda/bin/conda"

# Note: We don't initialize our own session here
# The session will be passed to the functions from agent.py

def analyze_readme(repo_directory: str, ssm_session: PersistentSSMSession = None) -> dict:
    """
    Analyzes the README of a GitHub repository and extracts setup instructions.
    
    Args:
        repo_directory: Directory where the repo was cloned
        ssm_session: The persistent SSM session to use for commands
        
    Returns:
        Dict containing extracted setup information
    """
    if ssm_session is None:
        # This is a fallback in case the session isn't provided
        # but it's better to always provide the session from agent.py
        ssm_session = PersistentSSMSession()
        print("Analyze SSM session was not created")
    try:
        # Commands to check for README files in different formats
        readme_check_command = f"""
        cd /home/ec2-user/{repo_directory} && 
        if [ -f README.md ]; then
            cat README.md
        elif [ -f README.txt ]; then
            cat README.txt
        elif [ -f README ]; then
            cat README
        elif [ -f readme.md ]; then
            cat readme.md
        else
            echo "No README file found"
        fi
        """
        
        # Execute command to read README
        readme_result = ssm_session.execute_command(readme_check_command)
        
        if "No README file found" in readme_result:
            return {
                "status": "Warning",
                "error": "No README file found in the repository",
                "setup_steps": []
            }
        
        readme_content = readme_result
        
        # Check for available package managers and dependency files
        dep_check_command = f"""
        cd /home/ec2-user/{repo_directory} && 
        ([ -f requirements.txt ] && echo "requirements.txt found" || echo "requirements.txt not found") && 
        ([ -f pyproject.toml ] && echo "pyproject.toml found" || echo "pyproject.toml not found") && 
        ([ -f environment.yml ] && echo "environment.yml found" || echo "environment.yml not found") && 
        ([ -f Pipfile ] && echo "Pipfile found" || echo "Pipfile not found") && 
        ([ -f package.json ] && echo "package.json found" || echo "package.json not found") && 
        (which conda > /dev/null && echo "conda available" || echo "conda not available") && 
        (which pip > /dev/null && echo "pip available" || echo "pip not available") && 
        (which npm > /dev/null && echo "npm available" || echo "npm not available")
        """
        
        dep_check_output = ssm_session.execute_command(dep_check_command)

        runable_files_command = f"""
        cd /home/ec2-user/{repo_directory} && 
        echo "=== Executable Files ===" &&
        find . -type f -executable | sort &&
        echo -e "\\n=== Python Files ===" &&
        find . -name "*.py" | sort &&
        echo -e "\\n=== Shell Scripts ===" &&
        find . -name "*.sh" | sort &&
        echo -e "\\n=== JavaScript Files ===" &&
        find . -name "*.js" | sort &&
        echo -e "\\n=== Common Entry Points ===" &&
        find . -name "main.py" -o -name "app.py" -o -name "index.js" -o -name "server.js" -o -name "start.sh"
        """
        
        runable_files_result = ssm_session.execute_command(runable_files_command)
        
        # Now use Mistral AI to analyze the README and determine setup steps
        # Modified prompt to emphasize conda for Python projects
        prompt = f"""
        Below is the README content from a GitHub repository. Please analyze it and extract specific setup instructions.
        
        README CONTENT:
        {readme_content}
        
        DEPENDENCY FILES AND TOOLS CHECK:
        {dep_check_output}

        EXECUTABLE FILENAMES:
        {runable_files_result}
        
        Based on the README content, the available dependency files and executable filenames in the directory, provide a step-by-step list of commands needed to install all dependencies and un the project.

        Return your answer in JSON format with the following structure:
        {{
            "setup_steps": [
                "command 1",
                "command 2",
                ...
            ]
        }}
        
        If any information is missing, make a reasonable guess based on the repository structure. If there is no command to run the project, specify "None".
        """
        print("readme", prompt)
        try:
            # Call Mistral API to analyze
            response = mistral_client.chat.complete(
                model=MISTRAL_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            analysis_result = json.loads(response.choices[0].message.content)
            
            return {
                "status": "Success",
                "readme_content": readme_content,
                "analysis": analysis_result
            }
        except Exception as e:
            return {
                "status": "Failed",
                "error": f"README analysis failed: {str(e)}",
                "setup_steps": []
            }
        
    except Exception as e:
        return {
            "status": "Failed",
            "error": str(e),
            "setup_steps": []
        }

def setup_and_run_github_project(repo_directory: str, ssm_session: PersistentSSMSession = None) -> dict:
    """
    Sets up a GitHub project based on README analysis, using conda for all Python projects.
    
    Args:
        repo_directory: Directory where the repo was cloned
        ssm_session: The persistent SSM session to use for commands
        
    Returns:
        Dict containing setup results
    """
    if ssm_session is None:
        # This is a fallback in case the session isn't provided
        ssm_session = PersistentSSMSession()
        print("Setup SSM session was not created")
    step_results = []
    current_step = 0
    
    try:
        # Analyze the README to get setup steps
        analysis_result = analyze_readme(repo_directory, ssm_session)
        
        if analysis_result["status"] != "Success":
            return {
                "status": "Failed",
                "error": f"README analysis failed: {analysis_result.get('error', 'Unknown error')}",
                "steps_executed": []
            }
        
        # Extract setup information
        setup_info = analysis_result["analysis"]
        setup_steps = setup_info.get("setup_steps", [])
        print("setup_step", setup_steps)
        run_command = setup_info.get("run_command", "")
        print("run command", run_command)
        
        # Now run each setup step
        for step in setup_steps:
            if step.strip():  
                step_cmd = step
                print("step_cmd", step_cmd)
                step_result = ssm_session.execute_command(step_cmd)
                
                step_results.append({
                    "step": f"Setup step {current_step}: {step_cmd}",
                    "command": step_cmd,
                    "status": "Success",
                    "output": step_result,
                    "error": ""
                })
                current_step += 1
        
        return {
            "status": "Success",
            "repo_directory": repo_directory,
            "environment": {
                "type": "conda",
                "name": "env1" 
            },
            "steps_executed": step_results,
            "run_command": run_command,
        }
        
    except Exception as e:
        return {
            "status": "Failed",
            "error": str(e),
            "steps_executed": step_results,
            "repo_directory": repo_directory
        }

# def run_github_project(repo_directory: str, run_command: str, ssm_session: PersistentSSMSession = None) -> dict:
#     """
#     Runs a GitHub project using conda for Python projects.
    
#     Args:
#         repo_directory: Directory where the repo was cloned
#         env_name: Environment name (for Python projects)
#         run_command: Command to run (e.g., "python3 script.py")
#         ssm_session: The persistent SSM session to use for commands
        
#     Returns:
#         Dict containing run results
#     """
#     print("run_command", run_command)
#     if ssm_session is None:
#         # This is a fallback in case the session isn't provided
#         ssm_session = PersistentSSMSession()
#         print("Run SSM session was not created")
#     try:
#         if not run_command:
#             print("No Custom Run command was passed in")
#             # Default to running main.py if it exists
#             check_main_cmd = f"[ -f 'main.py' ] && echo 'main.py found' || echo 'main.py not found'"
#             main_check_result = ssm_session.execute_command(check_main_cmd)
            
#             if "main.py found" in main_check_result:
#                 run_command = "python main.py"
#             else:
#                 return {
#                     "status": "Failed",
#                     "error": "Could not determine how to run the project, please provide more information",
#                     "repo_directory": repo_directory
#                 }
            
#         # Execute the run command
#         run_result = ssm_session.execute_command(run_command)
        
#         return {
#             "status": "Success",
#             "repo_directory": repo_directory,
#             "command": run_command,
#             "output": run_result,
#             "error": ""
#         }
        
#     except Exception as e:
#         return {
#             "status": "Failed",
#             "error": str(e),
#             "repo_directory": repo_directory,
#             "command": run_command if run_command else "Unknown"
#         }
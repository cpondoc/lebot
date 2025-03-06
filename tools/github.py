"""
Tools for setting up GitHub repositories on an AWS instance, ensuring only conda environments are used.
"""

import json
import os
import time
from typing import Dict, List
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve AWS credentials and instance ID from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
INSTANCE_ID = os.getenv("INSTANCE_ID")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Initialize Mistral client for understanding READMEs
from mistralai import Mistral
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
# Model and env variable config
MISTRAL_MODEL = "mistral-large-latest"

def wait_for_command(ssm, command_id, instance_id, max_retries=20, initial_delay=2):
    """
    Helper function to wait for SSM command completion with proper error handling.
    
    Args:
        ssm: Boto3 SSM client
        command_id: The command ID to check
        instance_id: The instance ID the command was sent to
        max_retries: Maximum number of retries
        initial_delay: Initial delay before first check
        
    Returns:
        Dict containing command output or None if failed
    """
    time.sleep(initial_delay)  # Initial delay
    
    for attempt in range(max_retries):
        try:
            output = ssm.get_command_invocation(
                CommandId=command_id, 
                InstanceId=instance_id
            )
            
            status = output["Status"]
            
            # If the command has completed
            if status in ("Success", "Failed", "Cancelled", "TimedOut"):
                return output
                
            # If still in progress, wait with exponential backoff
            sleep_duration = min(2 ** attempt, 10)
            print(f"Command still in progress, waiting {sleep_duration}s... (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_duration)
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = str(e)
            
            # If it's specifically the InvocationDoesNotExist error
            if error_code == "InvocationDoesNotExist" or "InvocationDoesNotExist" in error_message:
                if attempt < max_retries - 1:  # If not the last attempt
                    print(f"Command invocation not found yet, retrying... (attempt {attempt+1}/{max_retries})")
                    time.sleep(3)  # Wait before retrying
                    continue
                else:
                    print(f"Command invocation not found after {max_retries} attempts")
                    return None
            else:
                print(f"Error checking command status: {e}")
                return None
                
    # If we've exhausted retries
    print(f"Command timed out after {max_retries} attempts")
    return None

def run_ssm_command(ssm, command, max_wait_time=60):
    """
    Helper function to run SSM commands with proper error handling.
    
    Args:
        ssm: Boto3 SSM client
        command: Command to execute
        max_wait_time: Maximum time to wait for command completion
        
    Returns:
        Dict containing command output or error details
    """
    try:
        # Execute the command
        response = ssm.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [command]}
        )
        
        command_id = response["Command"]["CommandId"]
        
        # Wait for completion
        result = wait_for_command(ssm, command_id, INSTANCE_ID, 
                                 max_retries=max(5, max_wait_time//3), 
                                 initial_delay=min(3, max_wait_time//10))
        
        if result:
            return {
                "success": True,
                "status": result.get("Status", "Unknown"),
                "output": result.get("StandardOutputContent", ""),
                "error": result.get("StandardErrorContent", ""),
            }
        else:
            return {
                "success": False,
                "status": "Unknown",
                "output": "",
                "error": "Command execution status could not be determined",
            }
            
    except Exception as e:
        return {
            "success": False,
            "status": "Failed",
            "output": "",
            "error": f"Error executing command: {str(e)}",
        }

def clone_github_repo(repo_url: str, directory_name: str = None) -> Dict:
    """
    Clones a GitHub repository to the EC2 instance.
    
    Args:
        repo_url: URL of the GitHub repository (e.g., https://github.com/username/repo)
        directory_name: Optional custom directory name. If not provided, will use repo name
        
    Returns:
        Dict containing information about the cloning operation
    """
    try:
        # Clean the repository URL
        if repo_url.endswith(".git"):
            repo_url = repo_url
        elif not repo_url.endswith("/"):
            repo_url = f"{repo_url}.git"
        else:
            repo_url = f"{repo_url[:-1]}.git"
        
        # Extract repository name from URL if directory name is not provided
        if not directory_name:
            directory_name = repo_url.split("/")[-1].replace(".git", "")
        
        # Initialize SSM client
        ssm = boto3.client(
            "ssm",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        
        # First, check if git is installed
        check_git_cmd = "which git || echo 'Git not installed'"
        git_check_result = run_ssm_command(ssm, check_git_cmd)
        
        if not git_check_result["success"]:
            return {
                "status": "Failed",
                "error": "Could not check if Git is installed",
                "directory": directory_name,
                "repo_url": repo_url
            }
        
        if "Git not installed" in git_check_result["output"]:
            # Install git if not available
            install_git_cmd = "sudo yum install -y git || sudo apt-get update && sudo apt-get install -y git"
            install_result = run_ssm_command(ssm, install_git_cmd, 60)
            
            if not install_result["success"]:
                return {
                    "status": "Failed",
                    "error": "Failed to install Git",
                    "directory": directory_name,
                    "repo_url": repo_url
                }
            
            # Verify git installation
            verify_git_result = run_ssm_command(ssm, check_git_cmd)
            if "Git not installed" in verify_git_result["output"]:
                return {
                    "status": "Failed",
                    "error": "Could not install Git",
                    "directory": directory_name,
                    "repo_url": repo_url
                }
        
        # Command to clone the repository
        # Check if directory already exists and remove it if it does
        clone_cmd = f"""
        cd /home/ec2-user/ && 
        if [ -d "{directory_name}" ]; then
            echo "Directory already exists. Removing it..."
            rm -rf "{directory_name}"
        fi && 
        echo "Cloning repository {repo_url} into {directory_name}..." && 
        git clone {repo_url} {directory_name} && 
        echo "Repository cloned successfully" && 
        ls -la {directory_name}
        """
        
        # Execute the git clone command - this can take a while
        clone_result = run_ssm_command(ssm, clone_cmd, 120)
        
        if not clone_result["success"]:
            return {
                "status": "Failed",
                "error": "Git clone command failed or timed out",
                "directory": directory_name,
                "repo_url": repo_url,
                "output": clone_result["output"],
                "error_details": clone_result["error"]
            }
        
        # Verify the repository was cloned by checking if directory exists and contains files
        verify_cmd = f"cd /home/ec2-user/ && [ -d '{directory_name}' ] && [ -d '{directory_name}/.git' ] && echo 'Repository verified' || echo 'Repository verification failed'"
        verify_result = run_ssm_command(ssm, verify_cmd)
        
        if not verify_result["success"] or "Repository verified" not in verify_result["output"]:
            return {
                "status": "Failed",
                "error": "Repository cloning verification failed",
                "directory": directory_name,
                "repo_url": repo_url,
                "output": clone_result["output"],
                "verification": verify_result["output"] if verify_result["success"] else "Verification failed"
            }
        
        result = {
            "status": "Success",
            "directory": directory_name,
            "repo_url": repo_url,
            "output": clone_result["output"],
            "error": clone_result["error"]
        }
        
        return result
    
    except Exception as e:
        return {
            "status": "Failed",
            "error": str(e),
            "directory": directory_name if directory_name else "unknown",
            "repo_url": repo_url
        }

def analyze_readme(repo_directory: str) -> Dict:
    """
    Analyzes the README of a GitHub repository and extracts setup instructions.
    
    Args:
        repo_directory: Directory where the repo was cloned
        
    Returns:
        Dict containing extracted setup information
    """
    try:
        # Initialize SSM client
        ssm = boto3.client(
            "ssm",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        
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
        readme_result = run_ssm_command(ssm, readme_check_command)
        
        if not readme_result["success"]:
            return {
                "status": "Failed",
                "error": "Could not read README",
                "setup_steps": []
            }
        
        readme_content = readme_result["output"]
        
        if readme_content == "No README file found":
            return {
                "status": "Warning",
                "error": "No README file found in the repository",
                "setup_steps": []
            }
        
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
        
        dep_check_result = run_ssm_command(ssm, dep_check_command)
        
        if not dep_check_result["success"]:
            # Continue with just README content
            dep_check_output = "Could not check dependencies"
        else:
            dep_check_output = dep_check_result["output"]
        
        # Now use Mistral AI to analyze the README and determine setup steps
        # Modified prompt to emphasize conda for Python projects
        prompt = f"""
        Below is the README content from a GitHub repository. Please analyze it and extract specific setup instructions.
        
        README CONTENT:
        {readme_content}
        
        DEPENDENCY FILES AND TOOLS CHECK:
        {dep_check_output}
        
        Based on the README content and the available dependency files, provide a step-by-step list of commands needed to:
        1. Set up a conda environment if this is a Python project (no virtualenv should be used)
        2. Install all dependencies within the conda environment
        3. Run the main component of the project

        Return your answer in JSON format with the following structure:
        {{
            "is_python_project": true/false,
            "environment_type": "conda", 
            "env_name": "suggested_environment_name",
            "setup_steps": [
                "command 1",
                "command 2",
                ...
            ],
            "run_command": "command to run the project"
        }}
        
        IMPORTANT: Always use conda for Python projects, not virtualenv or venv. Set "environment_type" to "conda" for all Python projects.
        If any information is missing, make a reasonable guess based on the repository structure.
        """
        
        try:
            # Call Mistral API to analyze
            response = mistral_client.chat.complete(
                model=MISTRAL_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            analysis_result = json.loads(response.choices[0].message.content)
            
            # Force environment type to be conda for all Python projects
            if analysis_result.get("is_python_project", False):
                analysis_result["environment_type"] = "conda"
            
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

def setup_github_project(repo_directory: str, environment_name: str = None) -> Dict:
    """
    Sets up a GitHub project based on README analysis, using conda for all Python projects.
    
    Args:
        repo_directory: Directory where the repo was cloned
        environment_name: Custom environment name (optional)
        
    Returns:
        Dict containing setup results
    """
    step_results = []
    current_step = 0
    
    try:
        # Initialize SSM client
        ssm = boto3.client(
            "ssm",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        
        # Verify the repository directory exists
        check_dir_cmd = f"cd /home/ec2-user/ && [ -d '{repo_directory}' ] && echo 'Directory exists' || echo 'Directory not found'"
        dir_check_result = run_ssm_command(ssm, check_dir_cmd)
        
        if not dir_check_result["success"] or "Directory not found" in dir_check_result["output"]:
            return {
                "status": "Failed",
                "error": f"Repository directory '{repo_directory}' not found or could not be checked",
                "steps_executed": []
            }
        
        # Analyze the README to get setup steps
        analysis_result = analyze_readme(repo_directory)
        
        if analysis_result["status"] != "Success":
            return {
                "status": "Failed",
                "error": f"README analysis failed: {analysis_result.get('error', 'Unknown error')}",
                "steps_executed": []
            }
        
        # Extract setup information
        setup_info = analysis_result["analysis"]
        is_python = setup_info.get("is_python_project", False)
        
        # Force conda for Python projects
        env_type = "conda" if is_python else "none"
        setup_info["environment_type"] = env_type
        
        env_name = environment_name or setup_info.get("env_name", repo_directory)
        setup_steps = setup_info.get("setup_steps", [])
        run_command = setup_info.get("run_command", "")
        
        # Check if conda is installed
        check_conda_cmd = "cd /home/ec2-user/ && which conda || echo 'Conda not installed'"
        conda_check_result = run_ssm_command(ssm, check_conda_cmd)
        conda_installed = conda_check_result["success"] and "Conda not installed" not in conda_check_result["output"]
        
        # Set conda path variable
        conda_path = "conda"  # Default
        
        # If we need conda but it's not installed, install miniconda
        if is_python and not conda_installed:
            install_conda_cmd = """
            cd /home/ec2-user/ && 
            echo "Installing Miniconda..." && 
            wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && 
            bash miniconda.sh -b -p /home/ec2-user/miniconda && 
            echo 'export PATH="/home/ec2-user/miniconda/bin:$PATH"' >> ~/.bashrc && 
            source ~/.bashrc && 
            /home/ec2-user/miniconda/bin/conda --version
            """
            
            conda_install_result = run_ssm_command(ssm, install_conda_cmd, 120)  # Long timeout for conda install
            
            step_results.append({
                "step": "Install Miniconda",
                "command": install_conda_cmd,
                "status": conda_install_result["status"],
                "output": conda_install_result["output"],
                "error": conda_install_result["error"]
            })
            
            # Set conda path for future commands to use miniconda explicitly
            conda_path = "/home/ec2-user/miniconda/bin/conda"
        
        # Set up Python environment if needed
        if is_python:
            # Check if environment already exists
            check_env_cmd = f"source ~/.bashrc && {conda_path} env list | grep '{env_name}' || echo 'Environment not found'"
            env_check_result = run_ssm_command(ssm, check_env_cmd)
            env_exists = env_check_result["success"] and "Environment not found" not in env_check_result["output"]
            
            if env_exists:
                # Remove existing environment
                remove_env_cmd = f"source ~/.bashrc && {conda_path} env remove -y -n {env_name}"
                remove_env_result = run_ssm_command(ssm, remove_env_cmd, 60)
                
                step_results.append({
                    "step": "Remove existing conda environment",
                    "command": remove_env_cmd,
                    "status": remove_env_result["status"],
                    "output": remove_env_result["output"],
                    "error": remove_env_result["error"]
                })
            
            # Create conda environment
            conda_create_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} create -y -n {env_name} python"
            create_env_result = run_ssm_command(ssm, conda_create_cmd, 90)
            
            step_results.append({
                "step": "Create conda environment",
                "command": conda_create_cmd,
                "status": create_env_result["status"],
                "output": create_env_result["output"],
                "error": create_env_result["error"]
            })
            current_step += 1
            
            # Check for common dependency files and install them automatically
            check_dep_files_cmd = f"""
            cd /home/ec2-user/{repo_directory} && 
            if [ -f "requirements.txt" ]; then
                echo "requirements.txt found"
            fi && 
            if [ -f "environment.yml" ]; then
                echo "environment.yml found"
            fi && 
            if [ -f "pyproject.toml" ]; then
                echo "pyproject.toml found"
            fi
            """
            
            dep_check_result = run_ssm_command(ssm, check_dep_files_cmd)
            
            if dep_check_result["success"]:
                # Install dependencies based on which files were found
                if "requirements.txt found" in dep_check_result["output"]:
                    pip_install_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} run -n {env_name} pip install -r requirements.txt"
                    pip_install_result = run_ssm_command(ssm, pip_install_cmd, 120)
                    
                    step_results.append({
                        "step": "Install requirements.txt",
                        "command": pip_install_cmd,
                        "status": pip_install_result["status"],
                        "output": pip_install_result["output"],
                        "error": pip_install_result["error"]
                    })
                    current_step += 1
                
                if "environment.yml found" in dep_check_result["output"]:
                    conda_env_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} env update -n {env_name} -f environment.yml"
                    conda_env_result = run_ssm_command(ssm, conda_env_cmd, 120)
                    
                    step_results.append({
                        "step": "Update from environment.yml",
                        "command": conda_env_cmd,
                        "status": conda_env_result["status"],
                        "output": conda_env_result["output"],
                        "error": conda_env_result["error"]
                    })
                    current_step += 1
                
                if "pyproject.toml found" in dep_check_result["output"]:
                    pip_install_project_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} run -n {env_name} pip install -e ."
                    pip_project_result = run_ssm_command(ssm, pip_install_project_cmd, 120)
                    
                    step_results.append({
                        "step": "Install project from pyproject.toml",
                        "command": pip_install_project_cmd,
                        "status": pip_project_result["status"],
                        "output": pip_project_result["output"],
                        "error": pip_project_result["error"]
                    })
                    current_step += 1
            
            # Now run each setup step inside the conda environment
            for step in setup_steps:
                if step.strip():  # Skip empty steps
                    # Modify any virtualenv commands to use conda
                    step_cmd = step
                    if any(venv_cmd in step_cmd for venv_cmd in ["virtualenv", "venv", "python -m venv"]):
                        # Skip virtual environment creation steps
                        continue
                        
                    # Make commands run in conda
                    conda_run_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} run -n {env_name} {step_cmd}"
                    step_result = run_ssm_command(ssm, conda_run_cmd, 60)
                    
                    step_results.append({
                        "step": f"Setup step {current_step}: {step_cmd}",
                        "command": conda_run_cmd,
                        "status": step_result["status"],
                        "output": step_result["output"],
                        "error": step_result["error"]
                    })
                    current_step += 1
        else:
            # Just run steps without conda for non-Python projects
            for step in setup_steps:
                if step.strip():  # Skip empty steps
                    cmd = f"cd /home/ec2-user/{repo_directory} && {step}"
                    step_result = run_ssm_command(ssm, cmd, 60)
                    
                    step_results.append({
                        "step": f"Setup step {current_step}: {step}",
                        "command": cmd,
                        "status": step_result["status"],
                        "output": step_result["output"],
                        "error": step_result["error"]
                    })
                    current_step += 1
        
        # Store setup information in a file for future reference
        setup_info_json = json.dumps({
            "repo_directory": repo_directory,
            "environment": {
                "type": "conda" if is_python else "none",
                "name": env_name if is_python else "None"
            },
            "run_command": run_command,
            "is_python": is_python
        }, indent=2)
        
        # Escape single quotes in the JSON string
        setup_info_json_escaped = setup_info_json.replace("'", "'\\''")
        
        store_info_cmd = f"""
        cd /home/ec2-user/{repo_directory} && 
        echo '{setup_info_json_escaped}' > .bot_setup_info.json && 
        echo "Setup information stored"
        """
        
        store_info_result = run_ssm_command(ssm, store_info_cmd)
        
        return {
            "status": "Success",
            "repo_directory": repo_directory,
            "environment": {
                "type": "conda" if is_python else "none",
                "name": env_name if is_python else "None"
            },
            "steps_executed": step_results,
            "run_command": run_command,
            "is_python": is_python
        }
        
    except Exception as e:
        return {
            "status": "Failed",
            "error": str(e),
            "steps_executed": step_results,
            "repo_directory": repo_directory
        }
def run_github_project(repo_directory: str, env_name: str = None, custom_command: str = None) -> Dict:
    """
    Runs a GitHub project using conda for Python projects.
    
    Args:
        repo_directory: Directory where the repo was cloned
        env_name: Environment name (for Python projects)
        custom_command: Custom command to run (e.g., "python3 script.py")
        
    Returns:
        Dict containing run results
    """
    try:
        # Initialize SSM client
        ssm = boto3.client(
            "ssm",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        
        # Verify the repository directory exists
        check_dir_cmd = f"cd /home/ec2-user/ && [ -d '{repo_directory}' ] && echo 'Directory exists' || echo 'Directory not found'"
        dir_check_result = run_ssm_command(ssm, check_dir_cmd)
        
        if not dir_check_result["success"] or "Directory not found" in dir_check_result["output"]:
            return {
                "status": "Failed",
                "error": f"Repository directory '{repo_directory}' not found or could not be checked",
                "output": ""
            }
        
        # Check if we have stored setup info from previous setup
        check_setup_info_cmd = f"cd /home/ec2-user/{repo_directory} && [ -f '.bot_setup_info.json' ] && cat .bot_setup_info.json || echo '{{}}'"
        setup_info_result = run_ssm_command(ssm, check_setup_info_cmd)
        
        # Default empty setup info
        setup_info_str = "{}" 
        
        if setup_info_result["success"]:
            setup_info_str = setup_info_result["output"].strip()
        
        # Try to parse the setup info
        try:
            # Parse the setup info
            if setup_info_str and setup_info_str != "{}":
                setup_info = json.loads(setup_info_str)
                is_python = setup_info.get("is_python", False)
                stored_env_name = setup_info.get("environment", {}).get("name", repo_directory)
                stored_run_command = setup_info.get("run_command", "")
                
                # Use stored values unless overridden
                if not env_name and stored_env_name != "None":
                    env_name = stored_env_name
                if not custom_command and stored_run_command:
                    custom_command = stored_run_command
        except json.JSONDecodeError:
            # Invalid JSON, use defaults
            is_python = True  # Assume Python project if we can't determine
        
        # If no custom command or env_name yet, analyze README
        if not custom_command or (not env_name and locals().get('is_python', True)):
            analysis_result = analyze_readme(repo_directory)
            if analysis_result["status"] == "Success":
                new_setup_info = analysis_result["analysis"]
                
                # Only use these if not already set
                if not custom_command:
                    custom_command = new_setup_info.get("run_command", "")
                
                is_python = new_setup_info.get("is_python_project", True)  # Default to True
                
                if not env_name and is_python:
                    env_name = new_setup_info.get("env_name", repo_directory)
        
        if not custom_command:
            # Default to running main.py if it exists
            check_main_cmd = f"cd /home/ec2-user/{repo_directory} && [ -f 'main.py' ] && echo 'main.py found' || echo 'main.py not found'"
            main_check_result = run_ssm_command(ssm, check_main_cmd)
            
            if main_check_result["success"] and "main.py found" in main_check_result["output"]:
                custom_command = "python main.py"
            else:
                return {
                    "status": "Failed",
                    "error": "Could not determine how to run the project and no custom command provided",
                    "repo_directory": repo_directory
                }
        
        # Set default environment name if needed for Python projects
        if is_python and not env_name:
            env_name = repo_directory
        
        # Check for conda and determine path
        conda_path = "conda"  # Default path
        
        # Check if conda is installed
        check_conda_cmd = "cd /home/ec2-user/ && which conda || echo 'Conda not installed'"
        conda_check_result = run_ssm_command(ssm, check_conda_cmd)
        conda_installed = conda_check_result["success"] and "Conda not installed" not in conda_check_result["output"]
        
        if not conda_installed:
            # Try miniconda path
            check_miniconda_cmd = "[ -d '/home/ec2-user/miniconda' ] && echo 'Miniconda found' || echo 'Miniconda not found'"
            miniconda_check_result = run_ssm_command(ssm, check_miniconda_cmd)
            
            if miniconda_check_result["success"] and "Miniconda found" in miniconda_check_result["output"]:
                conda_path = "/home/ec2-user/miniconda/bin/conda"
            else:
                # If we need conda for a Python project but it's not installed, install it
                if is_python:
                    install_conda_cmd = """
                    cd /home/ec2-user/ && 
                    echo "Installing Miniconda..." && 
                    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && 
                    bash miniconda.sh -b -p /home/ec2-user/miniconda && 
                    echo 'export PATH="/home/ec2-user/miniconda/bin:$PATH"' >> ~/.bashrc && 
                    source ~/.bashrc && 
                    /home/ec2-user/miniconda/bin/conda --version
                    """
                    
                    conda_install_result = run_ssm_command(ssm, install_conda_cmd, 120)
                    
                    if not conda_install_result["success"]:
                        return {
                            "status": "Failed",
                            "error": "Failed to install conda, which is required for Python projects",
                            "output": conda_install_result["output"],
                            "error_details": conda_install_result["error"]
                        }
                    
                    conda_path = "/home/ec2-user/miniconda/bin/conda"
                else:
                    # For non-Python projects, we don't need conda
                    pass
        
        # Check if the conda environment exists for Python projects
        if is_python:
            check_env_cmd = f"source ~/.bashrc && {conda_path} env list | grep '{env_name}' || echo 'Environment not found'"
            env_check_result = run_ssm_command(ssm, check_env_cmd)
            
            env_exists = env_check_result["success"] and "Environment not found" not in env_check_result["output"]
            
            if not env_exists:
                # If the environment doesn't exist, we need to create it
                print(f"Conda environment '{env_name}' not found, creating it...")
                
                create_env_cmd = f"source ~/.bashrc && {conda_path} create -y -n {env_name} python"
                create_env_result = run_ssm_command(ssm, create_env_cmd, 90)
                
                if not create_env_result["success"]:
                    return {
                        "status": "Failed",
                        "error": f"Failed to create conda environment '{env_name}'",
                        "output": create_env_result["output"],
                        "error_details": create_env_result["error"]
                    }
                    
                # Install requirements if available
                req_check_cmd = f"cd /home/ec2-user/{repo_directory} && [ -f 'requirements.txt' ] && echo 'requirements.txt found' || echo 'requirements.txt not found'"
                req_check_result = run_ssm_command(ssm, req_check_cmd)
                
                if req_check_result["success"] and "requirements.txt found" in req_check_result["output"]:
                    install_req_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} run -n {env_name} pip install -r requirements.txt"
                    install_req_result = run_ssm_command(ssm, install_req_cmd, 120)
                    
                    if not install_req_result["success"]:
                        print(f"Warning: Failed to install requirements: {install_req_result['error']}")
        
        # Prepare the run command
        if is_python:
            # Always use conda for Python projects
            run_cmd = f"source ~/.bashrc && cd /home/ec2-user/{repo_directory} && {conda_path} run -n {env_name} {custom_command}"
        else:
            # For non-Python projects, just run the command directly
            run_cmd = f"cd /home/ec2-user/{repo_directory} && {custom_command}"
        
        # Execute the run command
        run_result = run_ssm_command(ssm, run_cmd, 180)  # 3 minutes timeout
        
        if not run_result["success"]:
            return {
                "status": "Failed",
                "error": "Command execution failed or timed out",
                "repo_directory": repo_directory,
                "command": run_cmd,
                "output": run_result["output"],
                "error_details": run_result["error"]
            }
        
        return {
            "status": run_result["status"],
            "repo_directory": repo_directory,
            "command": run_cmd,
            "output": run_result["output"],
            "error": run_result["error"]
        }
        
    except Exception as e:
        return {
            "status": "Failed",
            "error": str(e),
            "repo_directory": repo_directory,
            "command": custom_command if custom_command else "Unknown"
        }
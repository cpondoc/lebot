"""
Code for a tool that manages AWS instances
"""

import os
import shlex
import boto3
import botocore
import time
from dotenv import load_dotenv

load_dotenv()

# Retrieve AWS credentials and instance ID from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
INSTANCE_ID = os.getenv("INSTANCE_ID")


class PersistentSSMSession:
    def __init__(self, user: str):
        # Configure the boto3 client with tcp_keepalive
        session = boto3.session.Session()
        self.ssm_client = session.client(
            "ssm",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            config=botocore.client.Config(
                tcp_keepalive=True,
                connect_timeout=10,
                read_timeout=30,
                retries={
                    "max_attempts": 5,
                    "mode": "adaptive",
                },
            ),
        )

        # Initialize state variables for tracking session state
        self.current_directory = None
        self.environment_vars = {}
        self.command_history = []
        self.session_id = None
        self.user = user
        self.run_from_current_user = f"sudo -u {user} bash -c "

        # Initialize user-specific home directory and conda environment
        self.initialize_directory(user)
        self.initialize_conda(user)

    def initialize_conda(self, user: str):
        """
        Initialize a conda environment specifically for the user

        [TO-DO]: Add try + except here
        """
        # Define environment
        self.env = f"{user}_env"
        self.conda_path = f"/home/ec2-user/miniconda/bin/conda"

        # Check if environment already exists
        check_env_cmd = f"source ~/.bashrc && {self.conda_path} env list | grep '{self.env}' || echo 'Environment not found'"
        response = self.ssm_client.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [check_env_cmd]},
        )
        command_id = response["Command"]["CommandId"]
        self._wait_for_command(command_id)
        output = self.ssm_client.get_command_invocation(
            CommandId=command_id, InstanceId=INSTANCE_ID
        )
        env_exists = "Environment not found" not in output["StandardOutputContent"]

        # If not, create a specific environment
        if not env_exists:
            conda_create_cmd = f"source ~/.bashrc && cd /home/ec2-user && {self.conda_path} create -y -n {self.env} python"
            env_check_result = self.ssm_client.send_command(
                InstanceIds=[INSTANCE_ID],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [conda_create_cmd]},
            )

    def initialize_directory(self, user: str):
        """
        Initialize home directory for specific user
        """
        # First, check if the user exists
        check_user_cmd = f"id {user}"
        response = self.ssm_client.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [check_user_cmd]},
        )
        command_id = response["Command"]["CommandId"]
        self._wait_for_command(command_id)
        output = self.ssm_client.get_command_invocation(
            CommandId=command_id, InstanceId=INSTANCE_ID
        )

        # If the user doesn't exist, create a new user
        if output["Status"] == "Failed":
            create_user_cmd = f"sudo adduser {user}"
            response = self.ssm_client.send_command(
                InstanceIds=[INSTANCE_ID],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [create_user_cmd]},
            )
            command_id = response["Command"]["CommandId"]
            self._wait_for_command(command_id)
            output = self.ssm_client.get_command_invocation(
                CommandId=command_id, InstanceId=INSTANCE_ID
            )
            if output["Status"] == "Failed":
                print("Creating new user failed!")

        self.current_directory = f"/home/{user}"

    def execute_command(self, command):
        """Execute a command while maintaining simulated persistence, handling multiple commands separated by &&."""

        # Split commands by "&&" and trim whitespace
        commands = [cmd.strip() for cmd in command.split("&&") if cmd.strip()]

        results = []

        for cmd in commands:
            # Special handling for cd commands
            if cmd.startswith("cd "):
                results.append(self._handle_cd_command(cmd))

            # Handle environment variable setting
            elif "=" in cmd and not cmd.startswith(("export ", "echo ", "printf ")):
                results.append(self._handle_env_var_setting(cmd))

            # Normal command execution
            else:
                results.append(self._execute_normal_command(cmd))

        return "\n".join(results)

    def _handle_cd_command(self, command):
        """Handle directory change commands"""
        dir_path = command.strip()[3:].strip()

        # Handle empty cd (go to home)
        if not dir_path:
            check_cmd = self.run_from_current_user + '"cd && pwd"'
        # Handle absolute paths
        elif dir_path.startswith("/"):
            check_cmd = (
                self.run_from_current_user
                + f""" "if [ -d '{dir_path}' ]; then cd '{dir_path}' && pwd; else echo 'Directory not found'; fi" """
            )
        # Handle relative paths
        else:
            check_cmd = (
                self.run_from_current_user
                + f""" "if [ -d '{self.current_directory}/{dir_path}' ] || [ -d '{dir_path}' ]; then cd '{self.current_directory}' && cd '{dir_path}' && pwd; else echo 'Directory not found'; fi" """
            )

        response = self.ssm_client.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [check_cmd]},
        )

        command_id = response["Command"]["CommandId"]
        self._wait_for_command(command_id)
        output = self.ssm_client.get_command_invocation(
            CommandId=command_id, InstanceId=INSTANCE_ID
        )

        result = output["StandardOutputContent"].strip()
        if result != "Directory not found":
            self.current_directory = result
            self.command_history.append(command)
            return f"Changed to directory: {self.current_directory}"
        else:
            return "Directory not found"

    def _handle_env_var_setting(self, command):
        """Handle environment variable setting"""
        try:
            var_name, var_value = command.strip().split("=", 1)
            self.environment_vars[var_name] = var_value

            # Actually set it on the server
            full_command = (
                self.run_from_current_user
                + f""" "cd '{self.current_directory}' && {var_name}={var_value} && echo 'Set {var_name}={var_value}'" """
            )

            response = self.ssm_client.send_command(
                InstanceIds=[INSTANCE_ID],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [full_command]},
            )

            command_id = response["Command"]["CommandId"]
            self._wait_for_command(command_id)
            self.command_history.append(command)
            return f"Set environment variable {var_name}={var_value}"
        except Exception as e:
            return f"Error setting environment variable: {e}"

    def _execute_normal_command(self, command):
        """Execute a regular shell command inside the conda environment"""
        # Build environment variable string
        env_vars = " ".join([f"{k}='{v}'" for k, v in self.environment_vars.items()])
        env_prefix = f"{env_vars} " if env_vars else ""

        # Build the full shell logic to run
        shell_logic = f"cd '{self.current_directory}' && {env_prefix}{command}"

        # Quote the entire shell logic so it becomes a single argument for `bash -c`
        quoted_shell_logic = shlex.quote(shell_logic)

        full_command = (
            f"{self.conda_path} run -n {self.env} bash -c {quoted_shell_logic}"
        )

        try:
            response = self.ssm_client.send_command(
                InstanceIds=[INSTANCE_ID],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": [full_command]},
            )

            command_id = response["Command"]["CommandId"]
            self._wait_for_command(command_id)
            output = self.ssm_client.get_command_invocation(
                CommandId=command_id, InstanceId=INSTANCE_ID
            )

            self.command_history.append(command)
            return output["StandardOutputContent"]
        except Exception as e:
            return f"Error executing command: {e}"

    def _wait_for_command(self, command_id, max_retries=10, sleep_time=3):
        """Wait for command to complete with exponential backoff"""
        for attempt in range(max_retries):
            try:
                output = self.ssm_client.get_command_invocation(
                    CommandId=command_id, InstanceId=INSTANCE_ID
                )

                status = output["Status"]
                if status in ("Success", "Failed", "Cancelled", "TimedOut"):
                    return True

                # Wait with exponential backoff
                sleep_duration = sleep_time * (2**attempt)
                time.sleep(min(sleep_duration, 15))  # Cap at 15 seconds

            except Exception as e:
                # print(f"Error waiting for command: {e}")
                time.sleep(sleep_time)

        print(f"Command {command_id} did not complete in the expected time")
        return False

    def get_state(self):
        """Return the current state of the session"""
        return {
            "current_directory": self.current_directory,
            "environment_variables": self.environment_vars,
            "command_history": (
                self.command_history[-10:] if self.command_history else []
            ),
        }


# Example usage
if __name__ == "__main__":
    ssm_session = PersistentSSMSession()

    try:
        print("Current directory:")
        print(ssm_session.execute_command("pwd"))

        print("\nListing directory contents:")
        print(ssm_session.execute_command("ls -la"))

        print("\nChanging directory:")
        print(ssm_session.execute_command("cd /tmp"))

        print("\nVerifying current directory:")
        print(ssm_session.execute_command("pwd"))

        print("\nCreating a file:")
        print(ssm_session.execute_command("touch test_persistence.txt"))

        print("\nListing directory contents:")
        print(ssm_session.execute_command("ls -la test_persistence.txt"))

        print("\nSetting an environment variable:")
        print(ssm_session.execute_command("TEST_VAR=hello_world"))

        print("\nReading the environment variable:")
        print(ssm_session.execute_command("echo $TEST_VAR"))

        print("\nRunning multiple commands:")
        print(
            ssm_session.execute_command(
                "mkdir -p test_dir && cd test_dir && pwd && touch inside_file.txt && ls -la"
            )
        )

        print("\nVerifying we're still in the original directory (/tmp):")
        print(ssm_session.execute_command("pwd"))

        print("\nChanging to the created directory:")
        print(ssm_session.execute_command("cd test_dir"))

        print("\nVerifying current directory changed:")
        print(ssm_session.execute_command("pwd"))

        print("\nCurrent session state:")
        print(ssm_session.get_state())

    except Exception as e:
        print(f"Error during execution: {e}")

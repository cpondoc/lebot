"""
Test script to run a command inside of an AWS VM.
"""
import boto3
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve AWS credentials and instance ID from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
INSTANCE_ID = os.getenv("INSTANCE_ID")
print(AWS_ACCESS_KEY_ID)
print(AWS_SECRET_ACCESS_KEY)
print(AWS_REGION)
print(INSTANCE_ID)

# Initialize boto3 clients
ec2 = boto3.client(
    "ec2",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

ssm = boto3.client(
    "ssm",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Function to start EC2 instance if it's stopped
def start_instance():
    response = ec2.describe_instance_status(InstanceIds=[INSTANCE_ID])
    statuses = response.get("InstanceStatuses", [])

    if not statuses or statuses[0]["InstanceState"]["Name"] != "running":
        print("Starting EC2 instance...")
        ec2.start_instances(InstanceIds=[INSTANCE_ID])
        time.sleep(30)  # Wait for the instance to boot
        print("Instance started.")

# Function to run a shell command on the EC2 instance using SSM
def run_command(command):
    response = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
    )
    
    command_id = response["Command"]["CommandId"]

    # Wait for command execution
    time.sleep(5)

    # Fetch command output
    output = ssm.get_command_invocation(
        CommandId=command_id,
        InstanceId=INSTANCE_ID
    )

    return output["StandardOutputContent"]

# Ensure the instance is running
start_instance()

# Run a command on the instance and get output
command_output = run_command("uname -a")  # Example: Get OS details
print("Command Output:\n", command_output)

## General notes:
- Using old CS 210 server
- Set up an IAM Role to get access to AWS SSM (used to help manage and monitor AWS resources)
- Can use `boto3` and predefined access keys to then programmatically start and instance and then write a command within. We can try to wrap these in some sort of tool calls to help the language model do that.
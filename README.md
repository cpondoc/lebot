# LeBot

By: Chris Pondoc, Joey O'Brien, Natalie Greenfield

## Description

We want to build a Discord bot that makes managing and interacting with cloud infrastructure easier. In particular, we want our bot to be able to access and run commands + code from an AWS EC2 instance using natural language. This template will let us expand in different directions, including being able to clone direct GitHub repositories, entirely deploy and run applications, and more.

## Set-Up
 
First, create and install the Conda environment from the provided `environment.yml` file:  
```sh
conda env create -f environment.yml
```

Once installation is complete, activate the new environment:


```sh
conda activate discord_bot
```

Next, set up your `.env` file using the `.example.env` file. Finally, start the bot by running:
```sh
python3 bot.py
```
<h1 align="center">🌤️ LeBot</h1>

<h4 align="center">
    <p>
        <a href="https://discord.com/channels/1326353542037901352/1343030976791580672">Channel Link</a> |
        <a href="https://www.youtube.com/watch?v=Cs7Up_YK6V4">Video</a>
    <p>
</h4>

## About

LeBot makes it easier to manage and interact with cloud infrastructure. As students, we were frustrated with how uninituitive it felt to first set up and run code on AWS and GCP. Thus, we built a bot lets users take action on their cloud instances using just natural language.

## How to Use

To get started, simply navigate to our [channel](https://discord.com/channels/1326353542037901352/1343030976791580672) and ask LeBot a question about your cloud instance. We also have the following commands below that you can use to get more information.

| Command     | Description |
|------------|-------------|
| `!about`   | Displays this help message. |
| `!examples` | Gives example repositories to play around with. LeBot may not work with repos that are not listed. |
| `!lebron`  | LeBron. |

## Examples

We also have some examples of what the bot is capable of doing below.

<details>
  <summary>Basic Questions about Instance</summary>
</details>

<details>
  <summary>Setting up GitHub Repositories</summary>
</details>

<details>
  <summary>Error Handling</summary>
</details>

<details>
  <summary>Long Horizon Planning</summary>
</details>

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

## Questions

This bot was created by Christopher Pondoc, Joseph O'Brien, and Natalie Greenfield. Feel free to reach out to them with any questions or concerns!

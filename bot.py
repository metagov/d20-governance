import discord
import random
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True
client = discord.Client(intents=intents)
token = os.getenv("DISCORD_TOKEN")
if token is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")


@client.event
async def on_ready():
    print("Logged in as {0.user}".format(client))


@client.event
async def on_message(message):
    print(message)
    print(message.content)
    if client.user.mentioned_in(message):
        if message.content.find("roll"):
            print("rolling...")
            # Roll the dice and assign a governance structure based on the result
            roll = random.randint(1, 6)
            if roll <= 3:
                # Benevolent Dictator structure
                await message.channel.send(
                    "Quick! Post :b: in the chat 3 times to claim benevolent dictatorship status!"
                )
                # TODO: Grant the appropriate user(s) decision-making power using roles or permissions
            else:
                # Consensus structure
                await message.channel.send("Your governance structure is Consensus")
                # TODO: Apply the appropriate communication constraint for this structure

        if message.content.find("task"):
            # Prompt players to submit their proposal for the Metagov mascot
            await message.channel.send(
                "Your first task is to decide what type of entity the Metagov mascot should be. Deliberate amongst yourselves. You will be prompted to submit an answer to this in 4 minutes."
            )
            # TODO: Set up a timer to prompt players to submit their proposals in 4 minutes
            # TODO: Collect and store the proposals in a data structure

        if message.content.find("add value"):
            # Prompt players to vote on a new cultural value to add to the organization
            await message.channel.send(
                "Vote on a new cultural value to add to your organization:"
            )
            values = [
                "Eloquence",
                "Secrecy",
                "Rituals",
                "Friendship",
                "Solidarity",
                "Obscure",
            ]
            for i in range(len(values)):
                await message.add_reaction(
                    f"{i+1}\N{variation selector-16}\N{combining enclosing keycap}"
                )
            # TODO: Collect and count the votes for each value
            # TODO: Apply the chosen communication constraint based on the new value

    # TODO: Implement the timer to prompt players to submit their proposals


client.run(token=token)

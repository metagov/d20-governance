import discord
import random
import os
import asyncio
import re
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions, MissingPermissions

description = '''A bot for experimenting with governance'''

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="/",
                   description=description, intents=intents)

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
if token is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")


# Events
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


# Commands
@bot.command()
async def start_game(ctx, num_players: int = None):
    """
    Starts a game of d20 governance with the specified number of players. Creates a temporary channel for players to communicate.

    Parameters:
      num_players (int): The number of plyers required to start the game. Must be at least 2.

    Example: 
      /start_game 4
    """
    if num_players is None:
        await ctx.send("Specify the number of players needed to start the game. Type `/ help start_game` for more information.")
        return
    if num_players < 2:
        await ctx.send("The game requires at least 2 players to start")
        return
    if num_players > 20:
        await ctx.send("The maximum number of players that can play at once is 20")
        return
    else:
        await ctx.send(f"The game will start after {num_players - 1} players type join...")

        # Set timeout for starting game
        waiting_timeout = 600  # The window for starting a game will time out after 10 minutes
        # The game will auto-archive if there is no game play within 24 hours
        playing_timeout = 86400

        # Set game state and timeout
        state = "waiting_for_players"

        # Create temporary channel
        temp_channel = None

        # Set up vowel replacement event
        replace_vowels = False

    # Waiting for Players
    while state == "waiting_for_players":
        try:
            message = await bot.wait_for("message", timeout=waiting_timeout, check=lambda m: m.author != bot.user and m.content.lower() == "join")
        except asyncio.TimeoutError:
            await ctx.send("Game timed out. Not enough players joined.")
            break

        # Process join message
        player_name = message.author.name
        await ctx.send(f"{player_name} has joined the game!")

        # Check if enough players have joined
        members = []
        async for member in ctx.guild.fetch_members(limit=num_players):
            members.append(member)
        if len(members) == num_players:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            category = discord.utils.get(ctx.guild.categories, name="play")
            temp_channel = await category.create_text_channel(name="d20-play", overwrites=overwrites)
            await ctx.send(f"Temporary channel {temp_channel.mention} has been created.")
            await temp_channel.send("**d20 Play Has Begun**")
            await temp_channel.send(
                "**The Intro:**\n\n"
                "You have returned from an internet sabbath, "
                "and a communication collapse has swept over the internet's "
                "communication platforms. The usual ways of having conversations "
                "and making decisions online have been scrambled.\n\n"
                "Structures for making decisions and constraints on your ability "
                "to communicate are randomly imposed on this communication environment. "
                "You must now use new tools to piece together meaning, "
                "negotiate conversation, and make collective decisions "
                "in spite of this chaos.\n"
            )
            commands_list = await temp_channel.send(
                "**Available Commands:\n**"
                "'deciding'\n"
                "'task_one'\n"
                "'culture'\n"
                "'obscure'\n"
                "'end_obscurity'\n"
                "'secret_message'\n"
                "'quit'"
            )
            state = "playing"
            # TODO: Remove this list of available commands and have them set to a timer
            # TODO: Have a message here broadcasting the commands that the players have available to themselves
            # TODO: Make temporary channels have unique names appended to base "d20-play"
            # The appended text can be set by user or increment by number of active channels and order created

    # Playing The Game
    while state == "playing":
        try:
            message = await bot.wait_for("message", timeout=playing_timeout, check=lambda m: m.author != bot.user)
        except asyncio.TimeoutError:
            await temp_channel.send("Game timed out after no plays in 24 hours.")
            state = "game_end"

        # Cultural Constraints on Messages
        # Secrecy: Randomly Send Messages to DMs
        async def send_msg_to_random_player():
            players = [
                member for member in message.channel.members if not member.bot]
            random_player = random.choice(players)
            dm_channel = await random_player.create_dm()
            await dm_channel.send("Hello! This is a message sent to a random d20 governance player's DM.")

        if message.content.lower() == "secret_message":
            await send_msg_to_random_player()

        # Obscurity: Replace Vowles with Spaces
        # Switch vowel replacement
        if message.content.lower() == "obscure":
            replace_vowels = True
        if message.content.lower() == "end_obscurity":
            replace_vowels = False

        # Vowel replacement
        if replace_vowels:
            vowels = "aeiou"
            message_content = message.content.lower()
            message_content = "".join(
                [" " if c in vowels else c for c in message_content])
            await message.delete()
            await temp_channel.send(f"{message.author.mention} posted: {message_content}")
        # TODO: Change to be conditional on Cultural Module value "Obscure"

        # Decision Module Triggers
        if message.content.lower() == "deciding":
            await temp_channel.send(
                "*Randomly selecting decision module...*"
            )
            # Roll the dice and assign a governance structure based on the result
            roll = random.randint(1, 6)
            if roll <= 3:
                # Decision Module: Benevolent Dictator
                await temp_channel.send("**Decision Module: Benevolent Dictator**")
                await temp_channel.send(file=discord.File('assets/CR_Benevolent-Dictator.png'))
                await temp_channel.send(
                    "Quick! Post :b: in the chat 3 times to become the benevolent dictator!"
                )
                # TODO: Grant the appropriate user(s) decision-making power using roles or permissions
            else:
                # Decision Module: Consensus
                await temp_channel.send("**Decision Module: Consensus**")
                await temp_channel.send(file=discord.File('assets/CR_Consensus.png'))
                await temp_channel.send(
                    "Your organization has adopted a **consensus-based** governance structure. "
                    "Everyone must agree on a decision for it to pass"
                )
                # TODO: Apply the appropriate decision constraint for this structure
                # Idea: Maybe there is something else players can do if consensus is hard to arrive at

        # Task Triggers
        if message.content.lower() == "task_one":
            # Prompt players to submit their proposal for the community mascot
            await temp_channel.send(
                "**Your first task is to decide what type of entity your community's mascot should be.**"
            )
            await temp_channel.send(
                "Decide amongst yourselves. You will be prompted to submit an answer to this in 5 minutes."
            )

            async def task_one_submission():
                await asyncio.sleep(30)
                await temp_channel.send(
                    "**Submit your response to the following prompt:**"
                    "We propose that our community's mascot "
                    "be following type of entity:__________________________________"
                )
            await asyncio.create_task(task_one_submission())
            # TODO: Make the asyncio sleep parallel processing
            # TODO: Collect and store the proposals in a data structure
            # TODO: Make a way to vote on the proposals using the current decision module
            # TODO: Store the successful submission in a data structure

        # Cultural Modules Triggers
        if message.content.lower() == "culture":
            # Prompt players to vote on a new cultural value to adopt as an organization
            sent_message = await temp_channel.send(
                "Decide a new cultural value to adopt for your organization:\n"
                ":one: Eloquence\n"
                ":two: Secrecy\n"
                ":three: Rituals\n"
                ":four: Friendship\n"
                ":five: Solidarity\n"
                ":six: Obscurity"
            )
            values = [
                "Eloquence",
                "Secrecy",
                "Rituals",
                "Friendship",
                "Solidarity",
                "Obscurity",
            ]
            # Add reactions to the sent message
            for i in range(len(values)):
                await sent_message.add_reaction(
                    f"{i+1}\N{variation selector-16}\N{combining enclosing keycap}"
                )
            # TODO: Collect and count the votes for each value
            # TODO: Apply the chosen communication constraint based on the new value

        # Submission Triggers
        # TODO: Implement the timer to prompt players to submit their proposals

        # Quit game
        if message.content.lower() == "quit":
            await temp_channel.send(f"{message.author.name} has quit the game!")
            state = "game_end"

        if state == "game_end":
            # Archive temporary channel
            archive_category = discord.utils.get(
                ctx.guild.categories, name="archive")
            if temp_channel is not None:
                await message.channel.send(f"**The game is over. This channel is now archived.**")
                await temp_channel.edit(category=archive_category)
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(
                        read_messages=True, send_messages=False)
                }
                await temp_channel.edit(overwrites=overwrites)
            break
        # await asyncio.sleep(1)  # Check every second


bot.run(token=token)

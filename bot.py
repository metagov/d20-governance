import discord
import random
import os
import asyncio
import re
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions, MissingPermissions


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
if token is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")


def msg_contains_word(msg, word):
    return re.search(fr'\b({word})\b', msg) is not None


bannedWords = {"i"}


# Events
@bot.event
async def on_ready():
    print("Logged in as {0.user}".format(bot))


# Commands
@bot.command()
async def start_game(ctx):
    await ctx.send("Game will start after 1 player types join...")
    # TODO: Allow user who starts game set quorum (limit to 20)

    # Set game state and timeout
    state = "waiting_for_players"
    timeout = 600  # Game start window will time out after 10 minutes
    # TODO: Allow user to set timeout duration

    # Create temporary channel
    temp_channel = None

    # Set up vowel replacement event
    replace_vowels = False

    while state == "waiting_for_players":
        try:
            message = await bot.wait_for("message", timeout=timeout, check=lambda m: m.author != bot.user and m.content.lower() == "join")
        except asyncio.TimeoutError:
            await ctx.send("Game timed out. Not enough players joined.")
            break

        # Process join message
        player_name = message.author.name
        await ctx.send(f"{player_name} has joined the game!")

        # Check if enough players have joined
        members = []
        async for member in ctx.guild.fetch_members(limit=20):
            members.append(member)
        if len(members) >= 2:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            category = discord.utils.get(ctx.guild.categories, name="play")
            temp_channel = await category.create_text_channel(name="d20-play", overwrites=overwrites)
            await ctx.send(f"Temporary channel {temp_channel.mention} has been created.")
            await temp_channel.send("**d20 Play Has Begun**")
            await temp_channel.send("**Available Commands:**")
            await temp_channel.send("'roll', 'task-one', 'define-culture', and 'quit'")
            state = "playing"
            # TODO: Remove this and have these commands set to a timer
            # TODO: Have a message here broadcasting the commands that the players have available to themselves
            # TODO: Make temporary channels have unique names appended to base "d20-play"
            # TODO: The appended text can be set by user or increment by number of active channels and order created

    # Playing game
    while state == "playing":
        try:
            message = await bot.wait_for("message", check=lambda m: m.author != bot.user)
        except asyncio.TimeoutError:
            state = "game_over"

        # Process messages
        # Replace vowles with spaces
        if replace_vowels:
            vowels = "aeiou"
            message_content = message.content.lower()
            message_content = "".join(
                [" " if c in vowels else c for c in message_content])
            await message.delete()
            await temp_channel.send(f"{message.author.name} posted: {message_content}")
        else:
            await message.delete()
            await temp_channel.send(f"{message.author.name} posted: {message.content}")

        # Set up next event for vowel replacement
        replace_vowels = not replace_vowels
        # TODO: Right now replace_vowels alternates every message sent in channel for fun
        # TODO: Change to be conditional on Cultural Module value "Obscure"

        # Decision Module Triggers
        if message.content.lower() == "roll":
            await message.channel.send(
                "Rolling..."
            )
            # Roll the dice and assign a governance structure based on the result
            roll = random.randint(1, 6)
            if roll <= 3:
                # Decision Module: Benevolent Dictator
                await message.channel.send("**Decision Module: Benevolent Dictator**")
                await message.channel.send(file=discord.File('assets/CR_Benevolent-Dictator.png'))
                await message.channel.send(
                    "Quick! Post :b: in the chat 3 times to become the benevolent dictatorship!"
                )
                # TODO: Grant the appropriate user(s) decision-making power using roles or permissions
            else:
                # Decision Module: Consensus
                await message.channel.send("**Decision Module: Consensus**")
                await message.channel.send(file=discord.File('assets/CR_Consensus.png'))
                await message.channel.send(
                    "Your organization has adopted a consensus-based governance structure. Everyone must agree on a decision for it to pass"
                )
                # TODO: Apply the appropriate decision constraint for this structure

        # Task Triggers
        if message.content.lower() == "task-one":
            # Prompt players to submit their proposal for the community mascot
            await message.channel.send(
                "**Your first task is to decide what type of entity the your community's should be.**"
            )
            await message.channel.send(
                "Decide amongst yourselves. You will be prompted to submit an answer to this in 4 minutes."
            )
            # TODO: Set up a timer to prompt players to submit their proposals in 4 minutes
            # TODO: Collect and store the proposals in a data structure

        # Values Modules Triggers
        if message.content.lower() == "define-values":
            # Prompt players to vote on a new cultural value to adopt as an organization
            await message.channel.send(
                "Decide a new cultural value to adopt for your organization:"
            )
            values = [
                "Eloquence",
                "Secrecy",
                "Rituals",
                "Friendship",
                "Solidarity",
                "Obscure",
            ]
            # To be implemented (commented out to ensure "quit" still works):
            # for i in range(len(values)):
            #     await message.add_reaction(
            #         f"{i+1}\N{variation selector-16}\N{combining enclosing keycap}"
            #     )
            # TODO: Collect and count the votes for each value
            # TODO: Apply the chosen communication constraint based on the new value

        # Submission Triggers
        # TODO: Implement the timer to prompt players to submit their proposals

        # Quit game
        if message.content.lower() == "quit":
            await message.channel.send(f"{message.author.name} has quit the game!")
            # TODO: Make the game auto-archive after submission instead of manual quit.

            # Archive temporary channel
            archive_category = discord.utils.get(
                temp_channel.guild.categories, name="archive")
            if temp_channel is not None:
                await message.channel.send(f"**The game is over and your proposal submitted. This channel is now archived.**")
                await temp_channel.edit(category=archive_category)
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True),
                    ctx.guild.me: discord.PermissionOverwrite(
                        read_messages=True)
                }
                await temp_channel.edit(overwrites=overwrites)
                state = "game_over"

    # TODO: implement "game_over" state

bot.run(token=token)

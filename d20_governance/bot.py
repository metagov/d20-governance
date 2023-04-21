import discord
import random
import os
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
from discord.ext.commands import has_permissions, MissingPermissions
import yaml

description = """A bot for experimenting with governance"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", description=description, intents=intents)

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
if token is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")

# Timeouts
START_TIMEOUT = 600  # The window for starting a game will time out after 10 minutes
# The game will auto-archive if there is no game play within 24 hours
GAME_TIMEOUT = 86400
CONFIG_PATH = "d20_governance/config.yaml"
REPLACE_VOWELS = False
TEMP_CHANNEL = None


def read_config(file_path):
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    return config


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


# Commands
@bot.command()
async def test_game(ctx):
    """
    For testing the game. Bypasses join step.
    """
    print("Testing...")
    await ctx.send("Starting game")
    await setup(ctx)


@bot.command()
async def start_game(ctx, num_players: int = None):
    """
    Starts a game of d20 governance with the specified number of players. Creates a temporary channel for players to communicate.

    Parameters:
      num_players (int): The number of plyers required to start the game. Must be at least 2.

    Example:
      /start_game 4
    """
    print("Starting...")
    if num_players is None:
        await ctx.send(
            "Specify the number of players needed to start the game. Type `/ help start_game` for more information."
        )
        return
    if num_players < 2:
        await ctx.send("The game requires at least 2 players to start")
        return
    if num_players > 20:
        await ctx.send("The maximum number of players that can play at once is 20")
        return
    else:
        await ctx.send(f"The game will start after {num_players} players type join...")
        await wait_for_players(ctx, num_players)


# TODO: Prevent access to test_game and start_game outside of #game-creation channel


# Game States and Functions
# Waiting For Players
async def wait_for_players(ctx, num_players):
    print("Waiting...")
    while True:
        try:
            message = await bot.wait_for(
                "message",
                timeout=START_TIMEOUT,
                check=lambda m: m.author != bot.user and m.content.lower() == "join",
            )
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
        if len(members) == num_players + 1:  # plus 1 to account for bot as member
            await setup(ctx)
    # TODO: Turn the joining process into an emoji-based register instead of typing "join"


async def setup(ctx):
    print("Setting up...")
    config = read_config(CONFIG_PATH)

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True),
    }
    category = discord.utils.get(ctx.guild.categories, name="play")
    global TEMP_CHANNEL
    TEMP_CHANNEL = await category.create_text_channel(
        name="d20-play", overwrites=overwrites
    )
    await ctx.send(f"Temporary channel {TEMP_CHANNEL.mention} has been created.")
    await play(ctx, config)

    # TODO: Remove this list of available commands and have them set to a timer
    # TODO: Have a message here broadcasting the commands that the players have available to themselves
    # TODO: Make temporary channels have unique names appended to base "d20-play"
    # The appended text can be set by user or increment by number of active channels and order created


# Cultural Constraints on Messages
# Secrecy: Randomly Send Messages to DMs
async def send_msg_to_random_player():
    print("Sending random DM...")
    players = [member for member in TEMP_CHANNEL.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
    )


async def process_stage(stage):
    message = stage["message"]
    action = stage["action"]
    timeout = stage["timeout_mins"] * 60

    # Send the prompt to the channel
    await TEMP_CHANNEL.send(message)
    await asyncio.sleep(timeout)

    return True


async def play(ctx, game_config):
    stages = game_config["game"]["stages"]
    await TEMP_CHANNEL.send(game_config["game"]["intro"])
    commands = game_config["game"]["commands"]
    available_commands = "**Available Commands:**\n" + "\n".join(
        [f"'{command}'" for command in commands]
    )
    await TEMP_CHANNEL.send(available_commands)

    for stage in stages:
        name = stage["name"]
        print(f"Processing stage {name}")
        result = await process_stage(stage)
        if not result:
            await ctx.send(f"Error processing stage {stage}")
            break


# Archiving The Game
async def end(ctx, temp_channel):
    print("Archiving...")
    # Archive temporary channel
    archive_category = discord.utils.get(ctx.guild.categories, name="archive")
    if temp_channel is not None:
        await temp_channel.send(f"**The game is over. This channel is now archived.**")
        await temp_channel.edit(category=archive_category)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            ),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            ),
        }
        await temp_channel.edit(overwrites=overwrites)
    print("Archived...")
    return
    # TODO: Prevent bot from being able to send messages to arcvhived channels


@bot.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    if REPLACE_VOWELS and not message == "end_obscurity":
        vowels = "aeiou"
        message_content = message.content.lower()
        message_content = "".join([" " if c in vowels else c for c in message_content])
        await message.delete()
        await TEMP_CHANNEL.send(f"{message.author.mention} posted: {message_content}")

    # Process the commands after handling custom message processing
    await bot.process_commands(message)


# GAME COMMANDS


@bot.command()
async def decisions(ctx):
    print("Decisions command triggered.")
    await ctx.send("Selecting decision module...")
    # Roll the dice and assign a governance structure based on the result
    roll = random.randint(1, 6)
    if roll <= 3:
        # Decision Module: Benevolent Dictator
        await ctx.send("**Decision Module: Benevolent Dictator**")
        await ctx.send(file=discord.File("assets/CR_Benevolent-Dictator.png"))
        await ctx.send(
            "Quick! Post :b: in the chat 3 times to become the benevolent dictator!"
        )
    else:
        # Decision Module: Consensus
        await ctx.send("**Decision Module: Consensus**")
        await ctx.send(file=discord.File("assets/CR_Consensus.png"))
        await ctx.send(
            "Your organization has adopted a **consensus-based** governance structure. Everyone must agree on a decision for it to pass"
        )


@bot.command()
async def culture(ctx):
    print("Cultural module decision...")
    sent_message = await ctx.send(
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


@bot.command()
async def obscure(ctx):
    print("Obscurity on...")
    await ctx.send("Obscurity begins!")
    global REPLACE_VOWELS
    REPLACE_VOWELS = True


@bot.command()
async def end_obscurity(ctx):
    print("Obscurity off...")
    await ctx.send("Obscurity ends!")
    global REPLACE_VOWELS
    REPLACE_VOWELS = False


@bot.command()
async def secret_message(ctx):
    print("Secret message command triggered.")
    await send_msg_to_random_player()


@bot.command()
async def quit(ctx):
    print("Quiting...")
    await ctx.send(f"{ctx.author.name} has quit the game!")
    # TODO: Implement the logic for quitting the game and ending it for the user


@bot.command()
async def end_game(ctx):
    print("Ending game...")
    await end(ctx, TEMP_CHANNEL)
    print("Game ended.")


bot.run(token=token)

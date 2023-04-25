import discord
import random
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from discord import SelectOption
from discord.ui import View, Select, Button
from discord.ext import commands
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

# Presets
# Start Game Timeout
waiting_timeout = 600  # The window for starting a game will time out after 10 minutes
# Auto-Archive Timeout
playing_timeout = 86400
# Replace Vowel State
replace_vowels = False


def make_table_row(term, count, percentage):
    return f"{'': <20}{term: <20}{percentage: <20}"

# Classes
# Define a new ModalView to display game options


# class GameStartView(discord.ui.View):
#     def __init__(self, num_players_callback):
#         super().__init__()
#         self.num_players_callback = num_players_callback

#         # Dropdown menu for number of players
#         self.players_dropdown = discord.ui.Select(
#             placeholder='Select number of players',
#             options=[discord.SelectOption(
#                 label=str(i), value=str(i)) for i in range(2, 21)]
#         )
#         self.add_item(self.players_dropdown)

#         # Dropdown menu for game campaign
#         self.campaign_dropdown = discord.ui.Select(
#             placeholder='Select game campaign',
#             options=[
#                 discord.SelectOption(label='Campaign 1', value='campaign_1'),
#                 discord.SelectOption(label='Campaign 2', value='campaign_2'),
#                 discord.SelectOption(label='Campaign 3', value='campaign_3')
#             ]
#         )
#         self.add_item(self.campaign_dropdown)

#         # Submit button
#         self.submit_button = discord.ui.Button(label='Submit')
#         self.submit_button.callback = self.submit_callback
#         self.add_item(self.submit_button)

#     async def submit_callback(self, interaction: discord.Interaction):
#         await interaction.response.defer()
#         num_players = int(self.players_dropdown.values[0])
#         campaign = self.campaign_dropdown.values[0]
#         message = await interaction.original_message.edit(content=f"A new game has been proposed. {num_players} players are needed for the {campaign} campaign. Click the button below to join the game.")

#         # Join button
#         join_button = discord.ui.Button(label='Join')
#         join_button.callback = self.join_callback
#         self.add_item(join_button)

#         # Call the num_players_callback with the selected number of players
#         await self.num_players_callback(num_players)

#     async def join_callback(self, interaction: discord.Interaction):
#         await interaction.response.defer()
#         message = await interaction.original_message.edit(content=f"{interaction.user.mention} has joined the game.")


# Events
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


# Commands
@bot.command()
async def language_stats(ctx):
    language_terms = ['authority', 'rule', 'policy', 'vote', 'governance']

    channel = ctx.channel

    language_usage = {term: 0 for term in language_terms}

    async for message in channel.history(limit=None):
        for term in language_terms:
            if term.lower() in message.content.lower():
                language_usage[term] += 1

    total_messages = sum(language_usage.values())

    langauge_percentages = {term: round(
        count / total_messages * 100, 2) for term, count in language_usage.items()}

    table_rows = [make_table_row('Term', 'Count', 'Percentage')]
    for term, count in language_usage.items():
        percentage = langauge_percentages[term]
        table_rows.append(make_table_row(term, count, f'{percentage}%'))

    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(style=discord.ButtonStyle.green, label='Close', emoji='🔒',
                          custom_id='language_stats:close')
    )
    view.add_item(
        discord.ui.Select(placeholder='Select a term to view usage stats',
                          options=[discord.SelectOption(
                              label=term, value=term) for term in language_terms],
                          custom_id='language_stats:select_term')
    )

    embed = discord.Embed(title='Language Usage Statistics', color=0x00ff00)
    embed.description = '\n'.join(table_rows)

    message = await ctx.send(embed=embed, view=view)

    async def handle_select(interaction: discord.Interaction, term, message):
        await interaction.response.defer()

        count = language_usage[term]
        percentage = langauge_percentages[term]

        table_rows[0] = make_table_row(term, count, f'{percentage}%')
        embed.description = '\m'.join(table_rows)

        await message.edit(embed=embed)

    @bot.event
    async def on_select_option(interaction: discord.Interaction):
        if interaction.custom_id.startswith('language_stats:select_term'):
            term = interaction.data['values'][0]
            await handle_select(interaction, term, message)

    @bot.event
    async def on_button_click(interaction: discord.Interaction):
        if interaction.custom_id == 'language_states:close':
            view.children[0].disabled = True
            view.children[1].disabled = True
            await interaction.response.edit_message(embed=embed, view=view)


@bot.command()
async def test_game(ctx):
    """
    For testing the game. Bypasses join step.
    """
    print("Testing...")
    await ctx.send("Starting game")
    await make_game(ctx)


@bot.command()
async def start_game(ctx):
    """
    Starts a game of d20 governance with the specified number of players. Creates a temporary channel for players to communicate. A game can be for 2 to 20 players. Players join by reacting with a handshake emoji. 
    """
    print("Starting...")

    async def num_players_callback(num_players):
        # Wait until enough players have joined
        while len(view.children) < num_players + 1:
            await view.wait()

        await make_game(ctx, num_players)

    view = GameStartView(num_players_callback)
    await ctx.send("Select the number of players and the game campaign:", view=view)
# TODO: Prevent access to test_game and start_game outside of #game-creation channel


# Game States and Functions
# Waiting For Players
async def waiting(ctx, num_players):
    print("Waiting...")
    while True:
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
        if len(members) == num_players + 1:  # plus 1 to account for bot as member
            await make_game(ctx)
    # TODO: Turn the joining process into an emoji-based register instead of typing "join"

# Making The Game


async def make_game(ctx):
    print("Making...")
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
    }
    category = discord.utils.get(ctx.guild.categories, name="play")
    temp_channel = await category.create_text_channel(name=f"d20-play-{len(category.channels) + 1}", overwrites=overwrites)
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
        "'decisions'\n"
        "'task_one'\n"
        "'culture'\n"
        "'obscure'\n"
        "'end_obscurity'\n"
        "'secret_message'\n"
        "'quit'"
    )
    await playing(ctx, temp_channel, replace_vowels)
    # TODO: Remove this list of available commands and have them set to a timer
    # TODO: Have a message here broadcasting the commands that the players have available to themselves
    # TODO: Make temporary channels have unique names appended to base "d20-play"
    # The appended text can be set by user or increment by number of active channels and order created

# Playing The Game


async def playing(ctx, temp_channel, replace_vowels):
    print("Playing...")
    # Playing The Game
    while True:
        try:
            message = await bot.wait_for("message", timeout=playing_timeout, check=lambda m: m.author != bot.user)
        except asyncio.TimeoutError:
            await temp_channel.send("Game timed out after no plays in 24 hours.")
            await ending(ctx, temp_channel)

        # Cultural Constraints on Messages
        # Secrecy: Randomly Send Messages to DMs
        async def send_msg_to_random_player():
            print("Sending random DM...")
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
            print("Obscurity turned on...")
            replace_vowels = True
        if message.content.lower() == "end_obscurity":
            print("Obscurity turned off...")
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
        if message.content.lower() == "decisions":
            print("Selecting decision module...")
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
            print("Sending prompt one...")
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
        # TODO: Add a task that lets the players name their team and have that name appended to the channel name
        # Transform #d20-play to #d20-[name-of-team] (safety mechanisms for conforming to server guidlines?)

        # Cultural Modules Triggers
        if message.content.lower() == "culture":
            print("Cultural module decision...")
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
        # TODO: Implement the timer to prompt players to submit their complete proposals

        # Quit game
        if message.content.lower() == "quit":
            print("Quiting...")
            await temp_channel.send(f"{message.author.name} has quit the game!")
            await ending(ctx, temp_channel)
            # TODO: Set channel ID so this trigger can't be called in any other channel

# Archiving The Game


async def ending(ctx, temp_channel):
    print("Archiving...")
    # Archive temporary channel
    archive_category = discord.utils.get(
        ctx.guild.categories, name="archive")
    if temp_channel is not None:
        await temp_channel.send(f"**The game is over. This channel is now archived.**")
        await temp_channel.edit(category=archive_category)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=False)
        }
        await temp_channel.edit(overwrites=overwrites)
    print("Archived...")
    return
    # TODO: Prevent bot from being able to send messages to arcvhived channels

bot.run(token=token)

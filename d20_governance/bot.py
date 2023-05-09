import discord
import os
import asyncio
from discord.ext import commands
from typing import Set
from d20_governance.utils import *
from d20_governance.constants import *


description = """A bot for experimenting with governance"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", description=description, intents=intents)

# Iterate over the main modules
for module in GOVERNANCE_STACK_MODULES:
    module_name = module["name"]
    print(f"Module Name: {module_name}")

    # Check for submodules and iterate over them
    if "modules" in module:
        for submodule in module["modules"]:
            submodule_name = submodule["name"]
            print(f"  Submodule Name: {submodule_name}")

class JoinLeaveView(discord.ui.View):
    def __init__(self, ctx: commands.Context, num_players: int):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.num_players = num_players
        self.joined_players: Set[str] = set()

    @discord.ui.button(
        style=discord.ButtonStyle.green, label="Join", custom_id="join_button"
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        player_name = interaction.user.name
        if player_name not in self.joined_players:
            self.joined_players.add(player_name)
            await interaction.response.send_message(
                f"{player_name} has joined the quest!"
            )
            needed_players = self.num_players - len(self.joined_players)
            embed = discord.Embed(
                title=f"{self.ctx.author.display_name} Has Proposed a Quest: Join or Leave",
                description=f"**Current Players:** {', '.join(self.joined_players)}\n\n**Players needed to start:** {needed_players}",
            )  # Note: Not possible to mention author in embeds
            await interaction.message.edit(embed=embed, view=self)

            if len(self.joined_players) == self.num_players:
                # remove join and leave buttons
                await interaction.message.edit(view=None)
                # return variables from setup()
                TEMP_CHANNEL = await setup(self.ctx, self.joined_players)
                embed = discord.Embed(
                    title=f"The Quest That {self.ctx.author.display_name} Proposed is Ready to Play",
                    description=f"**Quest:** {TEMP_CHANNEL.mention}\n\n**Players:** {', '.join(self.joined_players)}",
                )
                await interaction.message.edit(embed=embed)
                await start_quest(self.ctx)

        else:
            # Ephemeral means only the person who took the action will see this message
            await interaction.response.send_message(
                "You have already joined the quest. Wait until enough people have joined for the quest to start.",
                ephemeral=True,
            )

    @discord.ui.button(
        style=discord.ButtonStyle.red, label="Leave", custom_id="leave_button"
    )
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        player_name = interaction.user.name
        if player_name in self.joined_players:
            # if players is in the list of joined players remove them from the list
            self.joined_players.remove(player_name)
            await interaction.response.send_message(
                f"{player_name} has abandoned the quest before it even began!"
            )
            needed_players = self.num_players - len(self.joined_players)
            embed = discord.Embed(
                title=f"{self.ctx.author.mention} Has Proposed a Quest: Join or Leave",
                description=f"**Current Players:** {', '.join(self.joined_players)}\n\n**Players needed to start:** {needed_players}",
            )
            await interaction.message.edit(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                "You can only leave a quest if you have signaled you would join it",
                ephemeral=True,
            )


@bot.event
async def on_ready():
    """
    Event handler for when the bot has logged in and is ready to start interacting with Discord
    """
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        await setup_server(guild)


@bot.event
async def on_guild_join(guild):
    """
    Event handler for when the bot has been invited to a new guild.
    """
    print(f"D20 Bot has been invited to server `{guild.name}`")
    await setup_server(guild)


# QUEST START AND PROGRESSION
@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def propose_quest(ctx, num_players: int = None):
    """
    Command to propose a game of d20 governance with the specified number of players.

    Parameters:
      num_players (int): The number of plyers required to start the game. Must be at least 2.

    Example:
      /propose_quest 4
    """
    print("Starting...")
    if num_players is None:
        await ctx.send(
            "Specify the number of players needed to start the game. Type `/ help start_game` for more information."
        )
        return
    if num_players < 1:  # FIXME: Change back to 2 after testing with others
        await ctx.send("The game requires at least 2 players to start")
        return
    if num_players > 20:
        await ctx.send("The maximum number of players that can play at once is 20")
        return
    else:
        print("Waiting...")
        view = JoinLeaveView(ctx, num_players)

        embed = discord.Embed(
            title=f"{ctx.author.display_name} Has Proposed a Quest: Join or Leave"
        )

        await ctx.send(embed=embed, view=view)


async def setup(ctx, joined_players):
    """
    Game State: Setup the config and create unique quest channel
    """
    print("Setting up...")

    # Set permissions for bot
    bot_permissions = discord.PermissionOverwrite(read_messages=True)

    # Create a dictionary containing overwrites for each player that joined,
    # giving them read_messages access to the temp channel and preventing message_delete
    player_overwrites = {
        ctx.guild.get_member_named(player): discord.PermissionOverwrite(
            read_messages=True, manage_messages=False
        )
        for player in joined_players
    }

    # Create a temporary channel in the d20-quests category
    overwrites = {
        # Default user cannot view channel
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        # Users that joined can view channel
        ctx.guild.me: bot_permissions,
        **player_overwrites,  # Merge player_overwrites with the main overwrites dictionary
    }
    quests_category = discord.utils.get(ctx.guild.categories, name="d20-quests")

    global TEMP_CHANNEL

    # create and name the channel with the quest_name from the yaml file
    # and add a number do distinguish channels
    TEMP_CHANNEL = await quests_category.create_text_channel(
        name=f"d20-{QUEST_TITLE}-{len(quests_category.channels) + 1}",
        overwrites=overwrites,
    )

    return TEMP_CHANNEL


async def start_quest(ctx):
    """
    Start a quest and create a new channel
    """
    # Generate intro image and send to temporary channel
    image = generate_image(QUEST_INTRO)
    image = overlay_text(image, QUEST_INTRO)
    image.save("generated_image.png")  # Save the image to a file
    # Post the image to the Discord channel
    intro_image_message = await TEMP_CHANNEL.send(
        file=discord.File("generated_image.png")
    )
    os.remove("generated_image.png")  # Clean up the image file
    await intro_image_message.pin()  # Pin the available commands message

    # Send commands message to temporary channel
    available_commands = "\n".join([f"`{command}`" for command in QUEST_COMMANDS])
    embed = discord.Embed(
        title="Available Commands",
        description=available_commands,
        color=discord.Color.blue(),
    )
    commands_message = await TEMP_CHANNEL.send(embed=embed)
    await commands_message.pin()  # Pin the available commands message

    for stage in QUEST_STAGE:
        print(f"Processing stage {stage}")
        result = await process_stages()
        if not result:
            await ctx.send(f"Error processing stage {stage}")
            break


async def process_stages():
    """
    Run stages from yaml config
    """
    # Generate stage message into image and send to temporary channel
    image = generate_image(QUEST_STAGE_MESSAGE)
    image = overlay_text(image, QUEST_STAGE_MESSAGE)
    image.save("generated_image.png")  # Save the image to a file
    # Post the image to the Discord channel
    await TEMP_CHANNEL.send(file=discord.File("generated_image.png"))
    os.remove("generated_image.png")  # Clean up the image file

    # Call the command corresponding to the event
    event_func = bot.get_command(QUEST_STAGE_ACTION).callback

    # Get the last message object from the channel to set context
    message_obj = await TEMP_CHANNEL.fetch_message(TEMP_CHANNEL.last_message_id)

    # Create a context object for the message
    ctx = await bot.get_context(message_obj)

    # Call the command function with with the context object
    await event_func(ctx=ctx)

    # Wait for the timeout period
    await asyncio.sleep(QUEST_STAGE_TIMEOUT)

    return True


async def end(ctx):
    """
    Archive the quest and channel
    """
    print("Archiving...")
    # Archive temporary channel
    archive_category = discord.utils.get(ctx.guild.categories, name="d20-archive")
    if TEMP_CHANNEL is not None:
        await TEMP_CHANNEL.send(f"**The game is over. This channel is now archived.**")
        await TEMP_CHANNEL.edit(category=archive_category)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            ),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            ),
        }
        await TEMP_CHANNEL.edit(overwrites=overwrites)
    print("Archived...")
    return
    # TODO: Prevent bot from being able to send messages to arcvhived channels


# CULTURE COMMANDS
@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def secret_message(ctx):
    """
    Secrecy: Randomly Send Messages to DMs
    """
    print("Secret message command triggered.")
    await send_msg_to_random_player()


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def obscurity(ctx, mode: str = None):
    """
    Toggle the obscurity mode or set it. Valid options are "scramble", "replace_vowels", "pig_latin", "camel_case". If no parameter is passed,
    obscurity will be toggled on or off.
    """
    global OBSCURITY
    global OBSCURITY_MODE

    # A list of available obscurity modes
    available_modes = ["scramble", "replace_vowels", "pig_latin", "camel_case"]
    embed = None
    if mode is None:
        OBSCURITY = not OBSCURITY
        embed = discord.Embed(
            title=f"Culture: Obscurity {'activated!' if OBSCURITY else 'deactivated!'}",
            color=discord.Color.dark_gold(),
        )
        if OBSCURITY:
            embed.add_field(name="Mode:", value=f"{OBSCURITY_MODE}", inline=False)
    elif mode not in available_modes:
        embed = discord.Embed(
            title=f"Error - The mode '{mode}' is not available.",
            color=discord.Color.red(),
        )
    else:
        OBSCURITY_MODE = mode
        OBSCURITY = True
        embed = discord.Embed(
            title="Culture: Obscurity On!", color=discord.Color.dark_gold()
        )
        embed.add_field(name="Mode:", value=f"{OBSCURITY_MODE}", inline=False)

    embed.set_thumbnail(
        url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/Embed_Thumbnails/obscurity.png"
    )
    await ctx.send(embed=embed)
    print(f"Obscurity: {'on' if OBSCURITY else 'off'}, Mode: {OBSCURITY_MODE}")


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def eloquence(ctx):
    global ELOQUENCE
    ELOQUENCE = not ELOQUENCE
    if ELOQUENCE:
        embed = discord.Embed(
            title="Culture: Eloquence", color=discord.Color.dark_gold()
        )
        embed.set_thumbnail(
            url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/Embed_Thumbnails/eloquence.png"
        )
        embed.add_field(
            name="ACTIVATED:",
            value="Messages will now be process through an LLM.",
            inline=False,
        )
        embed.add_field(
            name="LLM Prompt:",
            value="You are from the Shakespearean era. Please rewrite the following text in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent: [your message]",
            inline=False,
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Culture: Eloquence", color=discord.Color.dark_gold()
        )
        embed.set_thumbnail(
            url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/Embed_Thumbnails/eloquence.png"
        )
        embed.add_field(
            name="DEACTIVATED",
            value="Messages will no longer be processed through an LLM",
            inline=False,
        )
        await ctx.send(embed=embed)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def diversity(ctx):
    # Display the message count for each user
    message = "Message count by user:\n"

    # Sort the user_message_count dictionary by message count in descending order
    sorted_user_message_count = sorted(
        user_message_count.items(), key=lambda x: x[1], reverse=True
    )

    for user_id, count in sorted_user_message_count:
        user = await ctx.guild.fetch_member(user_id)
        message += f"{user.name}: {count}\n"
    await ctx.send(message)


# META GAME COMMANDS
@bot.command()
async def info(
    ctx,
    culture_module=None,
    current_decision_module=None,
    starting_decision_module=None,
):
    # TODO Pass starting or current decision module into the info command
    decision_module = current_decision_module or starting_decision_module
    embed = discord.Embed(title="Current Stats", color=discord.Color.dark_gold())
    embed.add_field(name="Current Decision Module:\n", value=f"{decision_module}\n\n")
    embed.add_field(name="Current Culture Module:\n", value=f"{culture_module}")
    await ctx.send(embed=embed)


@bot.command()
async def quit(ctx):
    """
    Individually quit the quest
    """
    print("Quiting...")
    await ctx.send(f"{ctx.author.name} has quit the game!")
    # TODO: Implement the logic for quitting the game and ending it for the user


@bot.command()
async def dissolve(ctx):
    """
    Trigger end of game
    """
    print("Ending game...")
    await end(ctx, TEMP_CHANNEL)
    print("Game ended.")


# TEST COMMANDS
@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def test_png_creation(ctx):
    create_svg_snapshot()
    with open("output.png", "rb") as f:
        png_file = discord.File(f, "output.svg")
        await ctx.send(file=png_file)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def gentest(ctx):
    """
    Test stability image generation
    """
    text = "Obscurity"
    image = generate_image(text)
    image = overlay_text(image, text)

    # Save the image to a file
    image.save("generated_image.png")

    # Post the image to the Discord channel
    await ctx.send(file=discord.File("generated_image.png"))

    # Clean up the image file
    os.remove("generated_image.png")


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def ctest(ctx):
    """
    A way to test and demo the culture messaging functionality
    """
    await culture_options_msg(ctx)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def dtest(ctx):
    """
    Test and demo the decision message functionality
    """
    starting_decision_module = await set_starting_decision_module(ctx)
    await decision_options_msg(ctx, starting_decision_module)


# ON MESSAGE
@bot.event
async def on_message(message):
    if message.author == bot.user:  # Ignore messages sent by the bot itself
        return

    # If message is a command, proceed directly to processing
    if message.content.startswith("/"):
        await bot.process_commands(message)
        return

    # Increment message count for the user
    user_id = message.author.id
    if user_id not in user_message_count:
        user_message_count[user_id] = 0
    user_message_count[user_id] += 1

    if OBSCURITY:
        await message.delete()
        obscurity_function = globals()[OBSCURITY_MODE]
        obscured_message = obscurity_function(message.content)
        await message.channel.send(
            f"{message.author.mention} posted: {obscured_message}"
        )
    elif ELOQUENCE:
        await message.delete()
        processing_message = await message.channel.send(
            f"Making {message.author.mention}'s post eloquent"
        )
        eloquent_text = await eloquence_filter(message.content)
        await processing_message.delete()
        await message.channel.send(f"{message.author.mention} posted: {eloquent_text}")


# BOT CHANNEL CHECKS
@bot.check
async def channel_name_check(ctx):
    """
    Check that the test_game and start_game commands are run in the `d20-agora` channel
    """
    # Check is "d20-agora" channel exists on server
    agora_channel = discord.utils.get(ctx.guild.channels, name="d20-agora")
    if agora_channel is None:
        embed = discord.Embed(
            title="Error - This command cannot be run in this channel.",
            color=discord.Color.red(),
        )
        embed.add_field(
            name=f"Missing channel: {agora_channel.name}",
            value=f"This command can only be run in the `{agora_channel.name}` channel.\n\n"
            f"The `{agora_channel.name}` channel was not found on this server.\n\n"
            f"To create it, click the Add Channel button in the Channels section on the left-hand side of the screen.\n\n"
            f"If you cannot add channels, ask a sever administrator to add this channel.\n\n"
            f"**Note:** The channel name must be exactly `{agora_channel.name}`.",
        )
        await ctx.send(embed=embed)
        return False
    if not agora_channel:
        embed = discord.Embed(
            title="Error - This command cannot be run in this channel.",
            color=discord.Color.red(),
        )
        embed.add_field(
            name=f"Wrong Channel: run in {agora_channel.name}",
            value=f"This command can only be run in the `{agora_channel.name}` channel.",
        )
        await ctx.send(embed=embed)
        return False
    else:
        return True


bot.run(token=DISCORD_TOKEN)

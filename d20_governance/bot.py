import discord
import os
import asyncio
import uuid
from discord.ext import commands
from typing import Set
from ruamel.yaml import YAML
from collections import OrderedDict
from d20_governance.utils.utils import *
from d20_governance.utils.constants import *
from d20_governance.utils.cultures import *
from d20_governance.utils.decisions import *
from langchain.memory import ConversationBufferMemory
from langchain import OpenAI, LLMChain, PromptTemplate
from langchain.chat_models import ChatOpenAI

description = """A bot for experimenting with governance"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", description=description, intents=intents)

QUEST_MODE = None


class JoinLeaveView(discord.ui.View):
    def __init__(self, ctx: commands.Context, num_players: int, gen_img: str):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.num_players = num_players
        self.gen_img = gen_img
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
                await start_quest(self.ctx, self.gen_img == "gen_img")

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
async def propose_quest(ctx, num_players: int = None, quest_mode: str = QUEST_MODE_YAML, gen_img: str = None):
    """
    Command to propose a game of d20 governance with the specified number of players.

    Parameters:
      num_players (int): The number of players required to start the game. Must be at least 2.

    Example:
      /propose_quest 4
    """
    print("Starting...")
    if quest_mode != QUEST_MODE_YAML and quest_mode != QUEST_MODE_LLM:
        raise ValueError("Invalid quest mode")
    global QUEST_MODE
    QUEST_MODE = quest_mode
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
        view = JoinLeaveView(ctx, num_players, gen_img)

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
    print("1")
    # Create a dictionary containing overwrites for each player that joined,
    # giving them read_messages access to the temp channel and preventing message_delete
    player_overwrites = {
        ctx.guild.get_member_named(player): discord.PermissionOverwrite(
            read_messages=True, manage_messages=False
        )
        for player in joined_players
    }
    print("2")
    # Create a temporary channel in the d20-quests category
    overwrites = {
        # Default user cannot view channel
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        # Users that joined can view channel
        ctx.guild.me: bot_permissions,
        **player_overwrites,  # Merge player_overwrites with the main overwrites dictionary
    }
    quests_category = discord.utils.get(ctx.guild.categories, name="d20-quests")
    print("3")
    global TEMP_CHANNEL

    # create and name the channel with the quest_name from the yaml file
    # and add a number do distinguish channels
    TEMP_CHANNEL = await quests_category.create_text_channel(
        name=f"d20-{QUEST_TITLE}-{len(quests_category.channels) + 1}",
        overwrites=overwrites,
    )
    print("4")
    return TEMP_CHANNEL

def get_llm_chain():
    template = """You are a chatbot generating the narrative and actions for a governance game.
    Your output must be of the following format:
        - stage: <stage_name>
          message: <exciting narrative message for the current stage of the game>
          action: "vote_governance <culture or decision>"
          timeout_mins: 1

    For the action field, you must select either "vote_governance culture" or "vote_governance decision". For the message field, make sure you are crafting an interesting and fun story that ties in with
    the overall game narrative so far. Also make sure that the message ties in with the action you 
    have selected. Your output MUST be valid yaml.

    {chat_history}
    Human: {human_input}
    Chatbot:"""

    prompt = PromptTemplate(
        input_variables=["chat_history", "human_input"], 
        template=template
    )
    memory = ConversationBufferMemory(memory_key="chat_history")
    llm_chain = LLMChain(
    llm=ChatOpenAI(temperature=0, model_name="gpt-4"), 
    prompt=prompt, 
    verbose=True, 
    memory=memory,
    )
    return llm_chain


async def start_quest(ctx, gen_img: bool):
    """
    Start a quest and create a new channel
    """
    global QUEST_INTRO
    if gen_img:
        # Generate intro image and send to temporary channel
        image = generate_image(QUEST_INTRO)
    else:
        # Create a white background image canvas instead og generating an image
        image = Image.new("RGB", (512, 512), (255, 255, 255))

    llm_chain = None
    if QUEST_MODE == QUEST_MODE_LLM:
        await TEMP_CHANNEL.send("generating next narrative step with llm..")
        llm_chain = get_llm_chain()
        yaml_string = llm_chain.predict(human_input="generate me an intro for my governance game")
        print(yaml_string)
        yaml_data = ru_yaml.load(yaml_string)
        if isinstance(yaml_data, list) and len(yaml_data) > 0:
            QUEST_INTRO = yaml_data[0]["message"]
        elif isinstance(yaml_data, dict) and len(yaml_data) > 0:
            QUEST_INTRO = ru_yaml.load(yaml_string)["message"]
        else:
            raise ValueError("yaml output in wrong format")

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

    for stage in QUEST_STAGES:
        try:
            if QUEST_MODE == QUEST_MODE_LLM:
                await TEMP_CHANNEL.send("generating next narrative step with llm..")
                yaml_string = llm_chain.predict(human_input="generate the next stage")
                print(yaml_string)
                yaml_data = ru_yaml.load(yaml_string)
            if isinstance(yaml_data, list) and len(yaml_data) > 0:
                stage = yaml_data[0]
            elif isinstance(yaml_data, dict) and len(yaml_data) > 0:
                stage = yaml_data
            else:
                raise ValueError("yaml output in wrong format")
            print(f"Processing stage {stage}")
            result = await process_stage(ctx, stage, gen_img)
            if not result:
                await ctx.send(f"Error processing stage {stage}")
                break
        except:
            await TEMP_CHANNEL.send(f"Received an error, retrying..")
            continue

async def process_stage(ctx, stage, gen_img):
    """
    Run stages from yaml config
    """

    # Generate stage message into image and send to temporary channel
    message = stage[QUEST_STAGE_MESSAGE]

    if gen_img:
        # Generate intro image and send to temporary channel
        image = generate_image(message)
    else:
        # Create a white background image canvas instead og generating an image
        image = Image.new("RGB", (512, 512), (255, 255, 255))

    image = overlay_text(image, message)
    image.save("generated_image.png")  # Save the image to a file
    # Post the image to the Discord channel
    await TEMP_CHANNEL.send(file=discord.File("generated_image.png"))
    os.remove("generated_image.png")  # Clean up the image file

    # Call the command corresponding to the event
    action_string = stage[QUEST_STAGE_ACTION]
    action_outcome = await execute_action(bot, action_string, TEMP_CHANNEL)
    if action_outcome is not None:
        await execute_action(bot, action_outcome, TEMP_CHANNEL)

    # Wait for the timeout period
    timeout_seconds = stage[QUEST_STAGE_TIMEOUT] * 60
    timeout_seconds = 2
    await asyncio.sleep(timeout_seconds)

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
async def transparency(ctx):
    embed = discord.Embed(
        title="New Culture: Transparency",
        description="The community has chosen to adopt a culture of transparency.",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def secrecy(ctx):
    embed = discord.Embed(
        title="New Culture: Secrecy",
        description="The community has chosen to adopt a culture of secrecy.",
        color=discord.Color.red(),
    )
    await ctx.send(embed=embed)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def autonomy(ctx):
    embed = discord.Embed(
        title="New Culture: Autonomy",
        description="The community has chosen to adopt a culture of autonomy.",
        color=discord.Color.blue(),
    )
    await ctx.send(embed=embed)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def secret_message(ctx):
    """
    Secrecy: Randomly Send Messages to DMs
    """
    print("Secret message command triggered.")
    await send_msg_to_random_player(TEMP_CHANNEL)


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
        url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/obscurity.png"
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
            url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/eloquence.png"
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
            url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/eloquence.png"
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


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if hasattr(bot, "vote_message") and reaction.message.id == bot.vote_message.id:
        if user.id in bot.voters:
            await reaction.remove(user)
            await user.send(f"Naughty naughty! You cannot vote twice!", delete_after=VOTE_DURATION_SECONDS)
        else:
            bot.voters.add(user.id)

@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def vote(ctx, question: str, *options: str):
    # Set starting decision module if necessary
    current_modules = get_current_governance_stack()["modules"]
    decision_module = next((module for module in current_modules if module['type'] == 'decision'), None)
    if decision_module is None:
        await set_starting_decision_module() 

    if len(options) <= 1:
        await ctx.send("Error: A poll must have at least two options.")
        return
    if len(options) > 10:
        await ctx.send("Error: A poll cannot have more than 10 options.")
        return

    emoji_list = [chr(0x1F1E6 + i) for i in range(26)]  # A-Z

    options_text = ""
    for i, option in enumerate(options):
        options_text += f"{emoji_list[i]} {option}\n"

    embed = discord.Embed(
        title=question, description=options_text, color=discord.Color.dark_gold()
    )
    vote_message = await ctx.send(embed=embed)

    for i in range(len(options)):
        await vote_message.add_reaction(emoji_list[i])

    # Initialize the set of voters and store the poll message
    bot.voters = set()
    bot.vote_message = vote_message

    await asyncio.sleep(VOTE_DURATION_SECONDS) # wait for votes to be cast

    vote_message = await ctx.channel.fetch_message(
        vote_message.id
    )  # Refresh message to get updated reactions
    reactions = vote_message.reactions
    results = {}
    total_votes = 0

    for i, reaction in enumerate(reactions):
        if reaction.emoji in emoji_list:
            results[options[i]] = (
                reaction.count - 1 # remove 1 to account for bot
            ) 
            total_votes += results[options[i]]

    # Calculate results
    results_text = f"Total votes: {total_votes}\n\n"
    for option, votes in results.items():
        percentage = (votes / total_votes) * 100 if total_votes else 0
        results_text += f"{option}: {votes} votes ({percentage:.2f}%)\n"

    winning_vote_count = 0
    tie = False
    winning_votes = []
    for option, votes in results.items():
        if votes > winning_vote_count:
            winning_vote_count = votes
            winning_votes = [option]
        elif votes == winning_vote_count:
            winning_votes.append(option)

    tie = len(winning_votes) > 1

    # Remove the bot's reactions
    bot_member = discord.utils.find(lambda m: m.id == bot.user.id, ctx.guild.members)
    for i in range(len(options)):
        await vote_message.remove_reaction(emoji_list[i], bot_member)

    embed = discord.Embed(
        title=f"{question} - Results",
        description=results_text,
        color=discord.Color.dark_gold(),
    )
    await ctx.send(embed=embed)

    if not tie:
        await ctx.send(
            f"The winning vote is: **{winning_votes[0]}** with {winning_vote_count} votes."
        )
    else:
        await ctx.send("No winning vote.")
        return None

    return winning_votes[0]

@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def vote_governance(ctx, governance_type: str):
    if governance_type is None:
        await ctx.send("Invalid governance type: {governance_type}")
        return
    modules = get_modules_for_type(governance_type)
    module_names = [module['name'] for module in modules]
    question = f"Which {governance_type} should we select?"
    winning_module_name = await vote(ctx, question, *module_names)
    # TODO: if no winning_module, hold retry logic or decide what to do
    if winning_module_name:
        winning_module = modules[module_names.index(winning_module_name)]
        add_module_to_stack(winning_module)
        await ctx.send(
            f" New module `{winning_module_name}` added to governance stack"
        )
        await post_governance(ctx)
    else: 
        embed = discord.Embed(
            title="Error - No winning module.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    return winning_module_name


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
async def show_governance(ctx):
    await post_governance(ctx)


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
    global FILE_COUNT

    print("Ending game...")
    await end(ctx)
    print("Game ended.")

    # Call generate_governance_stack_gif() to create a GIF from the saved snapshots
    generate_governance_journey_gif()

    await ctx.send("Here is a gif of your governance journey:")

    # Open the generated GIF and send it to Discord
    with open("governance_journey.gif", "rb") as f:
        gif_file = discord.File(f, "governance_journey.gif")
        await ctx.send(file=gif_file)
        os.remove("governance_journey.gif")

    FILE_COUNT = 0


# TEST COMMANDS
@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def clean(ctx):
    clean_temp_files()


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def clean_category_channels(ctx, category_name="d20-quests"):
    guild = ctx.guild
    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        await ctx.send(f'Category "{category_name}" was not found.')
        return

    for channel in category.channels:
        await channel.delete()

    await ctx.send(f'All channels in category "{category_name}" have been deleted.')


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def test_randomize_snapshot(ctx):
    shuffle_modules()
    make_governance_snapshot()


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def test_png_creation(ctx):
    make_governance_snapshot()
    with open("output.png", "rb") as f:
        png_file = discord.File(f, "output.svg")
        await ctx.send(file=png_file)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def test_generation(ctx):
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
async def test_culture(ctx):
    """
    A way to test and demo the culture messaging functionality
    """
    await vote_governance(ctx, "culture")


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-testing")
async def test_decision(ctx):
    """
    Test and demo the decision message functionality
    """
    await vote_governance(ctx, "decision")


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
        eloquent_text = await filter_eloquence(message.content)
        await processing_message.delete()
        await message.channel.send(f"{message.author.mention} posted: {eloquent_text}")


# BOT CHANNEL CHECKS
@bot.check
async def validate_channels(ctx):
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


try:
    bot.run(token=DISCORD_TOKEN)
finally:
    clean_temp_files()


    
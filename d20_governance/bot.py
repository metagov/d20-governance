import discord
import random
import os
import io
import asyncio
import emoji
from dotenv import load_dotenv
from discord.ext import commands
import yaml
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from PIL import Image, ImageDraw, ImageFont

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
GAME_TIMEOUT = (
    86400  # The game will auto-archive if there is no game play within 24 hours
)

# Const
CONFIG_PATH = "d20_governance/config.yaml"

# Init
OBSCURITY = False
ELOQUENCE = False
TEMP_CHANNEL = None
OBSCURITY_MODE = "scramble"

# Stores the number of messages sent by each user
user_message_count = {}


def read_config(file_path):
    """
    Function for reading a yaml file
    """
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    return config


# Decision Modules
decision_modules = [
    "👎 Approval Voting",
    "🪗 Consensus",
    "🥇 Ranked Choice",
    "☑️ Majority Voting",
]

# Dynamically extract emojis from the decision_modules list
# Prepare list
decision_emojis = []
for module in decision_modules:
    # Extract 'emoji' string produced by the emoji_list attribute for each culture module
    emojis = [e["emoji"] for e in emoji.emoji_list(module)]
    if len(emojis) > 0:
        # Append extracted emojis to the culture_emoji list
        decision_emojis.append(emojis[0])

# Prepare list of culture modules
list_decision_modules = "\n".join(decision_modules)

# Culture Modules
culture_modules = [
    "💐 Eloquence",
    "🤫 Secrecy",
    "🪨 Rituals",
    "🪢 Friendship",
    "🤝 Solidarity",
    "🥷 Obscurity",
]

# Dynamically extract emojis from the culture_modules list
# Prepare list
culture_emojis = []
for module in culture_modules:
    # Extract 'emoji' string produced by the emoji_list attribute for each culture module
    emojis = [e["emoji"] for e in emoji.emoji_list(module)]
    if len(emojis) > 0:
        # Append extracted emojis to the culture_emoji list
        culture_emojis.append(emojis[0])

# Prepare list of culture modules
list_culture_modules = "\n".join(culture_modules)


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


async def setup_server(guild):
    """
    Function to set up the server by checking and creating categories and channels as needed.
    """
    print("---")
    print(f"Checking setup for server: '{guild.name}'")
    print("Checking if necessary categories exist...")
    server_categories = ["d20-explore", "d20-quests", "d20-archive"]
    for category_name in server_categories:
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            print(f"Created category: {category.name}")
        else:
            print(f"Necessary categorie '{category.name}' already exists.")

    # Define the d20-agora channel
    print("Checking if necessary channels exist...")
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            read_messages=True, send_messages=True
        )
    }
    agora_category = discord.utils.get(guild.categories, name="d20-explore")
    agora_channel = discord.utils.get(guild.text_channels, name="d20-agora")
    if not agora_channel:
        # Create channel in the d20-explore category and apply permisions
        agora_channel = await guild.create_text_channel(
            name="d20-agora", overwrites=overwrites, category=agora_category
        )
        print(
            f"Created channel '{agora_channel.name}' under category '{agora_category}'."
        )
    else:
        print("The necessary channels exist.")


@bot.command()
# Check that command is run in the d20-agora channel
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def test(ctx):
    """
    Command to test the game. Bypasses the join step
    """
    print("Testing...")
    await ctx.send("Starting game")
    await setup(ctx)


@bot.command()
# Check that command is run in the d20-agora channel
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
    if num_players < 2:
        await ctx.send("The game requires at least 2 players to start")
        return
    if num_players > 20:
        await ctx.send("The maximum number of players that can play at once is 20")
        return
    else:
        await ctx.send(f"The game will start after {num_players} players type join...")
        await wait_for_players(ctx, num_players)
    # TODO: Turn this into a modal interaction


async def wait_for_players(ctx, num_players):
    """
    Game State: Create a wait period for players to join before setting up quest
    """
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
    """
    Game State: Setup the config and create quest channel
    """
    print("Setting up...")
    # Read config yaml
    game_config = read_config(CONFIG_PATH)
    quest_name = game_config["game"]["title"]

    # Create a temporary channel in the d20-quests category
    overwrites = {
        # Default user cannot view channel
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        # Users that joined can view channel
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True),
    }
    quests_category = discord.utils.get(ctx.guild.categories, name="d20-quests")
    # I can't remember why we set this temp_channel var in the global scope...
    global TEMP_CHANNEL
    TEMP_CHANNEL = await quests_category.create_text_channel(
        name=f"d20-{quest_name}-{len(quests_category.channels) + 1}",
        overwrites=overwrites,
    )
    await ctx.send(f"Temporary channel {TEMP_CHANNEL.mention} has been created.")
    await start_of_quest(ctx, game_config)


async def start_of_quest(ctx, game_config):
    """
    Start a quest and create a new channel
    """
    # Define game_config variables
    stages = game_config["game"]["stages"]
    intro = game_config["game"]["intro"]
    commands = game_config["game"]["meta_commands"]
    print(intro)

    # Turn intro message into image
    intro_img = messages_to_image(intro)
    img_bytes = io.BytesIO()
    intro_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Send quest intro message
    await TEMP_CHANNEL.send(file=discord.File(img_bytes, "output.png"))
    img_bytes.close()

    # Send commands message
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


async def process_stage(stage):
    """
    Run stages from yaml config
    """
    message = stage["message"]
    event = stage["action"]
    timeout = stage["timeout_mins"] * 60

    # Turn stage message into image
    message_img = messages_to_image(message)
    img_bytes = io.BytesIO()
    message_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Send image as message
    await TEMP_CHANNEL.send(file=discord.File(img_bytes, "output.png"))
    img_bytes.close()

    # Call the command corresponding to the event
    event_func = bot.get_command(event).callback

    # Get the last message object from the channel to set context
    message_obj = await TEMP_CHANNEL.fetch_message(TEMP_CHANNEL.last_message_id)

    # Create a context object for the message
    ctx = await bot.get_context(message_obj)

    # Call the command function with with the context object
    await event_func(ctx=ctx)

    # Wait for the timeout period
    await asyncio.sleep(timeout)

    return True


def messages_to_image(
    input_message, font_path="assets/fonts/bubble_love_demo.otf", font_size=20
):
    image = Image.new("RGB", (400, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, font_size)
    draw.text((10, 10), input_message, font=font, fill=(0, 0, 0))
    return image


async def start_of_quest(ctx, game_config):
    """
    Start a quest and create a new channel
    """
    # Define stages
    stages = game_config["game"]["stages"]
    # Send quest intro message
    await TEMP_CHANNEL.send(game_config["game"]["intro"])
    # Define commands
    commands = game_config["game"]["meta_commands"]
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


# Archive the game
async def end(ctx, temp_channel):
    print("Archiving...")
    # Archive temporary channel
    archive_category = discord.utils.get(ctx.guild.categories, name="d20-archive")
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


# GAME COMMANDS
@bot.command()
async def cdemo(ctx):
    """
    A way to test and demo the culture messaging functionality
    """
    await culture_options_msg(ctx)


async def culture_options_msg(ctx):
    print("A list of culture modules are presented")
    culture_how = "how culture is defined"
    msg = await ctx.send(
        "Decide a new cultural value to adopt for your organization:\n"
        f"{list_culture_modules}"
    )
    # Add reactions to the sent message based on emojis in culture_modules list
    for emoji in culture_emojis:
        await msg.add_reaction(emoji)
    # TODO: Collect and count the votes for each value
    # TODO: Apply the chosen communication constraint based on the new value
    await decision(ctx, culture_how)


@bot.command()
async def ddemo(ctx):
    """
    Test and demo the decision message functionality
    """
    starting_decision_module = await set_starting_decision_module(ctx)
    await decision_options_msg(ctx, starting_decision_module)


async def set_starting_decision_module(ctx):
    print("Randomly assign a starting decision module")
    # TODO: Probably a better way of coding this up
    rand = random.randint(1, 4)
    print(decision_modules[0])
    if rand == 1:
        starting_decision_module = decision_modules[0]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        # await ctx.send(file=discord.File("assets/CR_Consensus.png")) # TODO: select correct image
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    if rand == 2:
        starting_decision_module = decision_modules[1]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        await ctx.send(file=discord.File("assets/CR_Consensus.png"))
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    if rand == 3:
        starting_decision_module = decision_modules[2]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        # await ctx.send(file=discord.File("assets/CR_Consensus.png")) # TODO: select correct image
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    if rand == 4:
        starting_decision_module = decision_modules[3]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        # await ctx.send(file=discord.File("assets/CR_Consensus.png")) # TODO: select correct image
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    else:
        pass
    # TODO: Store this in a file per quest to reference later


async def decision_options_msg(
    ctx, current_decision_module=None, starting_decision_module=None
):
    decision_module = current_decision_module or starting_decision_module
    print("A list of decision modules are presented")
    decision_how = "how decisions are made"
    msg = await ctx.send(
        "Select a new decision making module to adopt for your group:\n"
        f"{list_decision_modules}"
    )
    # Add reactions to the sent message based on emojis in culture_modules list
    for emoji in decision_emojis:
        await msg.add_reaction(emoji)
    await decision(ctx, decision_how, decision_module=decision_module)


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


# TODO: This is a WIP -- Need to think through a modular system for decision and culture interactions
# TODO: Trigger a decisionon based on input
async def decision(
    ctx,
    culture_how=None,
    culture_modules=None,
    decision_how=None,
    decision_modules=None,
    decision_module=None,
):
    print("Decisions event triggered.")
    print(
        ctx,
        culture_how,
        culture_modules,
        decision_how,
        decision_modules,
        decision_module,
    )
    how = culture_how or decision_how
    await ctx.send(f"Make your decision about {how} using {decision_module}")
    # If passed a culture_message, select a culture based on decision_type
    if culture_how == True:
        for culture_module in culture_modules:
            if decision_module == "approval_voting":
                pass
            if decision_module == "consensus":
                pass
            if decision_module == "ranked_choice":
                pass
            if decision_module == "majority_voting":
                print("decision module is majority voting")
                await majority_voting()
                # TODO: implement a majority vote for selecting one of the culture_modules
                pass
            else:
                pass
    # If passed a decision message, select a new decision module based on durrent decision module
    if decision_how:
        for decision_module in decision_modules:
            if decision_module == "approval_voting":
                decision_definition = "approval_voting"
                # TODO: Send message with decision information to channel
                return decision_definition
            if decision_module == "consensus":
                decision_definition = "consensus"
                await ctx.send("**Your Decision Module: Consensus**")
                await ctx.send(file=discord.File("assets/CR_Consensus.png"))
                await ctx.send(
                    "Your organization has is now using a **consensus-based** decision making structure./n"
                    "Everyone must agree on a decision for it to pass"
                )
                return decision_definition
            if decision_module == "ranked_choice":
                decision_definition = "ranked_choice"
                # TODO: Send message with decision information to channel
                return decision_definition
            if decision_module == "majority_voting":
                decision_definition = "majority_voting"
                # TODO: Send message with decision information to channel
                return decision_definition
            else:
                pass


# Decision Modules
# TODO: Implement majority voting function
# TODO: Add params (threshold)


async def majority_voting():
    """
    Majority voting: A majority voting function
    """
    pass


# Cultural Modules - Commands


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def secret_message(ctx):
    """
    Secrecy: Randomly Send Messages to DMs
    """
    print("Secret message command triggered.")
    await send_msg_to_random_player()


async def send_msg_to_random_player():
    print("Sending random DM...")
    players = [member for member in TEMP_CHANNEL.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
    )


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def obscurity(ctx):
    """
    Toggle the obscurity mode
    """
    global OBSCURITY
    global OBSCURITY_MODE
    OBSCURITY = not OBSCURITY

    if OBSCURITY:
        await ctx.channel.send(f"Obscurity is on. Mode: {OBSCURITY_MODE}")
    else:
        await ctx.channel.send(f"Obscurity is off.")

    print(f"Obscurity: {'on' if OBSCURITY else 'off'}, Mode: {OBSCURITY_MODE}")


def scramble_word(word):
    if len(word) <= 3:
        return word
    else:
        middle = list(word[1:-1])
        random.shuffle(middle)
        return word[0] + "".join(middle) + word[-1]


def scramble(text):
    words = text.split()
    scrambled_words = [scramble_word(word) for word in words]
    return " ".join(scrambled_words)


def replace_vowels(text):
    vowels = "aeiou"
    message_content = text.lower()
    return "".join([" " if c in vowels else c for c in message_content])


def pig_latin_word(word):
    if word[0] in "aeiouAEIOU":
        return word + "yay"
    else:
        first_consonant_cluster = ""
        rest_of_word = word
        for letter in word:
            if letter not in "aeiouAEIOU":
                first_consonant_cluster += letter
                rest_of_word = rest_of_word[1:]
            else:
                break
        return rest_of_word + first_consonant_cluster + "ay"


def pig_latin(text):
    words = text.split()
    pig_latin_words = [pig_latin_word(word) for word in words]
    return " ".join(pig_latin_words)


def camel_case(text):
    words = text.split()
    camel_case_words = [word.capitalize() for word in words]
    return "".join(camel_case_words)


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def obscurity_mode(ctx, mode: str):
    """
    Set the obscurity mode. Valid options are "scramble", "replace_vowels", "pig_latin", "camel_case"
    """
    global OBSCURITY_MODE

    # A list of available obscurity modes
    available_modes = ["scramble", "replace_vowels", "pig_latin", "camel_case"]

    if mode not in available_modes:
        await ctx.channel.send(
            f"Invalid obscurity mode. Available modes: {', '.join(available_modes)}"
        )
    else:
        OBSCURITY_MODE = mode
        await ctx.channel.send(f"Obscurity mode set to: {mode}")


# Quit
@bot.command()
async def quit(ctx):
    print("Quiting...")
    await ctx.send(f"{ctx.author.name} has quit the game!")
    # TODO: Implement the logic for quitting the game and ending it for the user


# End Game
@bot.command()
async def end_game(ctx):
    print("Ending game...")
    await end(ctx, TEMP_CHANNEL)
    print("Game ended.")


@bot.command()
@commands.check(lambda ctx: ctx.channel.name == "d20-agora")
async def eloquence(ctx):
    global ELOQUENCE
    ELOQUENCE = not ELOQUENCE
    if ELOQUENCE:
        await ctx.send(
            "Eloquence mode activated. Messages will now be processed through an LLM."
        )
    else:
        await ctx.send(
            "Eloquence mode deactivated. Messages will no longer be processed through an LLM."
        )


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


async def eloquence_filter(text):
    """
    A LLM filter for messages during the /eloquence command/function
    """
    llm = OpenAI(temperature=0.9)
    prompt = PromptTemplate(
        input_variables=["input_text"],
        template="You are from the Shakespearean era. Please rewrite the following text in a way that makes the speaker sound as eloquent, persuasive, and rhetorical as possible, while maintaining the original meaning and intent: {input_text}",
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(text)


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


bot.run(token=token)

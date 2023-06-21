from typing import List
from click import command
import discord
from discord.ext import commands
from langchain import PromptTemplate
from pytest import param
import requests
import random
import base64
import cairosvg
import glob
import uuid
import pyttsx3
import datetime
import string
import asyncio
import logging
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont
from d20_governance.utils.constants import *
import shlex
from io import BytesIO
import os

from langchain.memory import ConversationBufferMemory
from langchain import OpenAI, LLMChain, PromptTemplate
from langchain.chat_models import ChatOpenAI

import shlex

class Action:
    def __init__(self, action: str, arguments: list, retries: int, retry_message: str, failure_message: str):
        self.action = action
        self.arguments = arguments
        self.retries = retries
        self.retry_message = retry_message
        self.failure_message = failure_message

    @classmethod
    def from_dict(cls, data: dict):
        action_string = data.get('action', '')
        tokens = shlex.split(action_string)
        action, *arguments = tokens
        return cls(
            action=action,
            arguments=arguments,
            retries=int(data.get('retries', 0)),
            retry_message=data.get('retry_message', ''),
            failure_message=data.get('failure_message', '')
        )

class Stage:
    def __init__(self, name, message, actions, progress_conditions):
        self.name = name
        self.message = message
        self.actions = actions
        self.progress_conditions = progress_conditions

class Quest:
    def __init__(self, quest_mode, gen_images, gen_audio, fast_mode, solo_mode):
        self.quest_data = None
        self.mode = quest_mode
        self.title = None
        self.stages = None
        self.joined_players = set()

        # meta game vars
        self.gen_audio = gen_audio
        self.gen_images = gen_images
        self.fast_mode = fast_mode
        self.game_channel = None
        self.solo_mode = solo_mode

        # josh game specific # TODO: find a more general solution
        self.players_to_submissions = {}
        self.players_to_nicknames = {}

        self.update_vars()

    def update_vars(self):
        # LLM mode does not have yaml
        if self.mode is not QUEST_MODE_LLM:
            with open(self.mode, "r") as f:
                quest_data = py_yaml.load(f, Loader=py_yaml.SafeLoader)
                self.quest_data = quest_data

        if self.quest_data is not None:
            self.title = self.quest_data.get("title")
            self.stages = self.quest_data.get("stages")
        elif self.mode:  # LLM mode has no quest data
            self.title = self.mode

    def set_quest_vars(self, quest_data, quest_mode):
        self.quest_data = quest_data
        self.mode = quest_mode
        self.update_vars()

    def add_player(self, player_name):
        # If player has already joined, this is a no-op
        self.joined_players.add(player_name)
        # TODO: figure out how to avoid this game-specific check here
        if self.mode == MINIGAME_JOSH:
            # Randomly select a nickname
            nickname = random.choice(nicknames)

            # Assign the nickname to the player
            self.players_to_nicknames[player_name] = nickname

            # Remove the nickname from the list so it can't be used again
            nicknames.remove(nickname)

    def add_submission(self, ctx, text):
        # get the name of the user invoking the command
        player_name = str(ctx.message.author.name)
        # get the nickname of the user invoking the command
        if self.mode == MINIGAME_JOSH:
            player_name = self.players_to_nicknames.get(player_name)
            self.players_to_submissions[player_name] = text
        else:
            self.players_to_submissions[player_name] = text

    def reset_submissions(self):
        self.players_to_submissions = {}

    def get_nickname(self, player_name):
        return self.players_to_nicknames.get(player_name)


# Decorator for access control management
def access_control():
    async def predicate(ctx):
        # If condition is true, command is able to be executed
        # Check if the command being run is /help and allow it to bypass checks
        if ctx.command.name == "help":
            print("Bypassing access_control check")
            return True

        # Check if command matches command_name
        if ctx.command.name == ACCESS_CONTROL_SETTINGS["command_name"]:
            return True

        # Check if the author is a bot
        if ctx.author.bot:
            return True

        # Check if the user has an allowed role
        for role in ctx.author.roles:
            if role.name in ACCESS_CONTROL_SETTINGS["allowed_roles"]:
                return True

        # Check if the user should be excluded based on role
        for role in ctx.author.roles:
            if role.name in ACCESS_CONTROL_SETTINGS["excluded_roles"]:
                message = f"This command is not available with the {role.name} role"  # might be useful for josh game, use not-josh role

        # If none of the above, the user doesn't have access to the command
        # Send an error message
        message = "Sorry, you do not have permission to run this command at this time."
        await ctx.send(message)
        return False

    return commands.check(predicate)


# Setup Utils
async def setup_server(guild):
    """
    Function to set up the server by checking and creating categories and channels as needed.
    """
    logging.info(f"---Checking setup for server: '{guild.name}'---")
    server_categories = ["d20-explore", "d20-quests", "d20-archive"]
    for category_name in server_categories:
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            logging.info(f"Created category: {category.name}")
        else:
            pass

    # Define the d20-agora channel
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
        logging.info(
            f"Created channel '{agora_channel.name}' under category '{agora_category}'."
        )
    else:
        pass

    # Check if all necessary channels and categories exist
    logging.info("Checking if necessary categories and channels exist...")
    channels_exist = all(
        discord.utils.get(guild.text_channels, name=name) for name in ["d20-agora"]
    )
    categories_exist = all(
        discord.utils.get(guild.categories, name=name) for name in server_categories
    )

    if channels_exist and categories_exist:
        logging.info("Necessary channels and categories exist.")
    else:
        logging.info("Some necessary channels or categories are missing.")


# Yaml command callback and parsing
async def execute_action(ctx, bot, action, temp_channel):
    command_name = action.action
    args = action.arguments
    command = bot.get_command(command_name)
    if command is None:
        raise Exception(f"Command {command_name} not found.")

    print(f"Executing {command}")

    # Pass the arguments to the command's callback function
    await command.callback(ctx, *args)

# Module Management
def get_modules_for_type(governance_type):
    """
    Send a message with the list of possible module names and make a new module based on selection
    """
    global ru_yaml
    governance_type_path = GOVERNANCE_TYPES.get(governance_type)
    with open(governance_type_path, "r") as f:
        data = ru_yaml.load(f)

    return data["modules"]

    # Note: Let the user select whic config files they will use
    ## They can select a quest and starting governance stack config
    ## The files will be added to the main directory and removed when either the game of the bot ends
    ## The governance config need to be passed to the make_governance_stack as well
    ## The governance config should have the uniqueID stripped to be ready for import into CR
    ## The final state of the governance file is posted as a md file to the discord along with the gif
    ## Should there be four different config files with the structure, process, decision, and culture modules?
    ## SPDC: Acronym for the gov stack
    ## This would make creating new modules easier instead of being contingent on a base config
    ## It would also allow someone to make their own gov stack to start the game
    ## In this case, there would need to be a way for adding some of the meta fields
    ## One element I don't know how to address at the moment is the nested aspect of CR in terms of EUs being able to
    ## Know how to next these modules in Discord
    ## Also unclear is we will be using a similar nesting structure
    ## For the time being, focus on a four-piece 1-level stack

    # Each decision or emoji react should be reading from a respective yaml file in order to select modules


def get_current_governance_stack():
    # Load the base yaml or governance stack config
    if os.path.exists(GOVERNANCE_STACK_CONFIG_PATH):
        with open(GOVERNANCE_STACK_CONFIG_PATH, "r") as f:
            base_yaml = ru_yaml.load(f)
    else:
        base_yaml = {"modules": []}  # or some other suitable default value
    return base_yaml


# Note: since we are not currently supporting nesting of modules,
# this function will ensure that there is only one of each module type.
# Later, we can modify this to include module nesting.
def add_module_to_stack(module):
    module["uniqueID"] = str(uuid.uuid4())

    # Load the base yaml or governance stack config
    base_yaml = get_current_governance_stack()

    # Find and remove the existing module of the same type if it exists
    base_yaml["modules"] = [
        m for m in base_yaml["modules"] if "type" in m and m["type"] != module["type"]
    ]

    # Append new module to base yaml or governance stack config
    base_yaml["modules"].append(module)

    # Write to governance stack config yaml
    with open(GOVERNANCE_STACK_CONFIG_PATH, "w") as f:
        ru_yaml.dump(base_yaml, f)

    make_governance_snapshot()

    return module


# Text Utils
async def stream_message(ctx, text, original_embed):
    embed = original_embed.copy()
    embed.description = "[...]"
    message_canvas = await ctx.send(embed=embed)
    try:
        chunks = chunk_text(text)
        joined_text = []
        for chunk in chunks:
            # Use the typing context manager to simulate typing
            async with ctx.typing():
                joined_text.append(chunk)
                # distorted_text = distort_text(joined_text)  # distorted text disabled
                joined_text_str = " ".join(joined_text)
                embed.description = joined_text_str
                await message_canvas.edit(embed=embed)
                sleep_time = random.uniform(0.7, 1.2)
                for word in chunk.split():
                    if "," in word:
                        sleep_time += 0.7
                    if "." in word:
                        sleep_time += 1.2
                    else:
                        pass
                await asyncio.sleep(sleep_time)
        final_message = "".join(joined_text_str) + " ✨"
        embed.description = final_message
        await message_canvas.edit(embed=embed)
    except Exception as e:
        print(e)


def chunk_text(text):
    words = text.split()
    chunks = []
    i = 0
    min = 10
    max = 14
    while i < len(words):
        chunk_size = min if random.random() < 0.6 else max
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size
    return chunks


def distort_text(word_list):
    distorted_list = []
    for i, word in enumerate(word_list):
        distortion_level = i + 1
        if len(word) <= 3:
            distorted_list.append(word)
            continue
        first_char = word[0]
        last_char = word[-1]
        middle_chars = list(word[1:-1])
        middle_chars_count = len(middle_chars)
        middle_chars_index = middle_chars_count // 2
        distorted_middle_chars = middle_chars.copy()
        if distortion_level > 1:
            if distortion_level > 2:
                if random.random() < 0.5 * distortion_level:
                    distorted_middle_chars[middle_chars_index] = "||"
            if random.random() < 0.4 * distortion_level:
                distorted_middle_chars[middle_chars_index] = "_"
        distorted_word = first_char + "".join(distorted_middle_chars) + last_char
        if len(distorted_word) > 3:
            distorted_word = (
                distorted_word[:3]
                + "".join(random.sample(string.punctuation, 3))
                + distorted_word[3:]
            )
        # Apply distortion based on probability and distortion level
        if random.random() < 0.1 * distortion_level:
            distorted_list.append("*" + word + "*")
        elif random.random() < 0.35 * distortion_level:
            distorted_list.append("_" + word + "_")
        elif random.random() < 0.6 * distortion_level:
            distorted_list.append("||" + word + "||")
        else:
            distorted_list.append(word)
    return distorted_list


# Audio Utils
# FIXME: Audio file is getting cut off before finishing string
def tts(text, filename):
    engine = pyttsx3.init()
    engine.setProperty("voice", "english")
    engine.setProperty("rate", 140)

    try:
        engine.save_to_file(text, filename)
        engine.runAndWait()
        print(f"{filename} created")
    finally:
        engine.stop()

    return filename


# Image Utils
# Generate Quest Images
def generate_image(prompt):
    response = requests.post(
        f"{STABILITY_API_HOST}/v1/generation/{ENGINE_ID}/text-to-image",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {STABILITY_TOKEN}",
            "Authorization": f"Bearer {STABILITY_TOKEN}",
        },
        json={
            "text_prompts": [{"text": f"{prompt}"}],
            "text_prompts": [{"text": f"{prompt}"}],
            "cfg_scale": 7,
            "clip_guidance_preset": "FAST_BLUE",
            "height": 512,
            "width": 512,
            "samples": 1,
            "steps": 10,  # minimum 10 steps, more steps longer generation time
        },
    )

    if response.status_code != 200:
        raise Exception("Non-200 response: " + str(response.text))

    data = response.json()

    image_data = base64.b64decode(data["artifacts"][0]["base64"])
    with open("generated_image.png", "wb") as f:
        f.write(image_data)

    return Image.open("generated_image.png")


def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    current_line = words[0]

    for word in words[1:]:
        if font.getsize(current_line + " " + word)[0] <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


def overlay_text(image, text):
    """
    Overlay text on images
    """
    draw = ImageDraw.Draw(image)
    font_size = 25
    font = ImageFont.truetype(FONT_PATH_BUBBLE, font_size)

    max_width = image.size[0] - 20
    wrapped_text = wrap_text(text, font, max_width)

    text_height = font_size + len(wrapped_text)
    image_width, image_height = image.size
    y_offset = (image_height - text_height) // 5

    for line in wrapped_text:
        text_width, _ = draw.textsize(line, font)
        position = ((image_width - text_width) // 2, y_offset)
        draw.text(
            position, line, (0, 0, 0), font, stroke_width=2, stroke_fill=(255, 255, 255)
        )
        y_offset += font_size

    return image


# Generate Governance Stack Images
def set_module_font_size(module_level=0):
    """
    Set and return font size based on module level
    """
    initial_font_size = 20
    font_size = initial_font_size - 2 * module_level

    font = ImageFont.truetype(FONT_PATH_LATO, font_size)

    return font


def get_module_text_box_size(draw, module, module_level=0):
    """
    Calculate the module text box size based on font size
    """
    font = set_module_font_size(module_level)
    text_witdh, text_height = draw.textsize(module["name"], font=font)
    return text_witdh, text_height


def get_module_height(img, draw, module, x, y, module_level=0):
    """
    Calculate the height of a module.
    A module is the max icon height and text height.
    """
    font = set_module_font_size(module_level)
    _, text_height = get_module_text_box_size(draw, module, module_level)

    icon = add_svg_icon(img, module["icon"], x, y, module_level)
    _, icon_height = icon.size

    return max(text_height, icon_height)


def add_svg_icon(img, icon_path, x, y, module_level, size=None):
    """
    Load the SVG icon, replace its fill color with black, and draw it on the canvas.
    """
    buf = BytesIO()

    # Set the icon size based on its original size and module_level
    if not size:
        original_size = cairosvg.svg2png(
            url=icon_path, write_to=None, output_height=None
        )
        original_icon = Image.open(BytesIO(original_size))
        original_width, original_height = original_icon.size
        size = (original_width - 2 * module_level, original_height - 2 * module_level)

    # Create the resized icon
    cairosvg.svg2png(
        url=icon_path, write_to=buf, output_width=size[0], output_height=size[1]
    )
    buf.seek(0)

    icon = Image.open(buf)
    icon = icon.convert("RGBA")
    pixel_data = icon.load()

    for i in range(icon.size[0]):
        for j in range(icon.size[1]):
            if pixel_data[i, j][3] > 0:
                # Replace the fill color with black
                pixel_data[i, j] = (0, 0, 0, pixel_data[i, j][3])

    if size:
        size = (size[0] - 2 * module_level, size[1] - 2)

    img.paste(icon, (int(x), int(y) + (module_level * 1)), mask=icon)
    return icon


def draw_modules(
    img, draw, module, x, y, module_level=0, drawn_modules=set(), max_x=0, max_y=0
):
    """
    Draw module names, icons, and rectangles
    """
    module_height = get_module_height(img, draw, module, x, y, module_level)
    icon = add_svg_icon(img, module["icon"], x, y, module_level)
    icon_width, _ = icon.size

    uniqueID = module["uniqueID"]

    # Check if the module has already been drawn
    if uniqueID in drawn_modules:
        return x, y

    # Add the module's uniqueID to the set of drwn modules
    drawn_modules.add(uniqueID)
    print(
        f"Depth Level:{module_level}, UniqueID:{uniqueID}"
    )  # TODO: Remove, here for testing at the moment

    # Calculate the dimensions of the module name and select the appropriate font size
    font = set_module_font_size(module_level)
    text_width, text_height = get_module_text_box_size(draw, module, module_level)
    print(
        f" > Text dimensions for {module['name']}: width={text_width}, height={text_height}"
    )  # TODO: Remove, here for testing at the moment

    # Draw the module name
    draw.text(
        (x + icon_width + MODULE_PADDING, y + (module_level * 1)),
        module["name"],
        font=font,
        fill=(0, 0, 0),
    )
    print(
        f" >> Module name `{module['name']}` drawn at x={x}, y={y}"
    )  # TODO: Remove, here for testing at the moment

    # Calculate the x coordinate for the next module to be drawn
    next_x = x + icon_width + text_width + MODULE_PADDING

    # Recursively draw modules
    if "modules" in module:
        sub_module_x = next_x + 20
        sub_module_y = y
        for sub_module in module["modules"]:
            # Recurse through draw module function
            sub_module_x, _ = draw_modules(
                img,
                draw,
                sub_module,
                sub_module_x,
                sub_module_y,
                module_level + 1,
                drawn_modules,
                max_x,
                max_y,
            )
            sub_module_x += 20  # Add 20px for each sub module

        # Update the next module's x-coordinate
        next_x = max(next_x, sub_module_x - 20)

    # Draw a rectangle around modules
    rect_start = (x - MODULE_PADDING, y - MODULE_PADDING + (module_level * 3))
    rect_end = (
        next_x + MODULE_PADDING,
        y + module_height + MODULE_PADDING - (module_level * 1),
    )
    draw.rectangle([rect_start, rect_end], outline=(0, 0, 0), width=2)
    print(f"Depth Level:{module_level}, UniqueID:{uniqueID}")
    print(
        f"Rectangle drawn for module {module['name']}: start={rect_start}, end={rect_end}"
    )
    print(
        f"   >>> Module {module['name']} finished drawing"
    )  # TODO: Remove, here for testing

    # Calculate the maximum x-coordinate reached during drawing
    max_x = max(max_x, next_x)
    print(max_x)
    print(f"##{module_height}##")

    if module_level > 0:
        max_x += 5

    return max_x, module_height


def make_governance_snapshot():
    """
    Generate a governance stack snapshot.
    This is a PNG file based on the governance_stack_config YAML.
    """
    if os.path.isfile(GOVERNANCE_STACK_CONFIG_PATH):
        data = read_config(GOVERNANCE_STACK_CONFIG_PATH)
    else:
        print("No governance config created")

    global FILE_COUNT

    # Initialize the actual image canvas with responsive width
    img = Image.new(
        "RGB", (2000, 2000), (255, 255, 255, 255)
    )  # Set large to eventually crop. There's probably a more elegant way of doing this
    draw = ImageDraw.Draw(img)

    # Pass starting module positions and add with each iteration
    x, y = 20, 20
    max_y = 0
    module_height = 0
    for module in data["modules"]:
        x, max_height = draw_modules(img, draw, module, x, y)
        x += 30
        max_y = y + max(max_height, module_height) + MODULE_PADDING * 2

    max_x = x

    # Crop the image to make the canvas responsive to the content with a 10px margin on all sides
    img_cropped = img.crop(
        (
            0,
            0,
            max_x,
            max_y,
        )
    )

    # Save the output image to a PNG file
    os.makedirs(GOVERNANCE_STACK_SNAPSHOTS_PATH, exist_ok=True)
    if FILE_COUNT is not None:
        img_cropped.save(
            f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_{FILE_COUNT}.png"
        )
    else:
        img_cropped.save("governance_stack_snapshot.png")

    FILE_COUNT += 1  # Increment the file count for the next snapshot


# FIXME: This Shuffle is not working
def shuffle_modules():
    # Extract all sub-modules into a separate list
    if os.path.isfile(GOVERNANCE_STACK_CONFIG_PATH):
        data = read_config(GOVERNANCE_STACK_CONFIG_PATH)
    parent_modules = []
    sub_modules = []

    for module in data["modules"]:
        if "modules" in module:
            sub_modules.extend(module["modules"])
        else:
            parent_modules.append(module)

    # Shuffle parent modules and sub-modules together
    modules_combined = parent_modules + sub_modules
    random.shuffle(modules_combined)

    # Reassign sub-modules to parent modules, cycling through parent modules
    if parent_modules:
        for i, sub_module in enumerate(sub_modules):
            parent_module = parent_modules[i % len(parent_modules)]
            parent_module.setdefault("modules", []).append(sub_module)

    return modules_combined


# Post and show governance stack
def generate_governance_journey_gif():
    frames = []

    # Ensure the directories exist
    os.makedirs(GOVERNANCE_STACK_SNAPSHOTS_PATH, exist_ok=True)

    snapshot_files = sorted(
        glob.glob(f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_*.png")
    )

    for filename in snapshot_files:
        frames.append(Image.open(filename))
        frames[0].save(
            "governance_journey.gif",
            save_all=True,
            append_images=frames[1:],
            duration=200,  # milliseconds
            loop=0,
        )


async def post_governance(ctx):
    # Find all PNGs in the governance_stack folder
    snapshot_files = glob.glob(f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/*.png")

    # Check if there are any snapshots in the folder
    if len(snapshot_files) == 0:
        await ctx.send("No governance stack snapshots found.")
    else:
        # Find the most recently created snapshot in the folder
        latest_snapshot = max(snapshot_files, key=os.path.getctime)

        # Open the most recent snapshot and send it to Discord
        with open(latest_snapshot, "rb") as f:
            png_file = discord.File(f, f"{os.path.basename(latest_snapshot)}")
            await ctx.send("Your current governance stack: ", file=png_file)
            print(f"{os.path.basename(latest_snapshot)}")


# BOT CHANNEL CHECKS
async def check_cmd_channel(ctx, channel_name):
    """
    Check that the test_game and start_game commands are run in the `d20-agora` channel
    """
    # Check if the command being run is /help and allow it to bypass checks
    channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    if ctx.command.name == "help":
        return True
    elif ctx.channel.name != channel.name:
        embed = discord.Embed(
            title="Error: This command cannot be run in this channel.",
            description=f"Run this command in <#{channel.id}>",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
        return False
    else:
        return True


# REPO DIRECTORY CHECKS
def check_dirs():
    if not os.path.exists(AUDIO_MESSAGES_PATH):
        os.makedirs(AUDIO_MESSAGES_PATH)
        print(f"Created {AUDIO_MESSAGES_PATH} directory")
    if not os.path.exists(GOVERNANCE_STACK_SNAPSHOTS_PATH):
        os.makedirs(GOVERNANCE_STACK_SNAPSHOTS_PATH)
        print(f"Created {GOVERNANCE_STACK_SNAPSHOTS_PATH} directory")
    if not os.path.exists(LOGGING_PATH):
        os.makedirs(LOGGING_PATH)
        print(f"Created {LOGGING_PATH} directory")
    if not os.path.exists(LOG_FILE_NAME):
        with open(LOG_FILE_NAME, "w") as f:
            f.write("This is a new log file.")
            print(f"Creates {LOG_FILE_NAME} file")


# Cleanup
def clean_temp_files():
    """
    Delete temporary files
    """
    snapshot_files = glob.glob(
        f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_*.png"
    )
    # Cleanup: delete the governance snapshot files
    for filename in snapshot_files:
        os.remove(filename)
        logging.info(f"Deleted temporary governance snapshot files in {snapshot_files}")

    governance_config = glob.glob(GOVERNANCE_STACK_CONFIG_PATH)
    # Cleanup: delete the governance config
    for filename in governance_config:
        os.remove(filename)
        logging.info(
            f"Deleted temporary governance configuration in {governance_config}"
        )

    audio_files = glob.glob(f"{AUDIO_MESSAGES_PATH}/*.mp3")
    # Cleanup: delete the generated audio files
    for filename in audio_files:
        os.remove(filename)
        logging.info(f"Deleted temporary audio files in {audio_files}")

    log_files = glob.glob(f"{LOGGING_PATH}/*.log")
    days_to_keep = 7
    today = datetime.date.today()
    # Cleanup: Clean log files every 7 days
    for filename in log_files:
        if os.path.isfile(filename):
            modified_time = datetime.date.fromtimestamp(os.path.getmtime(filename))
            age_in_days = (today - modified_time).days
            if age_in_days >= days_to_keep:
                os.remove(filename)


async def delete_all_webhooks(guild):
    webhooks = await guild.webhooks()

    # Delete each webhook
    for webhook in webhooks:
        await webhook.delete()
        print("Webhooks from all guilds deleted")


# LLM HELPERS


def get_llm_agent():
    template = """You are a chatbot generating the narrative and actions for a governance game.
    Your output must be of the following format:
    - stage: <stage_name>
    message: <exciting narrative message for the current stage of the game>
    action: "vote_governance <culture or decision>"
    timeout_mins: 1

    For the action field, you must select either "vote_governance culture" or "vote_governance decision". 
    For the message field, make sure you are crafting an interesting and fun story that ties in with the overall game narrative so far. 
    Also make sure that the message ties in with the action you have selected. 
    Your output MUST be valid yaml.

    {chat_history}
    Human: {human_input}
    Chatbot:"""

    prompt = PromptTemplate(
        input_variables=["chat_history", "human_input"], template=template
    )
    memory = ConversationBufferMemory(memory_key="chat_history")
    llm_chain = LLMChain(
        llm=ChatOpenAI(temperature=0, model_name="gpt-4"),
        prompt=prompt,
        verbose=True,
        memory=memory,
    )
    return llm_chain


async def generate_stage_llm(llm_agent, quest: Quest):
    await quest.game_channel.send("generating next narrative step with llm..")
    MAX_ATTEMPTS = 5
    attempt = 0
    stage = None
    while attempt < MAX_ATTEMPTS and not stage:
        try:
            attempt += 1
            await quest.game_channel.send("generating next narrative step with llm..")
            yaml_string = llm_agent.predict(human_input="generate the next stage")
            print(yaml_string)
            yaml_data = ru_yaml.load(yaml_string)

            if isinstance(yaml_data, list) and len(yaml_data) > 0:
                stage = yaml_data[0]
            elif isinstance(yaml_data, dict) and len(yaml_data) > 0:
                stage = yaml_data
        except:
            await quest.game_channel.send("encountered error, retrying..")

    if not stage:
        raise ValueError(
            "yaml output in wrong format after {} attempts".format(MAX_ATTEMPTS)
        )

    stage = Stage(
        name=stage[QUEST_NAME_KEY],
        message=stage[QUEST_MESSAGE_KEY],
        actions=stage[QUEST_ACTIONS_KEY],
        progress_conditions=stage[QUEST_PROGRESS_CONDITIONS_KEY],
    )
    return stage

import discord
import requests
import random
import base64
import cairosvg
import glob
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from PIL import Image, ImageDraw, ImageFont
from d20_governance.constants import *
import shlex
from io import BytesIO


# Setup Utils
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


# Image Utils
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


def select_font(module_level=0):
    """
    Return the appropriate font based on the module level
    """
    initial_font_size = 20
    font_size = initial_font_size - 2 * module_level

    font = ImageFont.truetype(FONT_PATH_LATO, font_size)

    return font


def get_module_text_size(draw, module, module_level=0):
    """
    Calculate the module text size based on its font and type
    """
    font = select_font(module_level)
    text_witdh, text_height = draw.textsize(module["name"], font=font)
    return text_witdh, text_height


def get_module_height(img, draw, module, x, y, module_level=0):
    """
    Calculate the height of a module.
    a module is the max icon height and text height.
    """
    font = select_font(module_level)
    _, text_height = get_module_text_size(draw, module, module_level)

    icon = add_svg_icon(img, module["icon"], x, y, module_level)
    _, icon_height = icon.size

    return max(text_height, icon_height)


def draw_module(
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
    font = select_font(module_level)
    text_width, text_height = get_module_text_size(draw, module, module_level)
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
            sub_module_x, _ = draw_module(
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


def create_governance_stack_png_snapshot(modules=GOVERNANCE_MODULES):
    """
    Generate a governance stack snapshot.
    This is a PNG file based on the governance_stack_config YAML.
    """
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
    for module in modules:
        x, max_height = draw_module(img, draw, module, x, y)
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
    if FILE_COUNT is not None:
        img_cropped.save(
            f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_{FILE_COUNT}.png"
        )
    else:
        img_cropped.save("governance_stack_snapshot.png")

    FILE_COUNT += 1  # Increment the file count for the next snapshot


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


def generate_governance_stack_gif():
    frames = []
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

    # Cleanup: delete the snapshot files fromf {the GOVERNANCE_STACK_SNAPSHOTS_PATH} folder
    for filename in snapshot_files:
        os.remove(filename)


# FIXME: This Shuffle is not working
def shuffle_modules():
    # Extract all sub-modules into a separate list
    sub_modules = []
    parent_modules = []

    for module in GOVERNANCE_MODULES:
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


# Culture Utils
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


def parse_action_string(action_string):
    return shlex.split(action_string)


async def send_msg_to_random_player(temp_channel):
    print("Sending random DM...")
    players = [member for member in temp_channel.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
    )


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


# Decision Utils
async def majority_voting():
    """
    Majority voting: A majority voting function
    """
    pass


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


async def set_starting_decision_module(ctx):
    print("Randomly assign a starting decision module")
    # TODO: Probably a better way of coding this up
    rand = random.randint(1, 4)
    print(DECISION_MODULES[0])
    if rand == 1:
        starting_decision_module = DECISION_MODULES[0]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        # await ctx.send(file=discord.File("assets/CR_Consensus.png")) # TODO: select correct image
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    if rand == 2:
        starting_decision_module = DECISION_MODULES[1]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        await ctx.send(file=discord.File("assets/CR_Consensus.png"))
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    if rand == 3:
        starting_decision_module = DECISION_MODULES[2]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        # await ctx.send(file=discord.File("assets/CR_Consensus.png")) # TODO: select correct image
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    if rand == 4:
        starting_decision_module = DECISION_MODULES[3]
        await ctx.send(f"**Your Starting Decision Module: {starting_decision_module}**")
        # await ctx.send(file=discord.File("assets/CR_Consensus.png")) # TODO: select correct image
        await ctx.send(
            f"Your organization has is now using a **{starting_decision_module}** decision making structure."
        )
        return starting_decision_module
    else:
        pass
    # TODO: Store this in a file per quest to reference later


# TODO: This is a WIP -- Need to think through a modular system for decision and culture interactions
# TODO: Trigger a decisionon based on input
async def decision(
    ctx,
    culture_how=None,
    CULTURE_MODULES=None,
    decision_how=None,
    DECISION_MODULES=None,
    decision_module=None,
):
    print("Decisions event triggered.")
    print(
        ctx,
        culture_how,
        CULTURE_MODULES,
        decision_how,
        DECISION_MODULES,
        decision_module,
    )
    how = culture_how or decision_how
    await ctx.send(f"Make your decision about {how} using {decision_module}")
    # If passed a culture_message, select a culture based on decision_type
    if culture_how == True:
        for culture_module in CULTURE_MODULES:
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
        for decision_module in DECISION_MODULES:
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


def cleanup_governance_snapshots():
    snapshot_files = glob.glob(
        f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_*.png"
    )
    for filename in snapshot_files:
        os.remove(filename)


create_governance_stack_png_snapshot()

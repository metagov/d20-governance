import discord
import requests
import random
import base64
import cairosvg
import glob
from PIL import Image, ImageDraw, ImageFont
from constants import *
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


def make_governance_snapshot(modules=GOVERNANCE_MODULES):
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


def generate_governance_journey_gif():
    frames = []
    snapshot_files = sorted(
        glob.glob(f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_*.png")
    )
    for filename in snapshot_files:
        frames.append(Image.open(filename))


def parse_action_string(action_string):
    return shlex.split(action_string)


async def send_msg_to_random_player(temp_channel):
    print("Sending random DM...")
    players = [member for member in temp_channel.members if not member.bot]
    random_player = random.choice(players)
    dm_channel = await random_player.create_dm()
    await dm_channel.send(
        "🌟 Greetings, esteemed adventurer! A mischievous gnome has entrusted me with a cryptic message just for you: 'In the land of swirling colors, where unicorns prance and dragons snooze, a hidden treasure awaits those who dare to yawn beneath the crescent moon.' Keep this message close to your heart and let it guide you on your journey through the wondrous realms of the unknown. Farewell, and may your path be ever sprinkled with stardust! ✨"
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


def cleanup_governance_snapshots():
    snapshot_files = glob.glob(
        f"{GOVERNANCE_STACK_SNAPSHOTS_PATH}/governance_stack_snapshot_*.png"
    )
    for filename in snapshot_files:
        os.remove(filename)

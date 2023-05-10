import discord
import requests
import random
import base64
import svgwrite
import cairosvg
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from PIL import Image, ImageDraw, ImageFont
from d20_governance.constants import *
import xml.etree.ElementTree as ET
from svgwrite.extensions import Inkscape
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
        f"{API_HOST}/v1/generation/{ENGINE_ID}/text-to-image",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {STABILITY_TOKEN}"
        },
        json={
            "text_prompts": [
                {
                    "text": f"{prompt}"
                }
            ],
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
    with open('generated_image.png', 'wb') as f:
        f.write(image_data)

    return Image.open('generated_image.png')


def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    current_line = words[0]

    for word in words[1:]:
        if font.getsize(current_line + ' ' + word)[0] <= max_width:
            current_line += ' ' + word
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
    font = ImageFont.truetype(FONT_PATH, font_size)

    max_width = image.size[0] - 20
    wrapped_text = wrap_text(text, font, max_width)

    text_height = font_size + len(wrapped_text)
    image_width, image_height = image.size
    y_offset = (image_height - text_height) // 5

    for line in wrapped_text:
        text_width, _ = draw.textsize(line, font)
        position = ((image_width - text_width) // 2, y_offset)
        draw.text(position, line, (0, 0, 0), font,
                  stroke_width=2, stroke_fill=(255, 255, 255))
        y_offset += font_size

    return image


def add_svg_icon(dwg, svg_path, x, y, height=20, width=20):
    if svg_path is None:
        return

    # Convert the SVG icon to a PNG using CairoSVG
    png_data = cairosvg.svg2png(url=svg_path, output_width=width, output_height=height)

    # Encode the PNG as a base64 string
    encoded_png = base64.b64encode(png_data).decode('utf-8')

    # Add an <image> element referencing the base64-encoded PNG data
    dwg.add(dwg.image(href=f'data:image/png;base64,{encoded_png}', insert=(x, y), size=(width, height)))



def create_svg_snapshot():
    # Initialize the SVG drawing
    dwg = svgwrite.Drawing(None, profile="tiny", size=("600px", "400px"))

    # Draw the modules based on the YAML data
    module_y = 10
    for module in GOVERNANCE_STACK_MODULES:
        # Add the SVG icon for the current module
        add_svg_icon(dwg, module["icon"], 20, module_y - 10)
        
        # Draw the module name text
        dwg.add(dwg.text(module["name"], insert=("60px", f"{module_y + 5}px"), font_size="14px"))

        module_y += 30

        # Draw submodules if any
        if "modules" in module:
            sub_y = 10
            for sub_module in module["modules"]:
                # Draw the icon
                add_svg_icon(dwg, sub_module["icon"], 50, module_y + sub_y - 10)

                # Draw the submodule name text
                dwg.add(dwg.text(sub_module["name"], insert=("90px", f"{module_y + sub_y + 5}px"), font_size="14px"))

                sub_y += 30
            
            module_y += sub_y

    # Save the SVG content to a variable
    svg_content = dwg.tostring()

    # Convert the SVG content to a PNG ByteArray
    png_data = cairosvg.svg2png(bytestring=svg_content)

    # Save the ByteArray as a PNG file
    with open("output.png", "wb") as f:
        f.write(png_data)



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


async def send_msg_to_random_player():
    print("Sending random DM...")
    players = [member for member in TEMP_CHANNEL.members if not member.bot]
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

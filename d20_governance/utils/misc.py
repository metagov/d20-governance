import argparse
import discord
import os
import asyncio
import logging
import traceback
import sys
import time
import random

from colorama import Fore, Style
from typing import Union

from discord.app_commands import command as slash_command
from discord.interactions import Interaction
from discord import app_commands
from discord.ext import tasks, commands
from discord.ui import View

from d20_governance.utils.utils import *
from d20_governance.utils.constants import *
from d20_governance.utils.cultures import *
from d20_governance.utils.voting import vote, set_global_decision_module


description = """📦 A bot for experimenting with modular governance 📦"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", description=description, intents=intents)

# MISC COMMANDS AND FUNCTIONS


# TODO: it would be nice to not have this toggled when displaying the info, maybe have a different command for display diversity info
@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def diversity(ctx):
    """
    Toggle diversity module
    """
    module: Diversity = CULTURE_MODULES.get("diversity", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)

    # Display the diversity counts if global state is true
    if module.is_global_state_active():
        await module.display_info(ctx)


@bot.command(hidden=True)
async def secret_message(ctx):
    """
    Secrecy: Randomly Send Messages to DMs
    """
    print("Secret message command triggered.")
    await send_msg_to_random_player(bot.quest.game_channel)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def ritual(ctx):
    """
    Toggle ritual module.
    """
    module: Ritual = CULTURE_MODULES.get("ritual", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)


@bot.command(hidden=True)
@commands.check(lambda ctx: False)
async def vote_governance(ctx, governance_type: str):
    """
    Vote on governance module based on current or random decision module
    """
    if governance_type is None:
        await ctx.send("Invalid governance type: {governance_type}")
        return
    modules = get_modules_for_type(governance_type)
    module_names = [module["name"] for module in modules]
    question = f"Which {governance_type} should we select?"
    decision_module = await set_decision_module()
    timeout = 60
    winning_module_name = await vote(
        ctx, question, decision_module, timeout, *module_names
    )
    # TODO: if no winning_module, hold retry logic or decide what to do
    if winning_module_name:
        winning_module = modules[module_names.index(winning_module_name)]
        add_module_to_stack(winning_module)
        await ctx.send(f" New module `{winning_module_name}` added to governance stack")
        await post_governance(ctx)
    else:
        embed = discord.Embed(
            title="Error - No winning module.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    return winning_module_name


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_randomize_snapshot(ctx):
    """
    Test making a randomized governance snapshot
    """
    shuffle_modules()
    make_governance_snapshot()


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_png_creation(ctx):
    """
    Test governance stack png creation
    """
    make_governance_snapshot()
    with open("output.png", "rb") as f:
        png_file = discord.File(f, "output.svg")
        await ctx.send(file=png_file)


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_img_generation(ctx, text="Obscurity"):
    """
    Test stability image generation
    """
    image = generate_image(text)

    # Save the image to a file
    image.save("generated_image.png")

    # Post the image to the Discord channel
    await ctx.send(file=discord.File("generated_image.png"))

    # Clean up the image file
    os.remove("generated_image.png")


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_module_png_generation(ctx, module, module_dict=CULTURE_MODULES):
    """
    Test stability image generation
    """
    if module in module_dict:
        module_name = module_dict[module]["name"]
        svg_icon = module_dict[module]["icon"]
        image = make_module_png(module_name, svg_icon)
    await ctx.send(file=discord.File(image))

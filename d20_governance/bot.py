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

from discord.app_commands import command as slash_commands
from discord.interactions import Interaction
from discord import app_commands
from discord.ext import tasks, commands
from discord.ui import View

from d20_governance.utils.utils import *
from d20_governance.utils.constants import *
from d20_governance.utils.cultures import *
from d20_governance.utils.voting import (
    ACTIVE_GLOBAL_DECISION_MODULES,
    CONTINUOUS_INPUT_DECISION_MODULES,
    VoteContext,
    VoteFailedException,
    set_decision_module,
    vote_state_manager,
    vote,
    set_global_decision_module,
    decision_manager,
)
from discord import app_commands
from discord.ext import tasks, commands
from discord.ui import Button, View

description = """📦 A bot for experimenting with modular governance 📦"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True


class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.quest = Quest()

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event handler for when the bot has logged in and is ready to start interacting with Discord
        """
        with open("assets/imgs/game_icons/d20-gov-icon.png", "rb") as avatar_file:
            avatar = avatar_file.read()

        try:
            await bot.user.edit(username="D20 Governance Bot", avatar=avatar)
        except discord.errors.HTTPException as e:
            if "avatar" in str(e):
                print(
                    f"{Fore.BLACK}Changing avatar too fast, skipping this change.{Style.RESET_ALL}"
                )

        try:
            synced = await bot.tree.sync()
            print(f"{Fore.YELLOW}Synced {len(synced)} command(s).{Style.RESET_ALL}")
        except Exception as e:
            print(e)

        logging.basicConfig(
            filename="logs/bot.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        print(f"{Fore.YELLOW}>> Logging to logs/bot.log << {Style.RESET_ALL}")
        with open(f"{LOGGING_PATH}/bot.log", "a") as f:
            f.write(f"\n\n--- Bot started at {datetime.datetime.now()} ---\n\n")
        logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
        value_revision_manager.__init__()
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            await setup_server(guild)
            await delete_all_webhooks(guild)
        check_and_delete_webhooks_if_needed.start()

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Global message event listener
        """
        global VOTE_RETRY
        context = await bot.get_context(message)
        guild_id = context.guild.id if context.guild else None
        channel_id = context.channel.id if context.channel else None
        guild = context.guild
        channel = bot.get_channel(channel_id)
        try:
            if message.author == bot.user:  # Ignore messages sent by the bot itself
                return

            # Allow the "-help" command to run without channel checks
            if message.content.startswith("-help"):
                await bot.process_commands(message)
                return

            # If message is a slash command, proceed directly to processing
            if message.content.startswith("/"):
                await bot.process_commands(message)
                return

            # If message is a regular command, proceed directly to processing
            if message.content.startswith("-"):
                await bot.process_commands(message)
                return

            # This symbol ensures webhook messages don't loop
            if message.content.startswith("※"):
                return

            message_split = message.content.strip().split(" ")
            if len(message_split) >= 2:
                increment = message_split[-1]
                if increment == "+1" or increment == "-1":
                    module_name = message_split[0]
                    change = 1 if increment == "+1" else -1
                    if channel_id is not None and guild_id is not None:
                        # TODO: deduplicate and refactor this code
                        if module_name in CONTINUOUS_INPUT_DECISION_MODULES.keys():
                            if (
                                VOTE_RETRY
                            ):  # Decision modules can only be changed via continuous input during a vote retry.
                                decision_bucket = cooldowns["decisions"].get_bucket(
                                    message
                                )
                                retry_after = decision_bucket.update_rate_limit()
                                if retry_after:
                                    await context.send(
                                        f"{context.author.mention}: Decision cooldown active, try again in {retry_after:.2f} seconds"
                                    )
                                    return

                                module = CONTINUOUS_INPUT_DECISION_MODULES[module_name]
                                module.config["input_value"] += change
                                module.config["input_value"] = max(
                                    module.config["input_value"], 0
                                )
                                await display_module_status(
                                    context, CONTINUOUS_INPUT_DECISION_MODULES
                                )
                                # We do not call calculate_decision_module_inputs here as this is handled by the vote retry logic
                            return
                        elif module_name in CULTURE_MODULES.keys():
                            if channel.name == "d20-agora":
                                culture_bucket = cooldowns["cultures"].get_bucket(
                                    message
                                )
                                retry_after = culture_bucket.update_rate_limit()
                                if retry_after:
                                    await context.send(
                                        f"{context.author.mention}: Culture cooldown active, try again in {retry_after:.2f} seconds"
                                    )
                                    return

                                module = CULTURE_MODULES[module_name]
                                module.config["input_value"] += change
                                module.config["input_value"] = max(
                                    module.config["input_value"], 0
                                )
                                await display_module_status(context, CULTURE_MODULES)
                                await calculate_continuous_culture_inputs(
                                    context, guild_id, channel_id
                                )
                                return
                            else:
                                print(
                                    f"Continuous input module not found: {module_name}"
                                )
                                return

            # Process message if it was not a continuous input
            await process_message(context, message)
        except Exception as e:
            type, value, tb = sys.exc_info()
            traceback_str = "".join(traceback.format_exception(type, value, tb))
            print(f"{Fore.RED}Unhandled exception:\n{traceback_str}{Style.RESET_ALL}")
            logging.error(f"Unhandled exception:\n{traceback_str}")
            if bot.quest.game_channel:
                await bot.quest.game_channel.send("An error occured")
            else:
                await context.send("An error occurred.")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """
        Event handler for when the bot has been invited to a new guild.
        """
        print(
            f"{Fore.YELLOW}D20 Bot has been invited to server `{guild.name}`{Style.RESET_ALL}"
        )
        await setup_server(guild)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        """
        Event listener that prints command invoked, channel where invoked, and channel id
        """
        print(
            f"{Fore.BLUE}⁂ Invoked: `/{ctx.command.name}` in channel `{ctx.channel.name}`, ID: {ctx.channel.id} {Style.RESET_ALL}"
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("That command does not exist.")
        else:
            await ctx.send("An error occurred.")
        traceback_text = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        error_message = f"Error invoking command: {ctx.command.name if ctx.command else 'Command does not exist'} - {error}\n{traceback_text}"
        print(f"{Fore.RED}{error_message}{Style.RESET_ALL}")
        logging.error(error_message)

    @commands.Cog.listener()
    async def on_error(self, event):
        type, value, tb = sys.exc_info()
        traceback_str = "".join(traceback.format_exception(type, value, tb))
        print(
            f"{Fore.RED}Unhandled exception in {event}:\n{traceback_str}{Style.RESET_ALL}"
        )
        logging.error(f"Unhandled exception in {event}:\n{traceback_str}")

    @commands.Cog.listener()
    async def setup_hook(self) -> None:
        await self.add_cog(CultureModulesCog(self))


class CultureModulesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
    async def wildcard(self, ctx):
        """
        Toggle wildcard module
        """

        # get the wildcard module object
        module = CULTURE_MODULES.get("wildcard", None)
        if module is None:
            return
        if module.config["llm_disclosure"] is None:
            await ctx.send(
                "Cannot activate the **Wildcard Module** at this time. Play the **Build a Group Voice** quest by typing `/embark` in #d20-agora in order to make this module."
            )
            return

        await module.toggle_local_state_per_channel(ctx, ctx.guild.id, ctx.channel.id)

    @commands.command(hidden=True)
    @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
    async def obscurity(self, ctx, mode: str = None):
        """
        Toggle obscurity module
        """
        available_modes = ["scramble", "replace_vowels", "pig_latin", "camel_case"]
        module: CultureModule = CULTURE_MODULES.get("obscurity", None)
        if module is None:
            return

        if mode is None:
            await module.toggle_local_state_per_channel(
                ctx, ctx.guild.id, ctx.channel.id
            )

        elif mode not in available_modes:
            embed = discord.Embed(
                title=f"Error - The mode '{mode}' is not available.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
        else:
            module.config["mode"] = mode
            await module.toggle_local_state_per_channel(
                ctx, ctx.guild.id, ctx.channel.id
            )

    @commands.command(hidden=True)
    @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
    async def eloquence(self, ctx):
        """
        Toggle eloquence module
        """
        module = CULTURE_MODULES.get("eloquence", None)
        if module is None:
            return

        await module.toggle_local_state_per_channel(ctx, ctx.guild.id, ctx.channel.id)

    @commands.command(hidden=True)
    @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
    async def values(self, ctx):
        """
        Toggle values module
        """
        module = CULTURE_MODULES.get("values", None)
        if module is None:
            return

        await module.toggle_local_state_per_channel(ctx, ctx.guild.id, ctx.channel.id)

    @commands.command(hidden=True)
    @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
    async def amplify(self, ctx):
        """
        Toggle amplify module
        """
        module: Amplify = CULTURE_MODULES.get("amplify", None)
        if module is None:
            return

        await module.toggle_local_state_per_channel(ctx, ctx.guild.id, ctx.channel.id)

    @commands.command(hidden=True)
    @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
    async def ritual(self, ctx):
        """
        Toggle ritual module.
        """
        module: Ritual = CULTURE_MODULES.get("ritual", None)
        if module is None:
            return

        await module.toggle_local_state_per_channel(ctx, ctx.guild.id, ctx.channel.id)


bot = MyBot(command_prefix="/", description=description, intents=intents)
bot.remove_command("help")


def run_bot():
    bot.run(token=DISCORD_TOKEN)


@bot.tree.command(name="help", description="Help information")
async def help(interaction: discord.Interaction, command: str = None):
    prefix = "/"

    # Loop through slash commands
    slash_cmds = [c for c in bot.tree.walk_commands()]
    slash_cmds.sort(key=lambda c: c.name)
    slash_cmd_field = ""
    for cmd in slash_cmds:
        description = cmd.description
        slash_cmd_field += (
            f"**{prefix}{cmd.name}**\n{description or 'No description available.'}\n"
        )

    embed = discord.Embed(
        title="Commands and About",
        description=f"Here's a list of available commands. Use `{prefix}help <command>` for more info.\n\nTo play with the bot, visit `#d20-agora` and select any of the culture modules.\n\nYou can also `/embark` from the `#d20-agora` on a quest to form a new group identity and voice.\n",
    )

    embed.add_field(
        name="Slash Commands",
        value=slash_cmd_field,
        inline=False,
    )
    embed.add_field(
        name="Culture Modules",
        value="You can turn culture modules on and off in `#d20-agora` using a continuous input mechanism.\n\n To toggle culture modules type `<culture module> +1` or `<culture module -1>`. For example: `eloquence +1` or `amplify -1`.\n\n Available culture modules include:\n\n* Amplify\n* Obscurity\n* Ritual\n* Eloquence\n* Values\n* Wildcard",
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# QUEST FLOW
def setup_quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode):
    quest = Quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode)
    bot.quest = quest
    global QUEST_IN_PROGRESS
    QUEST_IN_PROGRESS = True
    return quest


async def start_quest(ctx, quest: Quest):
    """
    Sets up a new quest
    """
    embed = discord.Embed(
        title="Welcome",
        description="Your simulation is loading ...",
        color=discord.Color.dark_orange(),
    )

    # Send and store a message object as an initial message for the new quest game channel
    message_obj = await quest.game_channel.send(embed=embed)

    # Sleep for 3 seconds to give time for users to get to the channel and avoid possible latency issues in fetching the message_object
    await asyncio.sleep(3)

    if quest.mode == SIMULATIONS["llm_mode"]:
        llm_agent = get_llm_agent()
        num_stages = random.randint(5, 10)  # Adjust range as needed
        for _ in range(num_stages):
            print(f"{Fore.BLUE}Generating stage with llm..{Style.RESET_ALL}")
            stage = await generate_stage_llm(llm_agent)
            await process_stage(ctx, stage, quest)

    else:  # yaml mode
        for stage in quest.stages:
            # reset progress_completed to False at start of each stage
            await asyncio.sleep(0.5)
            quest.progress_completed = False
            actions = [
                Action.from_dict(action_dict)
                for action_dict in stage[QUEST_ACTIONS_KEY]
            ]
            progress_conditions = [
                Progress_Condition.from_dict(progress_condition_dict)
                for progress_condition_dict in stage[QUEST_PROGRESS_CONDITIONS_KEY]
            ]
            stage = Stage(
                name=stage[QUEST_NAME_KEY],
                message=stage[QUEST_MESSAGE_KEY],
                actions=actions,
                progress_conditions=progress_conditions,
                image_path=stage.get(QUEST_IMAGE_PATH_KEY),
            )

            print(f"{Fore.BLUE}↷ Processing stage: '{stage.name}'{Style.RESET_ALL}")

            await process_stage(ctx, stage, quest, message_obj)


# class VoteTimeoutView(View):
#     def __init__(self, countdown_timeout):
#         super().__init__(timeout=10.0)
#         self.wait_finished = asyncio.Event()
#         self.countdown_timeout = countdown_timeout

#     @discord.ui.button(
#         label="Extend Vote", style=discord.ButtonStyle.green, custom_id="extend_vote"
#     )
#     async def extend_vote_button(
#         self, interaction: discord.Interaction, button: discord.ui.Button
#     ):
#         # Extend vote duration by 60 seconds
#         self.timeout += 60
#         await interaction.response.send_message("Vote duration extended by 60 seconds.")

#     @discord.ui.button(
#         label="Extend Vote", style=discord.ButtonStyle.green, custom_id="extend_vote"
#     )
#     async def extend_vote_button(
#         self, interaction: discord.Interaction, button: discord.ui.Button
#     ):
#         # Extend vote duration by 60 seconds
#         self.timeout += 60
#         await interaction.response.send_message("Vote duration extended by 60 seconds.")


async def process_decision_retry(ctx, retry_message):
    await clear_decision_input_values(ctx)
    await ctx.send(retry_message)
    await ctx.send(
        "```💡--Do Not Dispair!--💡\n\nYou have a chance to change how you make decisions```"
    )
    await display_module_status(ctx, CONTINUOUS_INPUT_DECISION_MODULES)
    await ctx.send(
        f"```👀--Instructions--👀\n\n* Post a message with the decision type you want to use\n\n* For example, type: consensus +1\n\n* You can express your preference multiple times and use +1 or -1 after the decision type\n\n* The decision module with the most votes in 60 seconds, or the first to {INPUT_SPECTRUM['threshold']}, will be the new decision making module during the next decision retry.\n\n* You have 60 seconds before the next decision is retried. ⏳```"
    )

    """
    For 60 seconds, tally continuous votes; if threshold is reached for any module, it will be set as decision module, 
    otherwise status quo will remain  
    """
    for _ in range(60):
        reached_threshold = await calculate_continuous_decision_inputs(ctx)
        if reached_threshold:
            return
        await asyncio.sleep(1)

    await ctx.send("No winner was found. The status quo will remain.")


async def process_stage(ctx, stage: Stage, quest: Quest, message_obj: discord.Message):
    """
    Run stages from yaml config
    """
    game_channel_ctx = await get_channel_context(bot, quest.game_channel, message_obj)

    if game_channel_ctx.channel in ARCHIVED_CHANNELS:
        return

    if quest.gen_audio:
        loop = asyncio.get_event_loop()
        audio_filename = f"{AUDIO_MESSAGES_PATH}/{stage.name}.mp3"
        future = loop.run_in_executor(None, tts, stage.message, audio_filename)
        await future

    if quest.gen_images:
        # Check if stage has an non-empty image_path
        if hasattr(stage, "image_path") and stage.image_path != "None":
            image = Image.open(stage.image_path)  # Open the image
            image.save("generated_image.png")  # Save the image to a file
        # If no image, pass
        elif hasattr(stage, "image_path") and stage.image_path == "None":
            pass
        else:
            # Generate intro image and send to temporary channel
            image = generate_image(stage.message)
            image.save("generated_image.png")  # Save the image to a file

    # Post the image to the Discord channel
    if os.path.exists("generated_image.png"):
        await game_channel_ctx.send(file=discord.File("generated_image.png"))
        os.remove("generated_image.png")

    if quest.gen_audio:
        # Post audio file
        with open(audio_filename, "rb") as f:
            audio = discord.File(f)
            await game_channel_ctx.send(file=audio)
        os.remove(audio_filename)

    embed = discord.Embed(
        title=stage.name,
        description=stage.message,
        color=discord.Color.dark_orange(),
    )

    # Stream message
    if quest.fast_mode:
        # embed
        await game_channel_ctx.send(embed=embed)
    else:
        await stream_message(quest.game_channel, stage.message, embed)

    # store most recent message in reminder class
    reminder_manager.current_stage_message = stage.message

    # Call actions and poll for progress conditions simultaneously
    actions = stage.actions
    progress_conditions = stage.progress_conditions

    async def action_runner():
        for action in actions:
            command_name = action.action
            print(f"{Fore.BLUE}↷ Processing action: '{command_name}'{Style.RESET_ALL}")
            if command_name is None:
                raise Exception(f"Command {command_name} not found.")
            args = action.arguments
            command = globals().get(command_name)
            retries = action.retries if hasattr(action, "retries") else 0
            if bot.quest.progress_completed == True:
                print(
                    f"{Fore.BLUE}■ Progress condition met. Ending action_runner{Style.RESET_ALL}"
                )
                break
            while retries >= 0:
                try:
                    await execute_action(game_channel_ctx, command, args)
                    break
                except VoteFailedException as ve:
                    print(f"{Fore.RED}Vote failed: {ve} Retrying...{Style.RESET_ALL}")
                    if retries > 0:
                        # TODO: avoid the global
                        global VOTE_RETRY
                        VOTE_RETRY = True
                        # view = TimeoutView(countdown_timeout=60)
                        # await ctx.send("Do you need more time?", view=view)
                        # await view.wait()
                        print(f"Number of retries remaining: {retries}")
                        if hasattr(action, "retry_message") and action.retry_message:
                            await process_decision_retry(
                                game_channel_ctx, action.retry_message
                            )
                        retries -= 1
                    else:
                        if (
                            hasattr(action, "failure_message")
                            and action.failure_message
                        ):
                            options = list(bot.quest.players_to_submissions.values())

                            winning_option = random.choice(options)

                            embed = discord.Embed(
                                title=f"Results for: `{vote_state_manager.question}`:",
                                description=f"In absence of collective decision making, the bot as autocratically selected a random result. Result: {winning_option}",
                                color=discord.Color.dark_gold(),
                            )

                            bot.quest.reset_submissions()

                            decision_data = {
                                "decision": winning_option,
                                "decision_module": "implicit_feudalism",
                            }
                            DECISION_DICT[vote_state_manager.question] = decision_data
                            await game_channel_ctx.send(embed=embed)
                            break
                except Exception as e:
                    # For all other errors, log the error and continue to the next action
                    print(
                        f"Unexpected error encountered: {e}, continuing to next action."
                    )
                    logging.error(
                        f"Unexpected error encountered: {e}, continuing to next action."
                    )
                    break

    async def progress_checker():
        if progress_conditions is None or len(progress_conditions) == 0:
            return
        while True:
            if bot.quest.progress_completed:
                print("At least one progress condition met")
                break
            tasks = []
            for progress_condition in progress_conditions:
                function_name = progress_condition.progress_condition
                if function_name is None:
                    raise Exception(f"Function {function_name} not found.")
                function = globals().get(function_name)
                args = progress_condition.arguments
                tasks.append(
                    asyncio.create_task(function(game_channel_ctx, *args))
                )  # Modified line
                print(
                    f"{Fore.BLUE}+ `{function_name}` in channel `{game_channel_ctx.channel}` with arguments {args} added to task list{Style.RESET_ALL}"
                )  # Debugging line

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            for future in done:
                condition_result = await future
                if condition_result:
                    for task in pending:
                        task.cancel()  # Ensures all pending progress conditions are cancelled to avoid impacting future stages
                    return True
            await asyncio.sleep(1)  # sleep before checking

    # Run simultaneously and wait for both the action_runner and progress_checker to complete
    # If at least one of the progress conditions is met and all of the actions have completed, then the stage is complete
    await asyncio.gather(action_runner(), progress_checker())


async def countdown(
    ctx_interaction: Union[discord.ext.commands.Context, discord.Interaction],
    timeout_seconds=None,
    text: str = None,
):
    """
    Send an updating countdown display
    """
    if isinstance(ctx_interaction, discord.ext.commands.Context):
        channel = ctx_interaction.channel
    elif isinstance(ctx_interaction, discord.Interaction):
        channel = ctx_interaction.channel
    else:
        raise ValueError("Either ctx or interaction must be provided.")

    if hasattr(bot, "quest") and bot.quest.fast_mode:
        timeout_seconds = 10

    # TODO: make this better
    remaining_seconds = int(timeout_seconds)
    remaining_minutes = remaining_seconds / 60

    # Set new message interval
    message_interval_seconds = 60
    next_message_time = time.time() + message_interval_seconds

    first_message = (
        f"```⏳ Counting Down: {remaining_minutes:.2f} minutes remaining {text}```"
    )
    message = await channel.send(first_message)

    @tasks.loop(seconds=15)
    async def update_countdown():
        nonlocal remaining_seconds, remaining_minutes
        remaining_minutes = remaining_seconds / 60
        new_message = (
            f"```⏳ Counting Down: {remaining_minutes:.2f} minutes remaining {text}.```"
        )
        await message.edit(content=new_message)
        if remaining_minutes <= 0:
            new_message = f"```⏲️ Counting down finished.```"
            await channel.send(new_message)
            print(f"{Fore.BLUE}⧗ Countdown finished.{Style.RESET_ALL}")
            update_countdown.stop()

        # Check if all submissions have been submitted
        if bot.quest.progress_completed:
            await message.edit(
                content="```⏲️ All submissions submitted. Countdown finished.```"
            )
            update_countdown.stop()

    @tasks.loop(minutes=1)
    async def send_new_message():
        nonlocal remaining_seconds, remaining_minutes, message
        remaining_minutes = remaining_seconds / 60
        if remaining_minutes <= 0:
            await message.edit(content="```⏲️ Counting down finished.```")
            print(f"{Fore.BLUE}⧗ Countdown finished.{Style.RESET_ALL}")
            send_new_message.stop()
        if remaining_minutes <= remaining_minutes - 1:
            new_message = f"```⏳ Counting Down: {remaining_minutes:.2f} minutes remaining {text}.```"
            message = await channel.send(new_message)
            if bot.quest.progress_completed:
                await message.edit(
                    content="```⏲️ All submissions submitted. Countdown finished.```"
                )
                send_new_message.stop()

    update_countdown.start()
    send_new_message.start()

    try:
        while send_new_message.is_running() and update_countdown.is_running():
            remaining_seconds -= 1
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        update_countdown.stop()
        send_new_message.stop()
        print(f"{Fore.BLUE}⧗ Countdown cancelled.{Style.RESET_ALL}")


async def all_submissions_submitted(ctx):
    """
    Check that all submissions are submited
    """
    # TODO: can we avoid the progress_completed check
    while True:
        if bot.quest.progress_completed == True:
            break
        joined_players = bot.quest.joined_players
        players_to_submissions = bot.quest.players_to_submissions
        if len(joined_players) == len(players_to_submissions):
            await ctx.send(
                "```Everyone has made their submission. The next stage will start in 5 seconds```"
            )
            print(f"{Fore.BLUE}✓ All submissions submitted.{Style.RESET_ALL}")
            bot.quest.progress_completed = True
            await asyncio.sleep(5)
            return True
        print("⧗ Waiting for all submissions to be submitted")
        await asyncio.sleep(1)  # Wait for a second before checking again


# TODO: merge wait and progress_timeout
async def wait(ctx, seconds: str):
    """
    Simulation waits

    Used by in simulation yaml to add pauses in the simulations and check progress conditions
    """
    if bot.quest.fast_mode:
        seconds = 2
        print(f"{Fore.BLUE}◫ Pausing for {seconds} seconds...{Style.RESET_ALL}")
        await asyncio.sleep(int(seconds))
    else:
        print(f"{Fore.BLUE}◫ Pausing for {seconds} seconds...{Style.RESET_ALL}")
        await asyncio.sleep(int(seconds))
    return True


async def progress_timeout(ctx, seconds: str):
    """
    Progression timeout

    Used in simulation yamls to define limits for progression checks
    """
    if bot.quest.fast_mode:
        seconds = 7
        print(f"Progression timeout in {seconds} seconds...")
        await asyncio.sleep(int(seconds))
    else:
        print(f"Progression timeout in {seconds} seconds...")
        await asyncio.sleep(int(seconds))
    print(f"{Fore.BLUE}⧗ Progression timeout reached.{Style.RESET_ALL}")
    bot.quest.progress_completed = True
    return True


@bot.tree.command(
    name="remind_me", description="Send most recent stage message (used in quest)"
)
async def remind_me(interaction: discord.Interaction):
    await interaction.response.send_message(
        reminder_manager.current_stage_message, ephemeral=True
    )


async def end(ctx):
    """
    Archive the quest and channel
    """
    # Check if values_check_task is running and if so cancel process
    global values_check_task
    if values_check_task is not None and not values_check_task.done():
        values_check_task.cancel()
        print("value check loop canceled")
    global QUEST_IN_PROGRESS
    QUEST_IN_PROGRESS = False
    print(f"{Fore.BLUE}⇓ Archiving...{Style.RESET_ALL}")
    # Archive temporary channel
    archive_category = discord.utils.get(ctx.guild.categories, name="d20-archive")

    await ctx.send("```👋👋👋\n\nThe simulation is over. This channel is now archived.```")
    await ctx.channel.edit(category=archive_category)

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(
            read_messages=True, send_messages=False
        ),
        ctx.guild.me: discord.PermissionOverwrite(
            read_messages=True, send_messages=False
        ),
    }
    await ctx.channel.edit(overwrites=overwrites)

    ARCHIVED_CHANNELS.append(ctx.channel)

    print(f"{Fore.BLUE}⇓ Archived...{Style.RESET_ALL}")

    guild_id = ctx.guild.id
    guild = bot.get_guild(guild_id)
    await delete_all_webhooks(guild)


# VIEWS


class QuestBuilder(discord.ui.Select):
    def __init__(self, placeholder, options):
        super().__init__(
            placeholder=placeholder,
            options=options,
            max_values=1,
            min_values=1,
        )
        self.selected_value = None

    async def callback(self, interaction: discord.Interaction):
        self.selected_value = self.values[0]
        await interaction.response.defer()
        if all(
            dropdown.selected_value is not None
            for dropdown in [self.view.select1, self.view.select2, self.view.select3]
        ):
            self.view.enable_button()  # FIXME: Doesn't trigger function


class JoinLeaveView(discord.ui.View):
    def __init__(
        self,
        ctx: commands.Context,
        quest: Quest,
        num_players,
    ):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.num_players = num_players
        self.quest = quest
        self.lock = asyncio.Lock()

    async def update_embed(self, interaction):
        needed_players = self.num_players - len(self.quest.joined_players)
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            0,
            name="**Current Players:**",
            value=", ".join(self.quest.joined_players),
            inline=False,
        )
        embed.set_field_at(
            1,
            name="**Players needed to start:**",
            value=str(needed_players),
            inline=False,
        )

        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(
        style=discord.ButtonStyle.green, label="Join", custom_id="join_button"
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        quest = self.quest
        player_name = interaction.user.name

        async with self.lock:  # ensure that the player count gets updated synchronously, else we may end up creating multiple channels
            if player_name not in quest.joined_players:
                quest.add_player(player_name)
                await interaction.response.send_message(
                    f"{player_name} has joined the quest!"
                )
                await self.update_embed(interaction)
                if len(quest.joined_players) == self.num_players:
                    # delete the current message
                    await interaction.message.delete()

                    # create channel for game
                    await make_game_channel(self.ctx, quest)
                    embed = discord.Embed(
                        title=f"{self.ctx.author.display_name}'s proposal to play has enough players, and is ready to play",
                        description=f"**Quest:** {quest.game_channel.mention}\n\n**Players:** {', '.join(quest.joined_players)}",
                    )
                    # post updated message
                    await interaction.channel.send(embed=embed)
                    await start_quest(self.ctx, self.quest)
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
        quest = self.quest
        player_name = interaction.user.name
        if player_name in quest.joined_players:
            # if players is in the list of joined players remove them from the list
            quest.joined_players.remove(player_name)
            await interaction.response.send_message(
                f"{player_name} has abandoned the quest before it even began!"
            )
            await self.update_embed(interaction)

        else:
            await interaction.response.send_message(
                "You can only leave a quest if you have already joined",
                ephemeral=True,
            )


class SelectValue(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Select a value to revise",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        value_revision_manager.selected_value = self.values[0]
        await interaction.response.send_modal(NewValueModal())


class NewValueModal(discord.ui.Modal, title="Propose new value"):
    proposed_value_name = discord.ui.TextInput(
        label="Propose a new value name",
        style=discord.TextStyle.short,
        placeholder="Proposed value name",
        required=True,
        max_length=20,
    )
    proposed_value_definition = discord.ui.TextInput(
        label="Propose a new value definition",
        style=discord.TextStyle.long,
        placeholder="Proposed value definition",
        required=True,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await value_revision_manager.store_proposal(
            self.proposed_value_name, self.proposed_value_definition
        )

        await interaction.response.send_message(
            f"```{interaction.user.name} proposed a new value:\n\nValue Name: {self.proposed_value_name}\nValue Description: {self.proposed_value_definition}```"
        )

        await asyncio.sleep(2)
        print(f"proposed value: ")

        # Create a dictionary with only the proposed name and value
        current_proposal = {
            self.proposed_value_name.value: self.proposed_value_definition.value
        }

        member_count = (
            len(interaction.channel.members) - 1
        )  # subtract one to account for bot
        question = f"Should we change the value *{value_revision_manager.selected_value}* to the newly proposed value: *{self.proposed_value_name}*?"
        vote_context = VoteContext.create(
            interaction.channel.send,
            member_count,
            question=question,
            options=current_proposal,
            timeout=30,
            decision_module_name="lazy_consensus",
        )

        vote_result = await vote(vote_context)

        # Check if the proposed value was accepted (i.e., not objected to)
        if self.proposed_value_name.value in vote_result:
            await value_revision_manager.update_values_dict(
                value_revision_manager.selected_value, vote_result
            )

        await value_revision_manager.clear_proposed_values()


class ValueRevisionView(discord.ui.View):
    def __init__(self):
        super().__init__()

    def assign_values(self, values_dict):
        options = [
            discord.SelectOption(label=name, description=value[:60], value=name)
            for name, value in values_dict.items()
        ]

        self.add_item(SelectValue(options))


# QUEST START AND PROGRESSION
@bot.tree.command(
    name="embark", description="Propose a quest to embark on (used in #d20-agora)"
)
# @commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
@app_commands.choices(
    quest_mode=[
        app_commands.Choice(
            name=f"{SIMULATIONS['build_a_community']['emoji']} - {SIMULATIONS['build_a_community']['name']}: {SIMULATIONS['build_a_community']['description']}",
            value=SIMULATIONS["build_a_community"]["file"],
        )
    ]
)
@app_commands.choices(
    number_of_players=[
        app_commands.Choice(name="2", value=2),
        app_commands.Choice(name="3", value=3),
        app_commands.Choice(name="4", value=4),
        app_commands.Choice(name="5", value=5),
        app_commands.Choice(name="6", value=6),
        app_commands.Choice(name="7", value=7),
        app_commands.Choice(name="8", value=8),
    ]
)
@app_commands.choices(
    generate_images=[
        app_commands.Choice(name="🖼️ Yes", value="True"),
        app_commands.Choice(name="🔲 No", value="False"),
    ]
)
async def embark(
    interaction: discord.Interaction,
    quest_mode: app_commands.Choice[str],
    number_of_players: app_commands.Choice[int],
    generate_images: app_commands.Choice[str],
):
    """
    Embark on a d20 governance quest
    """
    # Get ctx
    ctx = await bot.get_context(interaction)

    # Make Quest Builder view and return values from selections
    print(f"{Fore.BLUE}Waiting for proposal to be built...{Style.RESET_ALL}")

    if not 1 <= number_of_players.value <= 8:
        await ctx.send("The game requires at least 2 and at most 8 players")
        return

    if QUEST_IN_PROGRESS:
        await ctx.send("There is already a quest in progress.")
        return

    # Quest setup
    quest = setup_quest(
        quest_mode.value,
        generate_images.value,
        gen_audio=None,
        fast_mode=None,
        solo_mode=False,
    )

    # Create Join View
    join_leave_view = JoinLeaveView(ctx, quest, number_of_players.value)
    embed = discord.Embed(
        title=f"{ctx.author.display_name} has proposed a game for {number_of_players.value} players: Join or Leave"
    )
    embed.add_field(name="**Current Players:**", value="", inline=False)
    embed.add_field(
        name="**Players needed to start:**",
        value=str(number_of_players.value),
        inline=False,
    )

    await ctx.send(embed=embed, view=join_leave_view)
    print(f"{Fore.BLUE}Waiting for players to join...{Style.RESET_ALL}")


async def make_game_channel(ctx, quest: Quest):
    """
    Game State: Setup the config and create unique quest channel
    """
    print(f"{Fore.BLUE}Making temporary game channel...{Style.RESET_ALL}")

    # Set permissions for bot
    bot_permissions = discord.PermissionOverwrite(
        read_messages=True,
        use_application_commands=True,
    )

    # Create a dictionary containing overwrites for each player that joined,
    # giving them read_messages access to the temp channel and preventing message_delete
    player_overwrites = {
        ctx.guild.get_member_named(player): discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            create_private_threads=False,
            create_public_threads=False,
            send_messages_in_threads=False,
            use_application_commands=True,
            send_voice_messages=False,
            mention_everyone=False,
            manage_nicknames=False,
            manage_messages=False,
            add_reactions=True,
        )
        for player in quest.joined_players
    }

    # Create a temporary channel in the d20-quests category
    overwrites = {
        # Default user cannot view channel
        ctx.guild.default_role: discord.PermissionOverwrite(
            read_messages=False, use_application_commands=True
        ),
        # Users that joined can view channel
        ctx.guild.me: bot_permissions,
        # Merge player_overwrites with the main overwrites dictionary
        **player_overwrites,
    }
    quests_category = discord.utils.get(ctx.guild.categories, name="d20-quests")

    # create and name the channel with the quest_name from the yaml file
    # and add a number to distinguish channels
    quest.game_channel = await quests_category.create_text_channel(
        name=f"d20-{quest.title}-{len(quests_category.channels) + 1}",
        overwrites=overwrites,
    )


@bot.command()
async def rename_channel(ctx):
    """
    Rename the quest channel
    """
    print(f"{Fore.BLUE}Renaming temporary game channel...{Style.RESET_ALL}")

    current_channel = ctx.channel
    print(current_channel)

    new_channel_name = f"d20-{decision_manager.decision_one}-voice"

    bot.quest.game_channel = await current_channel.edit(name=new_channel_name)

    await ctx.send(f"```This channel has been renamed to #{new_channel_name}```")


# CULTURE MODULES
# Community generated wildcard culture module
@bot.command(hidden=True)
async def construct_and_post_prompt(ctx):
    # assign prompt, affiliation, and purpose to the prompts dictionary
    prompt = f"You are from {prompt_object.decision_one}. Please rewrite the following input ina way that makes the speaker sound {prompt_object.decision_three} while maintaining the original meaning and intent. Incorporate the theme of {prompt_object.decision_two}. Don't complete any sentences, just rewrite them."

    # assign the prompt to the wildcard culture module config
    module = CULTURE_MODULES.get("wildcard", None)
    module.config["llm_disclosure"] = prompt

    # send a message detailing the name of the prompt,
    # the community that defined it,
    # the community's purpose,
    # and the values they had when they made the prompt
    confirmation_message = "A new group prompt has been constructed"
    await ctx.send(f"```{confirmation_message}: {prompt}```")


@bot.command(hidden=True)
async def turn_on_random_culture_module(ctx):
    """
    Randomly select a culture module to turn on
    """
    culture_commands = ["eloquence", "obscurity", "amplify"]
    random_command_name = random.choice(culture_commands)
    logging.info(f"Selected random culture module: {random_command_name}")

    random_culture_module_manager.random_culture_module = random_command_name
    random_command = bot.get_command(random_command_name)

    if random_command:
        try:
            # Execute command
            await random_command.invoke(ctx)
        except Exception as e:
            error_msg = f"Failed to execute command {random_command_name}: {e}"
            print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
            logging.error(error_msg)
    else:
        error_msg = f"Command {random_command_name} not found."
        print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        logging.error(error_msg)


@bot.command(hidden=True)
async def turn_off_random_culture_module(ctx):
    random_command_name = random_culture_module_manager.random_culture_module
    random_command = bot.get_command(random_command_name)

    if random_command:
        try:
            # Execute command
            await random_command.invoke(ctx)
            random_culture_module_manager.random_culture_module = ""
        except Exception as e:
            error_msg = f"Failed to execute command {random_command_name}: {e}"
            print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
            logging.error(error_msg)
    else:
        error_msg = f"Command {random_command_name} not found."
        print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        logging.error(error_msg)


# PROGRESSION COMMANDS
class TimeoutView(View):
    def __init__(self, countdown_timeout):
        super().__init__(timeout=10.0)
        self.wait_finished = asyncio.Event()
        self.countdown_timeout = countdown_timeout

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="yes")
    async def yes_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # await interaction.response.defer()
        await interaction.response.send_message(
            "Someone has answered yes. Starting the countdown."
        )
        countdown_task = asyncio.create_task(
            countdown(
                interaction,
                timeout_seconds=self.countdown_timeout,
                text="until the next stage.",
            )
        )
        countdown_task.add_done_callback(lambda _: self.wait_finished.set())

    @discord.ui.button(
        label="I don't need more time.",
        style=discord.ButtonStyle.gray,
        custom_id="no",
    )
    async def no_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # await interaction.response.defer()
        await interaction.response.send_message("Noted", ephemeral=True)
        return

    def set_message(self, message):
        self.message = message

    async def on_timeout(self):
        # Disable the button after the timeout
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        # Update the message to reflect the change
        await self.message.edit(view=self)
        self.wait_finished.set()

    async def wait(self):
        await self.wait_finished.wait()
        self.wait_finished.clear()


@bot.command(hidden=True)
async def ask_to_proceed(ctx, countdown_timeout: int = None):
    view = TimeoutView(countdown_timeout=countdown_timeout)
    message = await ctx.send("Do you need more time?", view=view)
    view.set_message(message)
    await view.wait()


# META GAME COMMANDS
@bot.command(hidden=True)
async def list_decisions(ctx):
    """
    Show a list of decisions made
    """
    title = "A record of our decisions:"
    value = ""
    for question, decision_data in DECISION_DICT.items():
        decision = decision_data["decision"]
        decision_module = decision_data["decision_module"]

        value += f"🤔 **Question:** {question}\n✅ **Decision:** {decision}\n🎯 **Decision method:** {decision_module}\n\n"

    embed = discord.Embed(
        title=title, description=value, color=discord.Color.dark_gold()
    )

    # If the decision dictionary is not empty show decision list
    if len(DECISION_DICT) > 0:
        await ctx.send(embed=embed)
    else:
        await ctx.send("No decisions have been made yet.")


@bot.command(hidden=True)
async def nickname(ctx):
    """
    Display nickname
    """
    player_name = ctx.author.name
    nickname = bot.quest.players_to_nicknames.get(player_name)
    if nickname is not None:
        # Make a link back to the original context
        original_context_link = discord.utils.escape_markdown(ctx.channel.mention)
        await ctx.author.send(
            f"Your nickname is {nickname}. Return to the game: {original_context_link}"
        )
    else:
        await ctx.author.send("You haven't been assigned a nickname yet")


@bot.command(hidden=True)
@access_control()
async def stack(ctx):
    """
    Post governance stack
    """
    await post_governance(ctx)


@bot.command(hidden=True)
async def quit(ctx):
    """
    Individually quit the quest
    """
    print(f"{Fore.BLUE}Quiting...{Style.RESET_ALL}")
    await ctx.send(f"{ctx.author.name} has quit the game!")
    # TODO: Implement the logic for quitting the game and ending it for the user


# TODO: combine dissolve and end into one command
@bot.command(hidden=True)
async def dissolve(ctx):
    """
    Trigger end of game
    """
    print(f"{Fore.BLUE}Ending game...{Style.RESET_ALL}")
    await end(ctx)
    print(f"{Fore.BLUE}Game ended.{Style.RESET_ALL}")


@bot.command(hidden=True)
@commands.check(lambda ctx: False)
async def post_governance_gif(ctx):
    """
    Call generate_governance_stack_gif() to create a GIF from the saved snapshots
    """
    global FILE_COUNT
    generate_governance_journey_gif()
    await ctx.send("Here is a gif of your governance journey:")

    # Open the generated GIF and send it to Discord
    with open("governance_journey.gif", "rb") as f:
        gif_file = discord.File(f, "governance_journey.gif")
        await ctx.send(file=gif_file)
        os.remove("governance_journey.gif")

    FILE_COUNT = 0


# META CONDITION COMMANDS
@bot.command(hidden=True)
async def update_bot_icon(ctx):
    # Update the bot profile picture
    with open(BOT_ICON, "rb") as image_file:
        image_bytes = image_file.read()

    await bot.user.edit(avatar=image_bytes)


# TODO: reconcile the two quiet mode commands
@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def quiet(ctx, mode: string = None):
    """
    Enforce quiet mode; prevent posting
    """
    global IS_QUIET
    if mode == None:
        pass
    if mode == "True":
        IS_QUIET = True
        await ctx.send("```Quiet mode is on```")
        print(f"{Fore.GREEN}Quiet mode is on.{Style.RESET_ALL}")
    if mode == "False":
        IS_QUIET = False
        await ctx.send("```Quiet mode is off```")
        print(f"{Fore.GREEN}Quiet mode is off.{Style.RESET_ALL}")


# MISC COMMANDS
@bot.command(hidden=True)
async def setcool(ctx, duration=0):
    """
    Set global cooloff duration
    """
    timeouts["cooldown"] = duration

    # Update cooldowns for the new timeout value
    cooldowns["decisions"] = commands.CooldownMapping.from_cooldown(
        1, timeouts["cooldown"], commands.BucketType.user
    )
    cooldowns["cultures"] = commands.CooldownMapping.from_cooldown(
        1, timeouts["cooldown"], commands.BucketType.user
    )

    await ctx.send(f"Global cooloff duration set to {timeouts['cooldown']}")


@bot.tree.command(name="submit", description="Make a submission (used in quest).")
async def submit(interaction: discord.Interaction, submission: str):
    """
    Submit a message

    To submit a message, type `/submit` followed by a space and your message.

    For example: `/submit this is my submission`

    See also `/help resubmit` for information on how to change your submission
    """
    confirmation_message = "has made their submission!"
    await submit_message(interaction, submission, confirmation_message)


@bot.tree.command(
    name="resubmit", description="Change your submission (used in quest)."
)
async def resubmit(interaction: discord.Interaction, submission: str):
    """
    Resubmit/revise a message

    To resubmit a message, type /resubmit followed by a space and your message.

    For example: /resubmit this is my revised submission
    """
    confirmation_message = "has revised their submission!"
    await submit_message(interaction, submission, confirmation_message)


async def submit_message(
    interaction: discord.Interaction,
    value_one: str,
    confirmation_message,
):
    if hasattr(bot, "quest"):
        bot.quest.add_submission(interaction, value_one)
        if bot.quest.mode != SIMULATIONS["josh_game"]:
            await interaction.response.send_message(
                f"🎉  {interaction.user.name} {confirmation_message} 📮"
            )
            return
        else:
            nickname = bot.quest.get_nickname(interaction.user.name)
            await interaction.response.send_message(
                f"🎉  {nickname} {confirmation_message} 📮"
            )
    else:
        await interaction.response.send_message(
            "Messages can only be submitted during simulations. Start a simulation by trying `/embark`."
        )


@bot.command(hidden=True)
# @commands.check(lambda ctx: False)
async def post_submissions(ctx):
    """
    Post submissions from /submit
    """
    submissions = []
    players_to_submissions = bot.quest.players_to_submissions
    title = "List of submitted proposals:"

    # Go through all nicknames and their submissions
    for player_name, submission in players_to_submissions.items():
        # Append a string formatted with the nickname and their submission
        submissions.append(f"🙋 **{player_name}**:\n📜  {submission}")

    # Join all submissions together with a newline in between each one
    formatted_submissions = "\n\n\n".join(submissions)

    embed = discord.Embed(
        title=title, description=formatted_submissions, color=discord.Color.dark_teal()
    )

    # Send the formatted submissions to the context
    await ctx.send(embed=embed)


@bot.command(hidden=True)
async def post_proposal_values(ctx):
    message = "Proposed values:\n"
    for key, value in value_revision_manager.proposed_values_dict.items():
        # Format the key as bold and add the value
        message += f"```**{key}**: {value}\n```"
    await ctx.send(message)


@bot.tree.command(
    name="propose_value_revision",
    description="Press enter to select and propose a revision to the values list (used in #d20-agora)",
)
async def propose_value_revision(interaction: discord.Interaction):
    view = ValueRevisionView()
    view.assign_values(value_revision_manager.agora_values_dict)

    await interaction.response.send_message(
        f"Here are the current values:",
        view=view,
        ephemeral=True,
    )


@bot.command(hidden=True)
# @commands.check(lambda ctx: False)
async def trigger_vote(
    ctx, question: str, timeout="20", type: str = None, topic: str = None
):
    """
    Call vote on values, submissions, etc
    """
    vote_state_manager.question = question
    quest = bot.quest
    member_count = len(ctx.channel.members) - 1  # subtract one to account for bot
    vote_context = VoteContext.create(
        ctx.send,
        member_count,
        ctx=ctx,
        question=question,
        timeout=int(timeout),
        topic=topic,
        quest=quest,
    )
    if type == "values":
        options = list(value_revision_manager.proposed_values_dict.values())
        vote_context.decision_module_name = "lazy_consensus"
        vote_context.options = options
        non_objection_options = await vote(vote_context=vote_context)
        value_revision_manager.agora_values_dict.update(non_objection_options)
    if type == "submissions":
        # Get all keys (player_names) from the players_to_submissions dictionary and convert it to a list
        options = list(bot.quest.players_to_submissions.values())
        vote_context.decision_module_name = "random"  # choose decision module randomly
        vote_context.options = options
        await vote(vote_context=vote_context)
        # Reset the players_to_submissions dictionary for the next round
        bot.quest.reset_submissions()


async def prompt_user(interaction: discord.Interaction, prompt_message: str) -> str:
    await interaction.channel.send(prompt_message, ephemeral=True)
    try:
        message_interaction = await bot.wait_for(
            "message", check=lambda m: m.author.id == interaction.user.id, timeout=60
        )
        return message_interaction.content
    except asyncio.TimeoutError:
        return None


# STREAM OF DELIBERATION QUESTIONS
@bot.command(hidden=True)
async def send_deliberation_questions(ctx, questions):
    # Check if the bot is in fast mode
    if hasattr(bot, "quest") and bot.quest.fast_mode:
        timeout_seconds = 15
        await asyncio.sleep(timeout_seconds)
        return

    # Make a copy of the deliberation questions list
    copy_of_deliberation_questions = deliberation_questions.copy()

    if questions == "deliberation_questions":
        questions = deliberation_questions

    # Reset the list if there are no more deliberation questions left
    if len(questions) == 0:
        questions = copy_of_deliberation_questions

    random_index = random.randint(0, len(questions) - 1)
    random_question = questions.pop(random_index)

    embed = discord.Embed(title="A Deliberation Question:", description=random_question)
    await ctx.channel.send(embed=embed)


# CLEANING COMMANDS
@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def clean(ctx):
    """
    Clean temporary files (called on bot shutdown, but sometimes useful to have while running)
    """
    clean_temp_files()


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def clean_category_channels(ctx, category_name="d20-quests"):
    """
    Clean category channels
    """
    guild = ctx.guild
    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        await ctx.send(f'Category "{category_name}" was not found.')
        return

    for channel in category.channels:
        await channel.delete()

    await ctx.send(f'All channels in category "{category_name}" have been deleted.')


# TEST COMMANDS
@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def solo(ctx, *args, quest_mode=SIMULATIONS["build_a_community"]["file"]):
    """
    Solo quest
    """

    global QUEST_MODE
    QUEST_MODE = quest_mode

    # Parse argument flags
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--audio", action="store_true", help="Generate TTS audio")
    parser.add_argument("-f", "--fast", action="store_true", help="Turn on fast mode")
    parser.add_argument(
        "-i", "--image", action="store_true", help="Turn on image generation"
    )
    args = parser.parse_args(args)
    gen_audio = args.audio
    fast_mode = args.fast
    gen_images = args.image

    # Set up quest
    if QUEST_IN_PROGRESS:
        await ctx.send("There is already a quest in progress.")
        return

    quest = setup_quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode=True)
    quest.add_player(ctx.author.name)

    await make_game_channel(ctx, quest)
    embed = discord.Embed(
        title="Solo game ready to play",
        description=f"Play here: {quest.game_channel.mention}",
    )
    await ctx.send(embed=embed)
    await start_quest(ctx, quest)


# COMMAND MANAGEMENT
@bot.command(hidden=True)
async def change_cmd_acl(ctx, setting_name, value, command_name=""):
    """
    Change settings for the @access_control decorator
    """
    if value.lower() == "none":
        value = ""
    if command_name.lower() == "none":
        command_name = ""

    valid_settings = ["allowed_roles", "excluded_roles"]
    if setting_name not in valid_settings:
        message = "Invalid setting name. Allowed setting names are, `allowed_roles`, `excluded_roles`, and `user_override`."
        return

    elif setting_name == "allowed_roles" or setting_name == "excluded_roles":
        value = value.split("|")

    ACCESS_CONTROL_SETTINGS[setting_name] = value

    if command_name != None:
        ACCESS_CONTROL_SETTINGS["command_name"] = command_name


async def clear_decision_input_values(ctx):
    """
    Set decision module input values to 0

    Used during vote retries
    """
    print("Clearing decision input values...")
    for decision_module in CONTINUOUS_INPUT_DECISION_MODULES.values():
        decision_module["input_value"] = 0
    print("Decision input values set to 0")


@bot.command(hidden=True)
async def list_values(ctx):
    print("Listing values...")
    message_content = "The Community's Current Values:\n\n"
    for (
        value,
        description,
    ) in value_revision_manager.agora_values_dict.items():
        message_content += f"{value}:\n{description}\n\n"
    message = f"```{message_content}```"
    await ctx.send(message)
    return message


async def update_decision_module(context, new_decision_module):
    """
    Update the active_global_decision_modules list by appending the new decision module

    Clear the list if there is already a decision module present

    Only one decision module should be present at any given time
    """
    print("Updating decision module...")
    channel_decision_modules = ACTIVE_GLOBAL_DECISION_MODULES.get(context.channel, [])
    if len(channel_decision_modules) > 0:
        channel_decision_modules = []
        channel_decision_modules.append(new_decision_module)
        ACTIVE_GLOBAL_DECISION_MODULES[context.channel] = channel_decision_modules
    else:
        channel_decision_modules.append(new_decision_module)
        ACTIVE_GLOBAL_DECISION_MODULES[context.channel] = channel_decision_modules


async def calculate_continuous_decision_inputs(ctx):
    """
    Change local state of modules based on calculation of module inputs
    """
    print("Calculating module inputs...")
    max_value = max(
        module["input_value"] for module in CONTINUOUS_INPUT_DECISION_MODULES.values()
    )
    max_module_names = [
        module_name
        for module_name, module in CONTINUOUS_INPUT_DECISION_MODULES.items()
        if module["input_value"] == max_value
    ]

    # If threshold has been reached in only one module, update the decision module
    if max_value >= INPUT_SPECTRUM["threshold"] and len(max_module_names) == 1:
        # Update the decision module
        await update_decision_module(ctx, max_module_names[0])
        await ctx.send(f"```{max_module_names[0]} mode activated!```")
        return True
    else:
        return False


async def calculate_continuous_culture_inputs(ctx, guild_id, channel_id):
    module: CultureModule
    for module_name, module in CULTURE_MODULES.items():
        # Check if input_value reaches the spectrum threshold and local state it not yet active
        if module.config["input_value"] > INPUT_SPECTRUM[
            "threshold"
        ] and not module.is_local_state_active_in_channel(guild_id, channel_id):
            # Activate local state
            await module.activate_local_state_in_channel(ctx, guild_id, channel_id)
            await ctx.send(
                f"```{module_name.capitalize()} module has been activated!```"
            )

        # Check if input_value goes below the threshold and local state is active
        elif module.config["input_value"] <= INPUT_SPECTRUM[
            "threshold"
        ] and module.is_local_state_active_in_channel(guild_id, channel_id):
            # Deactivate local state
            await module.deactivate_local_state_in_channel(ctx, guild_id, channel_id)
            await ctx.send(
                f"```{module_name.capitalize()} module has been deactivated```"
            )


# TODO: reconcile redundant code here
async def display_module_status(context, module_dict):
    """
    Display the current status of culture input values
    """
    print("Displaying module status...")
    if module_dict == CULTURE_MODULES:
        embed = discord.Embed(
            title="Culture Display Status",
            color=discord.Color.green(),
        )
    else:
        embed = discord.Embed(
            title="Decision Display Status",
            color=discord.Color.green(),
        )

    if module_dict == CULTURE_MODULES:
        for module_name in module_dict:
            module = CULTURE_MODULES[module_name]
            input_value = module.config["input_value"]
            module_name_field = module.config["name"].capitalize()
            input_filled = int(min(input_value, INPUT_SPECTRUM["scale"]))
            input_empty = INPUT_SPECTRUM["scale"] - input_filled

            progress_bar = "🟦" * input_filled + "🟨" * input_empty
            if module_dict == CULTURE_MODULES:
                progress_bar = (
                    progress_bar[: INPUT_SPECTRUM["threshold"]]
                    + "📍"
                    + progress_bar[INPUT_SPECTRUM["threshold"] :]
                )

            embed.add_field(
                name=module_name_field,
                value=f"{progress_bar}",
                inline=False,
            )
    else:
        for module_name in module_dict:
            module = module_dict[module_name]["name"]
            input_value = module_dict[module_name]["input_value"]
            module_name_field = module.capitalize()
            input_filled = int(min(input_value, INPUT_SPECTRUM["scale"]))
            input_empty = INPUT_SPECTRUM["scale"] - input_filled

            progress_bar = "🟦" * input_filled + "🟨" * input_empty
            if module_dict == CULTURE_MODULES:
                progress_bar = (
                    progress_bar[: INPUT_SPECTRUM["threshold"]]
                    + "📍"
                    + progress_bar[INPUT_SPECTRUM["threshold"] :]
                )

            embed.add_field(
                name=module_name_field,
                value=f"{progress_bar}",
                inline=False,
            )

    await context.send(embed=embed)


# MESSAGE PROCESSING
async def create_webhook(channel):
    """
    Create webhooks for having player avatars passed through to bot avatar
    """
    global WEBHOOK_LIST
    webhook = None
    for wh in WEBHOOK_LIST:
        if wh.channel.id == channel.id:
            webhook = wh

    if not webhook:
        webhook = await channel.create_webhook(name="InternalWebhook")
        WEBHOOK_LIST.append(webhook)

    return webhook


async def send_webhook_message(webhook, message, filtered_message):
    """
    Use webhook to transform avatar of bot to user avatar
    """
    try:
        if webhook is None:
            # Handle the case when webhook is not available
            return
        payload = {
            "content": f"※ {filtered_message}",
            "username": message.author.nick
            if message.author.nick
            else message.author.name,
            "avatar_url": message.author.avatar.url if message.author.avatar else None,
        }
        await webhook.send(**payload)
    except (
        discord.errors.NotFound,
        discord.errors.Forbidden,
        discord.errors.HTTPException,
        discord.errors.InvalidData,
        discord.errors.DiscordServerError,
    ) as e:
        # Handle specific Discord-related exceptions
        error_msg = f"An error occurred while sending the webhook message: {e}"
        print(error_msg)
        logging.error(error_msg)
    except Exception as e:
        # Handle the case when the bot doesn't have permission to send a webhook message
        error_msg = f"An unexpected error occurred: {e}"
        print(error_msg)
        logging.error(error_msg)


@tasks.loop(minutes=1.0)
async def check_and_delete_webhooks_if_needed():
    """
    Regularly check if the webhook limit has been reached and clear webhooks if necessary
    """
    for guild in bot.guilds:
        webhook_count = 0
        for channel in guild.text_channels:
            webhooks = await channel.webhooks()
            webhook_count += len(webhooks)
        if webhook_count > 8:
            await delete_all_webhooks(guild)

    print(f"Webhook check: # of webhooks: {webhook_count}")


async def process_message(ctx, message):
    """
    Process messages from on_message
    """
    guild_id = ctx.guild.id
    channel_id = ctx.channel.id
    key = (guild_id, channel_id)

    if IS_QUIET and not message.author.bot:
        await message.delete()
    else:
        # Check if any modes are active and deleted the original message
        active_modules_by_channel = ACTIVE_MODULES_BY_CHANNEL.get(key, OrderedSet())
        if active_modules_by_channel:
            message_content = message.content
            if (
                message_content == "check-values"
                and "values" in active_modules_by_channel
            ):
                module_name: Values = CULTURE_MODULES["values"]
                await module_name.check_values(bot, ctx, message)
                return

            message_content = message.content
            delete_message = False
            for module_name in active_modules_by_channel:
                module: CultureModule = CULTURE_MODULES[module_name]
                if module.config[
                    "message_alter_mode"
                ]:  # Not all culture modules filter messages; we only want to delete message and replace with webhook when we know it will be filtered
                    delete_message = True
                    break

            # We delete message before filtering because filtering has latency.
            if delete_message:
                await message.delete()

                filtered_message = await apply_culture_modules(
                    active_modules=active_modules_by_channel,
                    message=message,
                    message_content=message_content,
                )

                webhook = await create_webhook(message.channel)
                if module_name == "wildcard":
                    get_module = CULTURE_MODULES.get("wildcard", None)
                    llm_prompt = get_module.config["llm_disclosure"]
                    prompt_result = f"{filtered_message}\n\n```Message filtered by the voice of group: {prompt_object.decision_one}.```"
                    await send_webhook_message(webhook, message, prompt_result)
                else:
                    await send_webhook_message(webhook, message, filtered_message)


# TODO: write tests for culture module filtering
async def apply_culture_modules(active_modules, message, message_content: str):
    """
    Filter messages based on culture modules

    Filtering is cumulative

    Order of application is derived from the active_global_culture_modules list
    """

    # Increment message count for the user (for diversity module)
    user_id = message.author.id
    USER_MESSAGE_COUNT[user_id] = USER_MESSAGE_COUNT.get(user_id, 0) + 1

    # TODO: active_modules list should be the modules themselves, not their names
    for module_name in active_modules:
        module: CultureModule = CULTURE_MODULES[module_name]
        message_content = await module.filter_message(message, message_content)

    return message_content

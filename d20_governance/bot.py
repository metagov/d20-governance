import argparse
import discord
import os
import asyncio
import logging
import traceback
import sys
import time
from discord.app_commands import command as slash_command
from discord.ext import commands
from d20_governance.utils.utils import *
from d20_governance.utils.constants import VALUES_DICT
from d20_governance.utils.cultures import *
from d20_governance.utils.decisions import *
from d20_governance.utils.voting import vote, set_global_decision_module

description = """📦 A bot for experimenting with modular governance 📦"""

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", description=description, intents=intents)
bot.remove_command("help")

def run_bot():
    bot.run(token=DISCORD_TOKEN)

@bot.command()
async def help(ctx, command: str = None):
    """
    Help
    """
    prefix = bot.command_prefix
    if command:
        # Display help for a specific command
        cmd = bot.get_command(command)
        if not cmd:
            await ctx.send(f"Sorry, I couldn't find command **{command}**.")
            return
        cmd_help = cmd.help or "No help available."
        help_embed = discord.Embed(
            title=f"{prefix}{command} help", description=cmd_help, color=0x00FF00
        )
        await ctx.send(embed=help_embed)
    else:
        # Display a list of available commands
        cmds = [c.name for c in bot.commands if not c.hidden]
        cmds.sort()
        embed = discord.Embed(
            title="Commands List",
            description=f"Here's a list of available commands. Use `{prefix}help <command>` for more info.",
            color=0x00FF00,
        )
        for cmd in cmds:
            command = bot.get_command(cmd)
            description = command.brief or command.short_doc
            embed.add_field(
                name=f"{prefix}{cmd}",
                value=description or "No description available.",
                inline=False,
            )
        await ctx.send(embed=embed)


# QUEST FLOW
def setup_quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode):
    quest = Quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode)
    bot.quest = quest
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
            print("Generating stage with llm..")
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

            print(f"↷ Processing stage {stage.name}")

            await process_stage(ctx, stage, quest, message_obj)


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
        if (
            hasattr(stage, "image_path") and stage.image_path
        ):  # Check if stage has an image_path
            image = Image.open(stage.image_path)  # Open the image
        else:
            # Generate intro image and send to temporary channel
            image = generate_image(stage.message)
    else:
        # Create an empty image representing the void
        size = (256, 256)
        border = 10
        image = Image.new("RGB", size, (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            [(border, border), (size[0] - border, size[1] - border)],
            fill=(20, 20, 20),
        )

    image.save("generated_image.png")  # Save the image to a file

    # Post the image to the Discord channel
    await game_channel_ctx.send(file=discord.File("generated_image.png"))
    if os.path.exists("generated_image.png"):
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

    # Call actions and poll for progress conditions simultaneously
    actions = stage.actions
    progress_conditions = stage.progress_conditions

    async def action_runner():
        for action in actions:
            command_name = action.action
            if command_name is None:
                raise Exception(f"Command {command_name} not found.")
            args = action.arguments
            command = globals().get(command_name)
            retries = action.retries if hasattr(action, "retries") else 0
            if bot.quest.progress_completed == True:
                print("Progress condition met. Ending action_runner")
                break
            while retries >= 0:
                try:
                    await execute_action(game_channel_ctx, command, args)
                    break
                # TODO: Add more specific exceptions
                except Exception as e:
                    if retries > 0:
                        # TODO: how can we avoid the global
                        global VOTE_RETRY
                        VOTE_RETRY = True
                        print(f"Number of retries remaining: {retries}")
                        if hasattr(action, "retry_message") and action.retry_message:
                            await clear_decision_input_values(game_channel_ctx)
                            await game_channel_ctx.send(action.retry_message)
                            await game_channel_ctx.send(
                                "```💡--Do Not Dispair!--💡\n\nYou have a chance to change how you make decisions```"
                            )
                            await display_module_status(
                                game_channel_ctx, DECISION_MODULES
                            )
                            await game_channel_ctx.send(
                                "```👀--Instructions--👀\n\n* Post a message with the decision type you want to use\n\n* For example, type: consensus +1\n\n* You can express your preference multiple times and use +1 or -1 after the decision type\n\n* The decision module with the most votes in 60 seconds, or the first to 10, will be the new decision making module during the next decision retry.\n\n* You have 60 seconds before the next decision is retried. ⏳```"
                            )
                            loop_count = 0
                            # TODO: fixup this loop
                            while True:
                                condition_result = await calculate_module_inputs(
                                    game_channel_ctx, retry=True, tally=False
                                )
                                if condition_result:
                                    VOTE_RETRY = False
                                    break
                                loop_count += 1
                                print(f"⧗ {loop_count} seconds to set new decision")
                                if loop_count == 60:
                                    VOTE_RETRY = False
                                    print("Tallying Inputs")
                                    await calculate_module_inputs(
                                        game_channel_ctx, retry=True, tally=True
                                    )
                                    break
                                await asyncio.sleep(1)
                            retries -= 1
                    else:
                        if (
                            hasattr(action, "failure_message")
                            and action.failure_message
                        ):
                            await game_channel_ctx.send(action.failure_message)
                            await end(game_channel_ctx)
                        # if a vote fails and there is a soft failure action, the soft failure message is sent and the while loop exited
                        elif hasattr(action, "soft_failure") and action.soft_failure:
                            await game_channel_ctx.send(action.soft_failure)
                            # TODO: Instead of breaking out of the action_runner, return to next vote
                            # Might need to do this in the Vote function
                            break
                        raise Exception(
                            f"Failed to execute action {action.action}: {e}"
                        )

    async def progress_checker():
        if progress_conditions == None or len(progress_conditions) == 0:
            return
        while True:
            if bot.quest.progress_completed == True:
                print("At least one progress condition met")
                break
            tasks = []
            for progress_condition in progress_conditions:
                function_name = progress_condition.progress_condition
                if function_name is None:
                    raise Exception(f"Function {function_name} not found.")
                function = globals().get(function_name)
                args = progress_condition.arguments
                tasks.append(function(game_channel_ctx, *args))
                print(
                    f"+ `{function_name}` in channel `{game_channel_ctx.channel}` with arguments {args} added to task list"
                )  # Debugging line
            for future in asyncio.as_completed(tasks):
                condition_result = await future
                if condition_result:
                    return True
            await asyncio.sleep(1)  # sleep before checking again to avoid busy looping

    # Run simultaneously and wait for both the action_runner and progress_checker to complete
    # If at least one of the progress conditions is met and all of the actions have completed, then the stage is complete
    await asyncio.gather(action_runner(), progress_checker())


async def countdown(ctx, timeout_seconds, text: str = None):
    """
    Send an updating countdown display
    """
    if hasattr(bot, "quest") and bot.quest.fast_mode:
        timeout_seconds = 15

    # TODO: make this better
    remaining_seconds = int(timeout_seconds)

    # Set new message interval
    message_interval_seconds = 60
    next_message_time = time.time() + message_interval_seconds

    remaining_minutes = remaining_seconds / 60

    first_message = f"```⏱️ {remaining_minutes:.2f} minutes remaining {text}.\n👇 👇 👇```"
    message = await ctx.send(first_message)

    while remaining_seconds > 0:
        remaining_minutes = remaining_seconds / 60
        new_message = (
            f"```⏳ Counting Down: {remaining_minutes:.2f} minutes remaining {text}.```"
        )
        if time.time() >= next_message_time:
            new_message = await ctx.send(new_message)
            next_message_time = (
                time.time() + message_interval_seconds
            )  # schedule next message

        # TODO: can we avoid this check
        if bot.quest.progress_completed == True:  # check if all submissions are done
            print("Stopping countdown")
            if time.time() >= next_message_time:
                await new_message.edit(
                    content="```⏲️ All submissions submitted. Countdown finished.```"
                )
            else:
                await message.edit(
                    content="```⏲️ All submissions submitted. Countdown finished.```"
                )
            break

        remaining_seconds -= 1
        await asyncio.sleep(1)

    if remaining_seconds <= 0:  # send this message if time runs out
        await message.edit(content="```⏲️ Counting down finished.```")
    print("⧗ Countdown finished.")


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
            print("All submissions submitted.")
            bot.quest.progress_completed = True
            return True
        print("⧗ Waiting for all submissions to be submitted.")
        await asyncio.sleep(1)  # Wait for a second before checking again

# TODO: what's the difference between pause / progress_timeout, can they be collapsed

async def pause(ctx, seconds: str):
    """
    Simulation pauses

    Used by in simulation yaml to add pauses in the simulations
    """
    if bot.quest.fast_mode:
        seconds = 1
        print(f"Pausing for {seconds} seconds...")
        await asyncio.sleep(int(seconds))
    else:
        print(f"Pausing for {seconds} seconds...")
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
    bot.quest.progress_completed = True
    return True


async def end(ctx):
    """
    Archive the quest and channel
    """
    print("Archiving...")
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

    print("Archived...")


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


class QuestBuilderView(discord.ui.View):
    def __init__(self, *, timeout=120):
        super().__init__(timeout=timeout)
        self.select1 = QuestBuilder(
            placeholder="Select Quest",
            options=[
                discord.SelectOption(
                    label="QUEST: WHIMSY",
                    emoji="🤪",
                    description="A whimsical governance game",
                    value=SIMULATIONS["whimsy"],
                ),
                discord.SelectOption(
                    label="QUEST: MASCOT",
                    emoji="🐻‍❄️",
                    description="Propose a new community mascot",
                    value=SIMULATIONS["mascot"],
                ),
                discord.SelectOption(
                    label="QUEST: COLONY",
                    emoji="🛸",
                    description="Governance under space colony",
                    value=SIMULATIONS["colony"],
                ),
                discord.SelectOption(
                    label="QUEST: ???",
                    emoji="🤔",
                    description="A random game of d20 governance",
                    value=SIMULATIONS["llm_mode"],
                ),
                discord.SelectOption(
                    label="MINIGAME: JOSH GAME",
                    emoji="🙅",
                    description="Decide the real Josh",
                    value=SIMULATIONS["josh_game"],
                ),
                discord.SelectOption(
                    label="TUTORIAL: BUILD A COMMUNITY",
                    emoji="🎪",
                    description="Build a community",
                    value=SIMULATIONS["build_a_community"],
                ),
            ],
        )
        self.select2 = QuestBuilder(
            placeholder="Select number of players",
            options=[
                discord.SelectOption(
                    label=n,
                    emoji="#️⃣",
                    value=str(n),
                )
                for n in range(1, 20)
            ],
        )
        self.select3 = QuestBuilder(
            placeholder="Generate images?",
            options=[
                discord.SelectOption(
                    label="Yes",
                    emoji="🖼️",
                    description="Turn image generation on",
                    value=True,
                ),
                discord.SelectOption(
                    label="No",
                    emoji="🔳",
                    description="Turn image generation off",
                    value=False,
                ),
            ],
        )
        self.add_item(self.select1)
        self.add_item(self.select2)
        self.add_item(self.select3)

        self.button = discord.ui.Button(
            label="Propose Quest",
            style=discord.ButtonStyle.green,
            disabled=False,  # FIXME: should be set to True and enabled through enable_button
            emoji="✅",
        )
        self.add_item(self.button)

        self.button.callback = self.on_button_click

    def get_results(self):
        return (
            self.select1.selected_value,
            self.select2.selected_value,
            self.select3.selected_value,
        )

    def enable_button(self):
        self.button.disabled = False

    async def on_button_click(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.defer()

    async def wait_for_input(self, ctx):
        self.ctx = ctx
        await ctx.send("build your quest proposal:", view=self)

        try:
            await self.wait()
        except asyncio.TimeoutError:
            self.stop()
        else:
            return (
                self.select1.selected_value,
                int(self.select2.selected_value),
                self.select3.selected_value
                == "True",  # this is how you convert string to bool
            )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.channel != self.ctx.channel:
            await interaction.response.send_message(
                "this interaction is not in the expected channel.", ephemeral=True
            )
            return False
        elif interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Only the original author can interact with this view.", ephemeral=True
            )
            return False
        return True


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

        async with self.lock: # ensure that the player count gets updated synchronously, else we may end up creating multiple channels
            if player_name not in quest.joined_players:
                quest.add_player(player_name)
                await interaction.response.send_message(
                    f"{player_name} has joined the quest!"
                )
                await self.update_embed(interaction) 
                if len(quest.joined_players) == self.num_players: 
                    print(quest.joined_players)
                    print(self.num_players)

                    # remove join and leave buttons
                    await interaction.message.edit(view=None)
                    # create channel for game
                    await make_game_channel(self.ctx, quest)
                    embed = discord.Embed(
                        title=f"{self.ctx.author.display_name}'s proposal to play has enough players, and is ready to play",
                        description=f"**Quest:** {quest.game_channel.mention}\n\n**Players:** {', '.join(quest.joined_players)}",
                    )
                    await interaction.message.edit(embed=embed)
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

# EVENTS
@bot.event
async def on_ready():
    """
    Event handler for when the bot has logged in and is ready to start interacting with Discord
    """
    await bot.tree.sync()
    logging.basicConfig(
        filename="logs/bot.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print(">> Logging to logs/bot.log <<")
    with open(f"{LOGGING_PATH}/bot.log", "a") as f:
        f.write(f"\n\n--- Bot started at {datetime.datetime.now()} ---\n\n")
    logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        await bot.tree.sync(guild=guild)
        await setup_server(guild)
        await delete_all_webhooks(guild)


@bot.event
async def on_guild_join(guild):
    """
    Event handler for when the bot has been invited to a new guild.
    """
    print(f"D20 Bot has been invited to server `{guild.name}`")
    await setup_server(guild)


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if hasattr(bot, "vote_message") and reaction.message.id == bot.vote_message.id:
        if user.id in bot.voters:
            await reaction.remove(user)
            await user.send(
                f"Naughty naughty! You cannot vote twice!",
                delete_after=timeouts["vote"],
            )
        else:
            bot.voters.add(user.id)


# QUEST START AND PROGRESSION
@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def embark(ctx, *args):
    """
    Embark on a d20 governance quest
    """
    # Parse argument flags
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a", "--audio", action="store_true", help="Generate text-to-speech audio"
    )
    parser.add_argument("-f", "--fast", action="store_true", help="Turn on fast mode")
    args = parser.parse_args(args)
    gen_audio = args.audio
    fast_mode = args.fast

    # Make Quest Builder view and return values from selections
    print("Waiting for proposal to be built...")
    view = QuestBuilderView()
    selected_values = await view.wait_for_input(ctx)
    if selected_values is None:
        await ctx.send("The quest proposal timed out.", ephemeral=True)
        return
    quest_mode, num_players, gen_images = selected_values

    if not 1 <= num_players <= 20:
        await ctx.send("The game requires at least 2 and at most 20 players")
        return

    # Quest setup
    quest = setup_quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode=False)

    # Create Join View
    join_leave_view = JoinLeaveView(ctx, quest, num_players)
    embed = discord.Embed(
        title=f"{ctx.author.display_name} has proposed a game for {num_players} players: Join or Leave"
    )
    embed.add_field(
        name="**Current Players:**", value="", inline=False
    )  # Empty initial value.
    embed.add_field(
        name="**Players needed to start:**", value=str(num_players), inline=False
    )  # Empty initial value.

    await ctx.send(embed=embed, view=join_leave_view)
    print("Waiting for players to join...")


async def make_game_channel(ctx, quest: Quest):
    """
    Game State: Setup the config and create unique quest channel
    """
    print("Making temporary game channel...")

    # Set permissions for bot
    bot_permissions = discord.PermissionOverwrite(read_messages=True)
    # Create a dictionary containing overwrites for each player that joined,
    # giving them read_messages access to the temp channel and preventing message_delete
    player_overwrites = {
        ctx.guild.get_member_named(player): discord.PermissionOverwrite(
            read_messages=True, manage_messages=False
        )
        for player in quest.joined_players
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

    # create and name the channel with the quest_name from the yaml file
    # and add a number do distinguish channels
    quest.game_channel = await quests_category.create_text_channel(
        name=f"d20-{quest.title}-{len(quests_category.channels) + 1}",
        overwrites=overwrites,
    )

@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def quiet(ctx, mode: string = None):
    """
    Enforce quiet mode; prevent posting
    """
    global IS_QUIET
    if mode == None:
        pass
    if mode:
        IS_QUIET = True
        await ctx.send("```Quiet mode is on```")
        print("Quiet mode is on.")
    else:
        IS_QUIET = False
        await ctx.send("```Quiet mode is off```")
        print("Quiet mode is off.")

@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def transparency(ctx):
    """
    Toggle transparency module
    """
    embed = discord.Embed(
        title="New Culture: Transparency",
        description="The community has chosen to adopt a culture of transparency.",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def secrecy(ctx):
    """
    Toggle secrecy module
    """
    embed = discord.Embed(
        title="New Culture: Secrecy",
        description="The community has chosen to adopt a culture of secrecy.",
        color=discord.Color.red(),
    )
    await ctx.send(embed=embed)


@bot.command(brief="Toggle autonomy module")
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def autonomy(ctx):
    """
    Toggle autonomy module
    """
    embed = discord.Embed(
        title="New Culture: Autonomy",
        description="The community has chosen to adopt a culture of autonomy.",
        color=discord.Color.blue(),
    )
    await ctx.send(embed=embed)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def obscurity(ctx, mode: str = None):
    """
    Control obscurity module
    """
    available_modes = ["scramble", "replace_vowels", "pig_latin", "camel_case"]
    module = CULTURE_MODULES.get("obscurity", None)
    if module is None:
        return

    if mode is None:
        await module.toggle_global_state(ctx)
    if mode not in available_modes:
        embed = discord.Embed(
            title=f"Error - The mode '{mode}' is not available.",
            color=discord.Color.red(),
        )
    else:
        module.config["mode"] = mode
        await module.toggle_global_state(ctx)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def eloquence(ctx):
    """
    Trigger eloquence module

    Defaults to toggling culture module unless true or false are passed to set global state
    """
    module = CULTURE_MODULES.get("eloquence", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def values(ctx):
    """
    Trigger values module
    """
    module = CULTURE_MODULES.get("values", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)


# TODO: it would be nice to not have this toggled when displaying the info, maybe have a different command for display diversity info
@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def diversity(ctx):
    """
    Trigger diversity module
    """
    module: Diversity = CULTURE_MODULES.get("diversity", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)

    # Display the diversity counts if global state is true
    if module.is_global_state_active():
        await module.display_info(ctx)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def amplify(ctx):
    """
    Trigger amplify module
    """
    module: Amplify = CULTURE_MODULES.get("amplify", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def ritual(ctx):
    """
    Trigger ritual module.
    """
    module: Ritual = CULTURE_MODULES.get("ritual", None)
    if module is None:
        return

    await module.toggle_global_state(ctx)


@bot.command(hidden=True)
@commands.check(lambda ctx: False)
async def secret_message(ctx):
    """
    Secrecy: Randomly Send Messages to DMs
    """
    print("Secret message command triggered.")
    await send_msg_to_random_player(bot.quest.game_channel)


#TODO: I think we can probably remove this? 
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


# META GAME COMMANDS
@bot.command()
@access_control()
async def info(
    ctx,
    culture_module=None,
    current_decision_module=None,
    starting_decision_module=None,
):
    """
    View meta information
    """
    # TODO Pass starting or current decision module into the info command
    decision_module = current_decision_module or starting_decision_module
    embed = discord.Embed(title="Current Stats", color=discord.Color.dark_gold())
    embed.add_field(name="Current Decision Module:\n", value=f"{decision_module}\n\n")
    embed.add_field(name="Current Culture Module:\n", value=f"{culture_module}")
    await ctx.send(embed=embed)


@bot.command()
async def show_decisions(ctx):
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


@bot.command()
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
    print("Quiting...")
    await ctx.send(f"{ctx.author.name} has quit the game!")
    # TODO: Implement the logic for quitting the game and ending it for the user

# TODO: combine dissolve and end into one command
@bot.command(hidden=True)
async def dissolve(ctx):
    """
    Trigger end of game
    """
    print("Ending game...")
    await end(ctx)
    print("Game ended.")


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
async def is_quiet(ctx):
    """
    Enforce quiet mode; prevent posting
    """
    global IS_QUIET
    IS_QUIET = True
    print("Quiet mode is on.")


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def is_not_quiet(ctx):
    """
    Turn off quiet mode
    """
    global IS_QUIET
    IS_QUIET = False
    print("Quiet mode is off.")


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


@bot.tree.command(name="submit", description="Make a submission.")
@access_control()
async def submit(interaction: discord.Interaction, submission: str):
    """
    Submit a message

    To submit a message, type `/submit` followed by a space and your message.

    For example: `/submit this is my submission`

    See also `/help resubmit` for information on how to change your submission
    """
    confirmation_message = "has made their submission!"
    await submit_message(interaction, submission, confirmation_message)


@bot.tree.command(name="resubmit", description="Change your last submission.")
@access_control()
async def resubmit(interaction: discord.Interaction, submission: str):
    """
    Resubmit/revise a message

    To resubmit a message, type /resubmit followed by a space and your message.

    For example: /resubmit this is my revised submission
    """
    confirmation_message = "has revised their submission!"
    await submit_message(interaction, submission, confirmation_message)


async def submit_message(
    interaction: discord.Interaction, text: str, confirmation_message
):
    # await ctx.message.delete()
    if hasattr(bot, "quest"):
        bot.quest.add_submission(interaction, text)
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
@commands.check(lambda ctx: False)
async def post_submissions(ctx):
    """
    Post submissions from /submit
    """
    submissions = []
    players_to_submissions = bot.quest.players_to_submissions
    title = "Submissions:"

    # Go through all nicknames and their submissions
    for player_name, submission in players_to_submissions.items():
        # Append a string formatted with the nickname and their submission
        submissions.append(f"📜 **{player_name}**:\n          🗣️  {submission}")

    # Join all submissions together with a newline in between each one
    formatted_submissions = "\n\n\n".join(submissions)

    embed = discord.Embed(
        title=title, description=formatted_submissions, color=discord.Color.dark_teal()
    )

    # Send the formatted submissions to the context
    await ctx.send(embed=embed)

# TODO: can we reconcile this with vote_on_values? 
@bot.command(hidden=True)
# @commands.check(lambda ctx: False)
async def vote_submissions(ctx, question: str, timeout="20"):
    """
    Call vote on all submissions from /submit and reset submission list
    """
    # Get all keys (player_names) from the players_to_submissions dictionary and convert it to a list
    contenders = list(bot.quest.players_to_submissions.values())
    quest = bot.quest
    await vote(ctx, quest, question, contenders, int(timeout))
    # Reset the players_to_submissions dictionary for the next round
    bot.quest.reset_submissions()

@bot.command()
async def post_proposal_values(ctx):
    message = "Proposed values:\n"
    for key, value in PROPOSED_VALUES_DICT.items():
        # Format the key as bold and add the value
        message += f"**{key}**: {value}\n"
    await ctx.send(message)

@bot.tree.command(
    name="propose_value",
    description="propose and define a value that will govern your interactions",
)
async def propose_value(interaction: discord.Interaction, name: str, definition: str):
    PROPOSED_VALUES_DICT[name] = definition
    print(PROPOSED_VALUES_DICT)
    await interaction.response.send_message(
        f"**{interaction.user.name} proposed a new value:**\n* **{name}:** {definition}"
    )

@bot.command(hidden=True)
# @commands.check(lambda ctx: False)
async def vote_on_values(ctx, question: str, timeout="20"):
    """
    Call vote on all submissions from /submit and reset submission list
    """
    # Get all keys (player_names) from the players_to_submissions dictionary and convert it to a list
    quest = bot.quest
    bot.values_dict = await lazy_consensus(ctx, quest, question, PROPOSED_VALUES_DICT, int(timeout))
    # Reset the values submissions dict for the next round
    PROPOSED_VALUES_DICT.clear()

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
async def solo(ctx, *args, quest_mode=SIMULATIONS["build_a_community"]):
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
    quest = setup_quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode=True)
    quest.add_player(ctx.author.name)

    await make_game_channel(ctx, quest)
    embed = discord.Embed(
        title="Solo game ready to play",
        description=f"Play here: {quest.game_channel.mention}",
    )
    await ctx.send(embed=embed)
    await start_quest(ctx, quest)

# TODO: can we remove? 
@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_randomize_snapshot(ctx):
    """
    Test making a randomized governance snapshot
    """
    shuffle_modules()
    make_governance_snapshot()

# TODO: can we remove? 
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

# TODO: can we remove? 
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

# TODO: can we remove? 
@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_module_png_generation(ctx, module, module_dict=CULTURE_MODULES):
    """
    Test stability image generation
    """
    if module in module_dict:
        module_name = module_dict[module]["name"]
        print(module_name)
        svg_icon = module_dict[module]["icon"]
        print(svg_icon)
        image = make_module_png(module_name, svg_icon)
        print(image)
    await ctx.send(file=discord.File(image))

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


# COMMAND TRACKING
@bot.event
async def on_command(ctx):
    """
    Event listener that prints command invoked, channel where invoked, and channel id
    """
    print(
        f"⁂ Invoked: `/{ctx.command.name}` in channel `{ctx.channel.name}`, ID: {ctx.channel.id}"
    )


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send('That command does not exist.')
    else:
        await ctx.send("An error occurred.")
    traceback_text = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    error_message = f"Error invoking command: {ctx.command.name if ctx.command else 'Command does not exist'} - {error}\n{traceback_text}"
    print(error_message)
    logging.error(error_message)


@bot.event
async def on_error(event):
    type, value, tb = sys.exc_info()
    traceback_str = "".join(traceback.format_exception(type, value, tb))
    print(f"Unhandled exception in {event}:\n{traceback_str}")
    logging.error(f"Unhandled exception in {event}:\n{traceback_str}")


# GOVERNANCE INPUT
@bot.command()
async def show_governance_status(ctx):
    """
    Display overall governance inputs
    """
    await display_module_status(ctx)


async def clear_decision_input_values(ctx):
    """
    Set decision module input values to 0

    Used during vote retries
    """
    for decision_module in DECISION_MODULES:
        DECISION_MODULES[decision_module]["input_value"] = 0
    print("Decision input values set to 0")


@bot.command()
async def list_values(ctx):
    values = bot.values_dict if bot.values_dict else DEFAULT_VALUES_DICT
    message_content = "Our collectively defined values + definitions:\n\n"
    for (
        value,
        description,
    ) in values.items():
        message_content += f"{value}:\n{description}\n\n"
    message = f"```{message_content}```"
    await ctx.send(message)


async def update_decision_module(context, new_decision_module):
    """
    Update the active_global_decision_modules list by appending the new decision module

    Clear the list if there is already a decision module present

    Only one decision module should be present at any given time
    """
    channel_decision_modules = ACTIVE_GLOBAL_DECISION_MODULES.get(context.channel, [])
    if len(channel_decision_modules) > 0:
        channel_decision_modules = []
        channel_decision_modules.append(new_decision_module)
        ACTIVE_GLOBAL_DECISION_MODULES[context.channel] = channel_decision_modules
    else:
        channel_decision_modules.append(new_decision_module)
        ACTIVE_GLOBAL_DECISION_MODULES[context.channel] = channel_decision_modules


async def calculate_module_inputs(context, retry=None, tally=None):
    """
    Change local state of modules based on calculation of module inputs
    """
    # Calculate decision inputs if retry True
    if retry:
        max_value = max(
            DECISION_MODULES[module]["input_value"] for module in DECISION_MODULES
        )
        max_keys = [
            module
            for module in DECISION_MODULES
            if DECISION_MODULES[module]["input_value"] == max_value
        ]

        if not tally:
            if max_value == INPUT_SPECTRUM["scale"] and len(max_keys) == 1:
                await update_decision_module(context, max_keys[0])
                await context.send(f"```{max_keys[0]} mode activated!```")
                return True

        else:
            if len(max_keys) > 1:
                await context.send(
                    f"```Poll resulted in tie. Previous decision module kept.```"
                )
            else:
                await update_decision_module(context, max_keys[0])
                await context.send(f"```{max_keys[0]} mode activated!```")

    # Calculate culture inputs
    async def evaluate_module_state(module_name):
        module = CULTURE_MODULES.get(module_name, None)
        if module is None:
            return

        # Toggle local and global state of modules based on input values
        # If local state not true and input value passes threshold
        if (
            not module.is_local_state_active()
            and module.config["input_value"] > INPUT_SPECTRUM["threshold"]
        ):
            module.activate_local_state()
            # If global state is true let user know that module is already activated
            if module.is_global_state_active():
                # already on
                await context.send(
                    f"```{module_name.capitalize()} module is already activated!```"
                )
            else:
                # Otherwiseactivate the global module
                await module.activate_global_state(context)

        # If local state is true and value is equales or gos under threshold
        elif (
            module.is_local_state_active()
            and module.config["input_value"] <= INPUT_SPECTRUM["threshold"]
        ):
            # Turn off local state
            module.deactivate_local_state()
            # If global state is false remove module from active modules list
            # TODO: There is still a logical knot in here that needs to be unwound
            # If global state is false, the next step shouldn't be to deactivate the global state
            if not module.is_global_state_active():
                await module.deactivate_global_state(context)

            # If global state is true
            else:
                # TODO: This is practically it's own function and can be made more modular in the future
                # Turn off global state based on timeout value
                timeout = 20
                await module.deactivate_global_state(context, timeout)
                # Send a countdown message to user letting them know the module they turned off will turn back on
                countdown_message = f"until {module_name} turns back on"
                await countdown(context, timeout, countdown_message)
                # If local state is false after timeout
                if not module.is_local_state_active():
                    # Reactivate the local state
                    module.activate_local_state()
                    # If value is less than or equal to threshold after timeout set input value to spectrum max
                    if module.config["input_value"] <= INPUT_SPECTRUM["threshold"]:
                        module.config["input_value"] = INPUT_SPECTRUM["scale"]
                        await display_module_status(context, CULTURE_MODULES)
                        await context.send(
                            f"```{module.config['name'].capitalize()} has been turned back on and set to the max!```"
                        )

    for module_name in CULTURE_MODULES.keys():
        await evaluate_module_state(module_name)

# TODO: reconcile redundant code here
async def display_module_status(context, module_dict):
    """
    Display the current status of culture input values
    """
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
    await calculate_module_inputs(context)


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
    payload = {
        "content": f"※ {filtered_message}",
        "username": message.author.name,
        "avatar_url": message.author.avatar.url if message.author.avatar else None,
    }
    await webhook.send(**payload)


async def process_message(ctx, message):
    """
    Process messages from on_message
    """
    if IS_QUIET and not message.author.bot:
        await message.delete()
    else:
        # Check if any modes are active deleted the original message
        active_modules_by_channel = ACTIVE_MODULES_BY_CHANNEL.get(
            str(message.channel), OrderedSet()
        )
        if active_modules_by_channel:
            message_content = message.content
            if message_content == "check-values" and "values" in active_modules_by_channel:
                module_name: Values = CULTURE_MODULES["values"]
                await module_name.check_values(bot, ctx, message)
                return 
            
            message_content = message.content
            delete_message = False
            for module_name in active_modules_by_channel:
                module: CultureModule = CULTURE_MODULES[module_name]
                if module.config["message_alter_mode"]: # Not all culture modules filter messages; we only want to delete message and replace with webhook when we know it will be filtered 
                    delete_message = True
                    break
            
            # We delete message before filtering because filtering has latency.
            if delete_message:
                await message.delete()

                filtered_message = await apply_culture_modules(
                    ctx,
                    active_modules=active_modules_by_channel,
                    message=message,
                    message_content=message_content,
                )

                webhook = await create_webhook(message.channel)
                await send_webhook_message(webhook, message, filtered_message)

# TODO: write tests for culture module filtering
async def apply_culture_modules(ctx, active_modules, message, message_content: str
):
    """
    Filter messages based on culture modules

    Filtering is cumulative

    Order of application is derived from the active_global_culture_modules list
    """

    # Increment message count for the user (for diversity module)
    user_id = message.author.id
    USER_MESSAGE_COUNT[user_id] = USER_MESSAGE_COUNT.get(user_id, 0) + 1

    for module_name in active_modules:
        module: CultureModule = CULTURE_MODULES[module_name] # TODO: active_modules list should be the modules themselves, not their names
        message_content = await module.filter_message(ctx, message, message_content)
    return message_content


# ON MESSAGE
@bot.event
async def on_message(message):
    """
    Global message event listener
    """
    global VOTE_RETRY
    context = await bot.get_context(message)
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

        for module_name in DECISION_MODULES.keys() | CULTURE_MODULES.keys():
            if (
                message.content.lower() == f"{module_name} +1"
                or message.content.lower() == f"{module_name} -1"
            ):
                change = 1 if message.content.lower().endswith("+1") else -1
                if module_name in DECISION_MODULES:
                    if VOTE_RETRY:
                        decision_bucket = cooldowns["decisions"].get_bucket(message)
                        retry_after = decision_bucket.update_rate_limit()
                        if retry_after:
                            await context.send(
                                f"{context.author.mention}: Decision cooldown active, try again in {retry_after:.2f} seconds"
                            )
                            return

                        DECISION_MODULES[module_name]["input_value"] += change
                        await display_module_status(context, DECISION_MODULES)
                        return
                    else:
                        return
                elif module_name in CULTURE_MODULES:
                    culture_bucket = cooldowns["cultures"].get_bucket(message)
                    retry_after = culture_bucket.update_rate_limit()
                    if retry_after:
                        await context.send(
                            f"{context.author.mention}: Culture cooldown active, try again in {retry_after:.2f} seconds"
                        )
                        return

                    module = CULTURE_MODULES[module_name]
                    module.config["input_value"] += change
                    await display_module_status(context, CULTURE_MODULES)
                    return

        await process_message(context, message)
    except Exception as e:
        type, value, tb = sys.exc_info()
        traceback_str = "".join(traceback.format_exception(type, value, tb))
        print(f"Unhandled exception:\n{traceback_str}")
        logging.error(f"Unhandled exception:\n{traceback_str}")
        await context.send("An error occurred.")

import argparse
import discord
import os
import asyncio
import logging
import traceback
import sys

from discord.ext import commands
from d20_governance.utils.utils import *
from d20_governance.utils.constants import *
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

bot = commands.Bot(command_prefix="/", description=description, intents=intents)
bot.remove_command("help")


def run_bot():
    bot.run(token=DISCORD_TOKEN)


@bot.command()
async def help(ctx, command: str = None):
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


logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
print("Logging to logs/bot.log")

# QUEST FLOW


def setup_quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode):
    quest = Quest(quest_mode, gen_images, gen_audio, fast_mode, solo_mode)
    bot.quest = quest
    return quest


async def start_quest(ctx, quest: Quest):
    """
    Sets up a new quest
    """

    if quest.mode == QUEST_MODE_LLM:
        llm_agent = get_llm_agent()
        num_stages = random.randint(5, 10)  # Adjust range as needed
        for _ in range(num_stages):
            print("Generating stage with llm..")
            stage = await generate_stage_llm(llm_agent)
            await process_stage(ctx, stage, quest)

    else:  # yaml mode
        for stage in quest.stages:
            actions = [
                Action.from_dict(action_dict)
                for action_dict in stage[QUEST_ACTIONS_KEY]
            ]
            stage = Stage(
                name=stage[QUEST_NAME_KEY],
                message=stage[QUEST_MESSAGE_KEY],
                actions=actions,
                progress_conditions=stage[QUEST_PROGRESS_CONDITIONS_KEY],
                image_path=stage.get(QUEST_IMAGE_PATH_KEY),
            )

            print(f"↷ Processing stage {stage.name}")

            await process_stage(ctx, stage, quest)


async def process_stage(ctx, stage: Stage, quest: Quest):
    """
    Run stages from yaml config
    """

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
    await quest.game_channel.send(file=discord.File("generated_image.png"))
    os.remove("generated_image.png")  # Clean up the image file

    if quest.gen_audio:
        # Post audio file
        with open(audio_filename, "rb") as f:
            audio = discord.File(f)
            await quest.game_channel.send(file=audio)
        os.remove(audio_filename)

    embed = discord.Embed(
        title=stage.name,
        description=stage.message,
        color=discord.Color.dark_orange(),
    )

    # Stream message
    if quest.fast_mode:
        # embed
        await quest.game_channel.send(embed=embed)
    else:
        await stream_message(quest.game_channel, stage.message, embed)

    # Call actions and poll for progress conditions simultaneously
    actions = stage.actions
    progress_conditions = stage.progress_conditions

    async def action_runner():
        for action in actions:
            game_channel_ctx = await get_channel_context(bot, quest.game_channel)
            command_name = action.action
            if command_name is None:
                raise Exception(f"Command {command_name} not found.")
            args = action.arguments
            command = globals().get(command_name)
            retries = action.retries if hasattr(action, "retries") else 0
            while retries >= 0:
                try:
                    await execute_action(game_channel_ctx, command, args)
                    break
                except Exception as e:
                    if retries > 0:
                        global VOTE_RETRY
                        VOTE_RETRY = True
                        print(f"Number of retries remaining: {retries}")
                        if hasattr(action, "retry_message") and action.retry_message:
                            await clear_decision_status(game_channel_ctx)
                            await game_channel_ctx.send(action.retry_message)
                            await game_channel_ctx.send(
                                "```💡--Do Not Dispair!--💡\n\nYou have a chance to change how you make decisions```"
                            )
                            await display_decision_status(game_channel_ctx)
                            await game_channel_ctx.send(
                                "```👀--Instructions--👀\n\n* Post a message with the decision type you want to use\n\n* For example, type: consensus +1\n\n* You can express your preference multiple times and use +1 or -1 after the decision type\n\n* The decision module with the most votes in 60 seconds, or the first to 10, will be the new decision making module during the next decision retry.\n\n* You have 60 seconds before the next decision is retried. ⏳```"
                            )
                            bypass_sleep = False
                            loop_count = 0
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
                            await end(ctx, quest)
                        raise Exception(
                            f"Failed to execute action {action.action}: {e}"
                        )

    async def progress_checker():
        if progress_conditions == None or len(progress_conditions) == 0:
            return
        while True:
            tasks = []
            for condition in progress_conditions:
                tokens = shlex.split(condition)
                func_name, *args = tokens
                func = globals()[func_name]
                print(
                    f"⁂ Invoked: `{func_name}` in channel `{quest.game_channel}` with arguments {args}. Channel ID: {quest.game_channel.id}"
                )  # Debugging line
                tasks.append(func(*args))
            for future in asyncio.as_completed(tasks):
                condition_result = await future
                if condition_result:
                    return True
            await asyncio.sleep(1)  # sleep before checking again to avoid busy looping

    # Run simultaneously and wait for both the action_runner and progress_checker to complete
    # If at least one of the progress conditions is met and all of the actions have completed, then the stage is complete
    await asyncio.gather(action_runner(), progress_checker())


async def all_submissions_submitted():
    while True:
        joined_players = bot.quest.joined_players
        players_to_submissions = bot.quest.players_to_submissions
        if len(joined_players) == len(players_to_submissions):
            print("All submissions submitted.")
            return True
        print("⧗ Waiting for all submissions to be submitted.")
        await asyncio.sleep(1)  # Wait for a second before checking again


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def timeout(seconds: str):
    if not bot.quest.fast_mode:
        print(f"Sleeping for {seconds} seconds...")
        await asyncio.sleep(int(seconds))
    return True


async def end(ctx, quest: Quest):
    """
    Archive the quest and channel
    """
    print("Archiving...")
    # Archive temporary channel
    archive_category = discord.utils.get(ctx.guild.categories, name="d20-archive")
    if quest.game_channel is not None:
        await quest.game_channel.send(
            "```👋👋👋\n\nThe game is over. This channel is now archived.```"
        )
        await quest.game_channel.edit(category=archive_category)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            ),
            ctx.guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=False
            ),
        }
        await quest.game_channel.edit(overwrites=overwrites)
    print("Archived...")
    return
    # TODO: Prevent bot from being able to send messages to arcvhived channels


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
                    value=QUEST_WHIMSY,
                ),
                discord.SelectOption(
                    label="QUEST: MASCOT",
                    emoji="🐻‍❄️",
                    description="Propose a new community mascot",
                    value=QUEST_MASCOT,
                ),
                discord.SelectOption(
                    label="QUEST: COLONY",
                    emoji="🛸",
                    description="Governance under space colony",
                    value=QUEST_COLONY,
                ),
                discord.SelectOption(
                    label="QUEST: ???",
                    emoji="🤔",
                    description="A random game of d20 governance",
                    value=QUEST_MODE_LLM,
                ),
                discord.SelectOption(
                    label="MINIGAME: JOSH GAME",
                    emoji="🙅",
                    description="Decide the real Josh",
                    value=MINIGAME_JOSH,
                ),
                discord.SelectOption(
                    label="TUTORIAL: BUILD A COMMUNITY",
                    emoji="🎪",
                    description="Build a community",
                    value=TUTORIAL_BUILD_COMMUNITY,
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
                for n in range(2, 20)
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
        if player_name not in quest.joined_players:
            quest.add_player(player_name)
            await interaction.response.send_message(
                f"{player_name} has joined the quest!"
            )
            await self.update_embed(interaction)

            if len(quest.joined_players) == self.num_players:
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
    logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        await setup_server(guild)
        await delete_all_webhooks(guild)
    check_dirs()


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
                delete_after=VOTE_DURATION_SECONDS,
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

    if not 2 <= num_players <= 20:
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
# @commands.check(lambda ctx: False)
async def countdown(ctx, timeout_seconds, text: str = None):
    if hasattr(bot, "quest") and bot.quest.fast_mode:
        timeout_seconds = 7

    # TODO: make this better
    remaining_seconds = int(timeout_seconds)
    sleep_interval = remaining_seconds / 5

    send_new_message = True
    message = None
    seconds_elapsed = 0
    while remaining_seconds > 0:
        remaining_minutes = remaining_seconds / 60
        new_message = f"```⏳ {remaining_minutes:.2f} minutes remaining {text}.```"
        if seconds_elapsed >= 60:
            send_new_message = True
            seconds_elapsed = 0
        if send_new_message:
            message = await ctx.send(new_message)
            send_new_message = False
        else:
            await message.edit(content=new_message)

        remaining_seconds -= sleep_interval
        seconds_elapsed += sleep_interval
        await asyncio.sleep(sleep_interval)

    await message.edit(content="```⏲️ Counting down finished.```")
    print("⧗ Countdown finished.")


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
async def obscurity(ctx, mode: str = None, state: bool = None, timeout: int = None):
    """
    Control obscurity module
    """
    global OBSCURITY, OBSCURITY_MODE, OBSCURITY_ACTIVATED

    # A list of available obscurity modes
    available_modes = ["scramble", "replace_vowels", "pig_latin", "camel_case"]

    channel_culture_modes = active_global_culture_modules.get(ctx.channel, [])

    # Turn on obscurity mode if not activated
    if state:
        if "OBSCURITY" not in channel_culture_modes:
            await turn_obscurity_on(ctx, channel_culture_modes)
        else:
            return

    # Turn off obscurity mode if activated
    if not state:
        if timeout == None:
            if "OBSCURITY" in channel_culture_modes:
                await turn_obscurity_off(ctx, channel_culture_modes)
            else:
                return
        if timeout is not None:
            if "OBSCURITY" in channel_culture_modes:
                OBSCURITY = None
                await turn_obscurity_off(ctx, channel_culture_modes)
                countdown_message = "until obscurity turns back on"
                await countdown(ctx, timeout, countdown_message)
            if not OBSCURITY_ACTIVATED:
                OBSCURITY = True
                await turn_obscurity_on(ctx, channel_culture_modes)
            else:
                return

    # Toggle obscurity mode and set global state
    if state == None:
        if mode is None:
            if "OBSCURITY" not in channel_culture_modes:
                OBSCURITY = True
                await turn_obscurity_on(ctx, channel_culture_modes)
            else:
                OBSCURITY = False
                await turn_obscurity_off(ctx, channel_culture_modes)
        elif mode not in available_modes:
            embed = discord.Embed(
                title=f"Error - The mode '{mode}' is not available.",
                color=discord.Color.red(),
            )
        else:
            OBSCURITY_MODE = mode
            if "OBSCURITY" not in channel_culture_modes:
                await turn_obscurity_on(ctx, channel_culture_modes)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def eloquence(ctx, state: bool = None, timeout: int = None):
    """
    Control eloquence module
    """
    global ELOQUENCE, ELOQUENCE_ACTIVATED

    channel_culture_modes = active_global_culture_modules.get(ctx.channel, [])

    # Turn on eloquence mode if not activated
    if state == True:
        if "ELOQUENCE" not in channel_culture_modes:
            await turn_eloquence_on(ctx, channel_culture_modes)
        else:
            return

    # Turn off eloquence mode if activated
    if state == False:
        if timeout == None:
            if "ELOQUENCE" in channel_culture_modes:
                await turn_eloquence_off(ctx, channel_culture_modes)
            else:
                return
        if timeout is not None:
            if "ELOQUENCE" in channel_culture_modes:
                ELOQUENCE = None
                await turn_eloquence_off(ctx, channel_culture_modes)
                countdown_message = "until eloquence turns back on"
                await countdown(ctx, timeout, countdown_message)
            if not ELOQUENCE_ACTIVATED:
                ELOQUENCE = True
                await turn_eloquence_on(ctx, channel_culture_modes)
            else:
                return

    # Toggle eloquence mode and set global state
    if state == None:
        if "ELOQUENCE" not in channel_culture_modes:
            ELOQUENCE = True
            await turn_eloquence_on(ctx, channel_culture_modes)
        else:
            ELOQUENCE = False
            await turn_eloquence_off(ctx, channel_culture_modes)


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def diversity(ctx):
    """
    Toggle diversity module
    """
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


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-agora"))
async def ritual(ctx):
    """
    Toggle ritual module.
    """
    global RITUAL
    RITUAL = not RITUAL
    if RITUAL:
        if "RITUAL" not in active_global_culture_modules:
            active_global_culture_modules.append("RITUAL")
            embed = discord.Embed(
                title="Culture: ritual", color=discord.Color.dark_gold()
            )
            # embed.set_thumbnail(
            #     url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/ritual.png"
            # )
            embed.add_field(
                name="ACTIVATED:",
                value="A ritual of agreement permeates throughout the group.",
                inline=False,
            )
            embed.add_field(
                name="ACTIVE CULTURE MODES:",
                value=f"{', '.join(active_global_culture_modules)}",
                inline=False,
            )
            await ctx.send(embed=embed)
    else:
        active_global_culture_modules.remove("RITUAL")
        embed = discord.Embed(title="Culture: ritual", color=discord.Color.dark_gold())
        # embed.set_thumbnail(
        #     url="https://raw.githubusercontent.com/metagov/d20-governance/main/assets/imgs/embed_thumbnails/ritual.png"
        # )
        embed.add_field(
            name="DEACTIVATED",
            value="Automatic agreement has ended. But will the effects linger in practice?",
            inline=False,
        )
        embed.add_field(
            name="ACTIVE CULTURE MODES:",
            value=f"{', '.join(active_global_culture_modules)}",
            inline=False,
        )
        await ctx.send(embed=embed)


@bot.command(hidden=True)
@commands.check(lambda ctx: False)
async def secret_message(ctx):
    """
    Secrecy: Randomly Send Messages to DMs
    """
    print("Secret message command triggered.")
    await send_msg_to_random_player(bot.quest.game_channel)


@bot.command(hidden=True)
@commands.check(lambda ctx: False)
async def vote_governance(ctx, governance_type: str):
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
@commands.check(lambda ctx: False)
async def post_results(ctx):
    await ctx.send("post_results")
    pass


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
async def nickname(ctx):
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


@bot.command()
@access_control()
async def stack(ctx):
    """
    Post governance stack
    """
    await post_governance(ctx)


@bot.command()
async def quit(ctx):
    """
    Individually quit the quest
    """
    print("Quiting...")
    await ctx.send(f"{ctx.author.name} has quit the game!")
    # TODO: Implement the logic for quitting the game and ending it for the user


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


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def is_quiet(ctx):
    global IS_QUIET
    IS_QUIET = True
    print("Quiet mode is on.")


@bot.command(hidden=True)
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def is_not_quiet(ctx):
    global IS_QUIET
    IS_QUIET = False
    print("Quiet mode is off.")


# MISC COMMANDS
@bot.command()
@access_control()
async def submit(ctx, *, text: str):
    # delete the user's message
    await ctx.message.delete()
    bot.quest.add_submission(ctx, text)
    if bot.quest.mode != MINIGAME_JOSH:
        await ctx.send(f"Added {ctx.author.name}'s submission to the list!")
        return
    else:
        nickname = bot.quest.get_nickname(ctx.author.name)
        await ctx.send(f"Added {nickname}'s submission to the list!")


@bot.command(hidden=True)
@commands.check(lambda ctx: False)
async def post_submissions(ctx):
    submissions = []
    players_to_submissions = bot.quest.players_to_submissions
    title = "Submissions:"

    # Go through all nicknames and their submissions
    for player_name, submission in players_to_submissions.items():
        # Append a string formatted with the nickname and their submission
        submissions.append(f"📜**{player_name}**:\n\n   🗣️ {submission}")

    # Join all submissions together with a newline in between each one
    formatted_submissions = "\n\n\n".join(submissions)

    embed = discord.Embed(
        title=title, description=formatted_submissions, color=discord.Color.dark_teal()
    )

    # Send the formatted submissions to the context
    await ctx.send(embed=embed)


@bot.command(hidden=True)
# @commands.check(lambda ctx: False)
async def vote_submissions(ctx, question: str, timeout="20"):
    # Get all keys (player_names) from the players_to_submissions dictionary and convert it to a list
    contenders = list(bot.quest.players_to_submissions.values())
    quest = bot.quest
    await vote(ctx, quest, question, contenders, int(timeout))
    # Reset the players_to_submissions dictionary for the next round
    bot.quest.reset_submissions()


# CLEANING COMMANDS
@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def clean(ctx):
    """
    Clean the temporary files
    """
    clean_temp_files()


@bot.command()
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
async def solo(ctx, *args, quest_mode=TUTORIAL_BUILD_COMMUNITY):
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


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_randomize_snapshot(ctx):
    """
    Test making a randomized governance snapshot
    """
    shuffle_modules()
    make_governance_snapshot()


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_png_creation(ctx):
    """
    Test governance stack png creation
    """
    make_governance_snapshot()
    with open("output.png", "rb") as f:
        png_file = discord.File(f, "output.svg")
        await ctx.send(file=png_file)


@bot.command()
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


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_culture(ctx):
    """
    A way to test and demo the culture messaging functionality
    """
    await vote_governance(ctx, "culture")


@bot.command()
@commands.check(lambda ctx: check_cmd_channel(ctx, "d20-testing"))
async def test_decision(ctx):
    """
    Test and demo the decision message functionality
    """
    await vote_governance(ctx, "decision")


@bot.command(hidden=True)
@access_control()
async def ping(ctx):
    """
    A ping command for testing
    """
    await ctx.send("Pong!")


# /change_access_control allowed_roles [] info
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
    print(
        f"⁂ Invoked: `/{ctx.command.name}` in channel `{ctx.channel.name}`, ID: {ctx.channel.id}"
    )


@bot.event
async def on_command_error(ctx, error):
    traceback_text = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    error_message = f"Error invoking command: {ctx.command.name if ctx.command else 'Command does not exist'} - {error}\n{traceback_text}"
    print(error_message)
    logging.error(error_message)
    await ctx.send("An error occurred.")


@bot.event
async def on_error(event):
    type, value, tb = sys.exc_info()
    traceback_str = "".join(traceback.format_exception(type, value, tb))
    print(f"Unhandled exception in {event}:\n{traceback_str}")
    logging.error(f"Unhandled exception in {event}:\n{traceback_str}")


# MESSAGE PROCESSING
async def create_webhook(channel):
    global webhooks
    webhook = None
    for wh in webhooks:
        if wh.channel.id == channel.id:
            webhook = wh

    if not webhook:
        webhook = await channel.create_webhook(name="InternalWebhook")
        webhooks.append(webhook)

    return webhook


async def send_webhook_message(webhook, message, filtered_message):
    payload = {
        "content": f"※ {filtered_message}",
        "username": message.author.name,
        "avatar_url": message.author.avatar.url if message.author.avatar else None,
    }
    await webhook.send(**payload)


async def process_message(message):
    # Increment message count for the user (for /diversity)
    user_id = message.author.id
    if user_id not in user_message_count:
        user_message_count[user_id] = 0
    user_message_count[user_id] += 1

    if IS_QUIET and not message.author.bot:
        await message.delete()
    else:
        # Assign message content to be filtered
        filtered_message = message.content

        # Check if any modes are active deleted the original message
        channel_culture_modes = active_global_culture_modules.get(message.channel, [])
        if channel_culture_modes:
            await message.delete()
            filtered_message = await apply_culture_modes(
                channel_culture_modes, message, filtered_message
            )
            webhook = await create_webhook(message.channel)
            await send_webhook_message(webhook, message, filtered_message)


async def apply_culture_modes(modes, message, filtered_message):
    for mode in modes:
        if mode == "RITUAL":
            # Get the most recently posted message in the channel that isn't from a bot
            async for msg in message.channel.history(limit=100):
                if msg.id == message.id:
                    continue
                if msg.author.bot:
                    continue
                if msg.content.startswith("/"):
                    continue
                previous_message = msg.content
                break
            filtered_message = await initialize_ritual_agreement(
                previous_message, filtered_message
            )
        if mode == "OBSCURITY":
            obscure_function = Obscurity(filtered_message)
            if OBSCURITY_MODE == "scramble":
                filtered_message = obscure_function.scramble()
            if OBSCURITY_MODE == "replace_vowels":
                filtered_message = obscure_function.replace_vowels()
            if OBSCURITY_MODE == "pig_latin":
                filtered_message = obscure_function.pig_latin()
            if OBSCURITY_MODE == "camel_case":
                filtered_message = obscure_function.camel_case()
        if mode == "ELOQUENCE":
            filtered_message = await filter_eloquence(filtered_message)
    return filtered_message


# GOVERNANCE INPUT
@bot.command()
async def show_governance_status(ctx):
    await display_culture_status(ctx)
    await display_decision_status(ctx)


async def clear_decision_status(ctx):
    for input_key in decision_inputs:
        decision_inputs[input_key] = 0


async def update_module_decision(context, new_decision_module):
    channel_decision_modules = active_global_culture_modules.get(context.channel, [])
    if len(channel_decision_modules) > 0:
        channel_decision_modules = []
        channel_decision_modules.append(new_decision_module)
        active_global_decision_modules[context.channel] = channel_decision_modules
    else:
        channel_decision_modules.append(new_decision_module)
        active_global_decision_modules[context.channel] = channel_decision_modules


async def calculate_module_inputs(context, retry=None, tally=None):
    """
    Change state of modules based on calculation of module inputs
    """
    # Calculate decision inputs if retry True
    if retry:
        max_value = max(decision_inputs.values())
        max_keys = [k for k, v in decision_inputs.items() if v == max_value]

        if not tally:
            if max_value == SPECTRUM_SCALE and len(max_keys) == 1:
                await update_module_decision(context, max_keys[0])
                await context.send(f"```{max_keys[0]} mode activated!```")
                return True

        else:
            if len(max_keys) > 1:
                await context.send(
                    f"```Poll resulted in tie. Previous decision module kept.```"
                )
            else:
                await update_module_decision(context, max_keys[0])
                await context.send(f"```{max_keys[0]} mode activated!```")

    # Calculate culture inputs
    for input_key in culture_inputs:
        global_key = globals()[input_key.upper()]
        # TODO: Is there a better way of changing the global variable dynamically
        # I tried global_key_activation = globals()[input_key.upper() + "_ACTIVATED"]
        # But global_key_activation shadows the global var and doesn't change the global bool value
        if (
            not globals()[input_key.upper() + "_ACTIVATED"]
            and culture_inputs[input_key] > SPECTRUM_THRESHOLD
        ):
            globals()[input_key.upper() + "_ACTIVATED"] = True
            if not global_key:
                function_to_call = globals().get(input_key)
                await function_to_call(context, state=True)
            if global_key:
                await context.send(
                    f"```{input_key.capitalize()} mode already activated!```"
                )
            if global_key == None:
                function_to_call = globals().get(input_key)
                await function_to_call(context)
        elif (
            globals()[input_key.upper() + "_ACTIVATED"]
            and culture_inputs[input_key] <= SPECTRUM_THRESHOLD
        ):
            globals()[input_key.upper() + "_ACTIVATED"] = False
            if not global_key:
                function_to_call = globals().get(input_key)
                await function_to_call(context, state=False)
            else:
                function_to_call = globals().get(input_key)
                await function_to_call(context, state=False, timeout=20)
                if not globals()[input_key.upper() + "_ACTIVATED"]:
                    globals()[input_key.upper() + "_ACTIVATED"] = True
                if culture_inputs[input_key] <= SPECTRUM_THRESHOLD:
                    culture_inputs[input_key] = SPECTRUM_SCALE
                    await display_culture_status(context)


async def display_decision_status(context):
    embed = discord.Embed(
        title="Decision Display Status",
        color=discord.Color.green(),
    )

    for input_key in decision_inputs:
        input_value = decision_inputs[input_key]
        input_filled = int(min(input_value, SPECTRUM_SCALE))
        input_empty = SPECTRUM_SCALE - input_filled

        progress_bar = "🟦" * input_filled + "🟨" * input_empty

        embed.add_field(
            name=f"{input_key.capitalize()}",
            value=f"{progress_bar}",
            inline=False,
        )

    await context.send(embed=embed)
    await calculate_module_inputs(context)


async def display_culture_status(context):
    embed = discord.Embed(
        title="Culture Display Status",
        color=discord.Color.green(),
    )

    for input_key in culture_inputs:
        input_value = culture_inputs[input_key]
        input_filled = int(min(input_value, SPECTRUM_SCALE))
        input_empty = SPECTRUM_SCALE - input_filled

        progress_bar = "🟦" * input_filled + "🟨" * input_empty
        progress_bar = (
            progress_bar[:SPECTRUM_THRESHOLD] + "📍" + progress_bar[SPECTRUM_THRESHOLD:]
        )

        embed.add_field(
            name=f"{input_key.capitalize()}",
            value=f"{progress_bar}",
            inline=False,
        )

    await context.send(embed=embed)
    await calculate_module_inputs(context)


# ON MESSAGE
@bot.event
async def on_message(message):
    global VOTE_RETRY, CULTURE_COOLDOWN, DECISION_COOLDOWN
    context = await bot.get_context(message)
    try:
        if message.author == bot.user:  # Ignore messages sent by the bot itself
            return

        # Allow the "/help" command to run without channel checks
        if message.content.startswith("/help"):
            await bot.process_commands(message)
            return

        # If message is a command, proceed directly to processing
        if message.content.startswith("/"):
            await bot.process_commands(message)
            return

        # This symbold ensures webhook messages don't loop
        if message.content.startswith("※"):
            return

        for input_key in decision_inputs.keys() | culture_inputs.keys():
            if (
                message.content.lower() == f"{input_key} +1"
                or message.content.lower() == f"{input_key} -1"
            ):
                if input_key in decision_inputs:
                    if VOTE_RETRY:
                        decision_bucket = DECISION_COOLDOWN.get_bucket(message)
                        retry_after = decision_bucket.update_rate_limit()
                        if retry_after:
                            await context.send(
                                f"{context.author.mention}: Decision cooldown active, try again in {retry_after:.2f} seconds"
                            )
                            return
                        await process_decision_input(context, input_key)
                        await display_decision_status(context)
                        return
                    else:
                        return
                elif input_key in culture_inputs:
                    culture_bucket = CULTURE_COOLDOWN.get_bucket(message)
                    retry_after = culture_bucket.update_rate_limit()
                    if retry_after:
                        await context.send(
                            f"{context.author.mention}: Culture cooldown active, try again in {retry_after:.2f} seconds"
                        )
                        return
                    await process_culture_input(context, input_key)
                    await display_culture_status(context)
                    return

        await process_message(message)
    except Exception as e:
        type, value, tb = sys.exc_info()
        traceback_str = "".join(traceback.format_exception(type, value, tb))
        print(f"Unhandled exception:\n{traceback_str}")
        logging.error(f"Unhandled exception:\n{traceback_str}")
        await message.context.send("An error occurred.")


async def process_decision_input(ctx, input_key):
    if input_key in decision_inputs:
        if ctx.message.content.endswith("+1"):
            await plus_one(ctx, input_key=input_key, input_dict=decision_inputs)
        if ctx.message.content.endswith("-1"):
            await minus_one(ctx, input_key=input_key, input_dict=decision_inputs)
    else:
        await ctx.send("Invalid input key")


async def process_culture_input(ctx, input_key):
    if input_key in culture_inputs:
        if ctx.message.content.endswith("+1"):
            await plus_one(ctx, input_key=input_key, input_dict=culture_inputs)
        if ctx.message.content.endswith("-1"):
            await minus_one(ctx, input_key=input_key, input_dict=culture_inputs)
    else:
        await ctx.send("Invalid input key")


async def plus_one(ctx, input_key, input_dict):
    if input_key in input_dict:
        if input_dict[input_key] < 10:
            input_dict[input_key] += 1


async def minus_one(ctx, input_key, input_dict):
    if input_key in input_dict:
        if input_dict[input_key] > 0:
            input_dict[input_key] -= 1


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

import time
import random
import threading

import discord
from discord.ui import View

from d20_governance.utils.constants import CIRCLE_EMOJIS
from d20_governance.utils.utils import Quest, get_module_png
from d20_governance.utils.decisions import *
from d20_governance.utils.cultures import value_revision_manager, prompt_object

from typing import Any, Coroutine, List, Tuple


# Voting functions
majority = (
    lambda results: max(results, key=results.get)
    if max(results.values()) > sum(results.values()) / 2
    else None
)
consensus = (
    lambda results: max(results, key=results.get)
    if max(results.values()) == sum(results.values())
    else None
)

VOTING_FUNCTIONS = {"majority": majority, "consensus": consensus}


async def set_global_decision_module(ctx, decision_module: str = None):
    channel_decision_modules = ACTIVE_GLOBAL_DECISION_MODULES.get(ctx.channel, [])

    if len(channel_decision_modules) > 0:
        channel_decision_modules = []

    if decision_module is None and not channel_decision_modules:
        decision_module = await set_decision_module()
        print(decision_module)

    if decision_module == "random":
        decision_modules = ["majority", "consensus"]
        decision_module = random.choice(decision_modules)

    channel_decision_modules.append(decision_module)
    ACTIVE_GLOBAL_DECISION_MODULES[ctx.channel] = channel_decision_modules
    print(f"Global Decision Module set to: {channel_decision_modules}")
    return channel_decision_modules


class VoteTimeoutView(View):
    def __init__(self, ctx):
        super().__init__(timeout=15.0)
        self.ctx = ctx
        self.timeout = 0
        self.extension_triggered = False
        self.timeout_reached = False

    @discord.ui.button(
        label="Extend Vote", style=discord.ButtonStyle.green, custom_id="extend_vote"
    )
    async def extend_vote_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Extend vote duration by 60 seconds
        if not self.extension_triggered:
            vote_view = VoteView(self.ctx, self.timeout)
            await interaction.response.send_message(
                "Vote duration extended by 60 seconds."
            )
            vote_view.timeout += 60
            self.extension_triggered = True
            if vote_view:
                vote_view.set_extended(True)
            button.disabled = True
            await interaction.message.edit(view=self)
            self.stop()
        else:
            await interaction.response.send_message(
                "You've already chosen to extend the vote duration.", ephemeral=True
            )

    @discord.ui.button(
        label="No need to extend", style=discord.ButtonStyle.gray, custom_id="end_vote"
    )
    async def end_vote_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Teminate the vote timeout
        self.stop()
        await interaction.response.send_message("Noted", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction):
        # Check if the timeout has occurred
        if self.timeout_reached():
            # Disable all buttons if the timeout has occurred
            for child in self.children:
                child.disabled = True

        return await super().interaction_check(interaction)

    async def on_timeout(self):
        self.timeout_reached = True
        await self.update_buttons()

    async def update_buttons(self):
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)


class VoteView(discord.ui.View):
    def __init__(self, ctx, timeout):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.votes = {}
        self.is_extended = False

    def set_extended(self, is_extended):
        self.is_extended = is_extended

    async def on_timeout(self):
        self.stop()

    def add_option(self, label, value, emoji=None):
        option = discord.SelectOption(label=label, value=value, emoji=emoji)
        if not self.children:
            self.add_item(
                discord.ui.Select(
                    options=f"{[option]} Submission",
                    placeholder="Vote on the available options.",
                    min_values=1,
                    max_values=1,
                    custom_id="vote_select",
                )
            )
        else:
            self.children[0].options.append(option)

    @discord.ui.select(custom_id="vote_select")
    async def on_vote_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        # Enforce that only one option can be selected
        vote = interaction.data.get("values")[0]
        player = interaction.user
        if player not in self.votes or self.votes[player] != vote:
            self.votes[player] = vote
            await interaction.response.send_message(
                "Your vote has been recorded.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You've already voted.", ephemeral=True
            )
        if self.is_extended:
            await interaction.followup.send("The vote has been extended.")


async def vote(
    ctx,
    quest: Quest,
    question: str = None,
    options: List[str] = [],
    timeout: int = 60,
    topic: str = None,
    decision_module: str = None,
):
    """
    Trigger a vote
    """
    if quest.fast_mode:
        timeout = 7

    if options == None:
        print("No options recieved to vote on")
        return

    if decision_module == None:
        channel_decision_modules = ACTIVE_GLOBAL_DECISION_MODULES.get(ctx.channel, [])

        if not channel_decision_modules:
            channel_decision_modules = await set_global_decision_module(ctx)

        decision_module = channel_decision_modules[0]

    print(f"A vote has been triggered. The decision module is: {decision_module}")

    if not options:
        raise Exception("No options were provided for voting.")

    # TODO: fix
    # if len(options) > 10 or (not quest.solo_mode and len(options) < 2):
    #     await ctx.send("Error: A poll must have between 2 and 10 options.")
    #     return

    # Define embed
    embed = discord.Embed(
        title=f"Vote: {question}",
        description=f"**Decision Module:** {decision_module.capitalize()}",
        color=discord.Color.dark_gold(),
    )

    # Get module png
    module_png = await get_module_png(decision_module)

    # Add module png to vote embed
    if module_png is not None:
        print("- Attaching module png to embed")
        file = discord.File(module_png, filename="module.png")
        embed.set_image(url=f"attachment://module.png")
        print("- Module png attached to embed")

    # Create list of options with emojis
    assigned_emojis = random.sample(CIRCLE_EMOJIS, len(options))

    options_text = ""
    for i, option in enumerate(options):
        options_text += f"{assigned_emojis[i]} {option}\n"

    # Add a description of how decisions are made based on decision module
    embed.add_field(
        name=f"How decisions are made under {decision_module.capitalize()}:",
        value=DECISION_MODULES[decision_module]["description"],
        inline=False,
    )

    # Create vote view UI
    vote_view = VoteView(ctx, timeout)

    # Add options to the view dropdown select menu
    for i, option in enumerate(options):
        if len(option) > 100:
            truncated_option = option[:97] + "..."
        else:
            truncated_option = option
        # truncate the option if it's longer than 100 characters
        vote_view.add_option(
            label=f"{truncated_option}",
            value=str(i),
            emoji=assigned_emojis[i],
        )

    # Send embed message and view
    await ctx.send(embed=embed, view=vote_view)

    # Count number of members
    member_count = len(ctx.channel.members) - 1  # -1 to account for the bot
    print("member count " + str(member_count))

    # Set start time
    start_time = time.time()

    # Set time for extension option to be presented to members
    extension_time = timeout - 45

    # Init extension_triggered variable
    extension_triggered = False

    # While loop that runs for duration of vote
    while True:
        elapsed_time = time.time() - start_time
        remaining_time = timeout - elapsed_time
        print(f"Inside while vote loop: {remaining_time}")

        # If all members have voted, break out of the loop
        if len(vote_view.votes) == member_count or elapsed_time > timeout:
            break

        # Set extension_triggered to True
        if remaining_time <= extension_time and not extension_triggered:
            print("Inside extension trigger if statement")
            extension_triggered = True

            extension_view = VoteTimeoutView(ctx)
            extension_message = await ctx.send(
                "```Do you want to extend the vote duration?```", view=extension_view
            )
            try:
                await extension_view.wait()
                if extension_view.extension_triggered:
                    timeout += 60  # Extend the timeout by 60 seconds
            except asyncio.TimeoutError:
                await extension_message.delete()
                raise Exception("No winner was found")

        await asyncio.sleep(1)  # Check every second

    # Calculate total votes per member interaction
    results = await get_vote_results(ctx, vote_view.votes, options)

    # Calculate winning option if exists
    winning_option = VOTING_FUNCTIONS[decision_module](results) if results else None
    results_message = get_results_message(results, winning_option)

    # Display results
    embed = discord.Embed(
        title=f"Results for: {question}:",
        description=results_message,
        color=discord.Color.dark_gold(),
    )

    if winning_option is not None:
        decision_data = {"decision": winning_option, "decision_module": decision_module}
        DECISION_DICT[question] = decision_data
        if value_revision_manager.proposed_values_dict:
            value_revision_manager.agora_values_dict.update(
                value_revision_manager.proposed_values_dict
            )
        if topic == "group_name":
            decision_manager.group_name = winning_option
            prompt_object.group_name = winning_option
        elif topic == "group_purpose":
            prompt_object.group_purpose = winning_option
        elif topic == "group_goal":
            decision_manager.group_purpose = winning_option

    else:
        # If retried are configured, voting will be repeated
        raise Exception("No winner was found.")

    await ctx.send(embed=embed)
    return winning_option


async def get_vote_results(results, votes, options):
    print("Getting vote results")
    results = {}
    # for each member return results of vote
    for vote in votes.values():
        option_index = int(vote)
        option = options[option_index]
        results[option] = results.get(option, 0) + 1

    return results


def get_results_message(results, winning_option):
    total_votes = sum(results.values())
    message = "**Vote Breakdown:**\n\n"
    message += f"** Total votes:** {total_votes}\n\n"
    for option, votes in results.items():
        percentage = (votes / total_votes) * 100 if total_votes else 0
        message += (
            f"**Option:** {option}\n**Votes:** {votes} -- ({percentage:.2f}%)\n\n"
        )

    if winning_option:
        message += f"**Winning option:** {winning_option}\n\n"
        message += (
            "A record of all decisions can be displayed by typing `-list_decisions`"
        )
    else:
        message += "No winner was found.\n\n"

    return message

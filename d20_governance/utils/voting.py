from typing import List
import random
import discord
from d20_governance.utils.constants import CIRCLE_EMOJIS
from d20_governance.utils.utils import Quest
from d20_governance.utils.decisions import *

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
    channel_decision_modules = active_global_decision_modules.get(ctx.channel, [])

    if len(channel_decision_modules) > 0:
        channel_decision_modules = []

    if decision_module is None and not channel_decision_modules:
        decision_module = await set_decision_module()
        print(decision_module)

    channel_decision_modules.append(decision_module)
    active_global_decision_modules[ctx.channel] = channel_decision_modules
    print(
        f"Global Decision Module set to: {channel_decision_modules} and {active_global_decision_modules}"
    )
    return channel_decision_modules


class VoteView(discord.ui.View):
    def __init__(self, ctx, timeout):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.votes = {}

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
        vote = interaction.data.get("values")[
            0
        ]  # We enforce above that only one option can be selected
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


async def vote(
    ctx,
    quest: Quest,
    question: str = None,
    options: List[str] = [],
    timeout: int = 60,
):
    """
    Trigger a vote
    """
    channel_decision_modules = active_global_decision_modules.get(ctx.channel, [])

    if not channel_decision_modules:
        channel_decision_modules = await set_global_decision_module(ctx)

    decision_module = channel_decision_modules[0]
    print(f"A vote has been triggered. The decision module is: {decision_module}")

    if not options:
        raise Exception("No options were provided for voting.")

    if len(options) > 10 or (not quest.solo_mode and len(options) < 2):
        await ctx.send("Error: A poll must have between 2 and 10 options.")
        return

    # Define embed
    embed = discord.Embed(
        title=f"Vote: {question}",
        description=f"Decision module: **{decision_module}**",
        color=discord.Color.dark_gold(),
    )

    # Create list of options with emojis
    assigned_emojis = random.sample(CIRCLE_EMOJIS, len(options))

    options_text = ""
    for i, option in enumerate(options):
        options_text += f"{assigned_emojis[i]} {option}\n"

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
            label=truncated_option,
            value=str(i),
            emoji=assigned_emojis[i],
        )

    # Send embed message and view
    await ctx.send(embed=embed, view=vote_view)
    await vote_view.wait()

    # Calculate total votes per member interaction
    results = await get_vote_results(ctx, vote_view.votes, options)

    # Calculate winning option if exists
    winning_option = VOTING_FUNCTIONS[decision_module](results) if results else None
    results_message = get_results_message(results, winning_option)

    # Display results
    embed = discord.Embed(
        title=f"Results for: `{question}`:",
        description=results_message,
        color=discord.Color.dark_gold(),
    )

    # If retries are configured, voting will be repeated
    if winning_option is None:
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
    message = f"Total votes: {total_votes}\n\n"
    for option, votes in results.items():
        percentage = (votes / total_votes) * 100 if total_votes else 0
        message += f"Option `{option}` received `{votes}` votes ({percentage:.2f}%)\n\n"

    if winning_option:
        message += f"The winner is `{winning_option}`.\n\n"
    else:
        message += "No winner was found.\n\n"

    return message

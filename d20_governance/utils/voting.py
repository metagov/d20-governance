from typing import List
import random
import discord
from d20_governance.utils.constants import CIRCLE_EMOJIS, PROPOSED_VALUES_DICT
from d20_governance.utils.utils import Quest, get_module_png
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
    channel_decision_modules = ACTIVE_GLOBAL_DECISION_MODULES.get(ctx.channel, [])

    if len(channel_decision_modules) > 0:
        channel_decision_modules = []

    if decision_module is None and not channel_decision_modules:
        decision_module = await set_decision_module()
        print(decision_module)

    channel_decision_modules.append(decision_module)
    ACTIVE_GLOBAL_DECISION_MODULES[ctx.channel] = channel_decision_modules
    print(
        f"Global Decision Module set to: {channel_decision_modules} and {ACTIVE_GLOBAL_DECISION_MODULES}"
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
    if quest.fast_mode:
        timeout = 7

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
        print("Attaching module png to embed")
        file = discord.File(module_png, filename="module.png")
        embed.set_image(url=f"attachment://module.png")
        print("Module png attached to embed")

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
            label=truncated_option,
            value=str(i),
            emoji=assigned_emojis[i],
        )

    # Send embed message and view
    await ctx.send(embed=embed, file=file, view=vote_view)
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

    if winning_option is not None:
        decision_data = {"decision": winning_option, "decision_module": decision_module}
        DECISION_DICT[question] = decision_data
        if PROPOSED_VALUES_DICT:
            VALUES_DICT.update(PROPOSED_VALUES_DICT)

    else:
        # If retries are configured, voting will be repeated
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
    message += f"** Total votes:** `{total_votes}`\n\n"
    for option, votes in results.items():
        percentage = (votes / total_votes) * 100 if total_votes else 0
        message += (
            f"**Option:** `{option}`\n** Votes:** `{votes}` -- ({percentage:.2f}%)\n\n"
        )

    if winning_option:
        message += f"**Winning option:** `{winning_option}`\n\n"
        message += (
            "A record of all decisions can be displayed by typing `-show_decisions`"
        )
    else:
        message += "No winner was found.\n\n"

    return message

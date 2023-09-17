from abc import ABC, abstractmethod
import asyncio
import time
from typing import Any, List, Tuple
import random
from attr import dataclass
import threading

import discord
from discord.ui import View

from d20_governance.utils.decisions import *
from d20_governance.utils.constants import (
    CIRCLE_EMOJIS,
    DECISION_DICT,
    GOVERNANCE_SVG_ICONS,
)
from d20_governance.utils.utils import (
    decision_manager,
    Quest,
    add_module_to_stack,
    get_current_governance_stack,
    get_modules_for_type,
    make_module_png,
)
from d20_governance.utils.cultures import (
    CULTURE_MODULES,
    value_revision_manager,
    prompt_object,
)

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

from d20_governance.utils.constants import (
    CIRCLE_EMOJIS,
    DECISION_DICT,
    GOVERNANCE_SVG_ICONS,
)
from d20_governance.utils.utils import (
    decision_manager,
    Quest,
    add_module_to_stack,
    get_current_governance_stack,
    get_modules_for_type,
    make_module_png,
)
from d20_governance.utils.cultures import (
    CULTURE_MODULES,
    value_revision_manager,
    prompt_object,
)


async def get_module_png(module):
    """
    Get module png from make_module_png function based on module
    """
    print("Getting module png")
    modules = {**DECISION_MODULES, **CULTURE_MODULES}

    if module in modules:
        name = modules[module]["name"]
        svg_icon = modules[module]["icon"]
        image_url = await make_module_png(name, svg_icon)
        return image_url
    else:
        print(f"Module {module} not found in module dictionaries")
        return None


class VoteStateManager:
    def __init__(self):
        self.question = ""


vote_state_manager = VoteStateManager()


class VoteFailedException(Exception):
    """
    Raised when a vote fails to produce a clear winner.
    """

    pass


@dataclass
class VoteContext:
    send_message: Any
    member_count: int
    ctx: Any = None
    options: List[str] = []
    question: str = None
    topic: str = None
    timeout: int = 60
    quest: Quest = None
    decision_module_name: str = None

    @staticmethod
    def create(send_message, member_count, **kwargs):
        return VoteContext(
            send_message=send_message,
            member_count=member_count,
            ctx=kwargs.get("ctx"),
            options=kwargs.get("options", []),
            question=kwargs.get("question"),
            topic=kwargs.get("topic"),
            timeout=kwargs.get("timeout", 60),
            quest=kwargs.get("quest"),
            decision_module_name=kwargs.get("decision_module_name"),
        )


class DecisionModule(ABC):
    def __init__(self, config):
        self.config = config

    def __getitem__(self, key):
        return self.config[key]

    def _get_results_message(self, results):
        total_votes = sum(results.values())
        message = "**Vote Breakdown:**\n\n"
        message += f"** Total votes:** {total_votes}\n\n"
        for option, votes in results.items():
            percentage = (votes / total_votes) * 100 if total_votes else 0
            message += (
                f"**Option:** {option}\n**Votes:** {votes} -- ({percentage:.2f}%)\n\n"
            )

        if self.winning_option:
            message += f"**Winning option:** {self.winning_option}\n\n"
            message += (
                "A record of all decisions can be displayed by typing `-list_decisions`"
            )
        else:
            message += "No winner was found.\n\n"

        return message

    async def get_vote_result(self, vote_context: VoteContext):
        if self.vote_view is None:
            raise ValueError("No vote view set")

        await self._wait_for_votes_or_timeout(
            vote_context.member_count, vote_context.timeout
        )

        # Tally votes
        results = self._tally_votes(vote_context.options)

        winning_option = (
            self.get_winning_option(vote_context, results) if results else None
        )
        self.vote_view = None

        if winning_option is None:
            # If retries are configured, voting will be repeated
            await vote_context.send_message("No winner was found.")
            raise VoteFailedException("No winner was found.")

        self.winning_option = winning_option
        self.record_vote_result(vote_context.question, vote_context.topic)
        return self._get_results_message(results), winning_option

    async def _wait_for_votes_or_timeout(self, member_count, timeout):
        start_time = time.time()
        while True:
            elapsed_time = time.time() - start_time
            if len(self.vote_view.votes) == member_count or elapsed_time > timeout:
                break
            await asyncio.sleep(1)

    def _tally_votes(self, options):
        results = {}
        votes = self.vote_view.votes
        for vote in votes.values():
            option_index = int(vote)
            option = options[option_index]
            results[option] = results.get(option, 0) + 1
        return results

    async def create_vote_view(self, vote_context, embed, file):
        # Create list of options with emojis
        assigned_emojis = random.sample(CIRCLE_EMOJIS, len(vote_context.options))

        options_text = ""
        for i, option in enumerate(vote_context.options):
            options_text += f"{assigned_emojis[i]} {option}\n"

        # Create vote view UI
        vote_view = VoteView(vote_context.timeout)

        # Add options to the view dropdown select menu
        for i, option in enumerate(vote_context.options):
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
        await vote_context.send_message(embed=embed, file=file, view=vote_view)
        self.vote_view = vote_view
        return vote_view

    def record_vote_result(self, question, topic):
        winning_option = self.winning_option
        decision_data = {"decision": winning_option, "decision_module": self["name"]}
        DECISION_DICT[question] = decision_data
        if topic == "group_name":
            decision_manager.group_name = winning_option
            prompt_object.group_name = winning_option
        elif topic == "group_purpose":
            prompt_object.group_purpose = winning_option
        elif topic == "group_goal":
            decision_manager.group_purpose = winning_option

    @abstractmethod
    def get_winning_option(self, vote_context, results):
        pass


class Majority(DecisionModule):
    def __init__(self, config):
        super().__init__(config)

    def get_winning_option(self, vote_context, results):
        if max(results.values()) > (sum(results.values()) / 2):
            return max(results, key=results.get)
        else:
            return None


class Consensus(DecisionModule):
    def __init__(self, config):
        super().__init__(config)

    def get_winning_option(self, vote_context, results):
        # All players must have voted, and all votes must be the same
        num_votes = sum(results.values())
        max_votes = max(results.values())
        if max_votes == num_votes and num_votes == vote_context.member_count:
            return max(results, key=results.get)
        else:
            return None


# TODO: make this handle more generic options than key-value pairs
class LazyConsensus(DecisionModule):
    def __init__(self, config):
        super().__init__(config)

    def __getitem__(self, key):
        return self.config[key]

    async def create_vote_view(self, vote_context, embed, file):
        views = []
        for name, description in vote_context.options.items():
            view = LazyConsensusView(name, vote_context.timeout)
            views.append(view)
            message = await vote_context.send_message(
                f"**Name:** {name}\n**Description:** {description}", view=view
            )
            view.set_message(message)

        await asyncio.gather(*(view.wait() for view in views))
        self.views = views
        return views

    async def get_vote_result(self, vote_context: VoteContext):
        non_objection_options = {
            view.option: vote_context.options[view.option]
            for view in self.views
            if not view.objections and view.option in vote_context.options
        }
        self.winning_options = non_objection_options
        self.record_vote_result(vote_context.question, vote_context.topic)
        return (
            self._get_results_message(vote_context.options, non_objection_options),
            non_objection_options,
        )

    def _get_results_message(self, all_options, non_objection_options):
        messages = []
        for name, description in all_options.items():
            status = "Accepted" if name in non_objection_options else "Rejected"
            messages.append(f"**{name}: {status}** ")
        return "\n".join(messages)

    def record_vote_result(self, question, topic=None):
        decision_data = {
            "decision": self.winning_options,
            "decision_module": self["name"],
        }
        DECISION_DICT[question] = decision_data

    def get_winning_option(self, vote_context, results):
        pass


class LazyConsensusView(discord.ui.View):
    def __init__(self, option, timeout):
        super().__init__(timeout=timeout)
        self.option = option
        self.objections = {}

    @discord.ui.button(
        style=discord.ButtonStyle.red, label="Object", custom_id="object_button"
    )
    async def object_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Record the user's objection
        self.objections[interaction.user] = True
        await interaction.response.send_message(
            "Your objection has been recorded.", ephemeral=True
        )

    def set_message(self, message):
        self.message = message

    async def on_timeout(self):
        # Disable the button after the timeout
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        # Update the message to reflect the change
        await self.message.edit(view=self)


async def set_decision_module():
    # Set starting decision module if necessary
    current_modules = get_current_governance_stack()["modules"]
    decision_module = next(
        (module for module in current_modules if module["type"] == "decision"), None
    )
    if decision_module is None:
        await set_starting_decision_module()

    return decision_module


async def set_starting_decision_module():
    print("Randomly assigning a starting decision module")
    decision_modules = get_modules_for_type("decision")
    if decision_modules:  # Check if decision_modules is not empty
        rand = random.randint(0, len(decision_modules) - 1)
        selected_module = decision_modules[rand]
        print(f"The selected module is: {selected_module}")
    else:
        raise ValueError("No decision modules available to choose from")
    add_module_to_stack(selected_module)


ACTIVE_GLOBAL_DECISION_MODULES = {}

DECISION_MODULES = {
    "majority": Majority(
        {
            "name": "majority",
            "description": "Majority requires a simiple majority from the number of people who voteon the options.",
            "state": False,
            "activated": False,
            "activated_message": "",
            "deactivated_message": "",
            "url": "",  # TODO: make decision img
            "icon": GOVERNANCE_SVG_ICONS["decision"],
            "input_value": 0,
            "valid_for_continuous_input": True,
        }
    ),
    "consensus": Consensus(
        {
            "name": "consensus",
            "description": "Consensus requires everyone in the simulation to vote on the same option.",
            "state": False,
            "activated": False,
            "activated_message": "",
            "deactivated_message": "",
            "url": "",  # TODO: make decision img
            "icon": GOVERNANCE_SVG_ICONS["decision"],
            "input_value": 0,
            "valid_for_continuous_input": True,
        }
    ),
    "lazy_consensus": LazyConsensus(
        {
            "name": "lazy consensus",
            "description": "Lazy consensus decision-making allows options to pass by default unless they are objected to.",
            "state": False,
            "activated": False,
            "activated_message": "",
            "deactivated_message": "",
            "url": "",  # TODO: make decision img
            "icon": GOVERNANCE_SVG_ICONS["decision"],
            "input_value": 0,
            "valid_for_continuous_input": False,
        }
    ),
}

CONTINUOUS_INPUT_DECISION_MODULES = {
    module: attributes
    for module, attributes in DECISION_MODULES.items()
    if attributes["valid_for_continuous_input"]
}


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
    def __init__(self, timeout):
        super().__init__(timeout=timeout)
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


async def vote(vote_context: VoteContext):
    """
    Trigger a vote
    """
    if vote_context.quest is not None:
        if vote_context.quest.fast_mode:
            vote_context.timeout = 7

    if vote_context.decision_module_name is None:
        channel_decision_modules = ACTIVE_GLOBAL_DECISION_MODULES.get(
            vote_context.ctx.channel, []
        )

        if not channel_decision_modules:
            channel_decision_modules = await set_global_decision_module(
                vote_context.ctx
            )

        vote_context.decision_module_name = channel_decision_modules[0]

    decision_module: DecisionModule = DECISION_MODULES[
        vote_context.decision_module_name
    ]
    print(
        f"A vote has been triggered. The decision module is: {vote_context.decision_module_name}"
    )

    if not vote_context.options:
        raise Exception("No options were provided for voting.")

    # Define embed
    embed = discord.Embed(
        title=f"Vote: {vote_context.question}",
        description=f"**Decision Module:** {vote_context.decision_module_name.capitalize()}",
        color=discord.Color.dark_gold(),
    )

    # Get module png
    module_png = await get_module_png(vote_context.decision_module_name)

    # Add module png to vote embed
    if module_png is not None:
        print("- Attaching module png to embed")
        file = discord.File(module_png, filename="module.png")
        embed.set_image(url=f"attachment://module.png")
        print("Module png attached to embed")

    # Add a description of how decisions are made based on decision module
    embed.add_field(
        name=f"How decisions are made under {vote_context.decision_module_name.capitalize()}:",
        value=DECISION_MODULES[vote_context.decision_module_name]["description"],
        inline=False,
    )

    await decision_module.create_vote_view(vote_context, embed, file)

    # member_count = len(vote_context.ctx.channel.members) - 1  # -1 to account for the bot

    results_message, winning_option = await decision_module.get_vote_result(
        vote_context
    )

    # Display results
    embed = discord.Embed(
        title=f"Results for: {vote_context.question}",
        description=results_message,
        color=discord.Color.dark_gold(),
    )

    if winning_option is not None:
        decision_data = {"decision": winning_option, "decision_module": decision_module}
        DECISION_DICT[vote_context.question] = decision_data
        if value_revision_manager.proposed_values_dict:
            value_revision_manager.agora_values_dict.update(
                value_revision_manager.proposed_values_dict
            )
        if vote_context.topic == "group_name":
            decision_manager.group_name = winning_option
            prompt_object.group_name = winning_option
        elif vote_context.topic == "group_purpose":
            prompt_object.group_purpose = winning_option
        elif vote_context.topic == "group_goal":
            decision_manager.group_purpose = winning_option

    else:
        # If retried are configured, voting will be repeated
        raise Exception("No winner was found.")

    await vote_context.ctx.send(embed=embed)
    return winning_option

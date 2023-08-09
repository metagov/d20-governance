from abc import ABC, abstractmethod
from d20_governance.utils.constants import *
from d20_governance.utils.utils import *
import random

class DecisionModule(ABC):
    def __init__(self, config):
        self.config = config 

    @property
    @abstractmethod
    def create_vote_view(self):
        pass

    @abstractmethod
    def get_decision_result(self):
        pass

class Majority(DecisionModule):
    def __init__(self, config):
        super().__init__(config)

    @property
    def create_vote_view(self):
        pass

    def get_decision_result(self, results):
        if max(results.values()) > (sum(results.values()) / 2):
            return max(results, key=results.get) 
        else:
            return None

class Consensus(DecisionModule):
    def __init__(self, config):
        super().__init__(config)

    @property
    def create_vote_view(self):
        pass

    def get_decision_result(self, quest: Quest, results):
        # All players must have voted, and all votes must be the same
        num_votes = sum(results.values())
        num_players = len(quest.joined_players)
        max_votes = max(results.values())
        if max_votes == num_votes and num_votes == num_players:
            return max(results, key=results.get) 
        else:
            return None

class ConsentView(discord.ui.View):
    def __init__(self, ctx, option, timeout=60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.option = option
        self.objections = {}

    @discord.ui.button(
        style=discord.ButtonStyle.red, label="Object", custom_id="object_button"
    )
    async def object_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Record the user's objection
        self.objections[interaction.user] = True
        await interaction.response.send_message("Your objection has been recorded.", ephemeral=True)

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

async def consent(ctx, quest: Quest, question, options, timeout: int = 60):
    if quest.fast_mode:
        timeout = 7

    # Send introduction embed
    embed = discord.Embed(
        title=f"Vote: {question}",
        description="**Decision Module:** Consent",
        color=discord.Color.dark_gold(),
    )

    # Get module png
    module_png = await get_module_png("consent") # TODO: fix, reconcile with other modules

    # Add module png to vote embed
    if module_png is not None:
        print("Attaching module png to embed")
        embed.set_image(url=f"attachment://module.png")
        file = discord.File(module_png, filename="module.png")
        print("Module png attached to embed")

    # Add a description of how decisions are made based on decision module
    embed.add_field(
        name=f"How decisions are made under consent:",
        value=DECISION_MODULES["consent"]["description"],
        inline=False,
    )

    await ctx.send(embed=embed, file=file)

    views = []
    for name, description in options.items():
        # Create a new ConsentView for this option
        view = ConsentView(ctx, name, timeout=timeout)
        views.append(view)

        # Display the option name, description and associated view to the user
        await ctx.send(f"**Name:** {name}\n**Description:** {description}", view=view)

    # Wait for all views to finish
    await asyncio.gather(*(view.wait() for view in views))

    # Determine the options that had no objections
    non_objection_options = {view.option: options[view.option] for view in views if not view.objections}

    # Iterate over the non_objection_options dict and format the name and description for each
    results_message = "\n".join(f"**{name}:** {description}" for name, description in non_objection_options.items())

    # Display results
    embed = discord.Embed(
        title=f"Results for: `{question}`:",
        description=results_message,
        color=discord.Color.dark_gold(),
    )
    
    await ctx.send(embed=embed)

    return non_objection_options


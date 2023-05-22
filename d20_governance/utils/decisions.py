from d20_governance.utils.constants import *
from d20_governance.utils.utils import *
import discord
import random


async def execute_action(bot, action_string, temp_channel):
    command_name, *args = parse_action_string(action_string.lower())
    command = bot.get_command(command_name)

    # Get the last message object from the channel to set context
    message_obj = await temp_channel.fetch_message(temp_channel.last_message_id)
    
    # Create a context object for the message
    ctx = await bot.get_context(message_obj)

    return await command.callback(ctx, *args)


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

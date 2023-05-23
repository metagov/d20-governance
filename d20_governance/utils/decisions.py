from d20_governance.utils.constants import *
from d20_governance.utils.utils import *
import discord
import random


async def execute_action(bot, action_string, temp_channel):
    command_name, *args = parse_action_string(action_string.lower())
    command = bot.get_command(command_name)
    if command is None:
        return

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


async def set_starting_decision_module():
    print("Randomly assigning a starting decision module")
    decision_modules = get_modules_for_type("decision")
    if decision_modules:  # Check if decision_modules is not empty
        rand = random.randint(0, len(decision_modules)-1)
        selected_module = decision_modules[rand]
        print(f"The selected module is: {selected_module}")
    else:
        raise ValueError("No decision modules available to choose from")
    add_module_to_stack(selected_module)

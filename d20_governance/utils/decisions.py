from d20_governance.utils.constants import *
from d20_governance.utils.utils import *
import discord
import random


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
        rand = random.randint(0, len(decision_modules) - 1)
        selected_module = decision_modules[rand]
        print(f"The selected module is: {selected_module}")
    else:
        raise ValueError("No decision modules available to choose from")
    add_module_to_stack(selected_module)

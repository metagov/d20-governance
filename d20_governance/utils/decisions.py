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


async def set_global_governance(decision_module: str = None):
    global GLOBAL_DECISION_MODULE
    if decision_module is None and GLOBAL_DECISION_MODULE is None:
        GLOBAL_DECISION_MODULE = await set_decision_module()
    GLOBAL_DECISION_MODULE = decision_module
    print(f"Global Decision Module set to: {GLOBAL_DECISION_MODULE}")


async def set_decision_module():
    # Set starting decision module if necessary
    global DECISION_MODULE
    current_modules = get_current_governance_stack()["modules"]
    decision_module = next(
        (module for module in current_modules if module["type"] == "decision"), None
    )
    if decision_module is None:
        await set_starting_decision_module()

    DECISION_MODULE = decision_module

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

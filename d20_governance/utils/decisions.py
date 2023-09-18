from abc import ABC, abstractmethod
import time
from typing import Any, Dict

from attr import dataclass
from d20_governance.utils.constants import *
from d20_governance.utils.cultures import prompt_object
from d20_governance.utils.utils import *
from d20_governance.utils.decisions import *
import random

from d20_governance.utils.voting import VoteContext, VoteView



# async def lazy_consensus(
#     ctx=None, channel=None, quest=None, question=None, options=None, timeout: int = 60
# ):
#     if quest is not None:
#         if quest.fast_mode:
#             timeout = 7

#     if ctx is not None:
#         send_message = ctx.send
#     else:
#         send_message = channel.send

#     # Send introduction embed
#     embed = discord.Embed(
#         title=f"Vote: {question}",
#         description="**Decision Module:** Lazy Consensus",
#         color=discord.Color.dark_gold(),
#     )

#     # Get module png
#     module_png = await get_module_png(
#         "lazy_consensus"
#     )  # TODO: fix, reconcile with other modules

#     # Add module png to vote embed
#     if module_png is not None:
#         print("Attaching module png to embed")
#         embed.set_image(url=f"attachment://module.png")
#         file = discord.File(module_png, filename="module.png")
#         print("Module png attached to embed")

#     # Add a description of how decisions are made based on decision module
#     embed.add_field(
#         name=f"How decisions are made under lazy consensus:",
#         value=DECISION_MODULES["lazy_consensus"]["description"],
#         inline=False,
#     )

#     await send_message(embed=embed, file=file)

#     # TODO: maybe all of this can be done in create vote views
#     views = []
#     for name, description in options.items():
#         # Create a new View for this option
#         view = LazyConsensusView(ctx, name, timeout=timeout)
#         views.append(view)

#         # Display the option name, description and associated view to the user
#         message = await send_message(
#             f"**Name:** {name}\n**Description:** {description}", view=view
#         )
#         view.set_message(message)

#     # Wait for all views to finish
#     await asyncio.gather(*(view.wait() for view in views))

#     # Determine the options that had no objections
#     non_objection_options = {
#         view.option: options[view.option] for view in views if not view.objections and view.option in options
#     }

#     # Iterate over the non_objection_options dict and format the name and description for each
#     results_message = "\n".join(
#         f"**{name}:** {description}"
#         for name, description in non_objection_options.items()
#     )

#     # Display results
#     embed = discord.Embed(
#         title=f"Results for: `{question}`:",
#         description=results_message,
#         color=discord.Color.dark_gold(),
#     )

#     await send_message(embed=embed)

#     return non_objection_options

# CHANNEL NAMES -> DECISION MODULE LISTS

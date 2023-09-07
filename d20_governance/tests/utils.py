from unittest.mock import AsyncMock, MagicMock
from d20_governance.utils.constants import SIMULATIONS
from d20_governance.utils.utils import Quest


def create_quest():
    # Create a real Quest object
    quest = Quest(
        quest_mode=SIMULATIONS["build_a_community"],
        gen_images=False,
        gen_audio=False,
        fast_mode=True,
        solo_mode=False,
    )

    # Create a mock for the game_channel
    mock_game_channel = MagicMock()
    mock_game_channel.fetch_message = AsyncMock()  # mock the fetch_message method
    mock_game_channel.send = AsyncMock()  # mock the send method

    # Assign the mock game_channel to the Quest
    quest.game_channel = mock_game_channel
    return quest

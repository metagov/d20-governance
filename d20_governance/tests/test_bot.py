import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import discord
from d20_governance.bot import process_stage, start_quest
from d20_governance.utils.constants import MINIGAME_JOSH
from d20_governance.utils.utils import Quest  # replace with actual import


def create_quest():
    # Create a real Quest object
    quest = Quest(quest_mode=MINIGAME_JOSH, gen_images=False, gen_audio=False, fast_mode=True)

    # Create a mock for the game_channel
    mock_game_channel = MagicMock()
    mock_game_channel.send = AsyncMock()  # mock the send method

    # Assign the mock game_channel to the Quest
    quest.game_channel = mock_game_channel
    return quest


class TestQuestMockActions(unittest.TestCase):
    @patch('d20_governance.utils.utils.generate_image', new_callable=AsyncMock)
    @patch('asyncio.sleep', new_callable=AsyncMock)  # replace the actual sleep with an AsyncMock
    @patch('d20_governance.bot.execute_action', new_callable=AsyncMock)
    def test_quest(self, mock_execute_action, mock_sleep, mock_generate_image):
        quest = create_quest()
        asyncio.run(start_quest(quest))

        mock_execute_action.assert_called()
        mock_sleep.assert_called()
        quest.game_channel.send.assert_called()

# class TestQuestWithActions(unittest.TestCase):
#     @patch('d20_governance.utils.utils.generate_image', new_callable=AsyncMock)
#     @patch('asyncio.sleep', new_callable=AsyncMock)  # replace the actual sleep with an AsyncMock
#     def test_quest(self, mock_sleep, mock_generate_image):
#         quest = create_quest()
#         mock_fetch_message = AsyncMock()
#                 # create a mock for the message
#         mock_message = MagicMock()

#         # set the 'content' attribute to some string
#         mock_message.content = 'some content'

#         # now, set the return value of fetch_message to this mock
#         mock_fetch_message.return_value = mock_message
#         quest.game_channel.fetch_message = mock_fetch_message

#         asyncio.run(start_quest(quest))

#         mock_fetch_message.assert_called()
#         mock_sleep.assert_called()
#         quest.game_channel.send.assert_called()


if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from discord.ext import commands
from d20_governance.bot import bot, nicknames_to_speeches

class TestVoteSpeeches(unittest.TestCase):
    @patch('d20_governance.bot.set_decision_module', new_callable=AsyncMock)  # Replace with actual import path
    @patch('d20_governance.bot.start_vote', new_callable=AsyncMock)  # Replace with actual import path
    async def test_vote_speeches(self, mock_start_vote, mock_set_decision_module):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        # Set up the return values of the mocked functions
        mock_set_decision_module.return_value = "majority"
        
        # Set up the nicknames_to_speeches dictionary
        global nicknames_to_speeches
        nicknames_to_speeches = {"Jamboree Josh": "speech1", "Jigsaw Josh": "speech2"}

        # Call the function to be tested
        await bot.vote_speeches(mock_ctx, "question")

        # Check that the mocked functions were called with the correct arguments
        mock_set_decision_module.assert_called_once()
        mock_start_vote.assert_called_once_with(mock_ctx, "decision_module", 20, "question", "Speaker1", "Speaker2")

if __name__ == '__main__':
    unittest.main()

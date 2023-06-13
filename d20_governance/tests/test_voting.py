import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from discord.ext import commands
from d20_governance.bot import bot, vote_speeches

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from discord.ext import commands
from d20_governance.tests.utils import create_quest
from d20_governance.utils.voting import vote

class TestVoteSpeeches(unittest.IsolatedAsyncioTestCase):  # use IsolatedAsyncioTestCase
    @patch('d20_governance.bot.set_decision_module', new_callable=AsyncMock)  # Replace with actual import path
    @patch('d20_governance.bot.bot', new_callable=MagicMock)  # Replace with actual import path
    @patch('discord.ui.View.wait', new_callable=AsyncMock)  # Replace with actual import path
    async def test_vote_speeches(self, mock_wait, mock_bot, mock_set_decision_module):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        # Set up the return values of the mocked functions
        mock_set_decision_module.return_value = "majority"

        quest = create_quest()
        quest.nicknames_to_speeches = {"Jamboree Josh": "speech1", "Jigsaw Josh": "speech2"}
        mock_bot.quest = quest

        # Call the function to be tested
        await vote_speeches(mock_ctx, "question")

        # Check that the mocked functions were called with the correct arguments
        mock_set_decision_module.assert_called_once()

class TestVote(unittest.IsolatedAsyncioTestCase):  # use IsolatedAsyncioTestCase
    @patch('d20_governance.bot.bot', new_callable=MagicMock)
    async def test_vote_majority_pass(self, mock_bot):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        quest = create_quest()
        mock_bot.quest = quest

        options = ["Jamboree Josh", "Jigsaw Josh"]

        # Create a mock vote_view
        vote_view = MagicMock()
        vote_view.wait = AsyncMock()

        # Setup mock votes
        # 3/5 majority
        vote_view.votes = {
            "voter1": 1,
            "voter2": 1,
            "voter3": 1,
            "voter4": 0,
            "voter5": 0
        }

        # Patch the VoteView class to always return our mocked vote_view
        with patch('d20_governance.utils.voting.VoteView', return_value=vote_view):

            # Call the function to be tested
            winner = await vote(mock_ctx, quest, "question", options, "majority")
            expected_winner = "Jigsaw Josh" 
            self.assertEqual(winner, expected_winner)


    @patch('d20_governance.bot.bot', new_callable=MagicMock)
    async def test_vote_majority_fail(self, mock_bot):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        quest = create_quest()
        mock_bot.quest = quest

        options = ["Jamboree Josh", "Jigsaw Josh"]

        # Create a mock vote_view
        vote_view = MagicMock()
        vote_view.wait = AsyncMock()

        # Setup mock votes
        # No majority
        vote_view.votes = {
            "voter1": 1,
            "voter2": 1,
            "voter3": 0,
            "voter4": 0
        }

        # Patch the VoteView class to always return our mocked vote_view
        with patch('d20_governance.utils.voting.VoteView', return_value=vote_view):

            # Call the function to be tested
            winner = await vote(mock_ctx, quest, "question", options, "majority")
            expected_winner = None 
            self.assertEqual(winner, expected_winner)

    @patch('d20_governance.bot.bot', new_callable=MagicMock)
    async def test_vote_consensus_pass(self, mock_bot):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        quest = create_quest()
        mock_bot.quest = quest

        options = ["Jamboree Josh", "Jigsaw Josh"]

        # Create a mock vote_view
        vote_view = MagicMock()
        vote_view.wait = AsyncMock()

        # Setup mock votes
        # Consensus
        vote_view.votes = {
            "voter1": 1,
            "voter2": 1,
            "voter3": 1,
            "voter4": 1,
            "voter5": 1
        }

        # Patch the VoteView class to always return our mocked vote_view
        with patch('d20_governance.utils.voting.VoteView', return_value=vote_view):

            # Call the function to be tested
            winner = await vote(mock_ctx, quest, "question", options, "consensus")
            expected_winner = "Jigsaw Josh" 
            self.assertEqual(winner, expected_winner)

    @patch('d20_governance.bot.bot', new_callable=MagicMock)
    async def test_vote_consensus_fail(self, mock_bot):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        quest = create_quest()
        mock_bot.quest = quest

        options = ["Jamboree Josh", "Jigsaw Josh"]

        # Create a mock vote_view
        vote_view = MagicMock()
        vote_view.wait = AsyncMock()

        # Setup mock votes
        # No consensus
        vote_view.votes = {
            "voter1": 1,
            "voter2": 1,
            "voter3": 1,
            "voter4": 0,
            "voter5": 0
        }

        # Patch the VoteView class to always return our mocked vote_view
        with patch('d20_governance.utils.voting.VoteView', return_value=vote_view):

            # Call the function to be tested
            winner = await vote(mock_ctx, quest, "question", options, "consensus")
            expected_winner = None
            self.assertEqual(winner, expected_winner)

if __name__ == '__main__':
    unittest.main()

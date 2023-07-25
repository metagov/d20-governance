import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from discord.ext import commands
from d20_governance.bot import bot, vote_submissions

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from discord.ext import commands
from d20_governance.tests.utils import create_quest
from d20_governance.utils.voting import ObjectionVoteView, vote


class TestVoteSpeeches(unittest.IsolatedAsyncioTestCase):  # use IsolatedAsyncioTestCase
    @patch('d20_governance.bot.set_decision_module', new_callable=AsyncMock)  
    @patch('d20_governance.bot.bot', new_callable=MagicMock) 
    @patch('discord.ui.View.wait', new_callable=AsyncMock)  
    async def test_vote_speeches(self, mock_wait, mock_bot, mock_set_decision_module):
        # Create a mock context
        mock_ctx = MagicMock(spec=commands.Context)

        # Set up the return values of the mocked functions
        mock_set_decision_module.return_value = "majority"

        quest = create_quest()
        quest.players_to_speeches = {
            "Jamboree Josh": "speech1",
            "Jigsaw Josh": "speech2",
        }
        mock_bot.quest = quest

        with self.assertRaises(Exception) as cm:
            await vote_submissions(mock_ctx, "question")
            self.assertEqual(str(cm.exception), "No winner was found.")


# class TestVote(unittest.IsolatedAsyncioTestCase):  # use IsolatedAsyncioTestCase
#     @patch("d20_governance.bot.bot", new_callable=MagicMock)
#     async def test_vote_majority_pass(self, mock_bot):
#         # Create a mock context
#         mock_ctx = MagicMock(spec=commands.Context)

#         quest = create_quest()
#         mock_bot.quest = quest

#         options = ["Jamboree Josh", "Jigsaw Josh"]

#         # Create a mock vote_view
#         vote_view = MagicMock()
#         vote_view.wait = AsyncMock()

#         # Setup mock votes
#         # 3/5 majority
#         vote_view.votes = {
#             "voter1": 1,
#             "voter2": 1,
#             "voter3": 1,
#             "voter4": 0,
#             "voter5": 0,
#         }

#         # Patch the VoteView class to always return our mocked vote_view
#         with patch("d20_governance.utils.voting.VoteView", return_value=vote_view):
#             # Call the function to be tested
#             winner = await vote(mock_ctx, quest, "question", options, "majority")
#             expected_winner = "Jigsaw Josh"
#             self.assertEqual(winner, expected_winner)

#     @patch('d20_governance.bot.bot', new_callable=MagicMock)
#     async def test_vote_majority_fail(self, mock_bot):
#         # Create a mock context
#         mock_ctx = MagicMock(spec=commands.Context)

#         quest = create_quest()
#         mock_bot.quest = quest

#         options = ["Jamboree Josh", "Jigsaw Josh"]

#         # Create a mock vote_view
#         vote_view = MagicMock()
#         vote_view.wait = AsyncMock()

#         # Setup mock votes
#         # No majority
#         vote_view.votes = {"voter1": 1, "voter2": 1, "voter3": 0, "voter4": 0}

#         # Patch the VoteView class to always return our mocked vote_view
#         with patch('d20_governance.utils.voting.VoteView', return_value=vote_view):
#             with self.assertRaises(Exception) as cm:
#                 await vote(mock_ctx, quest, "question", options, "majority")
                
#             self.assertEqual(str(cm.exception), "No winner was found.")


#     @patch("d20_governance.bot.bot", new_callable=MagicMock)
#     async def test_vote_consensus_pass(self, mock_bot):
#         # Create a mock context
#         mock_ctx = MagicMock(spec=commands.Context)

#         quest = create_quest()
#         mock_bot.quest = quest

#         options = ["Jamboree Josh", "Jigsaw Josh"]

#         # Create a mock vote_view
#         vote_view = MagicMock()
#         vote_view.wait = AsyncMock()

#         # Setup mock votes
#         # Consensus
#         vote_view.votes = {
#             "voter1": 1,
#             "voter2": 1,
#             "voter3": 1,
#             "voter4": 1,
#             "voter5": 1,
#         }

#         # Patch the VoteView class to always return our mocked vote_view
#         with patch("d20_governance.utils.voting.VoteView", return_value=vote_view):
#             # Call the function to be tested
#             winner = await vote(mock_ctx, quest, "question", options, "consensus")
#             expected_winner = "Jigsaw Josh"
#             self.assertEqual(winner, expected_winner)

#     @patch("d20_governance.bot.bot", new_callable=MagicMock)
#     async def test_vote_consensus_fail(self, mock_bot):
#         # Create a mock context
#         mock_ctx = MagicMock(spec=commands.Context)

#         quest = create_quest()
#         mock_bot.quest = quest

#         options = ["Jamboree Josh", "Jigsaw Josh"]

#         # Create a mock vote_view
#         vote_view = MagicMock()
#         vote_view.wait = AsyncMock()

#         # Setup mock votes
#         # No consensus
#         vote_view.votes = {
#             "voter1": 1,
#             "voter2": 1,
#             "voter3": 1,
#             "voter4": 0,
#             "voter5": 0,
#         }

#         # Patch the VoteView class to always return our mocked vote_view
#         with patch("d20_governance.utils.voting.VoteView", return_value=vote_view):
#             # Call the function to be tested
#             # Call the function to be tested and expect error
#            with self.assertRaises(Exception) as cm:
#                 await vote(mock_ctx, quest, "question", options, "consensus")
#                 self.assertEqual(str(cm.exception), "No winner was found.")


#     @patch("d20_governance.bot.bot", new_callable=MagicMock)
#     async def test_truncated_option(self, mock_bot):
#         # Prepare the function call
#         mock_ctx = MagicMock(spec=commands.Context)
#         quest = create_quest()
#         mock_bot.quest = quest

#         long_option = "a" * 101  # Create an option longer than 100 characters
#         short_option = "b" * 99  # Create an option shorter than 100 characters
#         options = [long_option, short_option]

#         # Create a mock vote_view
#         vote_view = MagicMock()
#         vote_view.wait = AsyncMock()

#          # Setup mock votes
#         vote_view.votes = {
#             "voter1": 1,
#             "voter2": 1,
#             "voter3": 0,
#             "voter4": 0,
#             "voter5": 0,
#         }

#             # Patch the VoteView class to always return our mocked vote_view
#         with patch("d20_governance.utils.voting.VoteView", return_value=vote_view):
#             # Call the function
#             result = await vote(mock_ctx, quest, "question", options, "majority")
#             self.assertEqual(result, long_option)

import unittest
import discord.ui
from unittest.mock import Mock

class TestObjectVoteView(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ctx = Mock()
        self.view = ObjectionVoteView(self.ctx, timeout=60)

    async def test_initialization(self):
        self.assertIsInstance(self.view, ObjectionVoteView)
        self.assertEqual(self.view.ctx, self.ctx)
        self.assertEqual(self.view.timeout, 60)
        self.assertEqual(self.view.votes, {})
        self.assertEqual(self.view.objections, {})

    async def test_add_option(self):
        self.view.add_option('test_label', 'test_value')
        self.assertEqual(len(self.view.children), 2)  # One select and one button

if __name__ == "__main__":
    unittest.main()

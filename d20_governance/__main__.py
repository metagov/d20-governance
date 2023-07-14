import datetime
from bot import run_bot
from utils.constants import LOGGING_PATH
from utils.utils import clean_temp_files

if __name__ == "__main__":
    try:
        with open(f"{LOGGING_PATH}/bot.log", "a") as f:
            f.write(f"\n\n--- Bot started at {datetime.datetime.now()} ---\n\n")
        run_bot()
    finally:
        clean_temp_files()
        with open(f"{LOGGING_PATH}/bot.log", "a") as f:
            f.write(f"\n--- Bot stopped at {datetime.datetime.now()} ---\n\n")

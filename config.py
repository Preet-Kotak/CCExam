import os
from dotenv import load_dotenv
load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
DATABASE_URL: str = os.environ["DATABASE_URL"]

GUILD_ID: int = int(os.environ["GUILD_ID"])

SCORE_RESULTS_CHANNEL_ID: int = int(os.environ["SCORE_RESULTS_CHANNEL_ID"])
LEADERBOARD_CHANNEL_ID: int = int(os.environ["LEADERBOARD_CHANNEL_ID"])
END_SEASON_CHANNEL_ID: int = int(os.environ["END_SEASON_CHANNEL_ID"])
CC_EXAMINER_ROLE_ID: int = int(os.environ["CC_EXAMINER_ROLE_ID"])

DISTRICTS = [
    "Capital Peak",
    "Barbarian Camp",
    "Wizard Valley",
    "Balloon Lagoon",
    "Builder's Workshop",
    "Dragon Cliffs",
    "Golem Quarry",
    "Skeleton Park",
    "Goblin Mines",
]

GRADE_MAP = {5: "A+", 4: "A", 3: "B+", 2: "B", 1: "C", 0: "D"}
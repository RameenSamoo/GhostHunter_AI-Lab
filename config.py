"""Central configuration for Ghost Hunter 2D.

Every tunable number in the game lives here so the rules can be read (and
defended) in one place.
"""

from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ROOT_DIR / "assets"
AUDIO_DIR = ROOT_DIR / "audio"
DATABASE_FILE = ROOT_DIR / "ghost_hunter.db"       # SQLite: hunters and high scores
HIGHSCORE_FILE = ROOT_DIR / "highscores.json"      # old JSON store, imported once into the database

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
WINDOW_TITLE = "Ghost Hunter 2D"


# ---------------------------------------------------------------------------
# Difficulty tiers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Difficulty:
    key: str                 # stable id used in the high-score file
    name: str                # display name
    size: int                # grid is size x size
    ghost_interval: float    # seconds between ghost moves
    wall_density: float      # fraction of cells that become walls
    flicker_min: float       # min seconds between ghost flickers
    flicker_max: float       # max seconds between ghost flickers
    multiplier: float        # score multiplier
    ai_speed: float = 6.0    # Sir Nadeem's speed in cells per second

    @property
    def wall_count(self) -> int:
        """Exact number of walls the CSP must place."""
        return round(self.wall_density * self.size * self.size)

    @property
    def min_spawn_distance(self) -> int:
        """Minimum Manhattan distance between hunter and ghost spawns."""
        return self.size // 2


DIFFICULTIES = (
    Difficulty("beginner", "Beginner", 8, 1.0, 0.10, 5.0, 8.0, 1.0, 5.0),
    Difficulty("intermediate", "Intermediate", 12, 0.8, 0.15, 7.0, 10.0, 1.5, 5.33),
    Difficulty("professional", "Professional", 18, 0.6, 0.18, 9.0, 13.0, 2.0, 5.66),
    Difficulty("expert", "Expert", 25, 0.4, 0.20, 11.0, 16.0, 3.0, 6.0),
)
DIFFICULTY_BY_KEY = {d.key: d for d in DIFFICULTIES}

# ---------------------------------------------------------------------------
# Sensor / HMM
# ---------------------------------------------------------------------------
SENSOR_SIGMA = 1.5        # std-dev of Gaussian noise on the walking-distance sensor
LIKELIHOOD_EPS = 1e-4     # floor added to every likelihood value

# ---------------------------------------------------------------------------
# Hunter movement (keyboard auto-repeat)
# ---------------------------------------------------------------------------
MOVE_REPEAT_DELAY = 0.20  # seconds before a held key starts repeating
MOVE_REPEAT_RATE = 6.0    # cells per second while held

# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------
FLICKER_DURATION = 0.3

RADAR_DURATION = 2.0
RADAR_COOLDOWN = 5.0
RADAR_USES = 3
RADAR_PENALTY = 500

HINT_DURATION = 2.0
HINT_COOLDOWN = 5.0
HINT_PENALTY = 300

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
BASE_SCORE = 10000
TIME_PENALTY_PER_SECOND = 50
MOVE_PENALTY = 20
HIGHSCORE_SLOTS = 5
NAME_MAX_LEN = 12

# ---------------------------------------------------------------------------
# Heartbeat (driven by the latest noisy sensor reading, never the true position)
# ---------------------------------------------------------------------------
HEARTBEAT_MIN_INTERVAL = 0.35   # seconds between beats at reading 0
HEARTBEAT_MAX_INTERVAL = 1.50   # seconds between beats at the map's max distance

# ---------------------------------------------------------------------------
# Game modes and the AI opponent
# ---------------------------------------------------------------------------
MODE_SOLO = "solo"
MODE_SIMULTANEOUS = "simultaneous"
MODE_TURNS = "turns"
MODES = (MODE_SOLO, MODE_SIMULTANEOUS, MODE_TURNS)
MODE_LABELS = {
    MODE_SOLO: "Solo",
    MODE_SIMULTANEOUS: "VS AI · Simultaneous",
    MODE_TURNS: "VS AI · Turn-based",
}

AI_NAME = "Sir Nadeem"
PLAYER_NAME = "You"

TURN_BANNER_DURATION = 2.5     # seconds the "Your turn" / "Sir Nadeem's turn" banner shows
AI_CATCH_MESSAGE = "Sir Nadeem caught the ghost, you loser"
AI_CATCH_MESSAGE_DURATION = 3.0

RESULT_AI_WINS = "AI got a higher score than you, better luck next time"
RESULT_PLAYER_WINS = "You beat Sir Nadeem!"
RESULT_TIE = "It's a tie!"

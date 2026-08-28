"""game/state.py -- Bot state machine."""
from enum import Enum


class BotState(Enum):
    IDLE = 'idle'
    LAUNCH = 'launch'
    LOBBY = 'lobby'
    PREP = 'prep'
    GAMEPLAY = 'gameplay'
    RESULTS = 'results'


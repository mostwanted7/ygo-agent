"""Hard rules for the Blackwing deck, checked before the model is asked (see decks/saffira/rules.py for examples)."""

from ygo_agent.agent.rules import Decide

DRAW, STANDBY = 0x1, 0x2


def pass_own_draw_standby_windows(ctx):
    """Enemy Controller / Mystical Space Typhoon in hand trigger empty response windows in your own Draw and Standby
    Phase; nothing there beats waiting for the Main Phase, so don't spend model calls on them. (Opponent's turn is
    left to the model: Set traps like Icarus Attack can matter in their Standby Phase.)"""
    if (ctx.kind == "chain" and ctx.my_turn and not ctx.d.get("forced") and not ctx.state.get("chain")
            and ctx.phase in (DRAW, STANDBY)):
        return Decide([], "nothing worth doing in your own empty Draw/Standby Phase window")
    return None


RULES = [
    pass_own_draw_standby_windows,
]

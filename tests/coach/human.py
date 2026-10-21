"""A scripted "human" for coach mode: the arena's Python client joins a room as a duelist and plays with a simple
policy, the way EDOPro would with a person at the keyboard.

    python tests/coach/human.py --port 7951 --deck decks/saffira/deck.ydk [--policy simple] [--delay 1.5] [--note "!..."]
"""

import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [p for p in (ROOT,) if p not in sys.path]

from ygo_agent.arena.client import ArenaClient  # noqa: E402
from ygo_agent.arena.deck import load_ydk  # noqa: E402
from ygo_agent.arena.policies import POLICIES  # noqa: E402


class Cards:
    """What the policies need of a SeatView (declarable card names)."""

    def __init__(self, cards):
        self.cards = cards


class Human(ArenaClient):
    """Thinks `delay` seconds over a Main or Battle Phase action and a third of that over anything else."""

    def __init__(self, *args, delay=0.0, **kw):
        super().__init__(*args, **kw)
        self.delay = delay

    async def _on_game_message(self, raw):
        from ygo_agent.core.constants import PROMPT_MESSAGES
        from ygo_agent.core.constants import Msg
        if raw[0] in PROMPT_MESSAGES and self.delay and not self._catching_up:
            await asyncio.sleep(self.delay if raw[0] in (Msg.SELECT_IDLECMD, Msg.SELECT_BATTLECMD) else self.delay / 3)
        await super()._on_game_message(raw)


async def play(port, deck, cards, policy="simple", delay=0.0, notes=(), seed=1, name="Human", timeout=900,
               host="127.0.0.1"):
    """Join, play one match (no rematch), return the client's log. `notes`: chat lines sent at the first prompts
    (e.g. "!keep Veiler for their turn")."""
    pick = POLICIES[policy](seed)
    view = Cards(cards)
    pending = list(notes)
    client = None

    def respond(prompt):
        if pending:
            client.chat(pending.pop(0))
        return pick(prompt, view)
    client = Human(name, deck, respond, rematch=False, delay=delay)
    for _ in range(100):
        try:
            await client.connect(host, port)
            break
        except OSError:
            await asyncio.sleep(0.3)
    await client.wait(timeout)
    await client.close()
    return client.log


def main(argv=None):
    import argparse
    from ygo_agent.core import Engine
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--deck", default=os.path.join(ROOT, "decks", "saffira", "deck.ydk"))
    ap.add_argument("--policy", default="simple", choices=sorted(POLICIES))
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--note", action="append", default=[])
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)
    engine = Engine.load()
    deck = load_ydk(args.deck, engine.cards).deck
    log = asyncio.run(play(args.port, deck, engine.cards, args.policy, args.delay, args.note, args.seed))
    print(f"done: position {log.position}, {len(log.game)} game messages, replay {'yes' if log.replay else 'no'}")


if __name__ == "__main__":
    main()

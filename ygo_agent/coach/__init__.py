"""Coach mode: a human plays a deck in the real EDOPro client while the agent coaches them.

The arena hosts the room, so it sees the human's seat exactly as their own client does: a SeatWatcher turns it into
the same decision JSON an AI seat gets. For each decision the coach (a DuelBrain in "coach" mode, brain.py) recommends
one move with a short, teachable why, shown in the terminal and the web panel (live.py), without ever holding up the
duel. After the game, review.py writes review.md: the key moments, what was better and why, against the playbook.
detect.py recognises the human's deck among the deck profiles; cli.py is `ygo-agent coach`. See docs/coach.md.
"""

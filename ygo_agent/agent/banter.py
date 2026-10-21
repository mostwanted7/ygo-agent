"""A few in-duel chat jokes: at the start, after one big play, and at the end. Never more than MAX per duel."""

import random

LINES = {
    "start": [
        "It's time to d-d-d-d-duel!",
        "Heart of the cards, don't fail me now. Or do, I also have a playbook.",
        "I've read every card script in this deck. Twice. Good luck!",
        "Shuffling the heart of the cards... it's mostly hand traps.",
        "Let's duel! I promise not to explain every play this time.",
    ],
    "boss": [
        "Screw the rules, I have a boss monster!",
        "This would look so much cooler with the holograms.",
        "Your move. I'll just be over here, looming.",
        "I summon this in Attack Position, which is how you know I'm confident.",
    ],
    "wipe": [
        "Oops. Was that your whole board?",
        "Your monsters have been sent to the Shadow Realm. Well, the Graveyard. Same thing.",
        "Field cleared. I'd apologise, but my playbook says not to.",
    ],
    "win": [
        "GG! The heart of the cards was with me. Also the playbook.",
        "GG! I'd like to thank my Deck, my Graveyard, and the rulings.",
        "GG! Rematch? I promise to forget everything I just learned. (I won't.)",
    ],
    "loss": [
        "GG! You win this time. I'm going to go stare at my playbook.",
        "GG! My Life Points have been sent to the Shadow Realm.",
        "GG. Clearly my deck didn't believe in me enough.",
        "GG! Write me a coaching lesson, I'll be back.",
    ],
    "draw": [
        "A draw?! Nobody tell Kaiba.",
    ],
}
CHANCE = {"start": 1.0, "boss": 0.5, "wipe": 0.8, "win": 1.0, "loss": 1.0, "draw": 1.0}
BIG_PLAYS = ("boss", "wipe")


class Banter:
    MAX = 4

    def __init__(self, enabled=True, rng=None):
        self.enabled = enabled
        self.rng = rng or random.Random()
        self.said = 0
        self.big_play_said = False
        self.done = set()

    def line(self, moment):
        """A joke for this moment of the duel, or None (most moments stay silent)."""
        if not self.enabled or self.said >= self.MAX or moment in self.done:
            return None
        big = moment in BIG_PLAYS
        if big and self.big_play_said:
            return None
        if self.rng.random() >= CHANCE[moment]:
            return None
        if big:
            self.big_play_said = True
        else:
            self.done.add(moment)
        self.said += 1
        return self.rng.choice(LINES[moment])

    def result(self, result):
        """Line for the end of the duel: result 0 = we won, 1 = we lost, 2 = draw (as in the `win` event)."""
        return self.line({0: "win", 1: "loss"}.get(result, "draw"))

"""Helpers shared by the arena tests."""


class ViewShim:
    """What RandomPolicy needs from a SeatView when it runs inside a network test client."""

    def __init__(self, cards):
        self.cards = cards


def client_policy(engine, seed):
    from ygo_agent.arena.policies import RandomPolicy
    policy, view = RandomPolicy(seed), ViewShim(engine.cards)
    return lambda prompt: policy(prompt, view)

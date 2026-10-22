"""The trainer: turn a new .ydk into a deck folder with a playbook the agent can play from.

    ygo-agent train path/to/Deck.ydk --name deck [--backend opus] [--player-backend opus] [--budget-usd 40]

Phases (pipeline.py), each one checkpointed in <deck>/train/state.json so `--resume` continues:

  0. Interview: the reviewer reads the dossier and asks the owner a few questions about the deck; the answers are
     the deck's tips.md (tips.py), which every later prompt that writes the playbook sees.
  1. Study (dossier.py, prompts.py): card texts, Lua scripts, archetypes and Extra Deck maths become a dossier; the
     reviewer writes a draft playbook in the house style from it and the tips, and the rulings it checked in the
     scripts.
  2. Lab (lab.py, goldfish.py): the player plays turn 1 with stacked hands (one per claimed line, plus random hands
     and a few going-second turns into a fixed board) against a dummy that never acts. The reviewer gets the end
     boards and the engine's rejections and marks each line verified or fixes it.
  3. Games (games.py, review.py): games against WindBot deck AIs; each game is reviewed the way CLAUDE.md's "Decks
     without a coach" says. Lessons need evidence that checks out against a script or the log (playbook.py).
  4. Converge: rounds of lab + games until a round finds no significant mistakes, or the rounds or the budget run
     out; then the saved regression cases are re-run and train-report.md is written (report.py).

The reviewer (llm.py) is agentic with the claude-code backend (read-only tools in a sandbox copy of the workspace)
and inline otherwise; either way it answers with JSON (schemas.py) that the trainer checks and applies.

After training, `ygo-agent learn` (learn.py) folds the owner's notes from played games (notes.py) and new tips into
the playbook through the same checks, without playing a game.
"""

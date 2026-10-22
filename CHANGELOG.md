# Changelog

## 0.1.0 beta 1 (2026-10-22)

The first release. Everything below works and has been played from EDOPro; it is a beta because it hasn't had much
use yet, and 1.0 waits for that (and for a few decks trained with the new loop). Expect small changes before then.

**Play**
- `ygo-agent play`: the agent hosts a duel room (a headless EDOPro-compatible host on the game's own engine,
  libocgcore); you join it from EDOPro. Master Rule 3 by default, Bo1/Bo3, an EDOPro replay file for every game.
- `play --join`: the older flow, where the agent's bot (a WindBot fork) joins a room you host in EDOPro.
- `selfplay`: AI vs AI, or AI vs one of EDOPro's WindBot deck AIs, in-process or in a room you can spectate.
- `teach`: the agent plays and explains every move for a spectator. `coach`: you play in EDOPro, the agent advises
  each decision live and reviews the game afterwards.

**The web app**
- `ygo-agent web`: start games, watch them live (the board, every decision with its reasoning and plan), browse and
  replay recorded games, manage decks (playbook, tips, pending notes), train a new deck and learn from your notes,
  all from the browser. The terminal commands are unchanged; the app runs them and shows each one's command line.
- A note box on every game: notes land in the game's `feedback.md`, like `!notes` typed in the duel chat.

**Decks and training**
- Three decks ship with playbooks: Saffira, Blackwing and Geargia.
- `ygo-agent train <deck.ydk> --name NAME`: reads every card and its script, interviews you about how the deck plays
  (your answers become `tips.md`), writes the playbook from both, then practises (a short lab of first turns and a
  couple of reviewed games against WindBot deck AIs) and corrects itself. A trained deck is a guidebook the model
  reads, not weights.
- `ygo-agent learn --deck NAME`: folds the notes you typed during games, and tips you added, into the playbook; every
  lesson is checked against the game log and the card scripts, and replayed against the deck's saved cases.
- Regression cases (`replay --save`, `test`), hard rules only for the play model's repeated no-judgment mistakes,
  and `test --ablate-rules` to drop the rules a newer model no longer needs.

**Backends**
- Claude through your Claude Code login (the default, Opus), the Anthropic API, any OpenAI-compatible server
  (Ollama, vLLM, llama.cpp, LM Studio, OpenRouter), and two no-LLM baselines (heuristic, random). Each seat picks its
  own backend profile from the config.

**Tools**
- `ygo-agent doctor` checks the setup; `ygo-agent bench` runs tournaments (win rate, latency, tokens, invalid
  replies) and a blind model exam; `ygo-agent decks` lists the deck profiles.

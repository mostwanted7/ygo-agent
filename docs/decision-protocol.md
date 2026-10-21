# Decision protocol

The schema between a **bot** (today: the WindBot fork's `BrainBridge`, `windbot-src/ExecutorBase/Game/BrainBridge.cs`
plus the events in `Game/GameBehavior.cs`) and the **agent** (`ygo_agent/agent/bridge_server.py` → `brain.py`).
Anything else that drives the agent, such as the arena's native AI seats, must emit exactly this schema, so that
`describe.py`, the deck rules and the saved test cases keep working unchanged. The native seats
(`ygo_agent/arena/native_seat.py`) do, and add a few optional fields and events that WindBot never sends; they are
marked *native* below, and [Native seats](#native-seats) describes how they build the messages.

## Transport

- TCP. The agent listens on `127.0.0.1:<bot.brain_port>` (default 7922); the bot connects.
- WindBot opens the connection only when it is started with `Brain=host:port`. Without that argument it is plain
  upstream WindBot.
- One connection per bot client, so one per **match**: a Bo3 runs all its games over one connection.
- UTF-8 without a BOM. One JSON object per line, terminated by `\n`.
- Bot → agent: **events** (no reply) and **decisions** (exactly one reply each). The bot blocks on each decision.
- Agent → bot: one **reply** per decision. No unsolicited messages.
- The bot waits up to 15 minutes for a reply, then disconnects and its built-in AI plays the rest of the game. The
  agent enforces its own, shorter deadline (`agent.decision_timeout_seconds`) and always answers.

## Conventions

- **Players are local.** `0` is the bot's own side ("me"), `1` the opponent, whatever the room seat or who went first.
  Fields named `c` (controller) and `player` use this convention.
- **Locations** (`l`) are EDOPro `LOCATION_*` values: `0x1` Deck, `0x2` hand, `0x4` Monster Zone, `0x8` Spell & Trap
  Zone, `0x10` GY, `0x20` banished, `0x40` Extra Deck, `0x80` Xyz material (overlay), `0x100` Field Zone, `0x200`
  Pendulum Zone. `0` in a `move` means "outside the game" (a new token, or a card removed from play).
- **Sequences** (`s`):
  - Monster Zone: `0`–`4` are the Main Monster Zones left to right; `5`, `6` the Extra Monster Zones (never occupied
    under MR3).
  - Spell & Trap Zone: `0`–`4` the S/T zones; `5` the Field Zone; `6`, `7` the Pendulum Zones.
  - Hand, GY, banished and Extra Deck **inside `state`**: the card's index in that list (the bot re-indexes them
    because its own sequences go stale).
  - Hand, Deck and Extra Deck cards **inside options** keep whatever sequence the bot tracked, which is often `-1`
    (cards drawn or added to the hand get `-1`). Never use `s` to identify a hand card in an option; identify it by
    its index in the options list.
- **Positions** (`p`): `0x1` face-up Attack, `0x2` face-down Attack, `0x4` face-up Defense, `0x8` face-down Defense.
- **Phases**: `0x1` Draw, `0x2` Standby, `0x4` Main 1, `0x8` Battle (start step), `0x10` Battle Step, `0x20` Damage Step,
  `0x40` Damage Calculation, `0x80` Battle (end step), `0x100` Main 2, `0x200` End.
- **Descriptions** (`desc`, `hint`, `option` values): EDOPro string ids. `< 2^20` is a system string
  (`strings.conf !system`); otherwise `code << 20 | index` is string `index` (0–15) of card `code`. `0` means none.
- **Card id** `0` means the bot can't see the card (face-down, the opponent's hand, an unrevealed Deck card).

### Card object

Full form (`state` piles and zones, options, `card` fields):

| field | type | meaning |
|---|---|---|
| `id` | int | card code, `0` if unknown to the bot |
| `c` | int | controller, `0` me / `1` opponent |
| `l` | int | location |
| `s` | int | sequence (see above) |
| `p` | int | position bits |
| `atk`, `def` | int | current ATK/DEF (only when `id != 0`) |
| `lv`, `rk`, `lk` | int | current Level, Rank, Link rating (only when `id != 0`) |
| `ov` | [int] | optional: codes of its Xyz materials |
| `dis` | true | optional: its effects are negated |
| `att` | true | optional: it already attacked this turn |
| `eq` | short card | optional: the card it is equipped to |
| `ctr` | [[type, count]] | optional, *native*: counters on it (`type` as in `strings.conf !counter`) |
| `sc` | [left, right] | optional, *native*: current Pendulum Scales, for a Pendulum card in a Pendulum Zone |
| `blv` | int | optional, *native*: the printed Level (Rank for Xyz) of a monster on the field whose current `lv`/`rk` differs from it |
| `own` | int | optional, *native*: the owner (`0` me / `1` opponent) of a card controlled by the other player |
| `uid` | int | optional, *native*: the card instance (see [Native seats](#native-seats)); not in short cards |

Short form (`chain_targets`, `last_summoned`, `battling`, `eq`): only `id`, `c`, `l`, `s`.

### State object

Every decision carries `state`, the board as the bot sees it right now:

```json
{"turn": 3, "turn_player": 0, "phase": 4,
 "me":  {"lp": 8000, "hand": [card...], "mz": [card|null x7], "sz": [card|null x8],
         "gy": [card...], "ban": [card...], "deck": 30, "extra": [card...]},
 "opp": {...same shape...},
 "chain": [{"card": card, "id": 40044918, "player": 1, "desc": 42991619073}],
 "chain_targets": [short card...], "last_summoned": [short card...], "summon_player": -1,
 "battling": [short card|null, short card|null]}
```

- `turn` counts both players' turns from 1. `turn_player` is local (0 = my turn).
- `mz` always has 7 slots and `sz` 8, `null` for empty zones, indexed by sequence.
- `deck` is a count. The opponent's `hand` entries usually have `id` 0 (known ones have their code). The opponent's
  `extra` lists every card, with `id` 0 except face-up ones.
- My own `extra` may come with `id` 0 entries. The agent fills them in from the deck list, minus copies it can see
  on the field, in the GY or banished (`DuelBrain.fill_extra`).
- `chain` is the current chain, link 1 first. `summon_player` is -1 when nothing is being summoned. `battling` is
  [my battling monster, theirs].
- Before the duel starts (the first `go_first`), every pile is empty, `deck` is 0, and `turn`/`phase` are 0.

## Events

`{"t": "event", "e": NAME, ...fields}`. All fields are always present unless marked optional.

| `e` | fields | when |
|---|---|---|
| `room` | `duel_flags` (int64, EDOPro `DUEL_*` bits: MR3 = 858112, MR5 = 190464), `forbidden_types`, `best_of`, `teams` [int, int], `start_lp`, `start_hand`, `draw_count`, `time_limit` (s, 0 = none) | once, on joining the room, before any game |
| `start` | `first` (bool, I go first), `lp` [me, opp], `names` [me, opp] | each game of the match |
| `draw` | `player`, `count` | |
| `new_turn` | `turn`, `player` | |
| `new_phase` | `phase`, `player` (the turn player) | |
| `move` | `id` (0 if hidden), `from` {c,l,s,p}, `to` {c,l,s,p}, `reason` (EDOPro `REASON_*` bits) | every card movement, including draws and hidden reorders |
| `summoning` | `id`, `to` {c,l,s,p}, `special` (bool) | a Normal/Flip Summon (`special` false) or Special Summon (true) starts |
| `chaining` | `id`, `card` (full card), `player`, `desc`, `link` (1-based chain link) | a card or effect is activated |
| `chain_solved` | `link` | that link finished resolving |
| `chain_negated`, `chain_disabled` | `link` | activation / effect negated |
| `chain_end` | none | the whole chain resolved |
| `attack` | `attacker` (full card), `target` (full card, or null for a direct attack) | attack declared |
| `damage`, `pay_lp`, `recover` | `player`, `amount`, `lp` (after) | battle/effect damage, LP paid as a cost, LP gained |
| `lp` | `player`, `lp` | LP set to a value |
| `pos_change` | `id`, `c`, `l`, `s`, `from`, `to` (positions) | battle position changed |
| `targeted` | `card` (full card) | a card became the target of a chain link |
| `chat` | `player`, `position`, `message`, `source` (`"duelist"`, `"spectator"` or `"system"`), `name` (optional, sender name) | a chat line arrived |
| `win` | `result` (0 I win, 1 I lose, 2 draw), `reason` (`strings.conf !victory` id) | end of a game |
| `retry` | none | the engine rejected the last response |
| `confirm` | `player` (who it was shown to), `cards` (full cards) | *native*: cards revealed, e.g. a searched card the opponent shows, or the top of a Deck |
| `equip` | `card`, `target` (full cards) | *native*: an equip card was equipped |
| `swap` | `cards` (two full cards, at their new places) | *native*: two monsters swapped control |
| `counter` | `card` (full), `type`, `count`, `add` (bool) | *native*: counters placed (`add`) or removed |
| `coin`, `dice` | `player`, `results` [int] (coin: 1 heads, 0 tails) | *native*: a coin toss or a die roll |
| `declared` | `player`, `kind` (`card`, `attribute`, `race`, `number`, `option`), `value` (code, bits, number or effect description) | *native*: what the opponent declared or chose (EDOPro shows it to the other player) |

A Flip Summon is a `summoning` with `special` false, like a Normal Summon; native seats add `flip: true` to it.

Chat details: `position` is the bot's own room seat. `player` is the sender's seat for duelists (so
`player == position` is the bot's own echo, which the agent ignores), 7 for spectators and 8+ for system messages.
EDOPro hosts send chat as `STOC_CHAT_2` (0xF3: type, is_team, name, message), which the fork converts into this event:
own team → `player = position`, other team → `1 - position`. Older hosts' `STOC_CHAT` (0x19) carries the seat
directly. A message starting with `!` is a coaching note: the agent saves it to the game's `feedback.md` and
acknowledges it in chat.

## Decisions

`{"t": "decide", "id": N, "kind": KIND, "state": {...}, ...kind fields}`.

- `id` starts at 1 on each connection and increases by 1 per decision. After a game's `game_over` round trip it
  restarts at 1, so every game of a match numbers its decisions from 1.
- Options are listed in a fixed order (below). Replies refer to them by **0-based index** into `options`, except
  where noted (`announce_card`, `place`).

### Replies

`{"id": N, "choice": [int, ...] | null, "say": string | null}`

- `id` must echo the decision's id; the bot ignores lines with any other id.
- `choice: null` (or a missing/invalid choice) = **fallback**: WindBot's own AI answers this one prompt. The agent
  falls back when the backend gives no usable answer, after the engine rejected a response (`retry`), and for
  prompts it leaves to WindBot (`place`, `announce_card` with more than 150 names). With `agent.fallback =
  "heuristic"` (native seats) the agent answers those itself instead, with the heuristic policy (a random legal
  answer after a `retry`), so `choice` is never null; see docs/backends.md.
- `choice: []` = pass / cancel / finish, where the kind allows it (below). Otherwise it is treated as a fallback.
- `say`: optional chat text, sent to the room right away. `\n` separates lines; lines longer than 240 characters are
  split. The agent uses it for its rare banter and to acknowledge `!notes`, never for explanations.

### Kinds

| kind | extra fields | options (in order) | reply |
|---|---|---|---|
| `idle` | | `{"a", "card", "desc"?}`: every `activate` (with `desc`), then `summon`, `spsummon`, `set_monster`, `set_spell`, `reposition`, then `to_battle` (if allowed), `to_end` (if allowed); the last two have no `card` | `[k]` |
| `battle` | | every `activate` (with `desc`), then `attack` (with `direct`: bool, can attack directly), then `to_main2`, `to_end` (each if allowed) | `[k]` |
| `chain` | `forced` (bool) | `{"a": "activate", "card", "desc"}` per activatable effect | `[k]`, or `[]` to pass (not allowed when `forced`) |
| `effect_yn` | `card` (full card), `desc` | none | `[1]` yes / `[0]` no |
| `yesno` | `desc` (system string; 30 = "replay the attack?") | none | `[1]` / `[0]` |
| `go_first` | | none | `[1]` go first / `[0]` go second |
| `select_card` | `min`, `max`, `hint`, `cancelable` | cards | `min`..`max` distinct indices; `[]` cancels if `cancelable` or `min == 0` |
| `tribute` | same as `select_card` | cards | same as `select_card` |
| `select_unselect` | `selected` (cards already picked), `min`, `max`, `hint`, `finishable`, `cancelable` | cards that can be picked next | exactly `[k]`: one pick per prompt; `[]` finishes (if `finishable`) or cancels (if `cancelable`) |
| `select_sum` | `sum`, `min`, `max`, `hint`, `exact` (bool) | cards with `v1`, `v2` (the value each counts as; `v2` 0 = none) | `min`..`max` distinct indices whose `v1` (or `v2`, else `v1`) totals equal `sum` (`exact`) or reach it |
| `option` | | effect descriptions (ints) | `[k]` |
| `position` | `card_id` | positions (ints) | `[k]` |
| `place` | `card_id` (the last select hint, usually the card's code), `player`, `location` (`0x4`, `0x8`, `0x100` or `0x200`), `available` (bit n = sequence n is free) | none | `[mask]`: zone bits, ANDed with `available`; 0 = fallback. If several bits survive, WindBot picks among them in its own order |
| `announce_card` | | every card code the prompt allows | `[code]`: the **card code itself**, not an index |
| `announce_number` | | numbers | `[k]` |
| `announce_attrib`, `announce_race` | `count` | attribute / race bit values | exactly `count` distinct indices |
| `game_over` | `result`, `reason` (as in `win`) | none | `choice` is ignored; `say` is the place for an end-of-game line |

Notes per kind:

- `select_unselect`: the bot sets `cancelable` whenever `finishable` is set, so check `finishable` first. The engine
  is in charge of the counts (min/max are sometimes per step, e.g. Synchro Materials, and sometimes for the whole
  selection). The agent may decide a multi-card pick at once: it sends the first index and answers the following
  prompts of the same selection (same `hint`) itself, matching the planned cards by `(id, c, l, s)`, then `[]` once
  the selection is finishable. If it falls back, the bot's own AI picks, and the agent isn't asked the same prompt a
  second time as `select_card`.
- `chain` is only sent when at least one effect can be activated, and not when the only option is a single forced
  activation: the bot passes empty response windows and activates a lone forced effect itself. A trigger effect with
  the generic description 221 arrives with `desc` 0.
- `idle`/`battle`/`chain` options with `a == "activate"` carry the effect's `desc`, which tells apart a card's
  different effects.
- Prompts WindBot answers itself, never sent: rock-paper-scissors, counter removal (`select_counter`), card sorting
  (`sort_card`) and chain ordering (`sort_chain`, always the default order). Native seats answer them the same way
  without asking the agent: counters come off the cards in the order offered, sorted cards and chains keep their
  order, rock-paper-scissors is random. Both also answer an empty chain window (pass), a single mandatory activation,
  a position prompt with one position, and yes/no 1989 (yes) by themselves.

### Agent-side validation

`ygo_agent/agent/validate.py` checks a backend's reply before sending it: in-range distinct indices, the count per
kind above, the sum for `select_sum`, `[]` only where allowed, and for `place` a mask with at least one available
bit. An invalid reply gets one retry with the error; a second failure becomes a fallback.

Backends get each decision as a `Request` carrying both the prompt text (`describe.py`) and the raw decision dict
above, so non-LLM backends (heuristic, random) decide from the same JSON. See docs/backends.md.

## Native seats

`ygo_agent/arena/native_seat.py` (`AgentSeat`) plays an arena seat with the agent in-process, no WindBot.
`native_view.py` (`NativeView`) builds the events and the state, `native_decide.py` (`build`) the decisions and their
encoding.

- **Sources.** Only what that player is allowed to see: the seat's own filtered message stream (exactly what its
  EDOPro client would receive) and its `SeatView` queries. Events come from the stream, as WindBot's GameBehavior
  builds them; `state` is queried at decision time, so ATK/DEF, Level/Rank, materials, counters, equip targets,
  scales and the negated status are the core's current values (WindBot's are refreshed only at certain points, and
  are 0 for cards it never got a refresh for, e.g. Deck cards offered by a search).
- **Card instances (`uid`).** Each card the seat can follow is one object that moves with every `MSG_MOVE`, draw,
  swap and shuffle, mirroring the core's arrays: piles in core order (Deck top last), zones by slot, Xyz materials
  under their monster. `uid` is a per-game counter given when the object is created (the opening Deck and Extra
  Deck, a token, a card the tracking had to rebuild), so it stays the same while the seat can follow the card,
  across zones and piles. A reorder the seat can't see through gives new uids: a Deck shuffle, the opponent's hand
  or Extra Deck shuffle, a Set-card shuffle. A card's code is kept the way WindBot keeps it: a move with a hidden
  code forgets it, a hidden shuffle forgets it, a confirmation teaches it, and a query that shows the code wins.
  `uid` adds nothing a careful human couldn't track at the table, and the fairness test checks that it never
  survives a hidden shuffle.
- **Conventions kept from the bridge.** The same option order, `desc` 0 for a generic trigger in `chain` and -1 in
  `effect_yn`, `s` -1 for hand, Deck and Extra Deck cards outside `state` (never a Deck sequence), re-indexed piles
  in `state`, the selection `hint` kept through a `select_unselect` selection and used up by the other selections,
  `place` offered as WindBot offers it (the first group of zones with a free one) and answered in WindBot's zone
  order.
- **Where native seats are more exact.** Every option maps to its own response; WindBot sends the same response for
  both options when one card is listed twice (a monster with two Special Summon procedures). Xyz materials offered
  in a selection carry their real controller (WindBot gives the raw player id) and the core's material list.
  `att` means "declared an attack this turn" (WindBot also marks, during the Battle Phase, monsters that can't
  attack). Before the duel (`go_first`) the state is always empty.
- **Replies.** The seat encodes the agent's choice into the core response (an index per option, `[code]` for
  `announce_card`, a zone mask for `place`, one pick per prompt for `select_unselect`). A choice the engine would
  refuse (e.g. a Ritual `select_sum` with a card too many), a brain error or a timeout gets the heuristic's answer;
  after a RETRY the seat never sends the refused response again. `Decision.decode(response)` turns any response
  for that prompt back into option indices (the same mapping the other way), for coach mode and the parity test.
- **Watching a seat.** `SeatWatcher(team, cards, on_event=, on_decision=, on_choice=)` is a DuelObserver that builds
  the same events and decisions for a seat it doesn't play (e.g. a human's, for coach mode) and reports each of that
  seat's responses as the option indices it stands for (None for an unselect, which the schema can't express).
- **Logs and the web panel.** Each game gets the usual `games/<time>_<deck>-vs-<opponent>/` folder.
  `native_seat.link(a, b, match_id=)` gives the seats of one duel the same web-panel game id (`<match_id>-g<n>`);
  the arena host links its agent seats with the arena run's folder name.

## Message flow of a match

```
room                                   (join)
[go_first]                             (game 1: whoever won RPS chooses)
start · new_turn · new_phase · ...     (events and decisions)
win → game_over (reply may carry say)
[go_first]                             (game 2: the loser of game 1 chooses; decision ids restart at 1)
start · ...
```

The agent starts a fresh game (new `DuelBrain`: log folder, history, banter count) on the first decision or `start`
event after a `win`. Chat that arrives between a `win` and the next game still belongs to the finished game, so a
`!note` typed right after the game lands in that game's `feedback.md`.

## Logs

Each game's `games/<time>_<deck>-vs-<opponent>/game.jsonl` holds one JSON object per line:
`{"ts": unix time, "kind": "event" | "decide" | "reply", "msg": ...}`. `event` and `decide` are the messages above,
exactly as received (the `room` event comes first). `reply` records what was sent back:
`{"id", "choice", "source"}`, plus `suggested` when a copilot pilot overrode the agent and `say` when chat was
sent. `source` is `backend` (the configured backend answered; logs before Stage 1 say `llm`), `rule:<name>`,
`auto`, `fallback`, `pilot` (the copilot's human chose) or `game_over`. `meta.json` names the backend profile and
holds the game's stats (docs/backends.md).
`ygo-agent replay` and the saved test cases replay the `event` and `decide` records.

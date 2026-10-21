# Web panel

A local page that shows a duel as the agent plays it: the board with card pictures, every decision with the
options, what was chosen, why, and the plan for the turn, the event log, coach advice, and a feedback box that
works like a `!note` in the duel chat. It also browses and replays recorded games.

![The web panel replaying a recorded Blackwing game](img/web-panel.png)

Standard library only: an HTTP server with Server-Sent Events (`ygo_agent/web/server.py`) and vanilla HTML/CSS/JS
in `ygo_agent/web/static/`, with no build step and nothing from a CDN, so it works offline.

## Running it

```sh
ygo-agent play --web                 # also selfplay/teach/coach --web, and the legacy --join flows; prints http://127.0.0.1:7930/
ygo-agent web                        # no live game: browse games/* and replay any of them
ygo-agent web --demo games/<dir> --speed 2   # replay a recorded game live, as if it were being played now
```

- `--web-port N` (play/selfplay/teach/coach) or `--port N` (web) picks the port. `[web]` in `config/default.toml`
  holds the defaults: `auto` (start it with every play/selfplay/teach/coach run without `--web`; `--no-web` turns
  it off for one run), `host` (`127.0.0.1`; keep it local, since the panel serves your logs
  and writes notes), `port` (7930), `open_browser`, `fetch_pics`.
- `--demo` paces the game for watching: about the real rhythm, with thinking time taken from each reply's latency
  (capped at 6 s, divided by `--speed`), and quick events squeezed. `--loop` restarts it. It's meant for the README
  GIF and for trying the panel without playing. The demo is a live game until its `game_end` (the recorded result,
  end time and stats are published last).
- The panel lives in the process that plays: `ygo-agent web` in another terminal shows recorded games and demos,
  not the games of a separate `play` process. Use `play --web` for those.

Using it:

- **Board**: the seat being viewed is at the bottom. Hover any card (board, hand, options, chain, log) for the large
  picture and full text. Click GY, banished or Extra Deck for the list. Defense-position cards are turned sideways;
  the opponent's face-down cards are card backs, your own set cards show their face dimmed with a SET tag.
  Chain links show as numbered markers on the cards and as a chain bar in the middle strip. Attacks draw an arrow,
  targets get a ring, LP changes animate.
- **Reasoning**: one card per decision, newest at the bottom. The chosen option is highlighted (multi-card picks
  are numbered in pick order), then the reason, the source badge (backend label, `rule · name`, `fallback`, `auto`,
  `you` for a coached human's own move, `pilot` in old copilot logs) and the latency and tokens. The current turn's
  plan stays at the top. Auto-scroll pauses when you scroll up; "Latest" resumes it. The `auto` switch shows
  decisions the agent made without asking (only one choice, planned picks). Zone placements are left out.
- **Coach games** (`ygo-agent coach --web`, docs/coach.md): your own seat at the bottom. Each card marks the coach's
  pick (dashed, `COACH`) and your move (✓), says `followed coach` or `diverged` (and `late` or `looked back` when
  the advice came after your move), and has the coach's reason and plan in a green line; while you think it says
  "waiting for your move", while the coach thinks "coach is thinking". Decisions the coach didn't weigh in on are
  `auto` cards. The timeline marks your moves green, or amber where you diverged. After the game the coach's review
  opens in a **Review** tab.
- **Timeline** (bottom): every decision of the game, coloured by source, with turn marks. Click or drag to scrub;
  the board, the reasoning and the log show the game as of that decision. Keys: `←`/`→` decision, `Shift+←/→`
  turn, `Home`/`End`, `Space` play/pause, `L` back to live, `G` games, `N` the note box, `Esc` close. Keys typed in
  the note box (or any field) never move the timeline.
- **Live or paused.** In a game still being played the board follows the newest decision and the events since. It
  leaves the live view only on an explicit move: a scrub, the arrow keys, `Home`, or a click on an *older*
  decision card (clicking the newest one, scrolling the reasoning list or a paused auto-scroll never do). While it
  shows an earlier decision, the board is dimmed, a bar over it says "Viewing decision #N (turn T), not live" with
  a **Back to live** button, and the header chip reads `PAUSED AT #N` instead of `LIVE`; `Esc`, `End`, `L`, the
  button, or stepping forward onto the newest decision follow the game again.
- **Render errors.** Each message is handled on its own: one the page can't render is logged to the browser
  console and counted in a small red "render error" chip in the header (hover it for the message), and the board
  and the timeline carry on with the next one.
- **Feedback box**: saves the note to the game's `feedback.md` in the same format as a `!note` from the chat,
  `- (turn T, right after decision #N) text`. During a live game it goes through the seat's DuelBrain (same counter,
  and `game.md` gets a "Web panel feedback" line); if you scrolled back, it is tagged with the decision on screen. For
  a recorded game it is appended to that folder's `feedback.md`.
- **Self-play** (two seats in one game): seat tabs switch the bottom side; "both" shows both seats' reasoning;
  "God view" shows the other seat's hand from its own view.
- **Games** (`G`, or the title): live games on the bus and every log under `games/`.

Card pictures come from `~/Games/ProjectIgnis/pics`. A missing one is downloaded from the URL EDOPro uses
(`config/user_configs.json`, then `config/configs.json`; `"default"` means
`https://pics.projectignis.org:2096/pics/{}.jpg`), cached in `~/.cache/ygo-agent/pics/`, and replaced by a
generated card (name, type, ATK/DEF) when offline. A failed download isn't retried for 10 minutes.

## How it fits together

```
DuelBrain ─▶ GameLog ─▶ Channel(game_id, seat) ─▶ Bus ──(Renderer: describe.py words, card names)──▶ backlog
                                                   │                                                    │
                                     feedback ◀────┘                    server.py: /stream (SSE) ◀──────┘
                                  (panel_note)                         /api/*, /card/*, /cardinfo/*
```

- **Hook.** `GameLog` (`ygo_agent/agent/gamelog.py`) already sees every event, decision, reply and prompt, so it is
  the only publisher: each log has a `web` Channel. Any seat that logs through a GameLog (the WindBot bridge today,
  native arena seats in Stage 3/4) is on the panel for free. While no panel runs, `Channel.send` returns at once.
  Quiet logs (replays, tests) don't publish unless created with `publish=True`.
- **Ids.** `GameLog(..., game_id=, seat=)` and `DuelBrain(..., game_id=, seat=)`. The default game id is the log
  folder's first name; two seats of one game must pass the same `game_id` and their own `seat`.
- **Bus** (`ygo_agent/web/bus.py`): thread-safe, in-process. Each game keeps a backlog (50k messages; the 16 newest
  games, finished ones dropped first), so a browser that opens mid-game catches up. `Channel.send` deep-copies the
  payload, because the brain keeps editing its own dicts.
- **Renderer** (`render.py`): adds the display text to every message as it is published, using the same
  `describe.py` the model's prompt uses, plus a brief of each card the game mentions (sent once per game).
- **Server** (`server.py`): `ThreadingHTTPServer`, one thread per request. It refuses requests whose `Host` or
  `Origin` isn't local (DNS rebinding, cross-site posts) and only takes JSON posts.
- **Recorded games** (`recorded.py`): rebuilds the same messages from a game folder: `game.jsonl` (events,
  decisions, and replies in logs since Stage 0), `game.md` (choice, source, reasoning and plan of every decision,
  for old logs too), `prompts.jsonl` (the backend's own reply, time and tokens) and `feedback.md`.

| endpoint | |
|---|---|
| `GET /stream?game=ID` | SSE. First `{"type": "games", "games": [...]}`, then the game's backlog (after `Last-Event-ID`, which browsers send when they reconnect), `{"type": "caught_up"}`, then live messages. Summary messages of other games (`game_start`, `meta`, `game_end`) come too, without an SSE id. `/stream` without a game sends only those. |
| `GET /api/games` | `{"live": [summary...], "recorded": [summary...]}` |
| `GET /api/recorded/NAME` | `{"name", "summary", "messages": [...]}`: a recorded game as bus messages (game id `rec:NAME`) |
| `GET /card/CODE.jpg` | the picture (JPEG/PNG), or the placeholder SVG |
| `GET /cardinfo/CODE` | `{"id", "name", "type_line", "text", "type", "atk", "def", "level", "scale"?, "attribute", "race", "alias", "extra"}` |
| `POST /api/feedback` | `{"game_id", "seat", "text", "decision"?, "turn"?}` → `{"ok", "live", "n", "context", "file"?}` |

## Message schema

Every message is a JSON object with `type`, `game_id`, `seat` (the publishing seat, 0 or 1; in its payload
"me"/player 0 is that seat, as in `docs/decision-protocol.md`), `ts` (unix seconds) and `seq` (per game, from 1;
the bus sets it). Publishers send through `Channel(game_id, seat).send(type, **fields)` or
`BUS.publish({...})`. The renderer adds the fields marked *(rendered)*.

| type | fields | from |
|---|---|---|
| `game_start` | `deck`, `deck_name`, `dir` (log folder), `name`; `demo` / `recorded` (bool, optional) | a seat's GameLog is created |
| `meta` | any of `deck`, `deck_name`, `mode` (`play`, `selfplay`, `teach`, `coach`; `copilot` in old logs), `backend` (`{label, name, type, model…}`), `rules`, `opponent`, `first`, `started`, `result`, `ended`, `stats`, `dir`, `name` | `GameLog.write_meta` (same keys as `meta.json`) |
| `event` | `ev`: the raw bridge event; `text` *(rendered)*: the `describe.py` line or null; `desc_text` *(rendered, chaining)*; `cards` *(rendered)* | every event |
| `decision` | `decision`: the raw decide message (with `state`); `question`, `options` *(rendered)*: the prompt's question and option lines; `hint_text` *(rendered, selections)*; `cards` *(rendered)*: `{code: {n, t, atk, def, lv}}` | every decision except `game_over` |
| `reply` | `id`, `choice` (every pick, also for `select_unselect`, where the bot is sent one per prompt), `sent` (what went to the bot), `source` (`backend`, `rule:<name>`, `auto`, `fallback`, `human` (a coached human's move), `game_over`; `pilot` in old copilot logs), `why`, `plan`, `label` (backend label), `seconds` (for `human`: their thinking time), `note` (warning), `usage` (`seconds`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `error`; for `human`, the coach's usage is on its `advice`), `say`, `suggested` (old copilot logs), `trivial` and `advised` (coach games) | the reply record, merged with the logged decision and the backend's usage |
| `advice` | `id` (the decision), `choice` (null: no advice), `why`, `plan`, `source` (`backend`, `rule:<name>`, `auto`, `skipped`: the human answered before the coach got to it, `failed`), `label`, `seconds` (backend time), `after` (seconds from the decision to the advice), `late` (bool: the human had already answered), `hindsight` (bool: a look back at an answered decision), `kind`, `usage` | coach mode: a recommendation for the human's seat, before or after their move |
| `human_choice` | `id`, `choice`, `advised`, `matched` (bool; for `select_unselect`, the first advised pick) | what the human did, published with whichever of `advice` and their `reply` comes second (advice with a choice only) |
| `review` | `markdown` (review.md), `path`, `seconds`, `label` (the review backend) | coach mode: the review after the game (recorded coach games replay it last) |
| `feedback_ack` | `text`, `context` (`turn T, right after decision #N`), `who` (`Opponent`, `Spectator`, `Web panel`) | a note was saved (chat `!note` or the panel) |
| `game_end` | `result` (`win` / `loss` / `draw`, for this seat), `reason`, `reason_text` *(rendered)* | the `win` event |

A decision card in the panel is the `decision` plus whatever arrives later for the same `(seat, id)`: `reply`,
`advice`, `human_choice`. A decision with neither a reply nor a human choice shows as "thinking"; in a coach game, as
"waiting for your move" (with the coach's line once its advice is in).

### What later stages publish

- **Stage 4 (self-play, several seats), done.** `ygo_agent.match.run_games` links the two AI seats of every duel
  (`native_seat.link`), so each seat's `DuelBrain(..., game_id=G, seat=S)` shares `G`: `<run>-m<match>-g<game>`
  in-process, `<run>-g<game>` in a room (`<run>-r<room>-g<game>` with parallel rooms), where `<run>` is the run
  folder's name. The panel shows both seats, seat tabs and god view. Parallel games are
  separate games in the list. A seat that logs quietly must pass `publish=True`; the terminal's `--quiet` (echo
  "key") still publishes everything.
- **Stage 5 (coach), done.** The coached seat's GameLog publishes the `decision` (the human's own view) at once,
  `advice` when the coach answers (`GameLog.advice()`, `late: true` if the human already chose), the human's move as
  a `reply` with `source: "human"`, and `human_choice` with whichever of the two comes second; then the `review`.
  An AI opponent in a coach game doesn't publish (its reasoning and hand would show).

## Screenshots

`docs/img/` holds `web-panel.png` (1440×900), `web-panel-1024.png`, `web-panel-light.png` and `web-games.png`,
taken from replays of real recorded games. To retake them, or to record frames of a demo for a GIF:

```sh
ygo-agent web --port 7931 &                     # or: ygo-agent web --demo games/<dir> --speed 2 --port 7931 &
node tests/web/shoot.mjs "http://127.0.0.1:7931/?game=rec:<dir>&d=17&theme=dark" docs/img/web-panel.png 1440x900
node tests/web/shoot.mjs frames.json            # [{"url": ..., "out": "frames/f%03d.png", "frames": 120, "every": 250}]
ffmpeg -framerate 4 -i frames/f%03d.png -vf "fps=8,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse" demo.gif
```

`shoot.mjs` drives headless Firefox over WebDriver BiDi with Node 22's built-in WebSocket, so nothing needs
installing. Page parameters: `game=rec:<dir>` or a live game id, `d=<decision id>`, `theme=dark|light`, `tab=log`,
`seat=1`.

## Tests

`tests/web/`: the bus (backlog, catch-up, several games and seats, eviction, SSE frames, the renderer); the GameLog
hook on a saved regression case (every decision gets its reply, the texts match `describe.py`, coach advice and the
human's move in either order, two seats in one game, panel notes in `feedback.md`); recorded games (`game.md` parsing, current and
pre-Stage-0 logs, every game under `games/` when there are any, demo mode through the bus); and the server over
urllib (static files, APIs, pictures local / downloaded and cached / placeholder, SSE resume, the feedback endpoint,
refused cross-site requests).

`tests/web/test_web_browser.py` (integration: the EDOPro install, Firefox and Node 22) follows live games in headless
Firefox through `tests/web/check.mjs`, a small WebDriver BiDi step runner that also collects console errors: a native
arena game (`tests/fixtures/web/native-place-game`, the game whose board once froze) replayed through a DuelBrain onto
the bus the way a live seat publishes it (`tests/web/live_replay.py`, also runnable by hand), the same game with
native-only message shapes slipped in (coin/dice/equip/counter/swap/declared/confirm events, an `announce_card`
answered with a code, a multi-step `select_unselect`), and a heuristic-vs-random native self-play game. Each checks
that the board reaches the final turn and LP with no render error; the first also checks that clicking the newest
card keeps the board live and that an older one pauses it visibly.

## Known gaps

- Between decisions the board follows the events (moves, summons, position changes, Set cards flipped by their
  activation, LP, chain); it is resynced from the full state at every decision. A card moved by an event shows its
  printed ATK/DEF until then, and a negation (the `NEG` badge, e.g. from Fiendish Chain) shows from the next
  decision's state.
- The opponent's Xyz materials and counters appear only when the seat reports them (`ov`, and `ctr` from native
  seats).
- Pendulum and Extra Monster Zones are drawn only when occupied, in a simple way (MR3 never uses the EMZ).

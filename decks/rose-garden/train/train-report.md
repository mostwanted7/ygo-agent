# Training report: Rose Garden

Status: **done**. Reviewer: opus; player: opus; rules MR3; opponents: windbot:Blue-Eyes, windbot:Dragunity.
Playbook: `rose-garden/playbook.md`, 8.3 KB.
Spent $11.09 (API-price equivalents; a Claude Code subscription isn't billed per call) in 21 min of running time.

## The owner's tips

- Interview: skipped (--no-interview).
- `tips.md`: 1 tip(s); the study wrote the playbook from them and every review saw them.

## Study

- Draft playbook: 9.2 KB (`train/study/playbook-draft.md`), 4 lines to test, 32/32 script citations verified (`train/study/card-checks.md`).
- Go first: False — The owner gave no tip on this. The deck's strongest plays break boards: Black Rose Dragon's wipe, and Ruddy Rose Dragon's wipe that leaves a 3200 attacker. Synchro Zone can't be used on turn 1 anyway. Going second also gives an extra card for the 2-3-card Synchro lines. The lab should compare it with going first on L1 or L2.
- Problems: 9.2 KB, over the 8 KB target

## Rounds

| round | lab hands | lines verified | games | W-L-D | major mistakes | lessons | playbook |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 2 | 2 | 2-0-0 | 0 | 0 | 8.3 KB |

## Games

| game | opponent | went | result | turns | invalid | fallback | cost | log |
|---|---|---|---|---|---|---|---|---|
| r1-g1 | windbot:Blue-Eyes | first | win | 5 | 0/82 | 0.0 | $1.70 | `train/round-1/games/2026-10-22_163433_rose-garden-vs-blue-eyes-ai` |
| r1-g2 | windbot:Dragunity | second | win | 6 | 0/69 | 0.0 | $1.51 | `train/round-1/games/2026-10-22_163433_rose-garden-vs-dragunity-ai` |

## Lines (lab verification)

| id | line | going | status | round | why |
|---|---|---|---|---|---|
| L1 | White Rose + Roxrose → Ruddy | first | verified | 1 | Both hands ran NS White Rose → Roxrose (Basal) → BRD with no wipe → White Rose's GY mill → Basal revives Roxrose → Ruddy, banish declined. Both ended on Ruddy Rose Dragon with BRD in the GY and no engine rejection. In ha |
| L2 | Opponent-turn wipe | first | untested |  |  |
| L3 | Lonefire → Periallis | first | untested |  |  |
| L4 | Ruddy wipe going second | second | verified | 1 | Better than expected. Basal from hand → Roxrose (searched a 2nd Basal) → White Rose Special Summoned itself → BRD, no wipe (Mariña milled) → NS Red Rose → Set Basal → Ruddy (BRD + Red Rose). Chain: Red Rose CL1, Ruddy CL |

## Where the player didn't follow a correct line (lab)

The same error in two rounds, after a wording fix, is a case for a hard rule in rules.py.

- (r1) hand-02 (L2): the player had White Rose + Roxrose + Synchro Zone but built Ruddy, so the owner's opponent-turn Synchro Zone play went untested. The Example sequence now reads: 'end with both face-up + Synchro Zone and Basal Set ... send it in their Main Phase'. For the lab, the line says 'do NOT Synchro' explicitly.

## Regression cases


Final run against the trained playbook: 0/0 cases passed every one of 0 runs (`train/tests-final.txt`).

## Mistakes by model

| player | mistakes | major | no judgment | already covered by the playbook |
|---|---|---|---|---|
| opus | 2 | 0 | 0 | 1 |

## Cost and time by phase

| kind | calls | cost | time |
|---|---|---|---|
| interview | 1 | $0.14 | 10 s |
| study | 1 | $1.62 | 6 min |
| condense | 2 | $0.33 | 1 min |
| lab-hand | 6 | $3.99 | 12 min |
| lab-review | 1 | $0.70 | 2 min |
| game | 2 | $3.22 | 8 min |
| review | 2 | $1.09 | 3 min |

## For a human to check

- 2 open question(s) were settled by later labs and games (`state.json`, settled_questions).
- Read the playbook against the card scripts; the lines still marked *(unverified)* haven't been seen working in the engine.
- `train/general-proposals.md`: proposed lessons for every deck (not applied).
- Owner's tip (Synchro Zone for an opponent-turn Black Rose Dragon): the playbook makes this a main priority (line L2), but nothing has tested it. Does flipping Synchro Zone in their Standby Phase and sending it in their Main Phase work in EDOPro (its cost needs STATUS_EFFECT_ENABLED)?
- Synchro Zone script line `e3:SetCountLimit(1,{id,1})` sits where the e5 limit should be. So e5 (the opponent-turn Synchro) seems to have no once-per-turn, and e3 (the revive) is keyed {id,1}. Is that the engine's real behaviour?
- When Black Rose Dragon's wipe destroys a face-up Synchro Zone at the same time as BRD, does Synchro Zone's revive (e3) still trigger for BRD?
- Does Rose Princess, Special Summoned by her own procedure (treated as a Tuner), let White Rose Dragon Special Summon itself?
- Lonefire / Ruddy Rose Witch lines (L3): which ending is stronger, Garden Rose Flora or Witch of the Black Rose plus a drawn Plant? Needs lab testing.
- Owner's tip (opponent-turn BRD through Synchro Zone): in hand-02 a Synchro Zone flipped face-up in the opponent's Draw Phase, but its e5 send-to-Synchro has still never been used. Does it work in their Main Phase (cost needs STATUS_EFFECT_ENABLED)?
- Synchro Zone script line 52 `e3:SetCountLimit(1,{id,1})` overwrites e3's limit and leaves e5 with none: is e5 really unlimited per turn in the engine?
- L3 comparison: Lonefire → Rose Girl → Periallis + Mariña (verified) vs Lonefire → Ruddy Rose Witch → Flora/Witch of the Black Rose (untested). Which ending is stronger against real opponents?
- Does Rose Princess, Special Summoned by her own procedure (treated as a Tuner), let White Rose Special Summon itself?
- When BRD's wipe destroys a face-up Synchro Zone together with BRD, does Zone's revive (e3) still trigger?

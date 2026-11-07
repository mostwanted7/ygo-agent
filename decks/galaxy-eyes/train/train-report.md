# Training report: Galaxy-Eyes

Status: **done**. Reviewer: opus; player: opus; rules MR3; opponents: windbot:Blue-Eyes, windbot:Dragunity.
Playbook: `galaxy-eyes/playbook.md`, 8.1 KB.
Spent $9.34 (API-price equivalents; a Claude Code subscription isn't billed per call) in 18 min of running time.

## The owner's tips

- Interview: skipped (--no-interview).
- `tips.md`: 1 tip(s); the study wrote the playbook from them and every review saw them.

## Study

- Draft playbook: 8.9 KB (`train/study/playbook-draft.md`), 4 lines to test, 34/34 script citations verified (`train/study/card-checks.md`).
- Go first: True — The owner gave no tip about this, so this is my own reading of the scripts. The common starters (Schwarzschild, Soldier + a LIGHT discard) end on two Rank 8s. A Number 38 or Number 90 negate plus Tachyon Transmigration (live from the hand with Number 107) is a solid board to defend with. The going-second tools (Cipher Dragon, Full Armor, Cipher Blade) still work later.
- Problems: 8.9 KB, over the 8 KB target

## Rounds

| round | lab hands | lines verified | games | W-L-D | major mistakes | lessons | playbook |
|---|---|---|---|---|---|---|---|
| 1 | 3 | 2 | 1 | 1-0-0 | 1 | 1 | 8.1 KB |

## Games

| game | opponent | went | result | turns | invalid | fallback | cost | log |
|---|---|---|---|---|---|---|---|---|
| r1-g1 | windbot:Blue-Eyes | first | win | 3 | 0/63 | 0.0 | $1.67 | `train/round-1/games/2026-10-24_014150_galaxy-eyes-vs-blue-eyes-ai` |

## Lines (lab verification)

| id | line | going | status | round | why |
|---|---|---|---|---|---|
| L1 | Schwarzschild → Dragluxion | first | verified | 1 | Schwarzschild pulled Afterglow → Dragluxion → Primal (from hand) searched Transmigration → Dragluxion to 107 (+C107) → Afterglow summoned Galaxy-Eyes Photon Dragon. With Primal already in hand, Dragluxion searched Galaxy |
| L2 | Soldier + Emperor | first | verified | 1 | Soldier (discard Emperor, revive, search Wizard) → Wizard Lv8 via Emperor's extra NS → Dragluxion (search Primal) → Primal searched Seventh Tachyon → Afterglow; Dragluxion to 107; regular NS Summoner revived Emperor, the |
| L3 | Seventh Tachyon → Schwarzschild | first | untested |  |  |
| L4 | Going second OTK into empty field | second | untested |  |  |

## Pitfalls added

- (lab, minor) **When you have a spare Normal Summon from Photon Emperor, don't spend it on another Photon Emperor** because it is Level 8 and needs 2 Tributes; use it on a Lv4 LIGHT (Wizard, Summoner).
- (r1-g1, major) **When Seventh Ascension or Seventh Tachyon is in hand, resolve Seventh Tachyon before Dragluxion becomes Number 107 or attaches C107**, because Seventh Tachyon must reveal a Number 101-107 still in your Extra Deck, and 107 and C107 are the only ones this deck has. Once both are gone, every Seventh card is dead.

## Regression cases

- `seventh-tachyon-before-107` (r1-g1 #18): With Seventh Ascension in hand, don't turn Dragluxion into Number 107 yet: Seventh Tachyon needs 107 or C107 in the Extra Deck to reveal. expect [] reject [[3]]

Final run against the trained playbook: 1/1 cases passed every one of 3 runs (`train/tests-final.txt`).

## Edits checked against the regression cases

Each condense and section rewrite was replayed against the saved cases with the player's backend (runs passed, before → after); a rewrite that made them fail more often got one fix-up try, else the previous text was kept.

| step | edit | before | after | fix-up | kept |
|---|---|---|---|---|---|
| r1.review.r1-g1 | section edits | 2/2 | 2/2 | – | after |
| r1.condense | condense | 2/2 | 2/2 | – | after |

## Mistakes by model

| player | mistakes | major | no judgment | already covered by the playbook |
|---|---|---|---|---|
| opus | 1 | 1 | 1 | 0 |

## Cost and time by phase

| kind | calls | cost | time |
|---|---|---|---|
| interview | 1 | $0.19 | 12 s |
| study | 1 | $1.83 | 5 min |
| condense | 2 | $0.35 | 2 min |
| lab-hand | 3 | $3.70 | 8 min |
| lab-review | 1 | $0.52 | 1 min |
| game | 1 | $1.67 | 4 min |
| review | 1 | $0.59 | 2 min |
| test | 4 | $0.50 | 1 min |

## For a human to check

- 1 open question(s) were settled by later labs and games (`state.json`, settled_questions).
- Read the playbook against the card scripts; the lines still marked *(unverified)* haven't been seen working in the engine.
- `train/general-proposals.md`: proposed lessons for every deck (not applied).
- Can a monster stolen by Galaxy-Eyes Cipher Dragon, whose name has become 'Galaxy-Eyes Cipher Dragon', be used for Cipher X's alternate summon (IsSetCard(SET_CIPHER_DRAGON))? That would make the steal permanent.
- If Afterglow is detached for Number 62's damage-calculation boost, can its trigger (which has no EFFECT_FLAG_DAMAGE_STEP) activate during the Damage Step?
- Does Number 62's damage-calculation boost (EVENT_PRE_DAMAGE_CALCULATE, IsRelateToBattle) work on a direct attack? The worked lethal example in L4 depends on it.
- Do Photon Tokens count as 'Photon' monsters for Photon Vanisher's summon condition and Photon Emperor's revive condition?
- When Schwarzschild pulls Tachyon Primal, is Primal's search trigger stopped by the negation? The playbook assumes yes, which is why it pulls Afterglow.
- Owner tip 1 still gives no target board. Lab boards were 107 + C62 + 38, 107 + 90 + Photon Blast. Which do you prefer, and when would you go for Cipher Dragon or Full Armor instead?
- Galaxy Hundred took Number 38 from the dummy's Extra Deck only because the dummy plays this same deck. Against real opponents, should Hundred mostly banish their best Extra Deck monster, or is Dragluxion's search better spent on Primal or Transmigration?

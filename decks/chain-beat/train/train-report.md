# Training report: Chain Beat

Status: **done**. Reviewer: opus; player: opus; rules MR3; opponents: windbot:Blue-Eyes, windbot:Dragunity.
Playbook: `chain-beat/playbook.md`, 8.5 KB.
Spent $13.37 (API-price equivalents; a Claude Code subscription isn't billed per call) in 25 min of running time.

## The owner's tips

- Interview: skipped (--no-interview).
- `tips.md`: 7 tip(s); the study wrote the playbook from them and every review saw them.

## Study

- Draft playbook: 8.0 KB (`train/study/playbook-draft.md`), 4 lines to test, 26/26 script citations verified (`train/study/card-checks.md`).
- Go first: True — Owner's tip: trap-heavy deck, going first lets every trap (Solemn Strike, Torrential, Macro Cosmos, Waking the Dragon bait) be live on the opponent's first turn.

## Rounds

| round | lab hands | lines verified | games | W-L-D | major mistakes | lessons | playbook |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 4 | 2 | 2-0-0 | 1 | 0 | 8.5 KB |

## Games

| game | opponent | went | result | turns | invalid | fallback | cost | log |
|---|---|---|---|---|---|---|---|---|
| r1-g1 | windbot:Blue-Eyes | first | win | 29 | 0/214 | 0.0 | $6.08 | `train/round-1/games/2026-10-22_163447_chain-beat-vs-blue-eyes-ai` |
| r1-g2 | windbot:Dragunity | second | win | 6 | 1/99 | 0.0 | $2.03 | `train/round-1/games/2026-10-22_163447_chain-beat-vs-dragunity-ai` |

## Lines (lab verification)

| id | line | going | status | round | why |
|---|---|---|---|---|---|
| L1 | Luna opener | first | verified | 1 | NS Luna, search 2nd Luna, Black Garden after the summon, Set Solemn Strike + Waking. End board matched exactly, and there were no rejections. No Duality was in the hand, so the Duality-first step went untested here, thou |
| L2 | Draw then set | first | verified | 1 | Pot of Desires → Upstart → Duality (took Luna) → NS Luna (searched Luna) instead of Thunderbird → Set Solemn, Torrential, Macro Cosmos. The board was equal or better than expected (Luna on field with Thunderbird, Rabbit  |
| L3 | Rabbit under Duality | first | verified | 1 | Duality (took Dark Hole) → NS Rabbit → Black Garden → Set Macro Cosmos and MST. Rabbit's banish was held for the whole turn, Macro was flipped in the opponent's Draw Phase, and there were no rejections. |
| L4 | Yata lock going second | second | verified | 1 | Pot of Desires → MST (hit Mirror Force) → Dark Hole cleared both monsters → NS Yata, direct attack for 200 and Yata's skip-draw effect resolved → MP2 Set Solemn + Black Garden; Yata returned to hand in the End Phase. |
| L5 | No monster going second | second | untested |  |  |

## Regression cases

- `commit-beater-before-yata-lock` (r1-g1 #78): Their field is empty, they are at 9400 LP after three Yata turns and Thunderbird sits in hand: Normal Summon Thunderbird to start real damage instead of another 200-damage Yata. expect [[1]] reject [[0]]

Final run against the trained playbook: 1/1 cases passed every one of 3 runs (`train/tests-final.txt`).

## Edits checked against the regression cases

Each condense and section rewrite was replayed against the saved cases with the player's backend (runs passed, before → after); a rewrite that made them fail more often got one fix-up try, else the previous text was kept.

| step | edit | before | after | fix-up | kept |
|---|---|---|---|---|---|
| r1.review.r1-g1 | section edits | 0/2 | 2/2 | – | after |
| r1.review.r1-g2 | section edits | 2/2 | 2/2 | – | after |
| r1.condense | condense | 2/2 | 2/2 | – | after |

## Mistakes by model

| player | mistakes | major | no judgment | already covered by the playbook |
|---|---|---|---|---|
| opus | 4 | 1 | 1 | 0 |

## Cost and time by phase

| kind | calls | cost | time |
|---|---|---|---|
| interview | 1 | $0.10 | 16 s |
| study | 1 | $0.70 | 3 min |
| lab-hand | 6 | $1.47 | 4 min |
| lab-review | 1 | $0.32 | 42 s |
| game | 2 | $8.12 | 17 min |
| review | 2 | $1.65 | 5 min |
| test | 5 | $0.83 | 2 min |
| condense | 1 | $0.19 | 57 s |

## For a human to check

- Read the playbook against the card scripts; the lines still marked *(unverified)* haven't been seen working in the engine.
- `train/general-proposals.md`: proposed lessons for every deck (not applied).
- Waking the Dragon summons with IsCanBeSpecialSummoned(e,0,tp,false,false); Ultimate Falcon has EnableReviveLimit. The owner says Falcon is the 99.99% pick. Lab: confirm EDOPro allows Falcon from the Extra Deck via Waking.
- Luna's negation needs the opponent's copy to pass IsAbleToGraveAsCost. Owner's tip: Macro Cosmos prevents the negation. This depends on the core treating TO_GRAVE_REDIRECT as making the cost impossible. Verify in the lab.
- Drowning Mirror Force needs GetAttackTarget()==nil at attack declaration. If Rabbit/Thunderbird leave in response to an attack on them, does the replayed direct attack raise a new attack-announce window for Drowning?
- Black Garden on your Normal Summon under Pot of Duality: does the halving still apply while the Rose Token is skipped (IsPlayerCanSpecialSummonMonster fails)? The script suggests halving yes, token no.
- Thunderbird banished during a Standby Phase: confirm it returns at the following Standby (retcon / reset 2), not the same one.
- Questions 1-5 stay open: the dummy never acted, so Waking/Falcon, Luna's negation under Macro Cosmos, Drowning after a dodge and Thunderbird's return timing never came up. Black Garden under Duality also went untested: every player activated Garden after its own summon. A lab hand with a scripted opponent action (backrow removal on Waking, an attack) is needed.
- Going second with no monster, the player kept the field empty and held Black Garden so that the opponent's attacks stay direct into Drowning Mirror Force. Black Garden's script (line 96-98) has the summoner Special Summon the Rose Token to its opponent's field, so the opponent's summons would give us a token and break the direct-attack condition. Does the owner agree that Garden should wait in that spot (tip 1 suggests activating Garden after we have a monster)?

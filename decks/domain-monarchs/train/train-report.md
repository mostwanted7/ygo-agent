# Training report: Domain Monarchs

Status: **done**. Reviewer: opus; player: opus; rules MR3; opponents: windbot:Blue-Eyes, windbot:Dragunity.
Playbook: `domain-monarchs/playbook.md`, 8.0 KB.
Spent $12.79 (API-price equivalents; a Claude Code subscription isn't billed per call) in 24 min of running time.

## The owner's tips

- Interview: skipped (--no-interview).
- `tips.md`: 6 tip(s); the study wrote the playbook from them and every review saw them.

## Study

- Draft playbook: 9.7 KB (`train/study/playbook-draft.md`), 5 lines to test, 29/29 script citations verified (`train/study/card-checks.md`).
- Go first: True — The owner's first tip is built around going first: one Tribute Summoned Monarch (Erebus, Ehther or Thestalos) behind Domain, Erupt or March, with Escalation or Stormforth Set. The scripts support it. Erebus's random shuffle from hand and Thestalos's discard work on the opponent's full opening hand, and Domain's Extra Deck lock holds as long as you control a Tribute Summoned monster and they don't.
- Problems: 9.7 KB, over the 8 KB target

## Rounds

| round | lab hands | lines verified | games | W-L-D | major mistakes | lessons | playbook |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 4 | 2 | 2-0-0 | 0 | 0 | 8.6 KB |

## Games

| game | opponent | went | result | turns | invalid | fallback | cost | log |
|---|---|---|---|---|---|---|---|---|
| r1-g1 | windbot:Blue-Eyes | first | win | 5 | 0/148 | 0.0 | $2.94 | `train/round-1/games/2026-10-22_160418_domain-monarchs-vs-blue-eyes-ai` |
| r1-g2 | windbot:Dragunity | second | win | 4 | 0/110 | 0.0 | $2.22 | `train/round-1/games/2026-10-22_160418_domain-monarchs-vs-dragunity-ai` |

## Lines (lab verification)

| id | line | going | status | round | why |
|---|---|---|---|---|---|
| L1 | Edea → Eidos double Monarch | first | verified | 1 | Domain → NS Edea → Eidos (extra granted) → Domain −2 on Ehther → Ehther tributing Eidos. The player pulled Kuraz instead of Ehther #2. Kuraz's trigger activated (#18) and destroyed Edea + Kuraz for 2 draws. Prime's GY ef |
| L2 | Domain + Mithra | first | verified | 1 | The exact expected board: Domain, Tribute Summoned Ehther, Erebus in GY, Ehther #2 returned to hand. Stormforth (from Pantheism's GY search) and Prime were also Set. Mithra's Tributed trigger granted the extra summon aft |
| L3 | Tenacity into Domain | first | verified | 1 | Tenacity revealing Erebus fetched Domain, then the player followed the L2 route: Erebus tributing Mithra (shuffle), then Mithra's extra summon for Ehther tributing Erebus, which pulled Ehther #2. It ended with Domain, Eh |
| L4 | One for One Edea chain | first | untested |  |  |
| L5 | Stormforth break | second | verified | 1 | Tenacity → Return; Domain; NS Edea → Eidos; Domain −2 on Erebus; Stormforth; Erebus Tribute Summoned by Tributing Blue-Eyes (#31). Erebus shuffled a Set S/T and Return chained to search Ehther. Pantheism's GY search got  |

## Where the player didn't follow a correct line (lab)

The same error in two rounds, after a wording fix, is a case for a hard rule in rules.py.

- (r1) hand-01: after Edea (Normal Summon) → Eidos → Ehther, the player planned a further turn-1 Tribute of Ehther for Erebus, which doesn't exist. Fixed by 'Count summons first' in Situational considerations and the one-extra-per-turn note in Card roles.
- (r1) hand-02/hand-03: Ehther #2 sat in hand through the dummy's whole turn, so the free opponent-turn Tribute Summon was lost when they passed to the End Phase. Hand-05 used it at the first Main Phase window and gained a body. Fixed by the 'Ehther works only in their Main Phase' wording.
- (r1) hand-06: Edea was left in face-up Attack opposite Blue-Eyes. Fixed by 'Leave fodder in Defense' in the No-Monarch bullet.

## Pitfalls added

- (lab, major) **Plan for only one extra Tribute Summon per turn**, because Eidos and Mithra both require `IsPlayerCanAdditionalTributeSummon`: after Edea's Normal Summon and Eidos's extra, the Monarch you just summoned can't be Tributed for another one this turn. Save the second Monarch for Escalation or Ehther's hand effect on their turn.

## Regression cases


Final run against the trained playbook: 0/0 cases passed every one of 0 runs (`train/tests-final.txt`).

## Cost and time by phase

| kind | calls | cost | time |
|---|---|---|---|
| interview | 1 | $0.09 | 13 s |
| study | 1 | $0.97 | 3 min |
| condense | 4 | $0.65 | 3 min |
| lab-hand | 6 | $3.98 | 12 min |
| lab-review | 1 | $0.72 | 2 min |
| game | 2 | $5.17 | 14 min |
| review | 2 | $1.21 | 3 min |

## For a human to check

- 5 open question(s) were settled by later labs and games (`state.json`, settled_questions).
- Read the playbook against the card scripts; the lines still marked *(unverified)* haven't been seen working in the engine.
- `train/general-proposals.md`: proposed lessons for every deck (not applied).
- Caius going first: the owner says it's bad. The script makes its banish mandatory on any card, so Mithra's Vassal Token on the opponent's field is a legal target that saves your own card. That's an edge case, not a conflict with the tip.
- Caius going first (owner's tip 1 says it's bad): the Vassal Token edge case is still untested and not in conflict.

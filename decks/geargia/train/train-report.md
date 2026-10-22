# Training report: Geargia

> **Note (2026-10-22):** after this training the deck list was switched to the user's Gadget Geargia (`~/Games/ProjectIgnis/deck/Gadget Geargia.ydk`: +2 Gold Gadget, +2 Silver Gadget; -2 Monster Reborn, -1 Graceful Charity, -1 Fiendish Chain). The playbook was adapted by hand (Gadget roles, Gadget + Armor, Limiter Removal floats; the Monster Reborn pitfall removed), not retrained. The case `loop-reborn-arsenal-before-xyz` depended on Monster Reborn and was moved to `train/retired-tests/`; the other six still pass (sonnet, 1 run each).

Status: **done**. Reviewer: opus; player: sonnet; rules MR3; opponents: windbot:Blue-Eyes, windbot:Dragunity.
Playbook: `geargia/playbook.md`, 13.9 KB.
Spent $14.32 of a $45.00 budget (API-price equivalents; a Claude Code subscription isn't billed per call) in 32 min of running time.

## Study

- Draft playbook: 13.5 KB (`train/study/playbook-draft.md`), 6 lines to test, 25/25 script citations verified (`train/study/card-checks.md`).
- Go first: True — The deck is a Trap-heavy stun deck (Solemn Strike/Judgment, Fiendish Chain, Geargiagear) that only produces 1 Rank 4 per turn. Its Traps need to be Set before the opponent's turn, and Geargiagear is a Normal Trap that pays off on the following turn. Going first lets the Traps and Gear Gigant X protect a modest board.

## Rounds

| round | lab hands | lines verified | games | W-L-D | major mistakes | lessons | playbook |
|---|---|---|---|---|---|---|---|
| 1 | 9 | 2 | 2 | 1-1-0 | 1 | 4 | 14.1 KB |
| 2 | 6 | 3 | 2 | 1-1-0 | 5 | 5 | 21.6 KB |

## Games

| game | opponent | went | result | turns | invalid | fallback | cost | log |
|---|---|---|---|---|---|---|---|---|
| r1-g1 | windbot:Blue-Eyes | first | win | 3 | 0/73 | 0.0 | $0.70 | `train/round-1/games/2026-10-21_214133_geargia-vs-blue-eyes-ai` |
| r1-g2 | windbot:Dragunity | second | loss | 13 | 0/221 | 0.0 | $2.24 | `train/round-1/games/2026-10-21_214133_geargia-vs-dragunity-ai` |
| r2-g1 | windbot:Blue-Eyes | first | loss | 4 | 0/73 | 0.0 | $0.79 | `train/round-2/games/2026-10-21_215852_geargia-vs-blue-eyes-ai` |
| r2-g2 | windbot:Dragunity | second | win | 8 | 0/80 | 0.0 | $0.82 | `train/round-2/games/2026-10-21_215852_geargia-vs-dragunity-ai` |

## Lines (lab verification)

| id | line | going | status | round | why |
|---|---|---|---|---|---|
| L1 | Line 1+: Geargiarsenal + 2 Geargiaccelerator → two Gear Gigant X | first | verified | 1 | hand-03/05/06 played NS Arsenal, SS Accelerator, Arsenal→Geargiano (Deck), Geargiano→revive Arsenal (negated, 1500 ATK), Xyz Gear Gigant X, detach→search, with no rejection. hand-01 (the stacked L1 hand) played a better  |
| L2 | Line 2: Geargiaccelerator + Geargiaccelerator/Geargiarmor | first | verified | 1 | hand-02: NS Geargiarmor face-up, SS Accelerator, Gear Gigant X, detach Armor→add Accelerator, Set Traps. hand-08 got the same two Lv4s through Mk-II (NS Mk-II→SS Armor from hand, SS Accelerator). |
| L3 | Line 3: Mk-II + a Lv4 Geargia in hand (Arsenal → Zenmaines branch) | first | untested |  |  |
| L4 | Line 4: Geargiarsenal with no other starter | first | verified | 2 | hand-06 (random hand: Arsenal, Geargiagear, Solemn Strike...) played the no-Reborn branch: NS Arsenal → Tribute → Geargiarmor from Deck (#8) → Armor turned itself face-down (#11) → Set Geargiagear + Solemn Strike. The ex |
| L5 | Line 5: Geargiagear in hand (add to any line) | first | verified | 2 | Line 1 (with the Geargiano loop) → Gear Gigant X searched Accelerator. Then Monster Reborn on the detached Arsenal + Accelerator from hand → a second Gear Gigant X, which detached Arsenal and took it back from the GY. Ge |
| G1 | Line G1: Arsenal + Accelerator + Limiter Removal | second | untested |  |  |
| G2 | Line G2: Lv4 Geargia + Geargiaccelerator vs a big Normal Monster | second | verified | 2 | The player used the Dark Rebellion branch of step 2: NS Armor face-up, SS both Accelerators, Dark Rebellion from the 2 Accelerators. It detached 2 to halve Blue-Eyes (DR 4000) and attacked: Blue-Eyes destroyed, 2500 dama |
| L1R | Line 1R: Line 1 + Monster Reborn → two Gear Gigant X | first | untested |  |  |

## Where the player didn't follow a correct line (lab)

The same error in two rounds, after a wording fix, is a case for a hard rule in rules.py.

- (r1) hand-06 (G1): the player summoned Gear Gigant X in Defense and never entered the Battle Phase, so Limiter Removal (4600 vs Blue-Eyes 3000) was never used. The G1 wording now says to summon it in Attack and attack Blue-Eyes, and point 5 of the going-second section says to go to battle.
- (r1) hand-05: the player ended with Gear Gigant X + 2 face-up Geargiaccelerators instead of Xyzing the two Accelerators into a second Gear Gigant X. Line 1+ now says not to stop with spare Accelerators on the field.
- (r1) hand-09 (going second, Armor + Accelerator vs Blue-Eyes): the player just Set Armor and passed. Line G2 (Castel / Dark Rebellion) now covers this hand.
- (r2) hand-01 (L3): after Mk-II summoned Arsenal, the player Set Geargiagear and ended. It never Tributed Arsenal → Geargiano or made Wind-Up Zenmaines. Fixed wording: 'don't stop with Mk-II + Arsenal on the field', plus a general rule to finish the Xyz before Setting cards.
- (r2) hand-04 (G1): the player made two Gear Gigant X and Set Limiter Removal, but never entered the Battle Phase. It also skipped the Geargiano loop, so no float target was in the GY. Fixed wording: going second, the Main Phase ends with 'Go to the Battle Phase'; never Set Limiter Removal; loop first in Line 1+.
- (r2) hand-02 (L4): the player held Armor in hand and Tributed Arsenal for Accelerator rather than Armor. This was reasonable; the playbook now lists it as an option.

## Lessons added

- (lab, major) **When the opponent's boss is a Normal Monster (e.g. Blue-Eyes White Dragon), don't plan on Fiendish Chain or Forbidden Droplet**: both need a face-up Effect monster on their field. Break it with Castel, Dark Rebellion or a Limiter Removal battle.
- (lab, minor) **When you hold Geargiarsenal + two Geargiaccelerator, make two Gear Gigant X**: Xyz the two Accelerators, detach one and add it back from the GY, Special Summon it next to the still face-up Arsenal, and Xyz again. Two searches and two bodies.
- (r1-g1, minor) **When you hold Limiter Removal during an attack, cast it in the attack's last response window, the one where only Limiter Removal is offered** (Damage Step, before damage calculation). Each attack opens about four response windows. Passing through the early ones is fine, and the boost still applies to the attack in progress. Count lethal first: in this game 2300 + 2×2300 + 2×1100 already beat 8000.
- (r1-g2, major) **When you Xyz Summon Dark Rebellion Xyz Dragon, use its effect that same turn, before you end the turn, especially while the opponent's negater is off the field** (e.g. Stardust Dragon/Assault Mode sitting in the GY after it Tributed itself). Both changes are permanent: the target's ATK stays halved and Dark Rebellion keeps the gain (the script resets them only when the card leaves the field). It can target any face-up monster with ATK, with no Level restriction. Halving a 2100 attacker makes Dark Rebellion 3550, which walls a 3000 boss. Left at 2500, it just dies to that boss.
- (r1-g2, minor) **When your field is empty and the opponent has attackers, Set any monster in hand as a blocker (even Ash Blossom, DEF 1800) instead of holding it as a hand trap**, unless you can name a specific search it will stop next turn. A blocker saves the damage of one attack. In this game, keeping Ash Blossom cost 5100 LP in one turn.
- (r1-g2, minor) **When the opponent has Stardust Dragon/Assault Mode (or another monster that Tributes itself to negate), feed it your least important activation first, then make the real plays while it is in the GY.** It negates one thing and only comes back in the End Phase. Here it ate Maxx "C", Monster Reborn, Arsenal's Tribute and the Gear Gigant X float. Everything activated after the bait resolved untouched, so put your removal (Dark Rebellion, Castel) and searches in that window.
- (lab, major) **Going second, when your Xyz is in Attack Position, go to the Battle Phase before ending the turn, and keep Limiter Removal in hand for your own Damage Step** because Setting it and passing deals no damage, and Gear Gigant X never trades with Blue-Eyes.
- (r2-g1, major) **When Monster Reborn revives Arsenal, Tribute that Arsenal for Geargiano and loop back (Geargiano → Arsenal) before you Xyz Summon Gear Gigant X** because the revived Arsenal keeps its effect and its Tribute has no once-per-turn limit. The loop costs nothing and leaves Geargiano in the GY as Gear Gigant X's float target. In r2-g1 the player skipped it, Gear Gigant X was destroyed with nothing to revive, and the empty field took 5500.
- (r2-g1, major) **When you activate Forbidden Droplet on the opponent's turn, send as many cards as they have face-up Effect monsters, and include your own face-up Attack Position weak monster (e.g. a Normal Summoned Mk-II) as part of the cost** because each card sent negates and halves one more of their monsters for the turn. Removing your only Attack Position body means battle can't touch your LP. In r2-g1 sending only 2 left Azure-Eyes at full ATK and Mk-II in Attack, which was exactly lethal.
- (r2-g2, major) **Before you choose "Go to the Battle Phase", add up every attacker you could have: make your Xyz in Main Phase 1, Flip Summon a face-down Armor, switch face-up Defense monsters that weren't summoned this turn to Attack, and use the Normal Summon on an Attack Position body** because Main Phase 2 bodies deal no damage. In r2-g2 this missed lethal twice. On turn 4, Gear Gigant X #2 plus a Normal Summoned Accelerator would have dealt 2300+2300+1000+1400 = 7000 against 7000. On turn 6, Armor and Accelerator were never switched to Attack, and the opponent survived at 400.
- (r2-g2, major) **When you activate Forbidden Droplet after an attack has been declared and you want that battle to go on (your monster wins against the halved attacker), pay the cost only with hand cards or Spells/Traps, never with a monster from your field** because removing a monster from your field changes your monster count. The attack is then replayed, and the opponent picks your weakest monster instead. Also, Geargiaccelerator's GY add is not offered when it is sent as Droplet's cost. In r2-g2 the halved 1500 Crystal Wing switched from Gear Gigant X (a lethal 800 back) to Mk-II.
- (r2-g2, minor) **When a response window opens right after the log line "Opponent Special Summons X" and it offers Solemn Strike but not your other Quick cards, that is the summon-negation window: the summon has NOT happened yet, and Solemn Strike negates it** (script: EVENT_SPSUMMON). Use it there on a boss like Crystal Wing Synchro Dragon. Don't wait for an attack.

## Regression cases

- `use-dark-rebellion-effect-before-ending` (r1-g2 #127): Dark Rebellion was just summoned with 2 materials, the opponent's negater was in the GY and Mystletainn was face-up: halve it before ending the turn. expect [[1]] reject [[2]]
- `set-ash-as-blocker-empty-field` (r1-g2 #183): With an empty field against two attackers and the Normal Summon unused, Set Ash Blossom face-down as a blocker rather than ending the turn. expect [[1]] reject [[3], [0]]
- `loop-reborn-arsenal-before-xyz` (r2-g1 #18): With a non-negated Arsenal revived by Monster Reborn, Tribute it for Geargiano (loop) before Xyz Summoning Gear Gigant X, so the float has a target. expect [[2]] reject [[10], [11]]
- `droplet-send-max-incl-attack-mk2` (r2-g1 #81): Facing lethal with three face-up Effect monsters, Forbidden Droplet must send 3 cards (ideally including the Attack Position Mk-II [5]), not just 2 hand cards. expect [] reject [[0, 3], [0, 1], [1, 3]]
- `switch-to-attack-for-lethal` (r2-g2 #64): The opponent at 3700 has one face-down Phalanx. Flip Summoning Armor and/or switching Accelerator to Attack before the Battle Phase gives lethal; going straight to battle falls 400 short. expect [[3], [4]] reject [[5]]
- `xyz-before-battle-for-lethal` (r2-g2 #37): Against an empty board at 7000 LP, summon Accelerator → Gear Gigant X #2 → re-add Accelerator → Normal Summon it in Attack: 2300+2300+1000+1400 = 7000. Going to battle first is not lethal. expect [[3]] reject [[10]]
- `droplet-cost-from-hand-no-replay` (r2-g2 #86): After Crystal Wing attacked Gear Gigant X, pay Droplet's cost from the hand so no replay happens: the halved 1500 attacker dies to 2300 and the 800 damage is lethal. expect [[0], [1], [2]] reject [[7]]

Final run against the trained playbook: 5/7 cases passed every one of 2 runs (`train/tests-final.txt`).

## Cost and time by phase

| kind | calls | cost | time |
|---|---|---|---|
| study | 1 | $1.22 | 4 min |
| lab-hand | 15 | $2.64 | 11 min |
| lab-review | 2 | $1.28 | 3 min |
| game | 4 | $4.55 | 17 min |
| review | 4 | $3.25 | 11 min |
| condense | 3 | $0.80 | 3 min |
| tests | 2 | $0.59 | 3 min |

## For a human to check

- Read the playbook against the card scripts; the lines still marked *(unverified)* haven't been seen working in the engine.
- `train/general-proposals.md`: proposed lessons for every deck (not applied).
- Does Geargiarmor's flip search trigger when Photon Papilloperative flips it face-up, and when it is flipped by being attacked?
- With Limiter Removal and Wind-Up Zenmaines: Limiter's End Phase destruction is a continuous effect. Does Zenmaines' destroy-replace, and then its End Phase destroy trigger, still happen that same End Phase?
- Do Gear Gigant X's leave-field float and Geargiaccelerator's GY add (both optional 'when' triggers) activate after Limiter Removal's End Phase destruction, or do they miss timing?
- When Geargiagear resolves, does the engine let you choose Attack or Defense position for the two Geargiano (script uses POS_FACEUP)?
- Can a Normal Set Geargiano Mk-II that is Flip Summoned next turn use its trigger, and does the AI get the Flip Summon option reliably?
- Geargiagear's End-Phase flip was never tested, because the dummy surrendered before its End Phase. Does it resolve with Lv4 Geargiano + Mk-II as written?
- Wind-Up Zenmaines (Line 3 without Accelerator) and Geargiarmor's turn-face-down (Line 4) are still untested.
- Going second against Blue-Eyes plus Mirror Force: is Castel's shuffle better than Dark Rebellion's attack in real games?
- rule proposal (r1-g1): When you control a Set Geargiagear and the opponent's End Phase response window offers it, activate it (unless the Deck has fewer than 2 Geargiano-type cards or you have fewer than 2 free Main Monster Zones).
- rule proposal (r1-g2): Before choosing 'End your turn' in Main Phase, if an ignition effect of a monster you control is offered and it targets only opponent's monsters (e.g. Dark Rebellion Xyz Dragon), activate it unless a written reason says otherwise.
- rule proposal (r1-g2): If your field has no monsters, the opponent controls at least one Attack Position monster, and 'Set <monster> face-down' is offered with the Normal Summon unused, Set a monster before ending the turn.
- repeated mistake (r1-g2): Geargiagear: 'It needs 2 Geargiano-type cards still in the Deck... Check both before you rely on it.' At turn 10 the player Set Geargiagear as its blocker plan with only 1 Geargiano-type card left in the Deck (decision 203, dead at 237).
- With two Gear Gigant X destroyed together by Limiter Removal, can both floats resolve? Each needs its own Lv3 Geargia target in the GY, and the 'when' trigger may miss timing. Test this in the lab.
- Going second with Arsenal + 2 Accelerator + Limiter Removal vs Blue-Eyes, which is better: Limiter Removal (both Gear Gigant X are lost in the End Phase), or Gear Gigant X + Castel shuffling Blue-Eyes (keeps the board)?
- The Castel branch of G2 is still untested.
- rule proposal (r2-g1): When activating Forbidden Droplet during the opponent's turn, select the maximum number of cost cards the prompt allows. Include your own face-up Attack Position monsters with ATK 1000 or less before hand cards.
- rule proposal (r2-g1): Before Xyz Summoning Gear Gigant X, if a face-up non-negated Geargiarsenal is on the field and a Geargiano is in the Deck, activate Arsenal's Tribute for Geargiano first.
- repeated mistake (r2-g1): Leave a Geargiano or Mk-II in the GY before Gear Gigant X can leave the field (General principles). The player ended turn 1 with Gear Gigant X and no Lv3 Geargia in the GY.
- rule proposal (r2-g2): Before choosing 'Go to the Battle Phase', add up the ATK of every monster that could attack. Count Attack Position monsters, face-up Defense monsters whose 'Change the battle position' option is offered, face-down monsters that can be Flip Summoned, and an unused Normal Summon. If the total covers the opponent's LP after removing their blockers, take those position-change and summon options first.
- rule proposal (r2-g2): When paying a cost for a Quick-Play/Trap after an opponent's attack declaration, never pick a monster from your own field if a hand card or Spell/Trap is eligible.
- rule proposal (r2-g2): In a response window that comes right after 'Opponent Special Summons X' and offers Solemn Strike, never pass with the reasoning 'the summon already resolved'. That window is the negation window.
- repeated mistake (r2-g2): Going second: 'Summon attackers in Attack Position and attack' (and 'Lethal check'). On turn 4 the player summoned its second Gear Gigant X and the Accelerator only in Main Phase 2, after the Battle Phase.

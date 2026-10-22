# Task: grade the answers in 3 position(s): p20, p35, p23.

Return one entry per position, in this order.

# Deck: Blackwing

## Decklist
Main Deck (40):
  1x Dark Armed Dragon
  3x Blackwing - Simoon the Poison Wind
  3x Blackwing - Gofu the Vague Shadow
  1x Blackwing - Kris the Crack of Dawn
  1x Blackwing - Bora the Spear
  1x Ahrima, the Wicked Warden
  3x Blackwing - Shamal the Sandstorm
  3x Blackwing - Sudri the Phantom Glimmer
  1x Blackwing - Gale the Whirlwind
  1x Blackwing - Harmattan the Dust
  3x Blackwing - Vata the Emblem of Wandering
  1x Blackwing - Sharnga the Waning Moon
  3x Blackwing - Chinook the Snow Blast
  1x Blackwing - Vayu the Emblem of Honor
  1x Blackwing - Oroshi the Squall
  1x Mystical Space Typhoon
  2x Enemy Controller
  2x Black Feather Whirlwind
  2x Black Whirlwind
  1x Lair of Darkness
  2x Icarus Attack
  1x Delta Crow - Anti Reverse
  1x Blackwing - Twin Shadow
  1x Blackbird Close
Extra Deck (15):
  2x Black-Winged Assault Dragon
  1x Blackwing Full Armor Master
  1x Void Ogre Dragon
  1x PSY-Framelord Omega
  1x Blackwing - Silverwind the Ascendant
  1x Black-Winged Dragon
  1x Clear Wing Synchro Dragon
  1x Blackwing Armor Master
  1x Black Rose Dragon
  1x Blackwing - Nothung the Starlight
  2x Blackwing - Boreastorm the Wicked Wind
  1x Coral Dragon
  1x Blackwing Armed Wing

## General strategy (for every deck)
- The playbooks are guidance, not scripts. When the board clearly calls for a different play than they describe,
  make it and say why in `why`.
- Lethal check: before you go to the Battle Phase, and again before you end your turn, count the most damage you
  can deal this turn: every attacker you can still summon or switch to Attack, ATK boosts, removal for their
  blockers, and burn. Look for the non-obvious lethal (an extra Xyz or Synchro, the Normal Summon kept for an
  attacker, a boost in the Damage Step, a burn effect after battle). If it is there, make the plays in Main Phase 1.
- Before planning a line that needs a specific card from your Deck or Extra Deck, check the state to see it is still
  there; Extra Deck monsters that were used or banished are gone.
- Spell/Trap timing: a Quick-Play Spell can be activated from the hand ONLY during your own turn. To use one on the
  opponent's turn it must already be Set, and a Set Quick-Play Spell or Trap can't be activated in the turn it was
  Set. So before ending your turn, Set the Quick-Play Spells and Traps you want available on their turn. From the
  Battle Phase, go to Main Phase 2 first: ending the turn from the Battle Phase skips your last chance to Set.
  Hand traps (monster effects like Effect Veiler) are different: they work from the hand on either turn.
- In response windows, passing ([]) is usually right unless responding gains something concrete. Don't waste
  hand traps or once-per-turn effects on low-value targets.
- You cannot see the opponent's hand or face-down cards. Don't assume what they are; play around likely threats.

## Playbook (the coaching notes the players follow)
## Lessons from games (newest first; these override everything below)

Your opponent is learning this deck from you, so these come from reviewing your own games against the card
scripts and the engine log.

### 2026-10-21 game 2 (vs WindBot Blue-Eyes) — won; your opponent rated the play as near perfect
1. **The main Simoon line is verified** (see "Main line"), including two upgrades you found: activate a second
   Black Whirlwind from hand before Normal Summoning Sudri (one summon → three searches), and Harmattan copying
   Boreastorm's Level 4 → Lv6, + Oroshi → a third body, Armor Master.
2. **The Assault Dragon wipe is one-sided with Full Armor Master on the field:** FAM is unaffected, so it survives.
   The right moment was the opponent's End Phase, once they had committed everything (4 Dragons + a Set card for
   Assault + two spent Continuous Spells). Then FAM attacked into an empty board. The wipe only works on the
   opponent's turn, so their End Phase is your LAST chance before your own turn: if they have more monsters than
   you can beat in battle, wipe there instead of waiting.
3. **Use Chinook after the attack is declared,** on the attacking monster. Then they can't back out, and the -700
   plus negation turns their attack into their own monster's destruction (Giganticastle 3100 → 2200 into FAM).
4. **Keep Blackbird Close in hand** while you control a Blackwing Synchro. It can be activated from hand then, and
   it's hidden and safe from Spell/Trap removal (Dragon Spirit of White banishes Spells/Traps).
5. Black Feather Whirlwind's counter protection saved Armor Master once. Letting Armor Master die later instead of
   spending Chinook/Blackbird Close on it was fine, since those were saved for bigger threats.

### 2026-10-21 game 1 (vs a Plant deck: Lonefire Blossom, Spore, Witch of the Black Rose) — won
1. **Only ONE Black-Winged Dragon is in the Extra Deck.** Once it's banished (Assault Dragon's summon) or used,
   Vata's effect, Twin Shadow → BWD and Blackbird Close's bonus summon are all dead. On turn 5 you Normal Summoned
   Vata for its BWD effect after BWD was already banished, so it did nothing. Check YOUR EXTRA DECK in the state
   before any line that needs a specific Extra Deck monster.
2. **"Blackwing" means the name contains "Blackwing".** Black-Winged Dragon and Black-Winged Assault Dragon are
   NOT Blackwings. They don't let Kris, Bora, Gale, Vata, Harmattan or Oroshi Special Summon from hand, and
   they don't turn on Delta Crow. Armor Master, Full Armor Master, Boreastorm, Nothung, Armed Wing and
   Silverwind are Blackwings.
3. **Simoon needs an empty board AND another Blackwing in hand to banish.** If Simoon is stuck in hand behind a
   board, keep a spare Blackwing in hand as its future cost instead of summoning it for no value. Plan for a
   turn where your board is empty, e.g. after Assault Dragon's wipe or after the opponent removes your monsters,
   and run the full Simoon engine then.
4. **Holding Assault Dragon's wipe was right.** It's a Quick Effect on the opponent's turn. Save it for a real
   threat: removal aimed at Assault, a boss monster, or an overcommitted board. Don't spend it on two weak
   monsters. Meanwhile each opponent monster effect burns 700; in this game that was 2800 damage.
5. **Gofu hand with no searcher (verified, see "Other starts"):** turning four monsters into one Assault Dragon is
   about the best that hand can do. The alternative is stopping at Armor Master + BWD: two bodies, and Armor
   Master (a Blackwing) turns on Delta Crow. Prefer Assault against decks that activate many monster effects.

## Status of this playbook

Built from the card texts, the EDOPro card scripts, and published Blackwing combo guides adapted to this exact
list. The main Simoon line and the Gofu line are verified in real games; anything still marked *(unverified)*
hasn't been played in this engine yet. If the engine offers something
different from what a line expects, trust the engine's options and adapt; don't force the line.

## Game plan

Synchro combo deck. Turn a Simoon (or another starter) into a chain of free Normal/Special Summons and searches,
then into a board of **Blackwing Full Armor Master** (unaffected by other cards, steals monsters) plus
**Black-Winged Assault Dragon** (burns 700 per opponent monster effect; can nuke the field), backed by
**Black Feather Whirlwind** (revives and protects) and Set traps.

## How the engine works (the rules that make the combos)

- **Simoon is the key starter.** If you control NO monsters: banish another Blackwing from hand → place
  **Black Whirlwind** face-up from the Deck, then Normal Summon Simoon without Tributing. That Normal Summon does
  NOT use your normal Normal Summon (confirmed in the script), so you still get your own Normal Summon after.
  Costs: only DARK monsters from the Extra Deck for the rest of the turn (all Blackwing Synchros are DARK;
  Clear Wing, Black Rose, PSY-Framelord Omega and Coral Dragon are not). In the End Phase, Black Whirlwind goes
  to the GY and you take 1000 damage.
- **Black Whirlwind**: every time a Blackwing is Normal Summoned, add a Blackwing with LESS ATK from the Deck.
  It has no once-per-turn limit, so every Normal Summon searches. Simoon (1600) → Sudri (1400) → Vata (800).
- **Sudri** (Normal Summon): add a card that mentions "Black-Winged Dragon" (Shamal, Vata, Chinook, Twin Shadow,
  Blackbird Close…). Also: Tribute 1 monster → Phantom Glimmer Token (Lv2 DARK Tuner), take 700 damage; only
  Synchro monsters from the Extra Deck that turn.
- **Shamal**: send it from hand/field to GY → place **Black Feather Whirlwind** face-up from the Deck. From the GY,
  when a Blackwing Synchro or Black-Winged Dragon is Special Summoned to your field: banish Shamal → add a
  Blackwing from your GY to hand (take 700 damage).
- **Vata**: Special Summon from hand if you control another Blackwing. Main Phase: send Vata + non-Tuner
  Blackwings **from the Deck** to the GY so the Levels total exactly 8 → Special Summon **Black-Winged Dragon**
  from the Extra Deck (DARK-only Extra Deck lock). Good Deck sends: Kris(4)+Chinook(2), Bora(4)+Harmattan(2),
  or Simoon(6). Pick the cards you want in the GY for Shamal to add back or Black Feather Whirlwind to revive.
- **Black Feather Whirlwind**: once per turn, when you Special Summon a DARK Synchro from the Extra Deck
  (including Black-Winged Dragon via Vata), revive a Blackwing or Black-Winged Dragon from your GY or banished
  pile with less ATK than it. It also protects your DARK monsters from destruction by removing a Black Feather
  Counter instead.
- **Black-Winged Dragon (BWD)**: effect damage to you becomes a Black Feather Counter on it instead. Do the
  self-damage effects (Shamal 700, Sudri 700, Simoon's End Phase 1000) while BWD is on the field. Later, remove
  the counters to shrink an opponent's monster and burn them.
- **Boreastorm** (Lv6 DARK Tuner Synchro; DARK Tuner + non-Tuner): when Synchro Summoned, send a Blackwing from
  the Deck to the GY and Boreastorm's Level becomes that card's Level. That lets you tune it for the next Synchro.
- **Black-Winged Assault Dragon** (Lv10): can be Special Summoned from the Extra Deck by banishing a Tuner Synchro
  (Boreastorm, Coral, or a Gofu-revived Synchro) AND Black-Winged Dragon from your field and/or GY. No
  Synchro Summon needed.
- **Full Armor Master** (Lv10): a Blackwing Tuner + non-Tuners totalling 10, e.g. Boreastorm set to Lv2 + BWD (8),
  or Boreastorm set to Lv4 + Simoon (6).
- **Extenders** (Special Summon from hand if you control another Blackwing): Kris (Lv4, once per turn), Bora (Lv4),
  Gale (Lv3 Tuner; halves a monster's ATK/DEF), Harmattan (Lv2; on summon can add another Blackwing's Level to its
  own), Vata (Lv2 Tuner), Oroshi (Lv1 Tuner). Sharnga (Lv2 Tuner) needs a 2000+ ATK monster on the field.
- **Gofu**: Special Summon from hand only while you control no monsters (it competes with Simoon for the empty
  board). It brings 2 tokens that can't be Tributed or used as Synchro Material, so they mostly clog zones. Gofu is
  a Lv5 Tuner. Later: banish Gofu + non-Tuners to revive a Blackwing Synchro of the same total Level as a Tuner.
- **Vayu** (in GY): banish it + a non-Tuner Blackwing from GY → Special Summon a Blackwing Synchro of the combined
  Level with effects negated. **Twin Shadow** (trap; from hand if you control 2+ Blackwings): shuffle a Tuner +
  non-Tuner Blackwing from GY/banished into the Deck → Special Summon a Blackwing Synchro or BWD of that Level
  (counts as a Synchro Summon).
- **Ahrima**: discard → add Lair of Darkness. On the field, Tribute another DARK monster → add **Simoon** (the
  only DARK monster in the Deck with 2000+ DEF). With **Lair of Darkness** all monsters are DARK and once per turn
  a Tribute for an effect can be an opponent's monster. That turns Ahrima, Sudri, Icarus Attack and Enemy
  Controller into removal.
- **Chinook**: send it from hand/field → send a Blackwing Synchro or BWD from the Extra Deck to the GY, and an
  opponent's monster loses 700 ATK and has its effects negated. It's a Quick Effect while you control a DARK
  Synchro. It's also how to put BWD in the GY for Assault Dragon.

## Main line: Simoon + any other Blackwing (verified in game 2)

1. Simoon: banish the least useful other Blackwing from hand → place Black Whirlwind → Normal Summon Simoon.
2. Black Whirlwind: add **Sudri**.
3. Normal Summon Sudri (your real Normal Summon). Sudri adds **Shamal**; Black Whirlwind adds **Vata**.
4. Send Shamal from hand → place Black Feather Whirlwind.
5. Special Summon Vata. Vata's effect: send Vata + Deck Blackwings totalling 8 → Special Summon BWD.
6. Black Feather Whirlwind revives a Blackwing with < 2800 ATK (e.g. the one Simoon banished, or one Vata sent).
   Shamal (GY) adds a Blackwing from GY to hand, and its 700 damage becomes a counter on BWD.
7. Make a Phantom Glimmer Token with Sudri if you need a Tuner (Tribute a monster you won't need; 700 → BWD).
8. Synchro Summon **Boreastorm** (DARK Tuner + non-Tuners = 6, e.g. token 2 + Sudri 4). Send a Blackwing so its
   Level becomes 2 (Chinook/Harmattan) or 4 (Kris/Bora/Sudri), depending on the next Synchro.
9. **Full Armor Master**: Boreastorm (Lv2) + BWD (8), or Boreastorm (Lv4) + Simoon (6).
10. **Assault Dragon**: banish Boreastorm + BWD from the field/GY.
11. Set traps (Twin Shadow, Icarus Attack, Blackbird Close, Delta Crow) and end. Black Whirlwind goes to the GY in
    the End Phase (1000 damage, or a counter if BWD is still out).

Game 2's version (hand: Simoon, Gofu, Sudri, Shamal, Black Whirlwind): Simoon banished Gofu → Vata; second Black
Whirlwind from hand; Sudri → Blackbird Close, the two Whirlwinds → Oroshi + Harmattan; Shamal → Black Feather
Whirlwind; Vata sent itself + Kris + Chinook → BWD; Black Feather Whirlwind revived Vata, Shamal added Chinook back;
Boreastorm (Vata + Sudri) sent the 2nd Shamal to become Lv4; Harmattan copied Lv4 → Lv6; Full Armor Master
(Boreastorm + Simoon); Armor Master (Oroshi + Harmattan); Assault Dragon (banish BWD + Boreastorm from GY).
Final board: Full Armor Master, Assault Dragon, Armor Master, with Blackbird Close + Chinook in hand.

Exact routes vary with the hand. Before each step, check zones (5 Main Monster Zones), what is still in the Deck,
and that the next Synchro's Levels and Tuner requirement work.

## Other starts

- **Ahrima** without Simoon: summon Ahrima, Tribute another DARK monster → add Simoon. You need an empty board
  for Simoon, so plan around it.
- **Sudri** as your Normal Summon: add Vata → Special Summon Vata → BWD.
- **Gofu** on an empty board, **verified in game 1** with Gofu + Bora + Gale + Oroshi: Special Summon Gofu (take the
  2 tokens) → Special Summon Bora and Gale (Gofu is a Blackwing) → Armor Master (Gale 3 + Bora 4) → Special Summon
  Oroshi → Black-Winged Dragon (Oroshi 1 + Armor Master 7) → Gofu's effect: banish Gofu + both tokens (5+1+1 = 7) to
  revive Armor Master as a Tuner → Assault Dragon by banishing Armor Master + BWD. The tokens can't be Synchro
  Material, but they do count for Gofu's banish. Without Bora/Gale: Gofu (5) + Harmattan (2) = Lv7 Armor Master.

## Going second / breaking boards

- **Dark Armed Dragon**: Special Summon it when exactly 3 DARK monsters are in your GY. Banish a DARK from the GY
  to destroy any card, with no once-per-turn limit.
- **Delta Crow** destroys all of their face-down Spells/Traps (from hand with exactly 3 Blackwings).
  **Icarus Attack** destroys 2 cards. **Mystical Space Typhoon** and **Enemy Controller** (change position, or
  Tribute → take control) clear the rest.
- Gale halves a monster's ATK/DEF, Chinook gives -700 and negates, and Nothung's summon deals 800 and gives -800.
- Black Rose Dragon wipes the field, but only on a turn you haven't used Simoon or Vata (it's FIRE).

## Locks and traps to respect

- Simoon or Vata used this turn → DARK-only Extra Deck. Sudri's Tribute effect → Synchro-only Extra Deck.
- Gofu and Simoon each need an empty board: decide which one starts.
- Black Whirlwind only triggers on **Normal** Summons, not Special Summons.
- Watch the 5 Main Monster Zones: Gofu tokens and extenders fill them fast.

# Position p20 (Blackwing, a `idle` decision)

## What the player saw

<<<
A new session started for this turn. Duel log so far:
DUEL START — you go first. LP 8000 vs 8000.
You draw 5 card(s).
Opponent draws 5 card(s).
=== TURN 1 (your turn) ===
-- Draw Phase
-- Standby Phase
-- Main Phase 1
"Blackwing - Chinook the Snow Blast": your hand → your M1 (by rule)
You Normal/Flip Summon "Blackwing - Chinook the Snow Blast" to M1 (face-up Attack).
"Blackwing - Vata the Emblem of Wandering": your hand → your M2
You Special Summon "Blackwing - Vata the Emblem of Wandering" to M2 (face-up Attack).
CL1: You activate "Blackwing - Vata the Emblem of Wandering" from your M2 — effect: "Special Summon this card" (the script's label for its Monster Zone effect, though this card is already on the field; see the card text)
"Blackwing - Kris the Crack of Dawn": your Deck → your GY (by effect)
"Blackwing - Chinook the Snow Blast": your Deck → your GY (by effect)
"Blackwing - Vata the Emblem of Wandering": your M2 → your GY (by effect)
"Black-Winged Dragon": your Extra Deck → your M2
You Special Summon "Black-Winged Dragon" to M2 (face-up Attack).
   CL1 resolved.

CURRENT STATE
TURN 1 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 8000

YOUR HAND (3) "Ahrima, the Wicked Warden", "Enemy Controller", "Blackwing - Vata the Emblem of Wandering"
YOUR MONSTERS: M1: "Blackwing - Chinook the Snow Blast" (face-up Attack, ATK 100 / DEF 700) | M2: "Black-Winged Dragon" (face-up Attack, ATK 2800 / DEF 1600)
YOUR SPELLS/TRAPS: none
YOUR GY (3) "Blackwing - Kris the Crack of Dawn", "Blackwing - Chinook the Snow Blast", "Blackwing - Vata the Emblem of Wandering"
YOUR BANISHED none
YOUR DECK: 33 cards | YOUR EXTRA DECK (14) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Blackwing Full Armor Master", "Black-Winged Assault Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 5 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: none
OPPONENT GY none
OPPONENT BANISHED none
OPPONENT DECK: 35 cards | OPPONENT EXTRA DECK: 12 card(s)

DECISION #13: Main Phase: choose your next action. Reply with exactly one option index.
[0] Activate "Ahrima, the Wicked Warden" from your hand — effect: "Search "Lair of Darkness""
[1] Set "Enemy Controller" in your Spell/Trap Zone
[2] End your turn (go to the End Phase)
>>>

## Texts of the deck's cards in this position
- "Black-Winged Dragon" [DARK Dragon Lv8 Effect/Synchro 2800/1600]: 1 Tuner + 1+ non-Tuner monsters
If you would take damage from a card effect, place 1 Black Feather Counter on this card instead. This card loses 700 ATK for each Black Feather Counter on it. Once per turn: You can remove all Black Feather Counters from this card, then target 1 face-up monster your opponent controls; that target loses 700 ATK for each Black Feather Counter removed, and if it does, inflict damage to your opponent equal to the ATK lost by this effect.
- "Blackwing - Boreastorm the Wicked Wind" [DARK Winged Beast Lv6 Effect/Tuner/Synchro 2400/1200]: 1 DARK Tuner + 1+ non-Tuner monsters
If this card is Synchro Summoned: You can send 1 "Blackwing" monster from your Deck to the GY, and if you do, this card's Level becomes the same as that monster's. When this card destroys a monster by battle and sends it to the GY: You can banish 1 "Blackwing" monster from your GY or face-up field, except the destroyed monster; Special Summon the destroyed monster to your field in Defense Position. You can only use each effect of "Blackwing - Boreastorm the Wicked Wind" once per turn.
- "Blackwing - Silverwind the Ascendant" [DARK Winged Beast Lv8 Effect/Synchro 2800/2000]: 1 "Blackwing" Tuner + 2 or more non-Tuner monsters
When this card is Synchro Summoned: You can target up to 2 face-up monsters on the field with DEF lower than this card's ATK; destroy those targets. You cannot conduct your Battle Phase the turn you activate this effect. During each of your opponent's turns, the first "Blackwing" monster you control that would be destroyed by battle, is not destroyed.
- "Blackwing - Chinook the Snow Blast" [DARK Winged Beast Lv2 Effect 100/700]: You can send this card from your hand or field to the GY, then target 1 face-up monster your opponent controls; send 1 "Blackwing" Synchro Monster or 1 "Black-Winged Dragon" from your Extra Deck to the GY, and if you do, until the end of this turn, the targeted monster loses 700 ATK, also negate its effects. This is a Quick Effect if you control a DARK Synchro Monster. You can only use this effect of "Blackwing - Chinook the Snow Blast" once per turn.
- "Coral Dragon" [WATER Dragon Lv6 Effect/Tuner/Synchro 2400/500]: 1 Tuner + 1+ non-Tuner monsters
Once per turn: You can discard 1 card, then target 1 card your opponent controls; destroy it. If this Synchro Summoned card is sent from the field to the GY: You can draw 1 card. You can only use this effect of "Coral Dragon" once per turn.
- "Blackwing Full Armor Master" [DARK Winged Beast Lv10 Effect/Synchro 3000/3000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
Unaffected by other cards' effects. Each time a monster your opponent controls activates its effect, place 1 Wedge Counter on that opponent's monster (max. 1) after that effect resolves. Once per turn: You can target 1 monster your opponent controls with a Wedge Counter; take control of it. Once per turn, during your End Phase: You can destroy all monsters on the field that have a Wedge Counter.
- "Blackwing Armor Master" [DARK Winged Beast Lv7 Effect/Synchro 2500/1500]: 1 "Blackwing" Tuner + 1 or more non-Tuner monsters
Cannot be destroyed by battle, and you take no battle damage from attacks involving this card. At the end of the Damage Step, if this card attacked a monster: You can place 1 Wedge Counter on that monster (max. 1). You can remove all Wedge Counters from your opponent's monsters; the ATK and DEF of those monsters that had Wedge Counters become 0 until the end of this turn.
- "Blackwing - Vata the Emblem of Wandering" [DARK Winged Beast Lv2 Effect/Tuner 800/0]: If you control a "Blackwing" monster other than "Blackwing - Vata the Emblem of Wandering", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Vata the Emblem of Wandering" once per turn this way. During your Main Phase: You can send this card on the field to the GY along with 1 or more non-Tuner "Blackwing" monsters from your Deck, so that the total Levels sent equal exactly 8, and if you do, Special Summon 1 "Black-Winged Dragon" from your Extra Deck, also you cannot Special Summon monsters from the Extra Deck for the rest of this turn, except DARK monsters. You can only use this effect of "Blackwing - Vata the Emblem of Wandering" once per turn.
- "Black-Winged Assault Dragon" [DARK Dragon Lv10 Effect/Synchro 3200/2800]: 1 Tuner Synchro Monster + 1+ non-Tuner monsters
Must be either Synchro Summoned, or Special Summoned from your Extra Deck by banishing 1 Tuner Synchro Monster and 1 "Black-Winged Dragon" from your face-up Monster Zone and/or GY. Each time your opponent activates a monster effect, place 1 Black Feather Counter on this card when that effect resolves, and if you do, inflict 700 damage to your opponent. During your opponent's turn (Quick Effect): You can Tribute this card with 4 or more Black Feather Counters on it; destroy all cards on the field.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "PSY-Framelord Omega" [LIGHT Psychic Lv8 Effect/Synchro 2800/2200]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, during the Main Phase (Quick Effect): You can banish both this face-up card from the field and 1 random card from your opponent's hand, face-up, until your next Standby Phase. Once per turn, during your opponent's Standby Phase: You can target 1 banished card; return it to the GY. If this card is in your GY: You can target 1 other card in the GY; shuffle both that card and this card from the GY into the Deck.
- "Blackwing Armed Wing" [DARK Winged Beast Lv6 Effect/Synchro 2300/1000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
If this card attacks a Defense Position monster, it gains 500 ATK during the Damage Step only, also inflict piercing battle damage.
- "Void Ogre Dragon" [DARK Dragon Lv8 Effect/Synchro 3000/3000]: 1 DARK Tuner + 1+ non-Tuner monsters
Once per turn, when your opponent activates a Spell/Trap Card while you have no cards in your hand (Quick Effect): You can negate the activation, and if you do, destroy it.
- "Blackwing - Kris the Crack of Dawn" [DARK Winged Beast Lv4 Effect 1900/300]: If you control a "Blackwing" monster other than "Blackwing - Kris the Crack of Dawn", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Kris the Crack of Dawn" once per turn this way. Once per turn, this card cannot be destroyed by Spell/Trap effects.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Ahrima, the Wicked Warden" [DARK Fiend Lv4 Effect 1700/0]: You can discard this card; add 1 "Lair of Darkness" from your Deck to your hand. You can Tribute 1 DARK monster; draw 1 card, or, if you Tributed a DARK monster other than this card to activate this effect, you can add 1 DARK monster with 2000 or more DEF from your Deck to your hand, instead. You can only use this effect of "Ahrima, the Wicked Warden" once per turn.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)
- "Enemy Controller" [Quick-Play Spell]: Activate 1 of these effects;
● Target 1 face-up monster your opponent controls; change that target's battle position.
● Tribute 1 monster, then target 1 face-up monster your opponent controls; take control of that target until the End Phase.

## Answers
A) [1] Set "Enemy Controller" in your Spell/Trap Zone
   reason given: I'm Setting Enemy Controller now so it can be used on the opponent's turn, either to switch an attacker's position or to Tribute Chinook and take one of their monsters. I'm keeping Ahrima in hand: next turn it can be Normal Summoned and Tribute a DARK monster to search Simoon, which is worth more than using it to add Lair of Darkness now.
B) [0] Activate "Ahrima, the Wicked Warden" from your hand — effect: "Search "Lair of Darkness""
   reason given: Discard Ahrima to search Lair of Darkness for free card advantage. Then Set Enemy Controller before ending the turn.

# Position p35 (Blackwing, a `select_card` decision)

## What the player saw

<<<
A new session started for this turn. Duel log so far:
DUEL START — you go first. LP 8000 vs 8000.
You draw 5 card(s).
Opponent draws 5 card(s).
=== TURN 1 (your turn) ===
-- Draw Phase
CL1: Opponent activates "Maxx "C"" from opponent's hand — effect: "Draw 1 card for eatch Special Summoned card on opponent's Field"
"Maxx "C"": opponent's hand → opponent's GY (as cost)
   CL1 resolved.
-- Standby Phase
-- Main Phase 1
"Blackwing - Sudri the Phantom Glimmer": your hand → your M1 (by rule)
You Normal/Flip Summon "Blackwing - Sudri the Phantom Glimmer" to M1 (face-up Attack).
CL1: You activate "Blackwing - Sudri the Phantom Glimmer" from your M1 — effect: "Add 1 card to the hand"
"Blackwing - Vata the Emblem of Wandering": your Deck → your hand (by effect)
Revealed to the opponent: "Blackwing - Vata the Emblem of Wandering" (your hand).
   CL1 resolved.
"Blackwing - Vata the Emblem of Wandering": your hand → your M2
You Special Summon "Blackwing - Vata the Emblem of Wandering" to M2 (face-up Attack).
Opponent draws 1 card(s).
CL1: You activate "Blackwing - Vata the Emblem of Wandering" from your M2 — effect: "Special Summon this card" (the script's label for its Monster Zone effect, though this card is already on the field; see the card text)
"Blackwing - Kris the Crack of Dawn": your Deck → your GY (by effect)
"Blackwing - Chinook the Snow Blast": your Deck → your GY (by effect)
"Blackwing - Vata the Emblem of Wandering": your M2 → your GY (by effect)
"Black-Winged Dragon": your Extra Deck → your M2
You Special Summon "Black-Winged Dragon" to M2 (face-up Attack).
Opponent draws 1 card(s).
   CL1 resolved.
"Blackwing - Sharnga the Waning Moon": your hand → your M3
You Special Summon "Blackwing - Sharnga the Waning Moon" to M3 (face-up Defense).
Opponent draws 1 card(s).
"Blackwing - Sudri the Phantom Glimmer": your M1 → your GY (as material, Synchro)
"Blackwing - Sharnga the Waning Moon": your M3 → your GY (as material, Synchro)
"Blackwing - Boreastorm the Wicked Wind": your Extra Deck → your M1
You Special Summon "Blackwing - Boreastorm the Wicked Wind" to M1 (face-up Attack).
Opponent draws 1 card(s).
CL1: You activate "Blackwing - Boreastorm the Wicked Wind" from your M1 — effect: "Change this card's Level"

Card texts (not shown to you yet this turn):
- "Maxx "C"" [EARTH Insect Lv2 Effect 500/200]: (Quick Effect): You can send this card from your hand to the GY; this turn, each time your opponent Special Summons a monster(s), immediately draw 1 card. You can only use this effect of "Maxx "C"" once per turn.

CURRENT STATE
TURN 1 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 8000

YOUR HAND (3) "Blackwing - Gofu the Vague Shadow", "Delta Crow - Anti Reverse", "Dark Armed Dragon"
YOUR MONSTERS: M1: "Blackwing - Boreastorm the Wicked Wind" (face-up Attack, ATK 2400 / DEF 1200) | M2: "Black-Winged Dragon" (face-up Attack, ATK 2800 / DEF 1600)
YOUR SPELLS/TRAPS: none
YOUR GY (5) "Blackwing - Kris the Crack of Dawn", "Blackwing - Chinook the Snow Blast", "Blackwing - Vata the Emblem of Wandering", "Blackwing - Sudri the Phantom Glimmer", "Blackwing - Sharnga the Waning Moon"
YOUR BANISHED none
YOUR DECK: 32 cards | YOUR EXTRA DECK (13) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Blackwing Full Armor Master", "Black-Winged Assault Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 8 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: none
OPPONENT GY (1) "Maxx "C""
OPPONENT BANISHED none
OPPONENT DECK: 35 cards | OPPONENT EXTRA DECK: 15 card(s)

CURRENT CHAIN (resolves last-to-first):
  CL1: you activated "Blackwing - Boreastorm the Wicked Wind" — Change this card's Level

DECISION #23: The game asks: "Select the card(s) to send to the GY". Choose between 1 and 1 card(s); reply with the list of option indices.
[0] "Blackwing - Shamal the Sandstorm" — your Deck
[1] "Blackwing - Chinook the Snow Blast" — your Deck
[2] "Blackwing - Gofu the Vague Shadow" — your Deck
[3] "Blackwing - Sudri the Phantom Glimmer" — your Deck
[4] "Blackwing - Shamal the Sandstorm" — your Deck
[5] "Blackwing - Shamal the Sandstorm" — your Deck
[6] "Blackwing - Harmattan the Dust" — your Deck
[7] "Blackwing - Gale the Whirlwind" — your Deck
[8] "Blackwing - Gofu the Vague Shadow" — your Deck
[9] "Blackwing - Oroshi the Squall" — your Deck
[10] "Blackwing - Vayu the Emblem of Honor" — your Deck
[11] "Blackwing - Sudri the Phantom Glimmer" — your Deck
[12] "Blackwing - Simoon the Poison Wind" — your Deck
[13] "Blackwing - Simoon the Poison Wind" — your Deck
[14] "Blackwing - Simoon the Poison Wind" — your Deck
[15] "Blackwing - Chinook the Snow Blast" — your Deck
[16] "Blackwing - Vata the Emblem of Wandering" — your Deck
[17] "Blackwing - Bora the Spear" — your Deck
[18] "Blackwing - Vata the Emblem of Wandering" — your Deck
>>>

## Texts of the deck's cards in this position
- "Blackwing - Gale the Whirlwind" [DARK Winged Beast Lv3 Effect/Tuner 1300/400]: If you control a "Blackwing" monster other than "Blackwing - Gale the Whirlwind", you can Special Summon this card (from your hand). Once per turn: You can target 1 face-up monster your opponent controls; that target's ATK and DEF become half its current ATK and DEF.
- "Blackwing - Shamal the Sandstorm" [DARK Winged Beast Lv4 Effect/Tuner 1600/0]: You can send this card from your hand or field to the GY; place 1 "Black Feather Whirlwind" from your Deck face-up in your Spell & Trap Zone. If a "Blackwing" Synchro Monster(s) or "Black-Winged Dragon" is Special Summoned to your field, while this card is in your GY (except during the Damage Step): You can banish this card, then target 1 "Blackwing" monster in your GY; add it to your hand, then take 700 damage. You can only use each effect of "Blackwing - Shamal the Sandstorm" once per turn.
- "Black-Winged Dragon" [DARK Dragon Lv8 Effect/Synchro 2800/1600]: 1 Tuner + 1+ non-Tuner monsters
If you would take damage from a card effect, place 1 Black Feather Counter on this card instead. This card loses 700 ATK for each Black Feather Counter on it. Once per turn: You can remove all Black Feather Counters from this card, then target 1 face-up monster your opponent controls; that target loses 700 ATK for each Black Feather Counter removed, and if it does, inflict damage to your opponent equal to the ATK lost by this effect.
- "Blackwing - Gofu the Vague Shadow" [DARK Winged Beast Lv5 Effect/Tuner 0/0]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) while you control no monsters. When this card is Special Summoned from the hand: You can Special Summon 2 "Vague Shadow Tokens" (Winged Beast-Type/DARK/Level 1/ATK 0/DEF 0), but they cannot be Tributed or be used as Synchro Material. You can banish this card and 1 or more face-up non-Tuners you control, then target 1 "Blackwing" Synchro Monster in your Graveyard whose Level equals the total Levels the banished monsters had on the field; Special Summon it, and if you do, it is treated as a Tuner.
- "Blackwing - Boreastorm the Wicked Wind" [DARK Winged Beast Lv6 Effect/Tuner/Synchro 2400/1200]: 1 DARK Tuner + 1+ non-Tuner monsters
If this card is Synchro Summoned: You can send 1 "Blackwing" monster from your Deck to the GY, and if you do, this card's Level becomes the same as that monster's. When this card destroys a monster by battle and sends it to the GY: You can banish 1 "Blackwing" monster from your GY or face-up field, except the destroyed monster; Special Summon the destroyed monster to your field in Defense Position. You can only use each effect of "Blackwing - Boreastorm the Wicked Wind" once per turn.
- "Blackwing - Silverwind the Ascendant" [DARK Winged Beast Lv8 Effect/Synchro 2800/2000]: 1 "Blackwing" Tuner + 2 or more non-Tuner monsters
When this card is Synchro Summoned: You can target up to 2 face-up monsters on the field with DEF lower than this card's ATK; destroy those targets. You cannot conduct your Battle Phase the turn you activate this effect. During each of your opponent's turns, the first "Blackwing" monster you control that would be destroyed by battle, is not destroyed.
- "Blackwing - Chinook the Snow Blast" [DARK Winged Beast Lv2 Effect 100/700]: You can send this card from your hand or field to the GY, then target 1 face-up monster your opponent controls; send 1 "Blackwing" Synchro Monster or 1 "Black-Winged Dragon" from your Extra Deck to the GY, and if you do, until the end of this turn, the targeted monster loses 700 ATK, also negate its effects. This is a Quick Effect if you control a DARK Synchro Monster. You can only use this effect of "Blackwing - Chinook the Snow Blast" once per turn.
- "Coral Dragon" [WATER Dragon Lv6 Effect/Tuner/Synchro 2400/500]: 1 Tuner + 1+ non-Tuner monsters
Once per turn: You can discard 1 card, then target 1 card your opponent controls; destroy it. If this Synchro Summoned card is sent from the field to the GY: You can draw 1 card. You can only use this effect of "Coral Dragon" once per turn.
- "Blackwing - Bora the Spear" [DARK Winged Beast Lv4 Effect 1700/800]: If you control a "Blackwing" monster other than "Blackwing - Bora the Spear", you can Special Summon this card (from your hand). If this card attacks a Defense Position monster, inflict piercing battle damage.
- "Blackwing Full Armor Master" [DARK Winged Beast Lv10 Effect/Synchro 3000/3000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
Unaffected by other cards' effects. Each time a monster your opponent controls activates its effect, place 1 Wedge Counter on that opponent's monster (max. 1) after that effect resolves. Once per turn: You can target 1 monster your opponent controls with a Wedge Counter; take control of it. Once per turn, during your End Phase: You can destroy all monsters on the field that have a Wedge Counter.
- "Blackwing - Sharnga the Waning Moon" [DARK Winged Beast Lv2 Effect/Tuner 500/500]: If a monster with 2000 or more ATK is on the field, you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Sharnga the Waning Moon" once per turn this way. If you control a "Blackwing" Synchro Monster (Quick Effect): You can banish this card from your GY, then target 1 face-up card your opponent controls; destroy it. You can only use this effect of "Blackwing - Sharnga the Waning Moon" once per Duel.
- "Delta Crow - Anti Reverse" [Trap]: If you control a "Blackwing" monster: Destroy all face-down Spells and Traps your opponent controls. If you control exactly 3 "Blackwing" monsters, you can activate this card from your hand.
- "Dark Armed Dragon" [DARK Dragon Lv7 Effect 2800/1000]: Cannot be Normal Summoned/Set. Must be Special Summoned (from your hand) by having exactly 3 DARK monsters in your GY. You can banish 1 DARK monster from your GY, then target 1 card on the field; destroy that target.
- "Blackwing Armor Master" [DARK Winged Beast Lv7 Effect/Synchro 2500/1500]: 1 "Blackwing" Tuner + 1 or more non-Tuner monsters
Cannot be destroyed by battle, and you take no battle damage from attacks involving this card. At the end of the Damage Step, if this card attacked a monster: You can place 1 Wedge Counter on that monster (max. 1). You can remove all Wedge Counters from your opponent's monsters; the ATK and DEF of those monsters that had Wedge Counters become 0 until the end of this turn.
- "Blackwing - Sudri the Phantom Glimmer" [DARK Winged Beast Lv4 Effect 1400/1400]: When this card is Normal Summoned: You can add 1 card that mentions "Black-Winged Dragon" from your Deck to your hand, except "Blackwing - Sudri the Phantom Glimmer". You can Tribute 1 monster; Special Summon 1 "Phantom Glimmer Token" (Winged Beast/Tuner/DARK/Level 2/ATK 700/DEF 700), then you take 700 damage. You cannot Special Summon monsters from the Extra Deck the turn you activate this effect, except Synchro Monsters. You can only use this effect of "Blackwing - Sudri the Phantom Glimmer" once per turn.
- "Blackwing - Vata the Emblem of Wandering" [DARK Winged Beast Lv2 Effect/Tuner 800/0]: If you control a "Blackwing" monster other than "Blackwing - Vata the Emblem of Wandering", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Vata the Emblem of Wandering" once per turn this way. During your Main Phase: You can send this card on the field to the GY along with 1 or more non-Tuner "Blackwing" monsters from your Deck, so that the total Levels sent equal exactly 8, and if you do, Special Summon 1 "Black-Winged Dragon" from your Extra Deck, also you cannot Special Summon monsters from the Extra Deck for the rest of this turn, except DARK monsters. You can only use this effect of "Blackwing - Vata the Emblem of Wandering" once per turn.
- "Blackwing - Vayu the Emblem of Honor" [DARK Winged Beast Lv1 Effect/Tuner 800/0]: This face-up card on the field cannot be used as a Synchro Material. If this card is in the Graveyard: You can target 1 non-Tuner "Blackwing" monster in your Graveyard; banish both this card and that target, and if you do, Special Summon 1 "Blackwing" Synchro Monster from your Extra Deck whose Level equals the total Levels of the banished monsters, but its effects are negated.
- "Black-Winged Assault Dragon" [DARK Dragon Lv10 Effect/Synchro 3200/2800]: 1 Tuner Synchro Monster + 1+ non-Tuner monsters
Must be either Synchro Summoned, or Special Summoned from your Extra Deck by banishing 1 Tuner Synchro Monster and 1 "Black-Winged Dragon" from your face-up Monster Zone and/or GY. Each time your opponent activates a monster effect, place 1 Black Feather Counter on this card when that effect resolves, and if you do, inflict 700 damage to your opponent. During your opponent's turn (Quick Effect): You can Tribute this card with 4 or more Black Feather Counters on it; destroy all cards on the field.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "Blackwing - Oroshi the Squall" [DARK Winged Beast Lv1 Effect/Tuner 400/600]: If you control a "Blackwing" monster other than "Blackwing - Oroshi the Squall", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Oroshi the Squall" once per turn this way. If this card is sent to the GY as a Synchro Material: You can target 1 monster on the field; change that target's battle position.
- "PSY-Framelord Omega" [LIGHT Psychic Lv8 Effect/Synchro 2800/2200]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, during the Main Phase (Quick Effect): You can banish both this face-up card from the field and 1 random card from your opponent's hand, face-up, until your next Standby Phase. Once per turn, during your opponent's Standby Phase: You can target 1 banished card; return it to the GY. If this card is in your GY: You can target 1 other card in the GY; shuffle both that card and this card from the GY into the Deck.
- "Blackwing Armed Wing" [DARK Winged Beast Lv6 Effect/Synchro 2300/1000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
If this card attacks a Defense Position monster, it gains 500 ATK during the Damage Step only, also inflict piercing battle damage.
- "Blackwing - Harmattan the Dust" [DARK Winged Beast Lv2 Effect 800/800]: If you control a "Blackwing" monster other than "Blackwing - Harmattan the Dust", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Harmattan the Dust" once per turn this way. When this card is Normal or Special Summoned: You can target 1 other "Blackwing" monster you control; increase this card's Level by that monster's.
- "Void Ogre Dragon" [DARK Dragon Lv8 Effect/Synchro 3000/3000]: 1 DARK Tuner + 1+ non-Tuner monsters
Once per turn, when your opponent activates a Spell/Trap Card while you have no cards in your hand (Quick Effect): You can negate the activation, and if you do, destroy it.
- "Blackwing - Kris the Crack of Dawn" [DARK Winged Beast Lv4 Effect 1900/300]: If you control a "Blackwing" monster other than "Blackwing - Kris the Crack of Dawn", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Kris the Crack of Dawn" once per turn this way. Once per turn, this card cannot be destroyed by Spell/Trap effects.
- "Blackwing - Simoon the Poison Wind" [DARK Winged Beast Lv6 Effect 1600/2000]: If you control no monsters and have this card in your hand: You can banish 1 other "Blackwing" monster from your hand; place 1 "Black Whirlwind" from your Deck face-up in your Spell & Trap Zone, then, either send this card to the GY, or immediately after this effect resolves, Normal Summon it without Tributing. You cannot Special Summon monsters from the Extra Deck for the rest of this turn, except DARK monsters. You can only use this effect of "Blackwing - Simoon the Poison Wind" once per turn. During the End Phase, if the "Black Whirlwind" placed by this effect is still on the field, send it to the GY, also take 1000 damage.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)

## Answers
A) [1] "Blackwing - Chinook the Snow Blast" — your Deck
   reason given: Sending Chinook makes Boreastorm Lv2. Boreastorm (Lv2) plus Black-Winged Dragon (Lv8) then make Full Armor Master. Both go to the GY, so Assault Dragon can banish them from there.
B) [16] "Blackwing - Vata the Emblem of Wandering" — your Deck
   reason given: Sending Vata sets Boreastorm to Level 2, so Boreastorm (2) + Black-Winged Dragon (8) can make Full Armor Master. After that, banishing both from the GY summons Assault Dragon. Black-Winged Dragon will end up banished, which makes Vata a dead card, so it's the best one to throw away. Chinook and Harmattan stay in the Deck as live draws.
C) [6] "Blackwing - Harmattan the Dust" — your Deck
   reason given: Boreastorm's Level change needs a Blackwing with Level 2 to make it Lv2. Sending Blackwing - Harmattan the Dust gives Boreastorm Lv2, so Boreastorm (2) + Black-Winged Dragon (8) = 10 for Blackwing Full Armor Master this turn. I'm sending Harmattan instead of Chinook or Vata, which are more useful later from the Deck.

# Position p23 (Blackwing, a `idle` decision)

## What the player saw

<<<
A new session started for this turn. Duel log so far:
DUEL START — you go first. LP 8000 vs 8000.
You draw 5 card(s).
Opponent draws 5 card(s).
=== TURN 1 (your turn) ===
-- Draw Phase
-- Standby Phase
-- Main Phase 1
"Blackwing - Sudri the Phantom Glimmer": your hand → your M1 (by rule)
You Normal/Flip Summon "Blackwing - Sudri the Phantom Glimmer" to M1 (face-up Attack).
CL1: You activate "Blackwing - Sudri the Phantom Glimmer" from your M1 — effect: "Add 1 card to the hand"
"Blackwing - Vata the Emblem of Wandering": your Deck → your hand (by effect)
Revealed to the opponent: "Blackwing - Vata the Emblem of Wandering" (your hand).
   CL1 resolved.
"Blackwing - Vata the Emblem of Wandering": your hand → your M2
You Special Summon "Blackwing - Vata the Emblem of Wandering" to M2 (face-up Attack).
CL1: You activate "Blackwing - Vata the Emblem of Wandering" from your M2 — effect: "Special Summon this card" (the script's label for its Monster Zone effect, though this card is already on the field; see the card text)
"Blackwing - Kris the Crack of Dawn": your Deck → your GY (by effect)
"Blackwing - Chinook the Snow Blast": your Deck → your GY (by effect)
"Blackwing - Vata the Emblem of Wandering": your M2 → your GY (by effect)
"Black-Winged Dragon": your Extra Deck → your M2
You Special Summon "Black-Winged Dragon" to M2 (face-up Attack).
   CL1 resolved.
"Dark Armed Dragon": your hand → your M3
You Special Summon "Dark Armed Dragon" to M3 (face-up Attack).
"Blackwing - Sharnga the Waning Moon": your hand → your M4
You Special Summon "Blackwing - Sharnga the Waning Moon" to M4 (face-up Defense).
"Blackwing - Sudri the Phantom Glimmer": your M1 → your GY (as material, Synchro)
"Blackwing - Sharnga the Waning Moon": your M4 → your GY (as material, Synchro)
"Blackwing - Boreastorm the Wicked Wind": your Extra Deck → your M1
You Special Summon "Blackwing - Boreastorm the Wicked Wind" to M1 (face-up Attack).
CL1: You activate "Blackwing - Boreastorm the Wicked Wind" from your M1 — effect: "Change this card's Level"
"Blackwing - Harmattan the Dust": your Deck → your GY (by effect)
   CL1 resolved.
"Blackwing - Boreastorm the Wicked Wind": your M1 → your GY (as material, Synchro)
"Black-Winged Dragon": your M2 → your GY (as material, Synchro)
"Blackwing Full Armor Master": your Extra Deck → your M1
You Special Summon "Blackwing Full Armor Master" to M1 (face-up Attack).
"Black-Winged Dragon": your GY → your banished (as cost)
"Blackwing - Boreastorm the Wicked Wind": your GY → your banished (as cost)
"Black-Winged Assault Dragon": your Extra Deck → your M2
You Special Summon "Black-Winged Assault Dragon" to M2 (face-up Attack).

CURRENT STATE
TURN 1 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 8000

YOUR HAND (2) "Blackwing - Gofu the Vague Shadow", "Delta Crow - Anti Reverse"
YOUR MONSTERS: M1: "Blackwing Full Armor Master" (face-up Attack, ATK 3000 / DEF 3000) | M2: "Black-Winged Assault Dragon" (face-up Attack, ATK 3200 / DEF 2800) | M3: "Dark Armed Dragon" (face-up Attack, ATK 2800 / DEF 1000)
YOUR SPELLS/TRAPS: none
YOUR GY (6) "Blackwing - Kris the Crack of Dawn", "Blackwing - Chinook the Snow Blast", "Blackwing - Vata the Emblem of Wandering", "Blackwing - Sudri the Phantom Glimmer", "Blackwing - Sharnga the Waning Moon", "Blackwing - Harmattan the Dust"
YOUR BANISHED (2) "Black-Winged Dragon", "Blackwing - Boreastorm the Wicked Wind"
YOUR DECK: 31 cards | YOUR EXTRA DECK (11) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 5 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: none
OPPONENT GY none
OPPONENT BANISHED none
OPPONENT DECK: 35 cards | OPPONENT EXTRA DECK: 15 card(s)

DECISION #37: Main Phase: choose your next action. Reply with exactly one option index.
[0] Activate "Dark Armed Dragon" (face-up Attack, ATK 2800 / DEF 1000) from your M3 — effect: "Destroy 1 card on the field"
[1] Set "Delta Crow - Anti Reverse" in your Spell/Trap Zone
[2] End your turn (go to the End Phase)
>>>

## Texts of the deck's cards in this position
- "Black-Winged Dragon" [DARK Dragon Lv8 Effect/Synchro 2800/1600]: 1 Tuner + 1+ non-Tuner monsters
If you would take damage from a card effect, place 1 Black Feather Counter on this card instead. This card loses 700 ATK for each Black Feather Counter on it. Once per turn: You can remove all Black Feather Counters from this card, then target 1 face-up monster your opponent controls; that target loses 700 ATK for each Black Feather Counter removed, and if it does, inflict damage to your opponent equal to the ATK lost by this effect.
- "Blackwing - Gofu the Vague Shadow" [DARK Winged Beast Lv5 Effect/Tuner 0/0]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) while you control no monsters. When this card is Special Summoned from the hand: You can Special Summon 2 "Vague Shadow Tokens" (Winged Beast-Type/DARK/Level 1/ATK 0/DEF 0), but they cannot be Tributed or be used as Synchro Material. You can banish this card and 1 or more face-up non-Tuners you control, then target 1 "Blackwing" Synchro Monster in your Graveyard whose Level equals the total Levels the banished monsters had on the field; Special Summon it, and if you do, it is treated as a Tuner.
- "Blackwing - Boreastorm the Wicked Wind" [DARK Winged Beast Lv6 Effect/Tuner/Synchro 2400/1200]: 1 DARK Tuner + 1+ non-Tuner monsters
If this card is Synchro Summoned: You can send 1 "Blackwing" monster from your Deck to the GY, and if you do, this card's Level becomes the same as that monster's. When this card destroys a monster by battle and sends it to the GY: You can banish 1 "Blackwing" monster from your GY or face-up field, except the destroyed monster; Special Summon the destroyed monster to your field in Defense Position. You can only use each effect of "Blackwing - Boreastorm the Wicked Wind" once per turn.
- "Blackwing - Silverwind the Ascendant" [DARK Winged Beast Lv8 Effect/Synchro 2800/2000]: 1 "Blackwing" Tuner + 2 or more non-Tuner monsters
When this card is Synchro Summoned: You can target up to 2 face-up monsters on the field with DEF lower than this card's ATK; destroy those targets. You cannot conduct your Battle Phase the turn you activate this effect. During each of your opponent's turns, the first "Blackwing" monster you control that would be destroyed by battle, is not destroyed.
- "Blackwing - Chinook the Snow Blast" [DARK Winged Beast Lv2 Effect 100/700]: You can send this card from your hand or field to the GY, then target 1 face-up monster your opponent controls; send 1 "Blackwing" Synchro Monster or 1 "Black-Winged Dragon" from your Extra Deck to the GY, and if you do, until the end of this turn, the targeted monster loses 700 ATK, also negate its effects. This is a Quick Effect if you control a DARK Synchro Monster. You can only use this effect of "Blackwing - Chinook the Snow Blast" once per turn.
- "Coral Dragon" [WATER Dragon Lv6 Effect/Tuner/Synchro 2400/500]: 1 Tuner + 1+ non-Tuner monsters
Once per turn: You can discard 1 card, then target 1 card your opponent controls; destroy it. If this Synchro Summoned card is sent from the field to the GY: You can draw 1 card. You can only use this effect of "Coral Dragon" once per turn.
- "Blackwing Full Armor Master" [DARK Winged Beast Lv10 Effect/Synchro 3000/3000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
Unaffected by other cards' effects. Each time a monster your opponent controls activates its effect, place 1 Wedge Counter on that opponent's monster (max. 1) after that effect resolves. Once per turn: You can target 1 monster your opponent controls with a Wedge Counter; take control of it. Once per turn, during your End Phase: You can destroy all monsters on the field that have a Wedge Counter.
- "Blackwing - Sharnga the Waning Moon" [DARK Winged Beast Lv2 Effect/Tuner 500/500]: If a monster with 2000 or more ATK is on the field, you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Sharnga the Waning Moon" once per turn this way. If you control a "Blackwing" Synchro Monster (Quick Effect): You can banish this card from your GY, then target 1 face-up card your opponent controls; destroy it. You can only use this effect of "Blackwing - Sharnga the Waning Moon" once per Duel.
- "Delta Crow - Anti Reverse" [Trap]: If you control a "Blackwing" monster: Destroy all face-down Spells and Traps your opponent controls. If you control exactly 3 "Blackwing" monsters, you can activate this card from your hand.
- "Dark Armed Dragon" [DARK Dragon Lv7 Effect 2800/1000]: Cannot be Normal Summoned/Set. Must be Special Summoned (from your hand) by having exactly 3 DARK monsters in your GY. You can banish 1 DARK monster from your GY, then target 1 card on the field; destroy that target.
- "Blackwing Armor Master" [DARK Winged Beast Lv7 Effect/Synchro 2500/1500]: 1 "Blackwing" Tuner + 1 or more non-Tuner monsters
Cannot be destroyed by battle, and you take no battle damage from attacks involving this card. At the end of the Damage Step, if this card attacked a monster: You can place 1 Wedge Counter on that monster (max. 1). You can remove all Wedge Counters from your opponent's monsters; the ATK and DEF of those monsters that had Wedge Counters become 0 until the end of this turn.
- "Blackwing - Sudri the Phantom Glimmer" [DARK Winged Beast Lv4 Effect 1400/1400]: When this card is Normal Summoned: You can add 1 card that mentions "Black-Winged Dragon" from your Deck to your hand, except "Blackwing - Sudri the Phantom Glimmer". You can Tribute 1 monster; Special Summon 1 "Phantom Glimmer Token" (Winged Beast/Tuner/DARK/Level 2/ATK 700/DEF 700), then you take 700 damage. You cannot Special Summon monsters from the Extra Deck the turn you activate this effect, except Synchro Monsters. You can only use this effect of "Blackwing - Sudri the Phantom Glimmer" once per turn.
- "Blackwing - Vata the Emblem of Wandering" [DARK Winged Beast Lv2 Effect/Tuner 800/0]: If you control a "Blackwing" monster other than "Blackwing - Vata the Emblem of Wandering", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Vata the Emblem of Wandering" once per turn this way. During your Main Phase: You can send this card on the field to the GY along with 1 or more non-Tuner "Blackwing" monsters from your Deck, so that the total Levels sent equal exactly 8, and if you do, Special Summon 1 "Black-Winged Dragon" from your Extra Deck, also you cannot Special Summon monsters from the Extra Deck for the rest of this turn, except DARK monsters. You can only use this effect of "Blackwing - Vata the Emblem of Wandering" once per turn.
- "Black-Winged Assault Dragon" [DARK Dragon Lv10 Effect/Synchro 3200/2800]: 1 Tuner Synchro Monster + 1+ non-Tuner monsters
Must be either Synchro Summoned, or Special Summoned from your Extra Deck by banishing 1 Tuner Synchro Monster and 1 "Black-Winged Dragon" from your face-up Monster Zone and/or GY. Each time your opponent activates a monster effect, place 1 Black Feather Counter on this card when that effect resolves, and if you do, inflict 700 damage to your opponent. During your opponent's turn (Quick Effect): You can Tribute this card with 4 or more Black Feather Counters on it; destroy all cards on the field.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "PSY-Framelord Omega" [LIGHT Psychic Lv8 Effect/Synchro 2800/2200]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, during the Main Phase (Quick Effect): You can banish both this face-up card from the field and 1 random card from your opponent's hand, face-up, until your next Standby Phase. Once per turn, during your opponent's Standby Phase: You can target 1 banished card; return it to the GY. If this card is in your GY: You can target 1 other card in the GY; shuffle both that card and this card from the GY into the Deck.
- "Blackwing Armed Wing" [DARK Winged Beast Lv6 Effect/Synchro 2300/1000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
If this card attacks a Defense Position monster, it gains 500 ATK during the Damage Step only, also inflict piercing battle damage.
- "Blackwing - Harmattan the Dust" [DARK Winged Beast Lv2 Effect 800/800]: If you control a "Blackwing" monster other than "Blackwing - Harmattan the Dust", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Harmattan the Dust" once per turn this way. When this card is Normal or Special Summoned: You can target 1 other "Blackwing" monster you control; increase this card's Level by that monster's.
- "Void Ogre Dragon" [DARK Dragon Lv8 Effect/Synchro 3000/3000]: 1 DARK Tuner + 1+ non-Tuner monsters
Once per turn, when your opponent activates a Spell/Trap Card while you have no cards in your hand (Quick Effect): You can negate the activation, and if you do, destroy it.
- "Blackwing - Kris the Crack of Dawn" [DARK Winged Beast Lv4 Effect 1900/300]: If you control a "Blackwing" monster other than "Blackwing - Kris the Crack of Dawn", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Kris the Crack of Dawn" once per turn this way. Once per turn, this card cannot be destroyed by Spell/Trap effects.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)

## Answers
A) [1] Set "Delta Crow - Anti Reverse" in your Spell/Trap Zone
   reason given: Nothing on my side can attack this turn (every monster was just Special Summoned), and the opponent has no field, so Dark Armed Dragon's destroy has no good target. Setting Delta Crow - Anti Reverse keeps a trap ready to clear face-down backrow on a later turn.
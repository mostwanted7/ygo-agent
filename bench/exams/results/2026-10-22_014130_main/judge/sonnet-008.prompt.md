# Task: grade the answers in 3 position(s): p23, p40, p22.

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
   reason given: Set Delta Crow to destroy their face-down Spells/Traps later. The opponent's board is empty, so Dark Armed Dragon has no target.

# Position p40 (Blackwing, a `option` decision)

## What the player saw

<<<
A new session started for this turn. Duel log so far:
DUEL START — you go second. LP 8000 vs 8000.
Opponent draws 5 card(s).
You draw 5 card(s).
=== TURN 1 (opponent's turn) ===
-- Draw Phase
-- Standby Phase
-- Main Phase 1
a hidden card: opponent's hand → opponent's S3 (by rule)
a hidden card: opponent's hand → opponent's S2 (by rule)
a hidden card: opponent's hand → opponent's S4 (by rule)
"Time Thief Winder": opponent's hand → opponent's M3 (by rule)
Opponent Normal/Flip Summons "Time Thief Winder" to M3 (face-up Attack).
CL1: Opponent activates "Time Thief Winder" from opponent's M3 — effect: "Add to hand"
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Time Thief Retrograde" (opponent's hand).
   CL1 resolved.
a hidden card: opponent's hand → opponent's S1 (by effect)
-- End Phase
=== TURN 2 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
CL1: You activate "Blackwing - Simoon the Poison Wind" from your hand — effect: "Place 1 "Black Whirlwind" in your Spell & Trap Zone"
"Blackwing - Vayu the Emblem of Honor": your hand → your banished (as cost)
Opponent's "Solemn Strike" is flipped face-up.
CL2: Opponent activates "Solemn Strike" from opponent's S3
Opponent pays 1500 LP (LP now 6500).
   CL1 was NEGATED.
"Blackwing - Simoon the Poison Wind": your hand → your GY (destroyed, by effect)
   CL2 resolved.
   CL1 resolved.
"Solemn Strike": opponent's S3 → opponent's GY (by rule)
"Blackwing - Chinook the Snow Blast": your hand → your M1 (by rule)
"Icarus Attack": your hand → your S1 (by rule)
-- End Phase
=== TURN 3 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"Time Thief Winder": opponent's hand → opponent's M2 (by rule)
Opponent Normal/Flip Summons "Time Thief Winder" to M2 (face-up Attack).
CL1: Opponent activates "Time Thief Winder" from opponent's M2 — effect: "Add to hand"
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Time Thief Startup" (opponent's hand).
   CL1 resolved.
"Time Thief Winder": opponent's M2 → opponent's Xyz material (as material, Xyz)
"Time Thief Winder": opponent's M3 → opponent's Xyz material (as material, Xyz)
"Time Thief Redoer": opponent's Extra Deck → opponent's M3
Opponent Special Summons "Time Thief Redoer" to M3 (face-up Attack).
-- Battle Phase (start step)
ATTACK: "Time Thief Redoer" (face-up Attack, ATK 2400 / DEF 2000, 2 material(s): Time Thief Winder, Time Thief Winder) — opponent's M3 attacks "Blackwing - Chinook the Snow Blast" (face-down Defense, ATK 100 / DEF 700) — your M1.
Your "Icarus Attack" is flipped face-up.
CL1: You activate "Icarus Attack" from your S1
"Blackwing - Chinook the Snow Blast": your M1 → your GY (Tributed, as cost)
   a face-down card — opponent's S2 is targeted.
   "Time Thief Redoer" (face-up Attack, ATK 2400 / DEF 2000, 2 material(s): Time Thief Winder, Time Thief Winder, already attacked) — opponent's M3 is targeted.
"Time Thief Redoer": opponent's M3 → opponent's GY (destroyed, by effect)
"Solemn Strike": opponent's S2 → opponent's GY (destroyed, by effect)
"Time Thief Winder": opponent's Xyz material → opponent's GY (by rule)
"Time Thief Winder": opponent's Xyz material → opponent's GY (by rule)
   CL1 resolved.
"Icarus Attack": your S1 → your GY (by rule)
-- Main Phase 2
-- End Phase
=== TURN 4 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
CL1: You activate "Blackwing - Simoon the Poison Wind" from your hand — effect: "Place 1 "Black Whirlwind" in your Spell & Trap Zone"
"Blackwing - Chinook the Snow Blast": your hand → your banished (as cost)
"Black Whirlwind": your Deck → your S1

Card texts (not shown to you yet this turn):
- "Time Thief Startup" [Quick-Play Spell]: Special Summon 1 "Time Thief" monster from your hand. During your Main Phase: You can banish this card from your GY, then target 1 "Time Thief" Xyz Monster you control; attach 3 "Time Thief" cards of different types (1 Monster, 1 Spell, and 1 Trap) from your GY to that monster as material. You can only use 1 "Time Thief Startup" effect per turn, and only once that turn.
- "Solemn Strike" [Counter Trap]: When a monster(s) would be Special Summoned, OR a monster effect is activated: Pay 1500 LP; negate the Summon or activation, and if you do, destroy that card.
- "Time Thief Redoer" [DARK Psychic Rank 4 Effect/Xyz 2400/2000]: 2 Level 4 monsters
Once per turn, during the Standby Phase: You can attach the top card of your opponent's Deck to this card as material. (Quick Effect): You can detach up to 3 different types of materials from this card, then apply the following effect(s) depending on what was detached.
● Monster: Banish this card until the End Phase.
● Spell: Draw 1 card.
● Trap: Place 1 face-up card your opponent controls on the top of the Deck.
You can only use this effect of "Time Thief Redoer" once per turn.
- "Time Thief Winder" [DARK Psychic Lv4 Effect 1800/1300]: You can detach 1 material from a monster you control; Special Summon this card from your hand. If this card is Normal or Special Summoned: You can add 1 "Time Thief" card from your Deck to your hand, except "Time Thief Winder". You can only use each effect of "Time Thief Winder" once per turn.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Time Thief Retrograde" [Counter Trap]: When a Spell/Trap Card is activated while you control a "Time Thief" Xyz Monster: Negate the activation, and if you do, attach that card to a "Time Thief" Xyz Monster you control as material. You can only activate 1 "Time Thief Retrograde" per turn.

CURRENT STATE
TURN 4 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 6500

YOUR HAND (2) "Blackwing - Gale the Whirlwind", "Blackwing - Simoon the Poison Wind"
YOUR MONSTERS: none
YOUR SPELLS/TRAPS: S1: "Black Whirlwind"
YOUR GY (3) "Blackwing - Simoon the Poison Wind", "Blackwing - Chinook the Snow Blast", "Icarus Attack"
YOUR BANISHED (2) "Blackwing - Vayu the Emblem of Honor", "Blackwing - Chinook the Snow Blast"
YOUR DECK: 32 cards | YOUR EXTRA DECK (15) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Black-Winged Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Blackwing Full Armor Master", "Black-Winged Assault Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 2 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: S1: face-down card | S4: face-down card
OPPONENT GY (5) "Solemn Strike", "Time Thief Redoer", "Solemn Strike", "Time Thief Winder", "Time Thief Winder"
OPPONENT BANISHED none
OPPONENT DECK: 36 cards | OPPONENT EXTRA DECK: 14 card(s)

CURRENT CHAIN (resolves last-to-first):
  CL1: you activated "Blackwing - Simoon the Poison Wind" — Place 1 "Black Whirlwind" in your Spell & Trap Zone

DECISION #23: Choose one of these effects/options. Reply with exactly one option index.
[0] Send this card to the GY
[1] Normal Summon this card without Tributing
>>>

## Texts of the deck's cards in this position
- "Blackwing - Gale the Whirlwind" [DARK Winged Beast Lv3 Effect/Tuner 1300/400]: If you control a "Blackwing" monster other than "Blackwing - Gale the Whirlwind", you can Special Summon this card (from your hand). Once per turn: You can target 1 face-up monster your opponent controls; that target's ATK and DEF become half its current ATK and DEF.
- "Black-Winged Dragon" [DARK Dragon Lv8 Effect/Synchro 2800/1600]: 1 Tuner + 1+ non-Tuner monsters
If you would take damage from a card effect, place 1 Black Feather Counter on this card instead. This card loses 700 ATK for each Black Feather Counter on it. Once per turn: You can remove all Black Feather Counters from this card, then target 1 face-up monster your opponent controls; that target loses 700 ATK for each Black Feather Counter removed, and if it does, inflict damage to your opponent equal to the ATK lost by this effect.
- "Blackwing - Boreastorm the Wicked Wind" [DARK Winged Beast Lv6 Effect/Tuner/Synchro 2400/1200]: 1 DARK Tuner + 1+ non-Tuner monsters
If this card is Synchro Summoned: You can send 1 "Blackwing" monster from your Deck to the GY, and if you do, this card's Level becomes the same as that monster's. When this card destroys a monster by battle and sends it to the GY: You can banish 1 "Blackwing" monster from your GY or face-up field, except the destroyed monster; Special Summon the destroyed monster to your field in Defense Position. You can only use each effect of "Blackwing - Boreastorm the Wicked Wind" once per turn.
- "Blackwing - Silverwind the Ascendant" [DARK Winged Beast Lv8 Effect/Synchro 2800/2000]: 1 "Blackwing" Tuner + 2 or more non-Tuner monsters
When this card is Synchro Summoned: You can target up to 2 face-up monsters on the field with DEF lower than this card's ATK; destroy those targets. You cannot conduct your Battle Phase the turn you activate this effect. During each of your opponent's turns, the first "Blackwing" monster you control that would be destroyed by battle, is not destroyed.
- "Blackwing - Chinook the Snow Blast" [DARK Winged Beast Lv2 Effect 100/700]: You can send this card from your hand or field to the GY, then target 1 face-up monster your opponent controls; send 1 "Blackwing" Synchro Monster or 1 "Black-Winged Dragon" from your Extra Deck to the GY, and if you do, until the end of this turn, the targeted monster loses 700 ATK, also negate its effects. This is a Quick Effect if you control a DARK Synchro Monster. You can only use this effect of "Blackwing - Chinook the Snow Blast" once per turn.
- "Coral Dragon" [WATER Dragon Lv6 Effect/Tuner/Synchro 2400/500]: 1 Tuner + 1+ non-Tuner monsters
Once per turn: You can discard 1 card, then target 1 card your opponent controls; destroy it. If this Synchro Summoned card is sent from the field to the GY: You can draw 1 card. You can only use this effect of "Coral Dragon" once per turn.
- "Icarus Attack" [Trap]: Tribute 1 Winged Beast monster, then target 2 cards on the field; destroy them.
- "Blackwing Full Armor Master" [DARK Winged Beast Lv10 Effect/Synchro 3000/3000]: 1 "Blackwing" Tuner + 1+ non-Tuner monsters
Unaffected by other cards' effects. Each time a monster your opponent controls activates its effect, place 1 Wedge Counter on that opponent's monster (max. 1) after that effect resolves. Once per turn: You can target 1 monster your opponent controls with a Wedge Counter; take control of it. Once per turn, during your End Phase: You can destroy all monsters on the field that have a Wedge Counter.
- "Blackwing Armor Master" [DARK Winged Beast Lv7 Effect/Synchro 2500/1500]: 1 "Blackwing" Tuner + 1 or more non-Tuner monsters
Cannot be destroyed by battle, and you take no battle damage from attacks involving this card. At the end of the Damage Step, if this card attacked a monster: You can place 1 Wedge Counter on that monster (max. 1). You can remove all Wedge Counters from your opponent's monsters; the ATK and DEF of those monsters that had Wedge Counters become 0 until the end of this turn.
- "Blackwing - Vayu the Emblem of Honor" [DARK Winged Beast Lv1 Effect/Tuner 800/0]: This face-up card on the field cannot be used as a Synchro Material. If this card is in the Graveyard: You can target 1 non-Tuner "Blackwing" monster in your Graveyard; banish both this card and that target, and if you do, Special Summon 1 "Blackwing" Synchro Monster from your Extra Deck whose Level equals the total Levels of the banished monsters, but its effects are negated.
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
- "Blackwing - Simoon the Poison Wind" [DARK Winged Beast Lv6 Effect 1600/2000]: If you control no monsters and have this card in your hand: You can banish 1 other "Blackwing" monster from your hand; place 1 "Black Whirlwind" from your Deck face-up in your Spell & Trap Zone, then, either send this card to the GY, or immediately after this effect resolves, Normal Summon it without Tributing. You cannot Special Summon monsters from the Extra Deck for the rest of this turn, except DARK monsters. You can only use this effect of "Blackwing - Simoon the Poison Wind" once per turn. During the End Phase, if the "Black Whirlwind" placed by this effect is still on the field, send it to the GY, also take 1000 damage.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Black Whirlwind" [Continuous Spell]: When a "Blackwing" monster is Normal Summoned to your field: You can add 1 "Blackwing" monster from your Deck to your hand with less ATK than that monster.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)

## Answers
A) [1] Normal Summon this card without Tributing
   reason given: Normal Summoning Simoon for free triggers Black Whirlwind to search (e.g. Sudri) and keeps my own Normal Summon available.

# Position p22 (Blackwing, a `idle` decision)

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
"Black Whirlwind": your hand → your S1 (by rule)
CL1: You activate "Black Whirlwind" from your S1
   CL1 resolved.
"Blackwing - Vata the Emblem of Wandering": your hand → your M1 (by rule)
You Normal/Flip Summon "Blackwing - Vata the Emblem of Wandering" to M1 (face-up Attack).
CL1: You activate "Black Whirlwind" from your S1 — effect: "Search"
"Blackwing - Gofu the Vague Shadow": your Deck → your hand (by effect)
Revealed to the opponent: "Blackwing - Gofu the Vague Shadow" (your hand).
   CL1 resolved.
"Black Feather Whirlwind": your hand → your S2 (by rule)
CL1: You activate "Black Feather Whirlwind" from your S2
   CL1 resolved.
-- End Phase
=== TURN 2 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"The Melody of Awakening Dragon": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "The Melody of Awakening Dragon" from opponent's S3
"The White Stone of Legend": opponent's hand → opponent's GY (as cost, discarded)
a hidden card: opponent's Deck → opponent's hand (by effect)
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Blue-Eyes Alternative White Dragon" (opponent's hand), "Blue-Eyes Alternative White Dragon" (opponent's hand).
   CL1 resolved.
"The Melody of Awakening Dragon": opponent's S3 → opponent's GY (by rule)
CL1: Opponent activates "The White Stone of Legend" from opponent's GY — effect: "Add card"
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Blue-Eyes White Dragon" (opponent's hand).
   CL1 resolved.
Revealed to you: "Blue-Eyes White Dragon" (opponent's hand).
"Blue-Eyes Alternative White Dragon": opponent's hand → opponent's M3
Opponent Special Summons "Blue-Eyes Alternative White Dragon" to M3 (face-up Attack).
CL1: Opponent activates "Blue-Eyes Alternative White Dragon" from opponent's M3 — effect: "Destroy"
   "Blackwing - Vata the Emblem of Wandering" (face-up Attack, ATK 800 / DEF 0) — your M1 is targeted.
"Blackwing - Vata the Emblem of Wandering": your M1 → your GY (destroyed, by effect)
   CL1 resolved.
a hidden card: opponent's hand → opponent's S3 (by rule)
-- Battle Phase (start step)
-- Main Phase 2
-- End Phase
=== TURN 3 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
"Blackwing - Gofu the Vague Shadow": your hand → your M1
You Special Summon "Blackwing - Gofu the Vague Shadow" to M1 (face-up Defense).
"Ahrima, the Wicked Warden": your hand → your M2 (by rule)
You Normal/Flip Summon "Ahrima, the Wicked Warden" to M2 (face-up Attack).
CL1: You activate "Ahrima, the Wicked Warden" from your M2 — effect: "Draw"
"Blackwing - Gofu the Vague Shadow": your M1 → your GY (Tributed, as cost)
"Blackwing - Simoon the Poison Wind": your Deck → your hand (by effect)
Revealed to the opponent: "Blackwing - Simoon the Poison Wind" (your hand).
   CL1 resolved.

Card texts (not shown to you yet this turn):
- "Blue-Eyes Alternative White Dragon" [LIGHT Dragon Lv8 Effect 3000/2500]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) by revealing "Blue-Eyes White Dragon" in your hand. You can only Special Summon "Blue-Eyes Alternative White Dragon" once per turn this way. This card's name becomes "Blue-Eyes White Dragon" while it is on the field or in the Graveyard. Once per turn: You can target 1 monster your opponent controls; destroy it. This card cannot attack the turn this effect is activated.
- "The Melody of Awakening Dragon" [Spell]: Discard 1 card; add up to 2 Dragon monsters with 3000 or more ATK and 2500 or less DEF from your Deck to your hand.
- "The White Stone of Legend" [LIGHT Dragon Lv1 Effect/Tuner 300/250]: If this card is sent to the GY: Add 1 "Blue-Eyes White Dragon" from your Deck to your hand.
- "Blue-Eyes White Dragon" [LIGHT Dragon Lv8 Normal 3000/2500]: This legendary dragon is a powerful engine of destruction. Virtually invincible, very few have faced this awesome creature and lived to tell the tale.

CURRENT STATE
TURN 3 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 8000

YOUR HAND (3) "Blackwing - Chinook the Snow Blast", "Enemy Controller", "Blackwing - Simoon the Poison Wind"
YOUR MONSTERS: M2: "Ahrima, the Wicked Warden" (face-up Attack, ATK 1700 / DEF 0)
YOUR SPELLS/TRAPS: S1: "Black Whirlwind" | S2: "Black Feather Whirlwind"
YOUR GY (2) "Blackwing - Vata the Emblem of Wandering", "Blackwing - Gofu the Vague Shadow"
YOUR BANISHED none
YOUR DECK: 32 cards | YOUR EXTRA DECK (15) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Black-Winged Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Blackwing Full Armor Master", "Black-Winged Assault Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 5 card(s)
OPPONENT MONSTERS: M3: "Blue-Eyes Alternative White Dragon" (face-up Attack, ATK 3000 / DEF 2500)
OPPONENT SPELLS/TRAPS: S3: face-down card
OPPONENT GY (2) "The White Stone of Legend", "The Melody of Awakening Dragon"
OPPONENT BANISHED none
OPPONENT DECK: 31 cards | OPPONENT EXTRA DECK: 15 card(s)

DECISION #27: Main Phase: choose your next action. Reply with exactly one option index.
[0] Activate "Blackwing - Chinook the Snow Blast" from your hand — effect: "Decrease ATK and negate effects"
[1] Activate "Enemy Controller" from your hand — effect: "Activate 1 of these effects"
[2] Set "Enemy Controller" in your Spell/Trap Zone
[3] Go to the Battle Phase
[4] End your turn (go to the End Phase)
>>>

## Texts of the deck's cards in this position
- "Black Feather Whirlwind" [Continuous Spell]: Once per turn, if you Special Summon a DARK Synchro Monster from the Extra Deck (except during the Damage Step): You can target 1 of your "Blackwing" monsters, or "Black-Winged Dragon", that is banished or in your GY, with less ATK than that Special Summoned monster; Special Summon it. Once per turn, if a DARK monster(s) you control would be destroyed by battle or card effect, you can remove 1 Black Feather Counter from your field instead.

* The above text is unofficial and describes the card's functionality in the OCG.
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
- "Blackwing - Simoon the Poison Wind" [DARK Winged Beast Lv6 Effect 1600/2000]: If you control no monsters and have this card in your hand: You can banish 1 other "Blackwing" monster from your hand; place 1 "Black Whirlwind" from your Deck face-up in your Spell & Trap Zone, then, either send this card to the GY, or immediately after this effect resolves, Normal Summon it without Tributing. You cannot Special Summon monsters from the Extra Deck for the rest of this turn, except DARK monsters. You can only use this effect of "Blackwing - Simoon the Poison Wind" once per turn. During the End Phase, if the "Black Whirlwind" placed by this effect is still on the field, send it to the GY, also take 1000 damage.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Ahrima, the Wicked Warden" [DARK Fiend Lv4 Effect 1700/0]: You can discard this card; add 1 "Lair of Darkness" from your Deck to your hand. You can Tribute 1 DARK monster; draw 1 card, or, if you Tributed a DARK monster other than this card to activate this effect, you can add 1 DARK monster with 2000 or more DEF from your Deck to your hand, instead. You can only use this effect of "Ahrima, the Wicked Warden" once per turn.
- "Black Whirlwind" [Continuous Spell]: When a "Blackwing" monster is Normal Summoned to your field: You can add 1 "Blackwing" monster from your Deck to your hand with less ATK than that monster.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)
- "Enemy Controller" [Quick-Play Spell]: Activate 1 of these effects;
● Target 1 face-up monster your opponent controls; change that target's battle position.
● Tribute 1 monster, then target 1 face-up monster your opponent controls; take control of that target until the End Phase.

## Answers
A) [1] Activate "Enemy Controller" from your hand — effect: "Activate 1 of these effects"
   reason given: Ahrima is blocking Simoon (Simoon needs an empty board), and Blue-Eyes Alternative would destroy Ahrima next turn anyway. Enemy Controller can Tribute Ahrima to take control of the 3000-ATK Alternative, so it can attack directly for 3000. That also leaves my board empty for a full Simoon turn next time, with Chinook as Simoon's banish cost.
B) [2] Set "Enemy Controller" in your Spell/Trap Zone
   reason given: Blue-Eyes Alternative (3000 ATK) outclasses Ahrima, and Enemy Controller's steal lasts only until End Phase, so using it now just trades Ahrima for 3000 damage that they can undo. Setting Enemy Controller keeps it as a Quick-Play answer for the opponent's turn, such as responding to their monster effect by tributing Ahrima to take control. Chinook would cost a Synchro or BWD from my Extra Deck for only -700 ATK.
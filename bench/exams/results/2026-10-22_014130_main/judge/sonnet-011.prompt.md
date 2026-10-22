# Task: grade the answers in 3 position(s): p33, p32, p28.

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

# Position p33 (Blackwing, a `select_unselect` decision)

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
"Blackwing - Sudri the Phantom Glimmer": your M1 → your GY (as material, Synchro)
"Blackwing - Vata the Emblem of Wandering": your M2 → your GY (as material, Synchro)
"Blackwing - Nothung the Starlight": your Extra Deck → your M1
You Special Summon "Blackwing - Nothung the Starlight" to M1 (face-up Attack).
Opponent draws 1 card(s).
CL1: You activate "Blackwing - Nothung the Starlight" from your M1 — effect: "Inflict damage"
Opponent takes 800 damage (LP now 7200).
   CL1 resolved.
"Blackwing - Sharnga the Waning Moon": your hand → your M2 (by rule)
You Normal/Flip Summon "Blackwing - Sharnga the Waning Moon" to M2 (face-up Attack).

Card texts (not shown to you yet this turn):
- "Maxx "C"" [EARTH Insect Lv2 Effect 500/200]: (Quick Effect): You can send this card from your hand to the GY; this turn, each time your opponent Special Summons a monster(s), immediately draw 1 card. You can only use this effect of "Maxx "C"" once per turn.

CURRENT STATE
TURN 1 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 7200

YOUR HAND (3) "Blackwing - Gofu the Vague Shadow", "Delta Crow - Anti Reverse", "Dark Armed Dragon"
YOUR MONSTERS: M1: "Blackwing - Nothung the Starlight" (face-up Attack, ATK 2400 / DEF 1600) | M2: "Blackwing - Sharnga the Waning Moon" (face-up Attack, ATK 500 / DEF 500)
YOUR SPELLS/TRAPS: none
YOUR GY (2) "Blackwing - Sudri the Phantom Glimmer", "Blackwing - Vata the Emblem of Wandering"
YOUR BANISHED none
YOUR DECK: 34 cards | YOUR EXTRA DECK (14) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Boreastorm the Wicked Wind", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Black-Winged Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Blackwing Full Armor Master", "Black-Winged Assault Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 6 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: none
OPPONENT GY (1) "Maxx "C""
OPPONENT BANISHED none
OPPONENT DECK: 37 cards | OPPONENT EXTRA DECK: 15 card(s)

DECISION #16: The game asks: "Select the card(s) to use as Synchro Material" (cards are picked one at a time; engine limits for this step: 1-1). Already picked: none. Reply with the indices of the card(s) you want from THIS list, in order. Replying [] cancels the whole action.
[0] "Blackwing - Sharnga the Waning Moon" (face-up Attack, ATK 500 / DEF 500) — your M2
>>>

## Texts of the deck's cards in this position
- "Black-Winged Dragon" [DARK Dragon Lv8 Effect/Synchro 2800/1600]: 1 Tuner + 1+ non-Tuner monsters
If you would take damage from a card effect, place 1 Black Feather Counter on this card instead. This card loses 700 ATK for each Black Feather Counter on it. Once per turn: You can remove all Black Feather Counters from this card, then target 1 face-up monster your opponent controls; that target loses 700 ATK for each Black Feather Counter removed, and if it does, inflict damage to your opponent equal to the ATK lost by this effect.
- "Blackwing - Gofu the Vague Shadow" [DARK Winged Beast Lv5 Effect/Tuner 0/0]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) while you control no monsters. When this card is Special Summoned from the hand: You can Special Summon 2 "Vague Shadow Tokens" (Winged Beast-Type/DARK/Level 1/ATK 0/DEF 0), but they cannot be Tributed or be used as Synchro Material. You can banish this card and 1 or more face-up non-Tuners you control, then target 1 "Blackwing" Synchro Monster in your Graveyard whose Level equals the total Levels the banished monsters had on the field; Special Summon it, and if you do, it is treated as a Tuner.
- "Blackwing - Boreastorm the Wicked Wind" [DARK Winged Beast Lv6 Effect/Tuner/Synchro 2400/1200]: 1 DARK Tuner + 1+ non-Tuner monsters
If this card is Synchro Summoned: You can send 1 "Blackwing" monster from your Deck to the GY, and if you do, this card's Level becomes the same as that monster's. When this card destroys a monster by battle and sends it to the GY: You can banish 1 "Blackwing" monster from your GY or face-up field, except the destroyed monster; Special Summon the destroyed monster to your field in Defense Position. You can only use each effect of "Blackwing - Boreastorm the Wicked Wind" once per turn.
- "Blackwing - Silverwind the Ascendant" [DARK Winged Beast Lv8 Effect/Synchro 2800/2000]: 1 "Blackwing" Tuner + 2 or more non-Tuner monsters
When this card is Synchro Summoned: You can target up to 2 face-up monsters on the field with DEF lower than this card's ATK; destroy those targets. You cannot conduct your Battle Phase the turn you activate this effect. During each of your opponent's turns, the first "Blackwing" monster you control that would be destroyed by battle, is not destroyed.
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
- "Void Ogre Dragon" [DARK Dragon Lv8 Effect/Synchro 3000/3000]: 1 DARK Tuner + 1+ non-Tuner monsters
Once per turn, when your opponent activates a Spell/Trap Card while you have no cards in your hand (Quick Effect): You can negate the activation, and if you do, destroy it.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)

## Answers
A) [0] "Blackwing - Sharnga the Waning Moon" (face-up Attack, ATK 500 / DEF 500) — your M2
   reason given: Sharnga (Lv2 DARK Tuner) plus Nothung (Lv6 non-Tuner) totals Level 8, which Synchro Summons Void Ogre Dragon (3000/3000) from the Extra Deck. It's the only legal material offered, so I'm continuing the summon rather than cancelling.

# Position p32 (Blackwing, a `chain` decision)

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
"Delta Crow - Anti Reverse": your hand → your S1 (by rule)
-- End Phase
=== TURN 2 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"Cards of Consonance": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Cards of Consonance" from opponent's S3
"The White Stone of Ancients": opponent's hand → opponent's GY (as cost, discarded)

Card texts (not shown to you yet this turn):
- "Cards of Consonance" [Spell]: Discard 1 Dragon Tuner with 1000 or less ATK; draw 2 cards.
- "The White Stone of Ancients" [LIGHT Dragon Lv1 Effect/Tuner 600/500]: Once per turn, during the End Phase, if this card is in the GY because it was sent there this turn: You can Special Summon 1 "Blue-Eyes" monster from your Deck. You can banish this card from your GY, then target 1 "Blue-Eyes" monster in your GY; add it to your hand. You can only use this effect of "The White Stone of Ancients" once per turn.

CURRENT STATE
TURN 2 — OPPONENT'S turn — Main Phase 1
LP: you 8000 | opponent 8000

YOUR HAND (1) "Blackwing - Gofu the Vague Shadow"
YOUR MONSTERS: M1: "Blackwing Full Armor Master" (face-up Attack, ATK 3000 / DEF 3000) | M2: "Black-Winged Assault Dragon" (face-up Attack, ATK 3200 / DEF 2800) | M3: "Dark Armed Dragon" (face-up Attack, ATK 2800 / DEF 1000)
YOUR SPELLS/TRAPS: S1: "Delta Crow - Anti Reverse" (set)
YOUR GY (6) "Blackwing - Kris the Crack of Dawn", "Blackwing - Chinook the Snow Blast", "Blackwing - Vata the Emblem of Wandering", "Blackwing - Sudri the Phantom Glimmer", "Blackwing - Sharnga the Waning Moon", "Blackwing - Harmattan the Dust"
YOUR BANISHED (2) "Black-Winged Dragon", "Blackwing - Boreastorm the Wicked Wind"
YOUR DECK: 31 cards | YOUR EXTRA DECK (11) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Blackwing Armor Master", "Clear Wing Synchro Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 4 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: S3: "Cards of Consonance"
OPPONENT GY (1) "The White Stone of Ancients"
OPPONENT BANISHED none
OPPONENT DECK: 34 cards | OPPONENT EXTRA DECK: 15 card(s)

CURRENT CHAIN (resolves last-to-first):
  CL1: opponent activated "Cards of Consonance"

DECISION #40: Response window: you may activate one of these cards/effects now. Reply with [] to pass (do nothing), or one option index to activate.
[0] Activate "Blackwing - Sharnga the Waning Moon" from your GY — effect: "Destroy 1 face-up card your opponent controls"
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
A) [] pass / none
   reason given: Sharnga's destroy is once per duel, so I won't spend it on a Cards of Consonance that is already being resolved. I'll save it for a real threat.
B) [] pass / none
   reason given: Cards of Consonance is a Normal Spell, so destroying it in the chain doesn't stop the draw. Sharnga's GY effect works only once per Duel, so I'm saving it for a real threat like a Blue-Eyes boss.

# Position p28 (Blackwing, a `select_card` decision)

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
Revealed to you: "Blue-Eyes White Dragon" (opponent's hand).
"Blue-Eyes Alternative White Dragon": opponent's hand → opponent's M3
Opponent Special Summons "Blue-Eyes Alternative White Dragon" to M3 (face-up Attack).
a hidden card: opponent's hand → opponent's S3 (by rule)
-- End Phase
=== TURN 2 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
"Blackwing - Gofu the Vague Shadow": your hand → your M1
You Special Summon "Blackwing - Gofu the Vague Shadow" to M1 (face-up Defense).
CL1: You activate "Blackwing - Gofu the Vague Shadow" from your M1 — effect: "Special Summon 2 "Vague Shadow Tokens""
"Vague Shadow Token": outside the game → your M2
You Special Summon "Vague Shadow Token" to M2 (face-up Defense).
"Vague Shadow Token": outside the game → your M3
You Special Summon "Vague Shadow Token" to M3 (face-up Defense).
   CL1 resolved.
"Black Feather Whirlwind": your hand → your S1 (by rule)
CL1: You activate "Black Feather Whirlwind" from your S1
   CL1 resolved.
"Blackwing - Sudri the Phantom Glimmer": your hand → your M4 (by rule)
You Normal/Flip Summon "Blackwing - Sudri the Phantom Glimmer" to M4 (face-up Attack).
CL1: You activate "Blackwing - Sudri the Phantom Glimmer" from your M4 — effect: "Add 1 card to the hand"
"Blackwing - Vata the Emblem of Wandering": your Deck → your hand (by effect)
Revealed to the opponent: "Blackwing - Vata the Emblem of Wandering" (your hand).
   CL1 resolved.
"Blackwing - Harmattan the Dust": your hand → your M5
You Special Summon "Blackwing - Harmattan the Dust" to M5 (face-up Defense).
"Blackwing - Gofu the Vague Shadow": your M1 → your GY (as material, Synchro)
"Blackwing - Harmattan the Dust": your M5 → your GY (as material, Synchro)
"Blackwing Armor Master": your Extra Deck → your M1
You Special Summon "Blackwing Armor Master" to M1 (face-up Attack).
"Blackwing - Vata the Emblem of Wandering": your hand → your M5
You Special Summon "Blackwing - Vata the Emblem of Wandering" to M5 (face-up Defense).
CL1: You activate "Blackwing - Vata the Emblem of Wandering" from your M5 — effect: "Special Summon this card" (the script's label for its Monster Zone effect, though this card is already on the field; see the card text)
"Blackwing - Chinook the Snow Blast": your Deck → your GY (by effect)
"Blackwing - Kris the Crack of Dawn": your Deck → your GY (by effect)
"Blackwing - Vata the Emblem of Wandering": your M5 → your GY (by effect)
"Black-Winged Dragon": your Extra Deck → your M5
You Special Summon "Black-Winged Dragon" to M5 (face-up Attack).
   CL1 resolved.
-- End Phase
=== TURN 3 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
CL1: Opponent activates "Blue-Eyes Alternative White Dragon" from opponent's M3 — effect: "Destroy"
   "Blackwing Armor Master" (face-up Attack, ATK 2500 / DEF 1500) — your M1 is targeted.
"Blackbird Close": your hand → your S2 (by rule)
CL2: You activate "Blackbird Close" from your S2
"Blackwing - Sudri the Phantom Glimmer": your M4 → your GY (as cost)
   CL1 was NEGATED.
"Blue-Eyes Alternative White Dragon": opponent's M3 → opponent's GY (destroyed, by effect)
   CL2 resolved.
   CL1 resolved.
"Blackbird Close": your S2 → your GY (by rule)
"Return of the Dragon Lords": opponent's hand → opponent's S2 (by rule)
CL1: Opponent activates "Return of the Dragon Lords" from opponent's S2
   "Blue-Eyes Alternative White Dragon" — opponent's GY is targeted.
"Blue-Eyes Alternative White Dragon": opponent's GY → opponent's M3
Opponent Special Summons "Blue-Eyes Alternative White Dragon" to M3 (face-up Attack).
   CL1 resolved.
"Return of the Dragon Lords": opponent's S2 → opponent's GY (by rule)
CL1: Opponent activates "Blue-Eyes Alternative White Dragon" from opponent's M3 — effect: "Destroy"
   "Blackwing Armor Master" (face-up Attack, ATK 2500 / DEF 1500) — your M1 is targeted.
"Blackwing Armor Master": your M1 → your GY (destroyed, by effect)
   CL1 resolved.
a hidden card: opponent's hand → opponent's S2 (by rule)
-- Battle Phase (start step)
-- Main Phase 2
-- End Phase
=== TURN 4 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
CL1: You activate "Blackwing - Chinook the Snow Blast" from your hand — effect: "Decrease ATK and negate effects"
"Blackwing - Chinook the Snow Blast": your hand → your GY (as cost)
   "Blue-Eyes Alternative White Dragon" (face-up Attack, ATK 3000 / DEF 2500) — opponent's M3 is targeted.
"Blackwing - Boreastorm the Wicked Wind": your Extra Deck → your GY (by effect)
   CL1 resolved.
-- Battle Phase (start step)

Card texts (not shown to you yet this turn):
- "Return of the Dragon Lords" [Spell]: Target 1 Level 7 or 8 Dragon monster in your GY; Special Summon it. If a Dragon monster(s) you control would be destroyed by battle or card effect, you can banish this card from your GY instead.
- "Vague Shadow Token" [DARK Winged Beast Lv1 Normal/Token 0/0]: Special Summoned with the effect of "Blackwing - Gofu the Vague Shadow". This Token cannot be Tributed or be used as Synchro Material.
- "Blue-Eyes Alternative White Dragon" [LIGHT Dragon Lv8 Effect 3000/2500]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) by revealing "Blue-Eyes White Dragon" in your hand. You can only Special Summon "Blue-Eyes Alternative White Dragon" once per turn this way. This card's name becomes "Blue-Eyes White Dragon" while it is on the field or in the Graveyard. Once per turn: You can target 1 monster your opponent controls; destroy it. This card cannot attack the turn this effect is activated.
- "Blue-Eyes White Dragon" [LIGHT Dragon Lv8 Normal 3000/2500]: This legendary dragon is a powerful engine of destruction. Virtually invincible, very few have faced this awesome creature and lived to tell the tale.

CURRENT STATE
TURN 4 — YOUR turn — Battle Phase (start step)
LP: you 8000 | opponent 8000

YOUR HAND (1) "Blackwing - Twin Shadow"
YOUR MONSTERS: M2: "Vague Shadow Token" (face-up Defense, ATK 0 / DEF 0) | M3: "Vague Shadow Token" (face-up Defense, ATK 0 / DEF 0) | M5: "Black-Winged Dragon" (face-up Attack, ATK 2800 / DEF 1600)
YOUR SPELLS/TRAPS: S1: "Black Feather Whirlwind"
YOUR GY (10) "Blackwing - Gofu the Vague Shadow", "Blackwing - Harmattan the Dust", "Blackwing - Chinook the Snow Blast", "Blackwing - Kris the Crack of Dawn", "Blackwing - Vata the Emblem of Wandering", "Blackwing - Sudri the Phantom Glimmer", "Blackbird Close", "Blackwing Armor Master", "Blackwing - Chinook the Snow Blast", "Blackwing - Boreastorm the Wicked Wind"
YOUR BANISHED none
YOUR DECK: 30 cards | YOUR EXTRA DECK (12) "Blackwing Armed Wing", "Coral Dragon", "Blackwing - Boreastorm the Wicked Wind", "Blackwing - Nothung the Starlight", "Black Rose Dragon", "Clear Wing Synchro Dragon", "Blackwing - Silverwind the Ascendant", "PSY-Framelord Omega", "Void Ogre Dragon", "Blackwing Full Armor Master", "Black-Winged Assault Dragon", "Black-Winged Assault Dragon"

OPPONENT HAND: 2 card(s)
OPPONENT MONSTERS: M3: "Blue-Eyes Alternative White Dragon" (face-up Attack, ATK 2300 / DEF 2500, effects negated)
OPPONENT SPELLS/TRAPS: S2: face-down card | S3: face-down card
OPPONENT GY (1) "Return of the Dragon Lords"
OPPONENT BANISHED none
OPPONENT DECK: 34 cards | OPPONENT EXTRA DECK: 15 card(s)

DECISION #46: The game asks: "Select an attack target" (this picks the target of the attack you just declared). Choose between 1 and 1 card(s); reply with the list of option indices. You may reply [] to cancel.
[0] "Blue-Eyes Alternative White Dragon" (face-up Attack, ATK 2300 / DEF 2500, effects negated) — opponent's M3
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
- "Blackwing - Twin Shadow" [Trap]: Shuffle 2 of your "Blackwing" monsters (1 Tuner and 1 non-Tuner) that are banished and/or in your GY into the Deck/Extra Deck; Special Summon 1 "Blackwing" Synchro Monster or "Black-Winged Dragon" from your Extra Deck whose Level equals the total Levels of those 2 monsters. (This is treated as a Synchro Summon.) If you control 2 or more "Blackwing" monsters, you can activate this card from your hand. You can only activate 1 "Blackwing - Twin Shadow" per turn.
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
- "Blackbird Close" [Counter Trap]: When a monster your opponent controls activates its effect: You can send 1 face-up "Blackwing" monster you control to the GY; negate the activation, and if you do, destroy it, then, you can Special Summon 1 "Black-Winged Dragon" from your Extra Deck. If you control a "Blackwing" Synchro Monster or "Black-Winged Dragon", you can activate this card from your hand.
- "Void Ogre Dragon" [DARK Dragon Lv8 Effect/Synchro 3000/3000]: 1 DARK Tuner + 1+ non-Tuner monsters
Once per turn, when your opponent activates a Spell/Trap Card while you have no cards in your hand (Quick Effect): You can negate the activation, and if you do, destroy it.
- "Blackwing - Kris the Crack of Dawn" [DARK Winged Beast Lv4 Effect 1900/300]: If you control a "Blackwing" monster other than "Blackwing - Kris the Crack of Dawn", you can Special Summon this card (from your hand). You can only Special Summon "Blackwing - Kris the Crack of Dawn" once per turn this way. Once per turn, this card cannot be destroyed by Spell/Trap effects.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Blackwing - Nothung the Starlight" [DARK Winged Beast Lv6 Effect/Synchro 2400/1600]: 1 Tuner + 1 or more non-Tuner monsters
If this card is Special Summoned: Inflict 800 damage to your opponent, then 1 face-up monster your opponent controls loses 800 ATK and DEF. You can only use this effect of "Blackwing - Nothung the Starlight" once per turn. During your Main Phase, you can Normal Summon 1 "Blackwing" monster in addition to your Normal Summon/Set. (You can only gain this effect once per turn.)

## Answers
A) [0] "Blue-Eyes Alternative White Dragon" (face-up Attack, ATK 2300 / DEF 2500, effects negated) — opponent's M3
   reason given: Black-Winged Dragon (2800) attacks the Blue-Eyes Alternative White Dragon, which is at 2300 ATK with its effects negated. That destroys it and deals 500 damage. Black Feather Whirlwind protects BWD from destruction if they have a trap.
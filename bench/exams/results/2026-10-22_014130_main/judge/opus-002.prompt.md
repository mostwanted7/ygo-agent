# Task: grade the answers in 3 position(s): p11, p04, p07.

Return one entry per position, in this order.

# Deck: Saffira

## Decklist
Main Deck (40):
  3x Saffira, Dragon Queen of the Voiceless Voice
  3x Manju of the Ten Thousand Hands
  3x Honest
  1x Condemned Witch
  1x Djinn Demolisher of Rituals
  1x Djinn Releaser of Rituals
  3x Tour Guide From the Underworld
  3x Ghost Ogre & Snow Rabbit
  3x Effect Veiler
  1x Sauravis, the Ancient and Ascended
  3x Saffira, Queen of Dragons
  1x Cyber Angel Benten
  1x Cyber Angel Idaten
  1x Change of Heart
  3x Pre-Preparation of Rites
  3x Preparation of Rites
  1x Prayers of the Voiceless Voice
  3x Hymn of Light
  2x Forbidden Lance
Extra Deck (12):
  1x Dante, Pilgrim of the Burning Abyss
  1x Clear Wing Synchro Dragon
  1x Black Rose Dragon
  1x Constellar Ptolemy M7
  1x Beatrice, Lady of the Eternal
  1x Jinzo - Layered
  1x Dark Rebellion Xyz Dragon
  1x Castel, the Skyblaster Musketeer
  1x Abyss Dweller
  1x Gagaga Cowboy
  1x Ghostrick Alucard
  1x Wind-Up Zenmaines

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
## Coaching lessons (from your opponent — these override everything below)

### 2026-10-21 game 2 (vs Geargia) — won
- **Set Forbidden Lance before you end your turn.** From the hand it can only be activated on your own turn, so
  holding it "for their turn" protected nothing for several turns. Keep it in hand only if you mean to use it this
  turn (e.g. to win a battle). Otherwise Set it in Main Phase 2, or in Main Phase 1 when there's no Battle Phase.

### 2026-10-21 — pre-game coaching on how the deck plays
1. **Search priority.** To summon Saffira you need two things: Saffira, Queen of Dragons, and a way to Ritual
   Summon her (Hymn of Light, Prayers, or SDQ's GY effect). Search whichever is missing. If you already have
   both, search a **Cyber Angel** to use as Tribute fodder with Manju or Preparation of Rites, NOT a second Saffira.
   Prefer Benten: when Tributed it searches a LIGHT Fairy, so it replaces itself.
2. **Ritual Spells belong in the GY.** From there they protect Saffira: Hymn stops destruction, Prayers brings
   a replacement Saffira. Prefer lines that end with them in the GY (SDQ's discard sends one; using one to
   summon puts it there).
3. **Don't waste bodies on Tributes.** Only Tribute cards that gain something from it: a Cyber Angel (Benten
   searches a LIGHT Fairy, Idaten gives your Ritual monsters +1000 ATK/DEF), or Tour Guide plus the Djinn it
   summoned (the Djinn gives Saffira its effect). Never Tribute hand traps or monsters you have another use for.
4. **Saffira's End Phase effect recycles hand traps.** If a hand trap that's good against this opponent is in
   your GY (Effect Veiler, Ghost Ogre), add it back with the "add 1 LIGHT monster from GY" mode. Otherwise
   draw 2 and discard 1 to dig for one. Pick hand traps for the matchup: Veiler against monster effects in
   their Main Phase, Ghost Ogre against effects of cards already on the field.
5. **Use Tour Guide's Xyz against problem cards.** If the opponent relies on Set cards or has another annoying
   card on the field, make a Rank 3 with Tour Guide + its Lv3 Fiend (Ghostrick Alucard destroys a Set card)
   instead of using them as Tributes.
6. **Synchro is a last resort.** The Tuners are your hand traps (Veiler, Ghost Ogre), so Synchro Summoning
   spends them. Tour Guide's Fiend can't be Synchro Material anyway.
7. **Remember how Saffira was summoned.** If Djinn Demolisher was one of the Tributes, the opponent can't
   target her, so holding Sauravis for protection is redundant; treat it as a spare card (e.g. Saffira's
   draw-2 discard). With Djinn Releaser the opponent can't Special Summon, so Sauravis's Summon negation is
   redundant too. Neither Djinn stops non-targeting removal; Hymn/Prayers in the GY cover that.

## Game plan

Ritual midrange. Ritual Summon **Saffira, Queen of Dragons** (Lv6, 2500/2400) without spending real cards,
protect her with Ritual Spells in the GY, a Djinn and hand traps, and use her End Phase effect every turn
to keep hand traps flowing. Grind the opponent out; Honest makes any LIGHT monster win a battle.

## Engine cards

- **Saffira, Dragon Queen of the Voiceless Voice (SDQ)**: two separate once-per-turn effects.
  - Hand: discard it → send 1 Ritual Spell from Deck to GY, then you *may* add Saffira or Sauravis from
    Deck or GY. Send **Hymn of Light** by default; send Prayers if Hymn is already in the GY or the opponent's
    removal banishes/bounces rather than destroys.
  - GY: banish it → Ritual Summon Saffira or Sauravis from hand, Tributing monsters from hand/field whose
    Levels total ≥ the Ritual monster's Level. No Ritual Spell needed.
  - So SDQ covers both the "way to summon" and the Saffira search. With SDQ you only need Tribute fodder.
- **Saffira, Queen of Dragons**: End Phase, if she was Ritual Summoned this turn OR a LIGHT monster went
  from hand/Deck to GY while she was face-up, choose one mode (once per turn): draw 2 then discard 1; discard
  1 random card from the opponent's hand; or add 1 LIGHT monster from your GY to hand. See lesson 4.
- **Hymn of Light**: Ritual Spell for Saffira (any Tributes, Levels ≥ 6). In GY: if your Ritual monster would
  be destroyed by battle or effect, banish Hymn instead.
- **Prayers of the Voiceless Voice**: Ritual Summons ANY LIGHT Ritual monster (Saffira, Sauravis, Cyber
  Angels), but only by Tributing LIGHT monsters. In GY: when your face-up LIGHT Ritual monster leaves the field
  because of an opponent's card effect, banish Prayers → Special Summon Saffira or Sauravis from hand or Deck.
  That Saffira isn't Ritual Summoned.
- **Pre-Preparation of Rites** (1 per turn): add a Ritual Spell + a Ritual monster named on it from Deck/GY:
  Hymn + Saffira, or Prayers + Saffira/Sauravis. Use it when you have neither half.
- **Preparation of Rites**: add a Lv7 or lower Ritual monster from Deck (Saffira if missing, otherwise a Cyber
  Angel), then you may add a Ritual Spell from GY if you need one to summon.
- **Manju**: Normal Summon → add a Ritual monster or Ritual Spell from Deck (see lesson 1).
- **Tour Guide From the Underworld**: Normal Summon → Special Summon a Lv3 Fiend from hand/Deck with its
  effects negated: a Djinn (or another Tour Guide). Then Tribute both (3+3 = 6) for Saffira, or Rank 3.
- **Djinn Releaser / Demolisher**: when used as a Tribute for a Ritual Summon (from hand, from field, or
  banished from GY in place of a Tribute) the Ritual monster gets: Releaser = **opponent can't Special Summon**
  while it's face-up; Demolisher = **can't be targeted** by the opponent's card effects. This works even when
  Tour Guide summoned the Djinn with its effects negated. Which Djinn to fetch *(untested)*: Releaser against
  decks that Special Summon a lot (most), Demolisher against targeting removal.
- **Cyber Angel Benten**: Lv6 LIGHT Ritual Fairy. When Tributed (from hand or field): add a LIGHT Fairy
  (Honest, Manju) from Deck. Exactly enough Levels for Saffira by itself.
- **Cyber Angel Idaten**: when Tributed, your Ritual monsters gain 1000 ATK/DEF. When Ritual Summoned (only
  possible via Prayers here), add a Ritual Spell from Deck/GY.
- **Sauravis, the Ancient and Ascended**: Lv7. From hand: discard it to negate an opponent's activation that
  targets a monster you control. On field: return it to hand to negate a Special Summon and banish that monster.
  Hold it as Saffira's protection unless a Djinn already covers that (lesson 7).

## Support cards

- **Honest**: when your LIGHT monster battles (Damage Step), send Honest from hand and that monster gains
  the opposing monster's ATK. Main Phase: return face-up Honest to hand.
- **Condemned Witch**: Normal Summon → add Forbidden Lance from Deck. Opponent's Main Phase: Tribute it →
  Special Summon a Lv4 Fairy from Deck (Honest, Manju).
- **Effect Veiler** and **Ghost Ogre & Snow Rabbit**: your hand traps. Save them for the opponent's key starter or
  boss monster; Saffira gets them back (lesson 4).
- **Change of Heart**: take their best monster, then attack with it or use it as Tribute/Xyz material so it
  never goes back.
- **Forbidden Lance**: Quick-Play; target a face-up monster: -800 ATK and unaffected by other Spells/Traps
  this turn. Saves Saffira from a Spell/Trap or wins a battle.

## Extra Deck

- Rank 3 (Tour Guide + Djinn/Tour Guide): **Ghostrick Alucard** (destroy a Set card), Wind-Up Zenmaines.
  This is the main way to deal with backrow (lesson 5).
- Rank 4 (Manju, Honest, Witch): Castel (flip a monster face-down / shuffle a card into the Deck), Dark
  Rebellion, Gagaga Cowboy (800 damage in Defense), Abyss Dweller.
- Rank 6 (two Lv6, e.g. Saffira + a Cyber Angel): Constellar Ptolemy M7 (return a monster on the field or in
  either GY to hand), Beatrice (send any card from Deck to GY), Jinzo - Layered (take control of a monster).
- Synchro 7, last resort only (lesson 6): Black Rose Dragon (destroy ALL cards on the field when
  Synchro Summoned), Clear Wing Synchro Dragon.
- Dante needs Burning Abyss monsters, so it can never be summoned here.

## Standard turns

1. **SDQ + Tribute fodder**: discard SDQ (send Hymn, add Saffira) → banish SDQ from GY to Ritual Summon
   Saffira, Tributing a Cyber Angel from hand or Tour Guide + Djinn.
2. **Saffira + Hymn already in hand**: Manju → search Cyber Angel Benten → Hymn, Tributing Benten (it
   searches a LIGHT Fairy). Hymn lands in the GY as protection.
3. **Tour Guide**: Normal Summon → Djinn from Deck → Tribute both for Saffira, or Rank 3 if the opponent has
   Set cards to clear.
4. **Missing both halves**: Pre-Preparation (Hymn + Saffira), or Preparation of Rites (Saffira, plus a Ritual
   Spell from GY if one is there).
5. Activate searches before committing your Normal Summon, so you know which monster you need.

## General principles

- One Normal Summon per turn: Tour Guide (fodder or Rank 3), Manju (search), or Witch (Lance) depending on
  what the hand is missing.
- Keep hand traps for the opponent's important plays, and keep the Ritual Spells flowing into the GY.
- Going first: set up Saffira (ideally with a Djinn) and pass holding hand traps. Going second: use hand traps
  during their turn, then Change of Heart / Rank 3 / Honest to break their board.
- Don't attack into face-down monsters with your only Saffira if losing her loses the game.

# Position p11 (Saffira, a `chain` decision)

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
CL1: You activate "Saffira, Dragon Queen of the Voiceless Voice" from your hand — effect: "Send 1 Ritual Spell from your Deck to the GY"
"Saffira, Dragon Queen of the Voiceless Voice": your hand → your GY (as cost, discarded)
"Prayers of the Voiceless Voice": your Deck → your GY (by effect)
"Saffira, Queen of Dragons": your Deck → your hand (by effect)
Revealed to the opponent: "Saffira, Queen of Dragons" (your hand).
   CL1 resolved.
"Manju of the Ten Thousand Hands": your hand → your M1 (by rule)
You Normal/Flip Summon "Manju of the Ten Thousand Hands" to M1 (face-up Attack).
CL1: You activate "Manju of the Ten Thousand Hands" from your M1 — effect: "Select 1 Ritual Monster Card or 1 Ritual Spell Card from your Deck"
"Cyber Angel Benten": your Deck → your hand (by effect)
Revealed to the opponent: "Cyber Angel Benten" (your hand).
   CL1 resolved.
"Hymn of Light": your hand → your S1 (by rule)
CL1: You activate "Hymn of Light" from your S1 — effect: "Ritual Summon"
"Cyber Angel Benten": your hand → your GY (Tributed, by effect, as material, Ritual)
"Saffira, Queen of Dragons": your hand → your M2
You Special Summon "Saffira, Queen of Dragons" to M2 (face-up Defense).
   CL1 resolved.
"Hymn of Light": your S1 → your GY (by rule)
CL1: You activate "Cyber Angel Benten" from your GY — effect: "effect 2 of Cyber Angel Benten"
"Honest": your Deck → your hand (by effect)
Revealed to the opponent: "Honest" (your hand).
   CL1 resolved.
-- End Phase
CL1: You activate "Saffira, Queen of Dragons" from your M2 — effect: "Select effect"
You draw 2 card(s).
"Ghost Ogre & Snow Rabbit": your hand → your GY (by effect, discarded)
   CL1 resolved.
=== TURN 2 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"Cards of Consonance": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Cards of Consonance" from opponent's S3
"The White Stone of Ancients": opponent's hand → opponent's GY (as cost, discarded)
Opponent draws 2 card(s).
   CL1 resolved.
"Cards of Consonance": opponent's S3 → opponent's GY (by rule)
"Dragon Shrine": opponent's hand → opponent's S3 (by effect)
CL1: Opponent activates "Dragon Shrine" from opponent's S3
"Dragon Spirit of White": opponent's Deck → opponent's GY (by effect)
"The White Stone of Legend": opponent's Deck → opponent's GY (by effect)
   CL1 resolved.
"Dragon Shrine": opponent's S3 → opponent's GY (by rule)
CL1: Opponent activates "The White Stone of Legend" from opponent's GY — effect: "Add card"
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Blue-Eyes White Dragon" (opponent's hand).
   CL1 resolved.
Revealed to you: "Blue-Eyes White Dragon" (opponent's hand).
"Blue-Eyes Alternative White Dragon": opponent's hand → opponent's M3
Opponent Special Summons "Blue-Eyes Alternative White Dragon" to M3 (face-up Attack).
"Trade-In": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Trade-In" from opponent's S3
"Blue-Eyes White Dragon": opponent's hand → opponent's GY (as cost, discarded)
Opponent draws 2 card(s).
   CL1 resolved.
"Trade-In": opponent's S3 → opponent's GY (by rule)
"Trade-In": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Trade-In" from opponent's S3
"Blue-Eyes White Dragon": opponent's hand → opponent's GY (as cost, discarded)
Opponent draws 2 card(s).
   CL1 resolved.
"Trade-In": opponent's S3 → opponent's GY (by rule)
"Pot of Desires": opponent's hand → opponent's S3 (by effect)
CL1: Opponent activates "Pot of Desires" from opponent's S3
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
Opponent draws 2 card(s).
   CL1 resolved.
"Pot of Desires": opponent's S3 → opponent's GY (by rule)
"Return of the Dragon Lords": opponent's hand → opponent's S3 (by effect)
CL1: Opponent activates "Return of the Dragon Lords" from opponent's S3
   "Blue-Eyes White Dragon" — opponent's GY is targeted.
"Blue-Eyes White Dragon": opponent's GY → opponent's M2
Opponent Special Summons "Blue-Eyes White Dragon" to M2 (face-up Attack).
   CL1 resolved.
"Return of the Dragon Lords": opponent's S3 → opponent's GY (by rule)
"Return of the Dragon Lords": opponent's hand → opponent's S3 (by effect)
CL1: Opponent activates "Return of the Dragon Lords" from opponent's S3
   "Blue-Eyes White Dragon" — opponent's GY is targeted.
"Blue-Eyes White Dragon": opponent's GY → opponent's M4
Opponent Special Summons "Blue-Eyes White Dragon" to M4 (face-up Attack).
   CL1 resolved.
"Return of the Dragon Lords": opponent's S3 → opponent's GY (by rule)
"Monster Reborn": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Monster Reborn" from opponent's S3
   "Dragon Spirit of White" — opponent's GY is targeted.
"Dragon Spirit of White": opponent's GY → opponent's M1
Opponent Special Summons "Dragon Spirit of White" to M1 (face-up Attack).
   CL1 resolved.
"Monster Reborn": opponent's S3 → opponent's GY (by rule)
CL1: Opponent activates "Blue-Eyes Alternative White Dragon" from opponent's M3 — effect: "Destroy"
   "Saffira, Queen of Dragons" (face-up Defense, ATK 2500 / DEF 2400) — your M2 is targeted.
CL2: You activate "Ghost Ogre & Snow Rabbit" from your hand
"Ghost Ogre & Snow Rabbit": your hand → your GY (as cost)
"Blue-Eyes Alternative White Dragon": opponent's M3 → opponent's GY (destroyed, by effect)
   CL2 resolved.
"Saffira, Queen of Dragons": your M2 → your GY (destroyed, by effect)
   CL1 resolved.
CL1: You activate "Prayers of the Voiceless Voice" from your GY — effect: "Special Summon 1 "Sauravis, the Ancient and Ascended", "Saffira, Queen of Dragons", or "Skull Guardian, Protector of the Voiceless Voice" from your hand or Deck"
"Prayers of the Voiceless Voice": your GY → your banished (as cost)
"Saffira, Queen of Dragons": your Deck → your M2
You Special Summon "Saffira, Queen of Dragons" to M2 (face-up Attack).
   CL1 resolved.
CL1: Opponent activates "The White Stone of Ancients" from opponent's GY — effect: "Special Summon"
"The White Stone of Ancients": opponent's GY → opponent's banished (as cost)
   "Blue-Eyes Alternative White Dragon" — opponent's GY is targeted.
a hidden card: opponent's GY → opponent's hand (by effect)
   CL1 resolved.
"Trade-In": opponent's hand → opponent's S3 (by effect)
CL1: Opponent activates "Trade-In" from opponent's S3
"Blue-Eyes Alternative White Dragon": opponent's hand → opponent's GY (as cost, discarded)
Opponent draws 2 card(s).
   CL1 resolved.
"Trade-In": opponent's S3 → opponent's GY (by rule)
"The White Stone of Ancients": opponent's hand → opponent's M3 (by effect)
Opponent Normal/Flip Summons "The White Stone of Ancients" to M3 (face-up Attack).
"Dragon Spirit of White": opponent's M1 → opponent's GY (as material, Synchro)
"The White Stone of Ancients": opponent's M3 → opponent's GY (as material, Synchro)
"Blue-Eyes Spirit Dragon": opponent's Extra Deck → opponent's M3
Opponent Special Summons "Blue-Eyes Spirit Dragon" to M3 (face-up Attack).
"Blue-Eyes White Dragon": opponent's M2 → opponent's Xyz material (as material, Xyz)
"Blue-Eyes White Dragon": opponent's M4 → opponent's Xyz material (as material, Xyz)
"Number 38: Hope Harbinger Dragon Titanic Galaxy": opponent's Extra Deck → opponent's M2
Opponent Special Summons "Number 38: Hope Harbinger Dragon Titanic Galaxy" to M2 (face-up Attack).
-- Battle Phase (start step)
ATTACK: "Number 38: Hope Harbinger Dragon Titanic Galaxy" (face-up Attack, ATK 3000 / DEF 2500, 2 material(s): Blue-Eyes White Dragon, Blue-Eyes White Dragon) — opponent's M2 attacks "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) — your M2.
CL1: You activate "Honest" from your hand — effect: "That monster gains ATK equal to the ATK of the opponent's monster it is battling, until the end of this turn"
"Honest": your hand → your GY (as cost)
   CL1 resolved.
Opponent takes 2500 damage (LP now 5500).
"Return of the Dragon Lords": opponent's GY → opponent's banished (by effect)
ATTACK: "Blue-Eyes Spirit Dragon" (face-up Attack, ATK 2500 / DEF 3000) — opponent's M3 attacks "Manju of the Ten Thousand Hands" (face-up Attack, ATK 1400 / DEF 1000) — your M1.
You take 1100 damage (LP now 6900).
"Manju of the Ten Thousand Hands": your M1 → your GY (destroyed, by battle)
-- Main Phase 2
-- End Phase
CL1: Opponent activates "The White Stone of Ancients" from opponent's GY — effect: "Return to hand"
"Blue-Eyes White Dragon": opponent's Deck → opponent's M4
Opponent Special Summons "Blue-Eyes White Dragon" to M4 (face-up Attack).
   CL1 resolved.
CL1: You activate "Saffira, Queen of Dragons" from your M2 — effect: "Select effect"
"Honest": your GY → your hand (by effect)
Revealed to the opponent: "Honest" (your hand).
   CL1 resolved.
=== TURN 3 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
"Tour Guide From the Underworld": your hand → your M1 (by rule)
You Normal/Flip Summon "Tour Guide From the Underworld" to M1 (face-up Attack).
CL1: You activate "Tour Guide From the Underworld" from your M1 — effect: "Special Summon"
"Djinn Releaser of Rituals": your Deck → your M3
You Special Summon "Djinn Releaser of Rituals" to M3 (face-up Defense).
   CL1 resolved.
CL1: You activate "Saffira, Dragon Queen of the Voiceless Voice" from your GY — effect: "Ritual Summon 1 LIGHT Warrior or Dragon Ritual Monster"
"Saffira, Dragon Queen of the Voiceless Voice": your GY → your banished (as cost)
CL2: Opponent activates "Blue-Eyes Spirit Dragon" from opponent's M3 — effect: "Negate activation"
   CL1 was NEGATED.
   CL2 resolved.
   CL1 resolved.
"Djinn Releaser of Rituals": your M3 → your Xyz material (as material, Xyz)
"Tour Guide From the Underworld": your M1 → your Xyz material (as material, Xyz)
"Wind-Up Zenmaines": your Extra Deck → your M1
You Special Summon "Wind-Up Zenmaines" to M1 (face-up Defense).
-- Battle Phase (start step)
CL1: Opponent activates "Blue-Eyes Spirit Dragon" from opponent's M3 — effect: "Special Summon"
"Blue-Eyes Spirit Dragon": opponent's M3 → opponent's GY (Tributed, as cost)
"Azure-Eyes Silver Dragon": opponent's Extra Deck → opponent's M3
Opponent Special Summons "Azure-Eyes Silver Dragon" to M3 (face-up Defense).
   CL1 resolved.
CL1: Opponent activates "Azure-Eyes Silver Dragon" from opponent's M3 — effect: "Special Summon"
   CL1 resolved.
ATTACK: "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) — your M2 attacks "Number 38: Hope Harbinger Dragon Titanic Galaxy" (face-up Attack, ATK 3000 / DEF 2500, 2 material(s): Blue-Eyes White Dragon, Blue-Eyes White Dragon) — opponent's M2.

Card texts (not shown to you yet this turn):
- "Return of the Dragon Lords" [Spell]: Target 1 Level 7 or 8 Dragon monster in your GY; Special Summon it. If a Dragon monster(s) you control would be destroyed by battle or card effect, you can banish this card from your GY instead.
- "Pot of Desires" [Spell]: Banish 10 cards from the top of your Deck, face-down; draw 2 cards. You can only activate 1 "Pot of Desires" per turn.
- "Trade-In" [Spell]: Discard 1 Level 8 monster; draw 2 cards.
- "Blue-Eyes Alternative White Dragon" [LIGHT Dragon Lv8 Effect 3000/2500]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) by revealing "Blue-Eyes White Dragon" in your hand. You can only Special Summon "Blue-Eyes Alternative White Dragon" once per turn this way. This card's name becomes "Blue-Eyes White Dragon" while it is on the field or in the Graveyard. Once per turn: You can target 1 monster your opponent controls; destroy it. This card cannot attack the turn this effect is activated.
- "Cards of Consonance" [Spell]: Discard 1 Dragon Tuner with 1000 or less ATK; draw 2 cards.
- "Azure-Eyes Silver Dragon" [LIGHT Dragon Lv9 Effect/Synchro 2500/3000]: 1 Tuner + 1+ non-Tuner Normal Monsters
If this card is Special Summoned: Until the end of the next turn, neither player can target Dragon monsters you currently control with card effects, also they cannot be destroyed by card effects. Once per turn, during your Standby Phase: You can target 1 Normal Monster in your GY; Special Summon it.
- "Dragon Shrine" [Spell]: Send 1 Dragon monster from your Deck to the GY, then, if that monster in your GY is a Dragon Normal Monster, you can send 1 more Dragon monster from your Deck to the GY. You can only activate 1 "Dragon Shrine" per turn.
- "Dragon Spirit of White" [LIGHT Dragon Lv8 Effect 2500/2000]: (This card is always treated as a "Blue-Eyes" card.)
This card is treated as a Normal Monster while in the hand or GY. When this card is Normal or Special Summoned: You can target 1 Spell/Trap your opponent controls; banish it. If your opponent controls a monster (Quick Effect): You can Tribute this card; Special Summon 1 "Blue-Eyes White Dragon" from your hand.
- "Blue-Eyes Spirit Dragon" [LIGHT Dragon Lv9 Effect/Synchro 2500/3000]: 1 Tuner + 1 or more non-Tuner "Blue-Eyes" monsters
Neither player can Special Summon 2 or more monsters at the same time. Once per turn, during either player's turn, when an effect of a card in the Graveyard is activated: You can negate the activation. During either player's turn: You can Tribute this Synchro Summoned card; Special Summon 1 LIGHT Dragon-Type Synchro Monster from your Extra Deck in Defense Position, except "Blue-Eyes Spirit Dragon", but destroy it during the End Phase of this turn.
- "Number 38: Hope Harbinger Dragon Titanic Galaxy" [LIGHT Dragon Rank 8 Effect/Xyz 3000/2500]: 2 Level 8 monsters
Once per turn, when a Spell Card or effect is activated on the field (Quick Effect): You can negate that effect, and if you do, attach that card to this card as material. When an opponent's monster declares an attack: You can detach 1 material from this card; change the attack target to this card and perform damage calculation. If another face-up Xyz Monster(s) you control is destroyed by battle or card effect: You can target 1 face-up Xyz Monster you control; it gains ATK equal to 1 of those destroyed monster's original ATK.
- "The White Stone of Ancients" [LIGHT Dragon Lv1 Effect/Tuner 600/500]: Once per turn, during the End Phase, if this card is in the GY because it was sent there this turn: You can Special Summon 1 "Blue-Eyes" monster from your Deck. You can banish this card from your GY, then target 1 "Blue-Eyes" monster in your GY; add it to your hand. You can only use this effect of "The White Stone of Ancients" once per turn.
- "The White Stone of Legend" [LIGHT Dragon Lv1 Effect/Tuner 300/250]: If this card is sent to the GY: Add 1 "Blue-Eyes White Dragon" from your Deck to your hand.
- "Monster Reborn" [Spell]: Target 1 monster in either GY; Special Summon it.
- "Blue-Eyes White Dragon" [LIGHT Dragon Lv8 Normal 3000/2500]: This legendary dragon is a powerful engine of destruction. Virtually invincible, very few have faced this awesome creature and lived to tell the tale.

CURRENT STATE
TURN 3 — YOUR turn — Battle Phase (start step)
LP: you 6900 | opponent 5500

YOUR HAND (3) "Sauravis, the Ancient and Ascended", "Honest", "Manju of the Ten Thousand Hands"
YOUR MONSTERS: M1: "Wind-Up Zenmaines" (face-up Defense, ATK 1500 / DEF 2100, 2 material(s): Djinn Releaser of Rituals, Tour Guide From the Underworld) | M2: "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400, already attacked)
YOUR SPELLS/TRAPS: none
YOUR GY (6) "Cyber Angel Benten", "Hymn of Light", "Ghost Ogre & Snow Rabbit", "Ghost Ogre & Snow Rabbit", "Saffira, Queen of Dragons", "Manju of the Ten Thousand Hands"
YOUR BANISHED (2) "Prayers of the Voiceless Voice", "Saffira, Dragon Queen of the Voiceless Voice"
YOUR DECK: 26 cards | YOUR EXTRA DECK (11) "Ghostrick Alucard", "Gagaga Cowboy", "Abyss Dweller", "Castel, the Skyblaster Musketeer", "Dark Rebellion Xyz Dragon", "Jinzo - Layered", "Beatrice, Lady of the Eternal", "Constellar Ptolemy M7", "Black Rose Dragon", "Clear Wing Synchro Dragon", "Dante, Pilgrim of the Burning Abyss"

OPPONENT HAND: 3 card(s)
OPPONENT MONSTERS: M2: "Number 38: Hope Harbinger Dragon Titanic Galaxy" (face-up Attack, ATK 3000 / DEF 2500, 2 material(s): Blue-Eyes White Dragon, Blue-Eyes White Dragon) | M3: "Azure-Eyes Silver Dragon" (face-up Defense, ATK 2500 / DEF 3000) | M4: "Blue-Eyes White Dragon" (face-up Attack, ATK 3000 / DEF 2500)
OPPONENT SPELLS/TRAPS: none
OPPONENT GY (13) "Cards of Consonance", "The White Stone of Legend", "Dragon Shrine", "Trade-In", "Trade-In", "Pot of Desires", "Return of the Dragon Lords", "Monster Reborn", "Blue-Eyes Alternative White Dragon", "Trade-In", "Dragon Spirit of White", "The White Stone of Ancients", "Blue-Eyes Spirit Dragon"
OPPONENT BANISHED (12) "The White Stone of Ancients", "Return of the Dragon Lords", 10 face-down
OPPONENT DECK: 10 cards | OPPONENT EXTRA DECK: 12 card(s)

DECISION #48: Response window: you may activate one of these cards/effects now. Reply with [] to pass (do nothing), or one option index to activate.
[0] Activate "Honest" from your hand — effect: "That monster gains ATK equal to the ATK of the opponent's monster it is battling, until the end of this turn"
>>>

## Texts of the deck's cards in this position
- "Sauravis, the Ancient and Ascended" [LIGHT Dragon Lv7 Effect/Ritual 2600/2800]: You can Ritual Summon this card with "Sprite's Blessing". When your opponent activates a card or effect that targets a monster you control (Quick Effect): You can discard this card; negate the activation. When your opponent would Special Summon a monster(s) (Quick Effect): You can return this card to the hand; negate the Special Summon, and if you do, banish that monster(s).
- "Djinn Releaser of Rituals" [DARK Fiend Lv3 Effect 1200/2000]: When you Ritual Summon a monster, you can banish this card from your Graveyard as 1 of the monsters required for the Ritual Summon. If a player Ritual Summons using this card, the other player cannot Special Summon while that Ritual Summoned monster is face-up on the field.
- "Tour Guide From the Underworld" [DARK Fiend Lv3 Effect 1000/600]: When this card is Normal Summoned: You can Special Summon 1 Level 3 Fiend monster from your hand or Deck, but negate its effects, also it cannot be used as Synchro Material.
- "Gagaga Cowboy" [EARTH Warrior Rank 4 Effect/Xyz 1500/2400]: 2 Level 4 monsters
Once per turn: You can detach 1 Xyz Material from this card; apply this effect, depending on this card's current battle position.
● Attack Position: If this card attacks an opponent's monster this turn, it gains 1000 ATK, also the opponent's monster loses 500 ATK, during the Damage Step only.
● Defense Position: Inflict 800 damage to your opponent.
- "Dark Rebellion Xyz Dragon" [DARK Dragon Rank 4 Effect/Xyz 2500/2000]: 2 Level 4 monsters
You can detach 2 materials from this card, then target 1 face-up monster your opponent controls; its ATK becomes half its current ATK, and if it does, this card gains that lost ATK.
- "Dante, Pilgrim of the Burning Abyss" [LIGHT Fairy Lv9 Effect/Fusion 2800/2500]: 3 "Burning Abyss" monsters with different names
Must be Fusion Summoned and cannot be Special Summoned by other ways. Cannot be targeted by an opponent's card effects. Once per turn, during either player's turn: You can send 1 "Burning Abyss" card from your hand to the Graveyard; draw 1 card. If this card is destroyed by battle and sent to the Graveyard, or if this card you control is sent to your Graveyard by an opponent's card effect: You can send 1 random card from your opponent's hand to the Graveyard.
- "Abyss Dweller" [WATER Sea Serpent Rank 4 Effect/Xyz 1700/1400]: 2 Level 4 monsters
While this card has a material attached that was originally WATER, all WATER monsters you control gain 500 ATK. Once per turn (Quick Effect): You can detach 1 material from this card; your opponent cannot activate any card effects in their GY this turn.
- "Beatrice, Lady of the Eternal" [LIGHT Fairy Rank 6 Effect/Xyz 2500/2800]: 2 Level 6 monsters
You can also Xyz Summon this card by sending 1 "Burning Abyss" monster from your hand to the GY, then using 1 "Dante" monster you control as material. (Transfer its materials to this card.) If Summoned this way, the following effect cannot be activated this turn. Once per turn (Quick Effect): You can detach 1 material from this card; send 1 card from your Deck to the GY. If this card in your possession is destroyed by your opponent's card and sent to your GY: You can Special Summon 1 "Burning Abyss" monster from your Extra Deck, ignoring its Summoning conditions.
- "Honest" [LIGHT Fairy Lv4 Effect 1100/1900]: During your Main Phase: You can return this face-up card from the field to the hand. During the Damage Step, when a LIGHT monster you control battles (Quick Effect): You can send this card from your hand to the GY; that monster gains ATK equal to the ATK of the opponent's monster it is battling, until the end of this turn.
- "Constellar Ptolemy M7" [LIGHT Machine Rank 6 Effect/Xyz 2700/2000]: 2 Level 6 monsters
You can also Xyz Summon this card by using a "Constellar" Xyz Monster you control as material, other than "Constellar Ptolemy M7". (Transfer its materials to this card.) If Summoned this way, the following effect cannot be activated this turn. Once per turn: You can detach 1 material from this card, then target 1 monster on the field or in either GY; return that target to the hand.
- "Saffira, Dragon Queen of the Voiceless Voice" [LIGHT Dragon Lv6 Effect 2500/2400]: You can discard this card; send 1 Ritual Spell from your Deck to the GY, then you can add 1 LIGHT Ritual Monster (Warrior or Dragon) from your Deck or GY to your hand. You can banish this card from your GY; Ritual Summon 1 LIGHT Ritual Monster (Warrior or Dragon) from your hand, by Tributing monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster. You can only use each effect of "Saffira, Dragon Queen of the Voiceless Voice" once per turn.
- "Prayers of the Voiceless Voice" [Ritual Spell]: This card can be used to Ritual Summon any LIGHT Ritual Monster. You must also Tribute LIGHT monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster. If a face-up LIGHT Ritual Monster(s) you control leaves the field by an opponent's card effect (except during the Damage Step): You can banish this card from your GY; Special Summon 1 "Sauravis, the Ancient and Ascended", "Saffira, Queen of Dragons", or "Skull Guardian, Protector of the Voiceless Voice" from your hand or Deck, ignoring its Summoning conditions. You can only use this effect of "Prayers of the Voiceless Voice" once per turn.
- "Saffira, Queen of Dragons" [LIGHT Dragon Lv6 Effect/Ritual 2500/2400]: You can Ritual Summon this card with "Hymn of Light". During the End Phase, if this card was Ritual Summoned this turn, or if a LIGHT monster was sent from the hand or Deck to the Graveyard this turn while this card was face-up on the field: You can activate 1 of these effects;
● Draw 2 cards, then discard 1 card.
● Discard 1 random card from your opponent's hand.
● Add 1 LIGHT monster from your Graveyard to your hand.
You can only use 1 "Saffira, Queen of Dragons" effect per turn, and only once that turn.
- "Ghost Ogre & Snow Rabbit" [LIGHT Psychic Lv3 Effect/Tuner 0/1800]: When a monster on the field activates its effect, or when a Spell/Trap that is already face-up on the field activates its effect (Quick Effect): You can send this card from your hand or field to the GY; destroy that card on the field. You can only use this effect of "Ghost Ogre & Snow Rabbit" once per turn.
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "Ghostrick Alucard" [DARK Zombie Rank 3 Effect/Xyz 1800/1600]: 2 Level 3 monsters
Monsters your opponent controls cannot target face-up "Ghostrick" monsters, or any face-down Defense Position monsters, for attacks, except this one. You can detach 1 Xyz Material from this card, then target 1 Set card your opponent controls; destroy that target. You can only use this effect of "Ghostrick Alucard" once per turn. If this card is sent to the Graveyard: You can target 1 other "Ghostrick" card in your Graveyard; add that target to your hand.
- "Cyber Angel Benten" [LIGHT Fairy Lv6 Effect/Ritual 1800/1500]: You can Ritual Summon this card with "Machine Angel Ritual". If this card destroys a monster by battle and sends it to the GY: Inflict damage to your opponent equal to that monster's original DEF in the GY. If this card is Tributed: You can add 1 LIGHT Fairy monster from your Deck to your hand.
- "Wind-Up Zenmaines" [FIRE Machine Rank 3 Effect/Xyz 1500/2100]: 2 Level 3 monsters
If this face-up card on the field would be destroyed, you can detach 1 Xyz Material from this card instead. Once per turn, during the End Phase, if this effect was used this turn: Target 1 card on the field; destroy it.
- "Hymn of Light" [Ritual Spell]: This card is used to Ritual Summon "Saffira, Queen of Dragons". You must also Tribute monsters from your hand or field whose total Levels equal 6 or more. If a Ritual Monster(s) you control would be destroyed by battle or card effect while this card is in your Graveyard, you can banish this card instead.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Castel, the Skyblaster Musketeer" [WIND Winged Beast Rank 4 Effect/Xyz 2000/1500]: 2 Level 4 monsters
You can detach 1 material from this card, then target 1 face-up monster on the field; change it to face-down Defense Position. You can detach 2 materials from this card, then target 1 other face-up card on the field; shuffle it into the Deck. You can only use 1 "Castel, the Skyblaster Musketeer" effect per turn, and only once that turn.
- "Manju of the Ten Thousand Hands" [LIGHT Fairy Lv4 Effect 1400/1000]: When this card is Normal or Flip Summoned: You can add 1 Ritual Monster or 1 Ritual Spell from your Deck to your hand.
- "Jinzo - Layered" [DARK Machine Rank 6 Effect/Xyz 2400/1500]: 2 Level 6 monsters
You can detach 1 material from this card, then target 1 face-up monster your opponent controls; take control of it until the End Phase, but it cannot activate its effects or declare an attack. If a Trap is on the field: You can Tribute 1 monster, and if you do, destroy 1 face-up card on the field. You can only use each effect of "Jinzo - Layered" once per turn.

## Answers
A) [0] Activate "Honest" from your hand — effect: "That monster gains ATK equal to the ATK of the opponent's monster it is battling, until the end of this turn"
   reason given: Honest gives Saffira +3000 ATK against Number 38, so she destroys it and deals 2500 damage. Number 38 only negates Spell effects, so it can't stop Honest.

# Position p04 (Saffira, a `idle` decision)

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
CL1: You activate "Saffira, Dragon Queen of the Voiceless Voice" from your hand — effect: "Send 1 Ritual Spell from your Deck to the GY"
"Saffira, Dragon Queen of the Voiceless Voice": your hand → your GY (as cost, discarded)
"Prayers of the Voiceless Voice": your Deck → your GY (by effect)
"Saffira, Queen of Dragons": your Deck → your hand (by effect)
Revealed to the opponent: "Saffira, Queen of Dragons" (your hand).
   CL1 resolved.
"Manju of the Ten Thousand Hands": your hand → your M1 (by rule)
You Normal/Flip Summon "Manju of the Ten Thousand Hands" to M1 (face-up Attack).
CL1: You activate "Manju of the Ten Thousand Hands" from your M1 — effect: "Select 1 Ritual Monster Card or 1 Ritual Spell Card from your Deck"
"Cyber Angel Benten": your Deck → your hand (by effect)
Revealed to the opponent: "Cyber Angel Benten" (your hand).
   CL1 resolved.
"Hymn of Light": your hand → your S1 (by rule)
CL1: You activate "Hymn of Light" from your S1 — effect: "Ritual Summon"
"Cyber Angel Benten": your hand → your GY (Tributed, by effect, as material, Ritual)
"Saffira, Queen of Dragons": your hand → your M2
You Special Summon "Saffira, Queen of Dragons" to M2 (face-up Attack).
Opponent draws 1 card(s).
   CL1 resolved.
"Hymn of Light": your S1 → your GY (by rule)
CL1: You activate "Cyber Angel Benten" from your GY — effect: "effect 2 of Cyber Angel Benten"
"Honest": your Deck → your hand (by effect)
Revealed to the opponent: "Honest" (your hand).
   CL1 resolved.
-- End Phase
CL1: You activate "Saffira, Queen of Dragons" from your M2 — effect: "Select effect"
You draw 2 card(s).
"Ghost Ogre & Snow Rabbit": your hand → your GY (by effect, discarded)
   CL1 resolved.
=== TURN 2 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"Pot of Desires": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Pot of Desires" from opponent's S3
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
a hidden card: opponent's Deck → opponent's banished (as cost)
Opponent draws 2 card(s).
   CL1 resolved.
"Pot of Desires": opponent's S3 → opponent's GY (by rule)
"Time Thief Startup": opponent's hand → opponent's S3 (by effect)
CL1: Opponent activates "Time Thief Startup" from opponent's S3
"Time Thief Regulator": opponent's hand → opponent's M3
Opponent Special Summons "Time Thief Regulator" to M3 (face-up Attack).
   CL1 resolved.
"Time Thief Startup": opponent's S3 → opponent's GY (by rule)
a hidden card: opponent's hand → opponent's S3 (by rule)
a hidden card: opponent's hand → opponent's S2 (by rule)
"Time Thief Winder": opponent's hand → opponent's M2 (by rule)
Opponent Normal/Flip Summons "Time Thief Winder" to M2 (face-up Attack).
CL1: Opponent activates "Time Thief Winder" from opponent's M2 — effect: "Add to hand"
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Time Thief Regulator" (opponent's hand).
   CL1 resolved.
"Time Thief Regulator": opponent's M3 → opponent's Xyz material (as material, Xyz)
"Time Thief Winder": opponent's M2 → opponent's Xyz material (as material, Xyz)
"Time Thief Redoer": opponent's Extra Deck → opponent's M3
Opponent Special Summons "Time Thief Redoer" to M3 (face-up Attack).
CL1: Opponent activates "Time Thief Redoer" from opponent's M3 — effect: "Detach materials and apply effects"
CL2: You activate "Ghost Ogre & Snow Rabbit" from your hand
"Ghost Ogre & Snow Rabbit": your hand → your GY (as cost)
"Time Thief Redoer": opponent's M3 → opponent's GY (destroyed, by effect)
"Time Thief Regulator": opponent's Xyz material → opponent's GY (by rule)
"Time Thief Winder": opponent's Xyz material → opponent's GY (by rule)
   CL2 resolved.
   CL1 resolved.
-- End Phase
CL1: You activate "Saffira, Queen of Dragons" from your M2 — effect: "Select effect"
"Ghost Ogre & Snow Rabbit": your GY → your hand (by effect)
Revealed to the opponent: "Ghost Ogre & Snow Rabbit" (your hand).
   CL1 resolved.
=== TURN 3 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
-- Main Phase 1
"Manju of the Ten Thousand Hands": your hand → your M3 (by effect)
You Normal/Flip Summon "Manju of the Ten Thousand Hands" to M3 (face-up Attack).
CL1: You activate "Manju of the Ten Thousand Hands" from your M3 — effect: "Select 1 Ritual Monster Card or 1 Ritual Spell Card from your Deck"
"Cyber Angel Idaten": your Deck → your hand (by effect)
Revealed to the opponent: "Cyber Angel Idaten" (your hand).
   CL1 resolved.
CL1: You activate "Saffira, Dragon Queen of the Voiceless Voice" from your GY — effect: "Ritual Summon 1 LIGHT Warrior or Dragon Ritual Monster"
"Saffira, Dragon Queen of the Voiceless Voice": your GY → your banished (as cost)
"Manju of the Ten Thousand Hands": your hand → your GY (Tributed, by effect, as material, Ritual)
"Cyber Angel Idaten": your hand → your GY (Tributed, by effect, as material, Ritual)
"Sauravis, the Ancient and Ascended": your hand → your M4
You Special Summon "Sauravis, the Ancient and Ascended" to M4 (face-up Attack).
   CL1 resolved.
CL1: You activate "Cyber Angel Idaten" from your GY — effect: "effect 2 of Cyber Angel Idaten"
   CL1 resolved.

Card texts (not shown to you yet this turn):
- "Time Thief Startup" [Quick-Play Spell]: Special Summon 1 "Time Thief" monster from your hand. During your Main Phase: You can banish this card from your GY, then target 1 "Time Thief" Xyz Monster you control; attach 3 "Time Thief" cards of different types (1 Monster, 1 Spell, and 1 Trap) from your GY to that monster as material. You can only use 1 "Time Thief Startup" effect per turn, and only once that turn.
- "Time Thief Regulator" [DARK Machine Lv4 Effect 600/200]: If you control no other monsters: You can Tribute this card; Special Summon 2 "Time Thief" monsters with different names from your Deck in Defense Position, except "Time Thief Regulator". When an Xyz Monster you control is destroyed by battle, while this card is in your GY: You can Special Summon this card, but banish it when it leaves the field. You can only use each effect of "Time Thief Regulator" once per turn.
- "Maxx "C"" [EARTH Insect Lv2 Effect 500/200]: (Quick Effect): You can send this card from your hand to the GY; this turn, each time your opponent Special Summons a monster(s), immediately draw 1 card. You can only use this effect of "Maxx "C"" once per turn.
- "Pot of Desires" [Spell]: Banish 10 cards from the top of your Deck, face-down; draw 2 cards. You can only activate 1 "Pot of Desires" per turn.
- "Time Thief Redoer" [DARK Psychic Rank 4 Effect/Xyz 2400/2000]: 2 Level 4 monsters
Once per turn, during the Standby Phase: You can attach the top card of your opponent's Deck to this card as material. (Quick Effect): You can detach up to 3 different types of materials from this card, then apply the following effect(s) depending on what was detached.
● Monster: Banish this card until the End Phase.
● Spell: Draw 1 card.
● Trap: Place 1 face-up card your opponent controls on the top of the Deck.
You can only use this effect of "Time Thief Redoer" once per turn.
- "Time Thief Winder" [DARK Psychic Lv4 Effect 1800/1300]: You can detach 1 material from a monster you control; Special Summon this card from your hand. If this card is Normal or Special Summoned: You can add 1 "Time Thief" card from your Deck to your hand, except "Time Thief Winder". You can only use each effect of "Time Thief Winder" once per turn.

* The above text is unofficial and describes the card's functionality in the OCG.

CURRENT STATE
TURN 3 — YOUR turn — Main Phase 1
LP: you 8000 | opponent 8000

YOUR HAND (2) "Honest", "Ghost Ogre & Snow Rabbit"
YOUR MONSTERS: M1: "Manju of the Ten Thousand Hands" (face-up Attack, ATK 1400 / DEF 1000) | M2: "Saffira, Queen of Dragons" (face-up Attack, ATK 3500 / DEF 3400) | M3: "Manju of the Ten Thousand Hands" (face-up Attack, ATK 1400 / DEF 1000) | M4: "Sauravis, the Ancient and Ascended" (face-up Attack, ATK 3600 / DEF 3800)
YOUR SPELLS/TRAPS: none
YOUR GY (6) "Prayers of the Voiceless Voice", "Cyber Angel Benten", "Hymn of Light", "Ghost Ogre & Snow Rabbit", "Manju of the Ten Thousand Hands", "Cyber Angel Idaten"
YOUR BANISHED (1) "Saffira, Dragon Queen of the Voiceless Voice"
YOUR DECK: 27 cards | YOUR EXTRA DECK (12) "Wind-Up Zenmaines", "Ghostrick Alucard", "Gagaga Cowboy", "Abyss Dweller", "Castel, the Skyblaster Musketeer", "Dark Rebellion Xyz Dragon", "Jinzo - Layered", "Beatrice, Lady of the Eternal", "Constellar Ptolemy M7", "Black Rose Dragon", "Clear Wing Synchro Dragon", "Dante, Pilgrim of the Burning Abyss"

OPPONENT HAND: 3 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: S2: face-down card | S3: face-down card
OPPONENT GY (6) "Maxx "C"", "Pot of Desires", "Time Thief Startup", "Time Thief Redoer", "Time Thief Regulator", "Time Thief Winder"
OPPONENT BANISHED (10) 10 face-down
OPPONENT DECK: 24 cards | OPPONENT EXTRA DECK: 14 card(s)

DECISION #39: Main Phase: choose your next action. Reply with exactly one option index.
[0] Special Summon "Gagaga Cowboy" from your Extra Deck (by its own summoning procedure)
[1] Special Summon "Abyss Dweller" from your Extra Deck (by its own summoning procedure)
[2] Special Summon "Castel, the Skyblaster Musketeer" from your Extra Deck (by its own summoning procedure)
[3] Special Summon "Dark Rebellion Xyz Dragon" from your Extra Deck (by its own summoning procedure)
[4] Change the battle position of "Manju of the Ten Thousand Hands" (face-up Attack, ATK 1400 / DEF 1000)
[5] Change the battle position of "Saffira, Queen of Dragons" (face-up Attack, ATK 3500 / DEF 3400)
[6] Go to the Battle Phase (attack available: your Attack Position monsters total 9900 ATK; opponent LP 8000; opponent has no monsters)
[7] End your turn (go to the End Phase)
>>>

## Texts of the deck's cards in this position
- "Cyber Angel Idaten" [LIGHT Fairy Lv6 Effect/Ritual 1600/2000]: You can Ritual Summon this card with "Machine Angel Ritual". If this card is Ritual Summoned: You can add 1 Ritual Spell from your Deck or GY to your hand. If this card is Tributed: You can make all Ritual Monsters you control gain 1000 ATK/DEF.
- "Sauravis, the Ancient and Ascended" [LIGHT Dragon Lv7 Effect/Ritual 2600/2800]: You can Ritual Summon this card with "Sprite's Blessing". When your opponent activates a card or effect that targets a monster you control (Quick Effect): You can discard this card; negate the activation. When your opponent would Special Summon a monster(s) (Quick Effect): You can return this card to the hand; negate the Special Summon, and if you do, banish that monster(s).
- "Gagaga Cowboy" [EARTH Warrior Rank 4 Effect/Xyz 1500/2400]: 2 Level 4 monsters
Once per turn: You can detach 1 Xyz Material from this card; apply this effect, depending on this card's current battle position.
● Attack Position: If this card attacks an opponent's monster this turn, it gains 1000 ATK, also the opponent's monster loses 500 ATK, during the Damage Step only.
● Defense Position: Inflict 800 damage to your opponent.
- "Dark Rebellion Xyz Dragon" [DARK Dragon Rank 4 Effect/Xyz 2500/2000]: 2 Level 4 monsters
You can detach 2 materials from this card, then target 1 face-up monster your opponent controls; its ATK becomes half its current ATK, and if it does, this card gains that lost ATK.
- "Dante, Pilgrim of the Burning Abyss" [LIGHT Fairy Lv9 Effect/Fusion 2800/2500]: 3 "Burning Abyss" monsters with different names
Must be Fusion Summoned and cannot be Special Summoned by other ways. Cannot be targeted by an opponent's card effects. Once per turn, during either player's turn: You can send 1 "Burning Abyss" card from your hand to the Graveyard; draw 1 card. If this card is destroyed by battle and sent to the Graveyard, or if this card you control is sent to your Graveyard by an opponent's card effect: You can send 1 random card from your opponent's hand to the Graveyard.
- "Abyss Dweller" [WATER Sea Serpent Rank 4 Effect/Xyz 1700/1400]: 2 Level 4 monsters
While this card has a material attached that was originally WATER, all WATER monsters you control gain 500 ATK. Once per turn (Quick Effect): You can detach 1 material from this card; your opponent cannot activate any card effects in their GY this turn.
- "Beatrice, Lady of the Eternal" [LIGHT Fairy Rank 6 Effect/Xyz 2500/2800]: 2 Level 6 monsters
You can also Xyz Summon this card by sending 1 "Burning Abyss" monster from your hand to the GY, then using 1 "Dante" monster you control as material. (Transfer its materials to this card.) If Summoned this way, the following effect cannot be activated this turn. Once per turn (Quick Effect): You can detach 1 material from this card; send 1 card from your Deck to the GY. If this card in your possession is destroyed by your opponent's card and sent to your GY: You can Special Summon 1 "Burning Abyss" monster from your Extra Deck, ignoring its Summoning conditions.
- "Honest" [LIGHT Fairy Lv4 Effect 1100/1900]: During your Main Phase: You can return this face-up card from the field to the hand. During the Damage Step, when a LIGHT monster you control battles (Quick Effect): You can send this card from your hand to the GY; that monster gains ATK equal to the ATK of the opponent's monster it is battling, until the end of this turn.
- "Constellar Ptolemy M7" [LIGHT Machine Rank 6 Effect/Xyz 2700/2000]: 2 Level 6 monsters
You can also Xyz Summon this card by using a "Constellar" Xyz Monster you control as material, other than "Constellar Ptolemy M7". (Transfer its materials to this card.) If Summoned this way, the following effect cannot be activated this turn. Once per turn: You can detach 1 material from this card, then target 1 monster on the field or in either GY; return that target to the hand.
- "Saffira, Dragon Queen of the Voiceless Voice" [LIGHT Dragon Lv6 Effect 2500/2400]: You can discard this card; send 1 Ritual Spell from your Deck to the GY, then you can add 1 LIGHT Ritual Monster (Warrior or Dragon) from your Deck or GY to your hand. You can banish this card from your GY; Ritual Summon 1 LIGHT Ritual Monster (Warrior or Dragon) from your hand, by Tributing monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster. You can only use each effect of "Saffira, Dragon Queen of the Voiceless Voice" once per turn.
- "Prayers of the Voiceless Voice" [Ritual Spell]: This card can be used to Ritual Summon any LIGHT Ritual Monster. You must also Tribute LIGHT monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster. If a face-up LIGHT Ritual Monster(s) you control leaves the field by an opponent's card effect (except during the Damage Step): You can banish this card from your GY; Special Summon 1 "Sauravis, the Ancient and Ascended", "Saffira, Queen of Dragons", or "Skull Guardian, Protector of the Voiceless Voice" from your hand or Deck, ignoring its Summoning conditions. You can only use this effect of "Prayers of the Voiceless Voice" once per turn.
- "Saffira, Queen of Dragons" [LIGHT Dragon Lv6 Effect/Ritual 2500/2400]: You can Ritual Summon this card with "Hymn of Light". During the End Phase, if this card was Ritual Summoned this turn, or if a LIGHT monster was sent from the hand or Deck to the Graveyard this turn while this card was face-up on the field: You can activate 1 of these effects;
● Draw 2 cards, then discard 1 card.
● Discard 1 random card from your opponent's hand.
● Add 1 LIGHT monster from your Graveyard to your hand.
You can only use 1 "Saffira, Queen of Dragons" effect per turn, and only once that turn.
- "Ghost Ogre & Snow Rabbit" [LIGHT Psychic Lv3 Effect/Tuner 0/1800]: When a monster on the field activates its effect, or when a Spell/Trap that is already face-up on the field activates its effect (Quick Effect): You can send this card from your hand or field to the GY; destroy that card on the field. You can only use this effect of "Ghost Ogre & Snow Rabbit" once per turn.
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "Ghostrick Alucard" [DARK Zombie Rank 3 Effect/Xyz 1800/1600]: 2 Level 3 monsters
Monsters your opponent controls cannot target face-up "Ghostrick" monsters, or any face-down Defense Position monsters, for attacks, except this one. You can detach 1 Xyz Material from this card, then target 1 Set card your opponent controls; destroy that target. You can only use this effect of "Ghostrick Alucard" once per turn. If this card is sent to the Graveyard: You can target 1 other "Ghostrick" card in your Graveyard; add that target to your hand.
- "Cyber Angel Benten" [LIGHT Fairy Lv6 Effect/Ritual 1800/1500]: You can Ritual Summon this card with "Machine Angel Ritual". If this card destroys a monster by battle and sends it to the GY: Inflict damage to your opponent equal to that monster's original DEF in the GY. If this card is Tributed: You can add 1 LIGHT Fairy monster from your Deck to your hand.
- "Wind-Up Zenmaines" [FIRE Machine Rank 3 Effect/Xyz 1500/2100]: 2 Level 3 monsters
If this face-up card on the field would be destroyed, you can detach 1 Xyz Material from this card instead. Once per turn, during the End Phase, if this effect was used this turn: Target 1 card on the field; destroy it.
- "Hymn of Light" [Ritual Spell]: This card is used to Ritual Summon "Saffira, Queen of Dragons". You must also Tribute monsters from your hand or field whose total Levels equal 6 or more. If a Ritual Monster(s) you control would be destroyed by battle or card effect while this card is in your Graveyard, you can banish this card instead.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Castel, the Skyblaster Musketeer" [WIND Winged Beast Rank 4 Effect/Xyz 2000/1500]: 2 Level 4 monsters
You can detach 1 material from this card, then target 1 face-up monster on the field; change it to face-down Defense Position. You can detach 2 materials from this card, then target 1 other face-up card on the field; shuffle it into the Deck. You can only use 1 "Castel, the Skyblaster Musketeer" effect per turn, and only once that turn.
- "Manju of the Ten Thousand Hands" [LIGHT Fairy Lv4 Effect 1400/1000]: When this card is Normal or Flip Summoned: You can add 1 Ritual Monster or 1 Ritual Spell from your Deck to your hand.
- "Jinzo - Layered" [DARK Machine Rank 6 Effect/Xyz 2400/1500]: 2 Level 6 monsters
You can detach 1 material from this card, then target 1 face-up monster your opponent controls; take control of it until the End Phase, but it cannot activate its effects or declare an attack. If a Trap is on the field: You can Tribute 1 monster, and if you do, destroy 1 face-up card on the field. You can only use each effect of "Jinzo - Layered" once per turn.

## Answers
A) [6] Go to the Battle Phase (attack available: your Attack Position monsters total 9900 ATK; opponent LP 8000; opponent has no monsters)
   reason given: The opponent has no monsters and my attackers total 9900 ATK against 8000 LP, so I attack for lethal.

# Position p07 (Saffira, a `battle` decision)

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
"Pre-Preparation of Rites": your hand → your S1 (by rule)
CL1: You activate "Pre-Preparation of Rites" from your S1 — effect: "Add 1 Ritual Spell from your Deck to your hand, and add 1 Ritual Monster from your Deck or GY to your hand whose name is mentioned on that Ritual Spell"
"Hymn of Light": your Deck → your hand (by effect)
"Saffira, Queen of Dragons": your Deck → your hand (by effect)
Revealed to the opponent: "Saffira, Queen of Dragons" (your hand), "Hymn of Light" (your hand).
   CL1 resolved.
"Pre-Preparation of Rites": your S1 → your GY (by rule)
"Preparation of Rites": your hand → your S1 (by rule)
CL1: You activate "Preparation of Rites" from your S1
"Cyber Angel Benten": your Deck → your hand (by effect)
Revealed to the opponent: "Cyber Angel Benten" (your hand).
   CL1 resolved.
"Preparation of Rites": your S1 → your GY (by rule)
"Hymn of Light": your hand → your S1 (by effect)
CL1: You activate "Hymn of Light" from your S1 — effect: "Ritual Summon"
"Cyber Angel Benten": your hand → your GY (Tributed, by effect, as material, Ritual)
"Saffira, Queen of Dragons": your hand → your M1
You Special Summon "Saffira, Queen of Dragons" to M1 (face-up Attack).
   CL1 resolved.
"Hymn of Light": your S1 → your GY (by rule)
CL1: You activate "Cyber Angel Benten" from your GY — effect: "effect 2 of Cyber Angel Benten"
"Manju of the Ten Thousand Hands": your Deck → your hand (by effect)
Revealed to the opponent: "Manju of the Ten Thousand Hands" (your hand).
   CL1 resolved.
"Manju of the Ten Thousand Hands": your hand → your M2 (by effect)
You Normal/Flip Summon "Manju of the Ten Thousand Hands" to M2 (face-up Attack).
CL1: You activate "Manju of the Ten Thousand Hands" from your M2 — effect: "Select 1 Ritual Monster Card or 1 Ritual Spell Card from your Deck"
"Hymn of Light": your Deck → your hand (by effect)
Revealed to the opponent: "Hymn of Light" (your hand).
   CL1 resolved.
-- End Phase
CL1: You activate "Saffira, Queen of Dragons" from your M1 — effect: "Select effect"
"Cyber Angel Benten": your GY → your hand (by effect)
Revealed to the opponent: "Cyber Angel Benten" (your hand).
   CL1 resolved.
=== TURN 2 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"Time Thief Startup": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Time Thief Startup" from opponent's S3
"Time Thief Winder": opponent's hand → opponent's M3
Opponent Special Summons "Time Thief Winder" to M3 (face-up Attack).
   CL1 resolved.
"Time Thief Startup": opponent's S3 → opponent's GY (by rule)
CL1: Opponent activates "Time Thief Winder" from opponent's M3 — effect: "Add to hand"
a hidden card: opponent's Deck → opponent's hand (by effect)
Revealed to you: "Time Thief Retrograde" (opponent's hand).
   CL1 resolved.
a hidden card: opponent's hand → opponent's S3 (by rule)
a hidden card: opponent's hand → opponent's S2 (by effect)
a hidden card: opponent's hand → opponent's S4 (by rule)
"Time Thief Chronocorder": opponent's hand → opponent's M2 (by rule)
Opponent Normal/Flip Summons "Time Thief Chronocorder" to M2 (face-up Attack).
"Time Thief Chronocorder": opponent's M2 → opponent's Xyz material (as material, Xyz)
"Time Thief Winder": opponent's M3 → opponent's Xyz material (as material, Xyz)
"Time Thief Redoer": opponent's Extra Deck → opponent's M3
Opponent Special Summons "Time Thief Redoer" to M3 (face-up Attack).
CL1: Opponent activates "Time Thief Redoer" from opponent's M3 — effect: "Detach materials and apply effects"
"Time Thief Chronocorder": opponent's Xyz material → opponent's GY (by effect)
"Time Thief Redoer": opponent's M3 → opponent's banished (by effect)
"Time Thief Winder": opponent's Xyz material → opponent's GY (by rule)
   CL1 resolved.
CL1: Opponent activates "Time Thief Chronocorder" from opponent's GY — effect: "Special Summon this card"
"Time Thief Chronocorder": opponent's GY → opponent's M3
Opponent Special Summons "Time Thief Chronocorder" to M3 (face-up Attack).
   CL1 resolved.
-- Battle Phase (start step)
-- Main Phase 2
-- End Phase
"Time Thief Redoer": opponent's banished → opponent's M2 (by effect)
=== TURN 3 (your turn) ===
-- Draw Phase
You draw 1 card(s).
-- Standby Phase
CL1: Opponent activates "Time Thief Redoer" from opponent's M2 — effect: "Attach the top card of your opponent's deck"
"Saffira, Queen of Dragons": your Deck → opponent's Xyz material (as material, Xyz)
   CL1 resolved.
CL1: Opponent activates "Time Thief Redoer" from opponent's M2 — effect: "Detach materials and apply effects"
"Saffira, Queen of Dragons": opponent's Xyz material → your GY (by effect)
"Time Thief Redoer": opponent's M2 → opponent's banished (by effect)
   CL1 resolved.
-- Main Phase 1
"Hymn of Light": your hand → your S1 (by effect)
CL1: You activate "Hymn of Light" from your S1 — effect: "Ritual Summon"
Opponent's "Solemn Judgment" is flipped face-up.
CL2: Opponent activates "Solemn Judgment" from opponent's S4
Opponent pays 4000 LP (LP now 4000).
   CL1 was NEGATED.
"Hymn of Light": your S1 → your GY (destroyed, by effect)
   CL2 resolved.
   CL1 resolved.
"Solemn Judgment": opponent's S4 → opponent's GY (by rule)
"Prayers of the Voiceless Voice": your hand → your S1 (by rule)
CL1: You activate "Prayers of the Voiceless Voice" from your S1 — effect: "Ritual Summon"
"Cyber Angel Benten": your hand → your GY (Tributed, by effect, as material, Ritual)
"Saffira, Queen of Dragons": your hand → your M3
You Special Summon "Saffira, Queen of Dragons" to M3 (face-up Attack).
   CL1 resolved.
"Prayers of the Voiceless Voice": your S1 → your GY (by rule)
CL1: You activate "Cyber Angel Benten" from your GY — effect: "effect 2 of Cyber Angel Benten"
CL2: Opponent activates "Ash Blossom & Joyous Spring" from opponent's hand — effect: "Negate that effect"
"Ash Blossom & Joyous Spring": opponent's hand → opponent's GY (as cost, discarded)
   CL1 was NEGATED.
   CL2 resolved.
   CL1 resolved.
"Condemned Witch": your hand → your M4 (by rule)
You Normal/Flip Summon "Condemned Witch" to M4 (face-up Attack).
CL1: You activate "Condemned Witch" from your M4 — effect: "effect 1 of Condemned Witch"
"Forbidden Lance": your Deck → your hand (by effect)
Revealed to the opponent: "Forbidden Lance" (your hand).
   CL1 resolved.
-- Battle Phase (start step)
CL1: Opponent activates "Time Thief Chronocorder" from opponent's M3 — effect: "Change the next battle damage"
"Time Thief Chronocorder": opponent's M3 → opponent's banished (Tributed, as cost)
   CL1 resolved.

Card texts (not shown to you yet this turn):
- "Time Thief Startup" [Quick-Play Spell]: Special Summon 1 "Time Thief" monster from your hand. During your Main Phase: You can banish this card from your GY, then target 1 "Time Thief" Xyz Monster you control; attach 3 "Time Thief" cards of different types (1 Monster, 1 Spell, and 1 Trap) from your GY to that monster as material. You can only use 1 "Time Thief Startup" effect per turn, and only once that turn.
- "Ash Blossom & Joyous Spring" [FIRE Zombie Lv3 Effect/Tuner 0/1800]: When a card or effect is activated that includes any of these effects (Quick Effect): You can discard this card; negate that effect.
● Add a card(s) from the Deck to the hand.
● Special Summon a Monster Card(s) from the Deck.
● Send a card(s) from the Deck to the GY.
You can only use this effect of "Ash Blossom & Joyous Spring" once per turn.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Solemn Judgment" [Counter Trap]: When a monster(s) would be Summoned, OR a Spell/Trap Card is activated: Pay half your LP; negate the Summon or activation, and if you do, destroy that card.
- "Time Thief Redoer" [DARK Psychic Rank 4 Effect/Xyz 2400/2000]: 2 Level 4 monsters
Once per turn, during the Standby Phase: You can attach the top card of your opponent's Deck to this card as material. (Quick Effect): You can detach up to 3 different types of materials from this card, then apply the following effect(s) depending on what was detached.
● Monster: Banish this card until the End Phase.
● Spell: Draw 1 card.
● Trap: Place 1 face-up card your opponent controls on the top of the Deck.
You can only use this effect of "Time Thief Redoer" once per turn.
- "Time Thief Winder" [DARK Psychic Lv4 Effect 1800/1300]: You can detach 1 material from a monster you control; Special Summon this card from your hand. If this card is Normal or Special Summoned: You can add 1 "Time Thief" card from your Deck to your hand, except "Time Thief Winder". You can only use each effect of "Time Thief Winder" once per turn.

* The above text is unofficial and describes the card's functionality in the OCG.
- "Time Thief Chronocorder" [DARK Machine Lv4 Effect 1000/1000]: During your opponent's Battle Phase (Quick Effect): You can Tribute this card; the next battle damage you take from an opponent's monster's attack this turn is inflicted to your opponent instead. If a face-up Xyz Monster you control leaves the field by card effect, while this card is in your GY (except during the Damage Step): You can Special Summon this card, but banish it when it leaves the field. You can only use each effect of "Time Thief Chronocorder" once per turn.
- "Time Thief Retrograde" [Counter Trap]: When a Spell/Trap Card is activated while you control a "Time Thief" Xyz Monster: Negate the activation, and if you do, attach that card to a "Time Thief" Xyz Monster you control as material. You can only activate 1 "Time Thief Retrograde" per turn.

CURRENT STATE
TURN 3 — YOUR turn — Battle Phase (start step)
LP: you 8000 | opponent 4000

YOUR HAND (2) "Forbidden Lance", "Effect Veiler"
YOUR MONSTERS: M1: "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) | M2: "Manju of the Ten Thousand Hands" (face-up Attack, ATK 1400 / DEF 1000) | M3: "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) | M4: "Condemned Witch" (face-up Attack, ATK 100 / DEF 2000)
YOUR SPELLS/TRAPS: none
YOUR GY (7) "Pre-Preparation of Rites", "Preparation of Rites", "Hymn of Light", "Saffira, Queen of Dragons", "Hymn of Light", "Cyber Angel Benten", "Prayers of the Voiceless Voice"
YOUR BANISHED none
YOUR DECK: 27 cards | YOUR EXTRA DECK (12) "Wind-Up Zenmaines", "Ghostrick Alucard", "Gagaga Cowboy", "Abyss Dweller", "Castel, the Skyblaster Musketeer", "Dark Rebellion Xyz Dragon", "Jinzo - Layered", "Beatrice, Lady of the Eternal", "Constellar Ptolemy M7", "Black Rose Dragon", "Clear Wing Synchro Dragon", "Dante, Pilgrim of the Burning Abyss"

OPPONENT HAND: 0 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: S2: face-down card | S3: face-down card
OPPONENT GY (4) "Time Thief Startup", "Time Thief Winder", "Solemn Judgment", "Ash Blossom & Joyous Spring"
OPPONENT BANISHED (2) "Time Thief Redoer", "Time Thief Chronocorder"
OPPONENT DECK: 37 cards | OPPONENT EXTRA DECK: 14 card(s)

DECISION #53: Battle Phase: choose your next action. Reply with exactly one option index.
[0] Activate "Forbidden Lance" from your hand
[1] Attack with "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (can attack directly)
[2] Attack with "Manju of the Ten Thousand Hands" (face-up Attack, ATK 1400 / DEF 1000) (can attack directly)
[3] Attack with "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (can attack directly)
[4] Attack with "Condemned Witch" (face-up Attack, ATK 100 / DEF 2000) (can attack directly)
[5] End the Battle Phase (go to Main Phase 2)
[6] End your turn (go to the End Phase)
>>>

## Texts of the deck's cards in this position
- "Gagaga Cowboy" [EARTH Warrior Rank 4 Effect/Xyz 1500/2400]: 2 Level 4 monsters
Once per turn: You can detach 1 Xyz Material from this card; apply this effect, depending on this card's current battle position.
● Attack Position: If this card attacks an opponent's monster this turn, it gains 1000 ATK, also the opponent's monster loses 500 ATK, during the Damage Step only.
● Defense Position: Inflict 800 damage to your opponent.
- "Pre-Preparation of Rites" [Spell]: Add 1 Ritual Spell from your Deck to your hand, and add 1 Ritual Monster from your Deck or GY to your hand whose name is mentioned on that Ritual Spell. You can only activate 1 "Pre-Preparation of Rites" per turn.
- "Dark Rebellion Xyz Dragon" [DARK Dragon Rank 4 Effect/Xyz 2500/2000]: 2 Level 4 monsters
You can detach 2 materials from this card, then target 1 face-up monster your opponent controls; its ATK becomes half its current ATK, and if it does, this card gains that lost ATK.
- "Dante, Pilgrim of the Burning Abyss" [LIGHT Fairy Lv9 Effect/Fusion 2800/2500]: 3 "Burning Abyss" monsters with different names
Must be Fusion Summoned and cannot be Special Summoned by other ways. Cannot be targeted by an opponent's card effects. Once per turn, during either player's turn: You can send 1 "Burning Abyss" card from your hand to the Graveyard; draw 1 card. If this card is destroyed by battle and sent to the Graveyard, or if this card you control is sent to your Graveyard by an opponent's card effect: You can send 1 random card from your opponent's hand to the Graveyard.
- "Abyss Dweller" [WATER Sea Serpent Rank 4 Effect/Xyz 1700/1400]: 2 Level 4 monsters
While this card has a material attached that was originally WATER, all WATER monsters you control gain 500 ATK. Once per turn (Quick Effect): You can detach 1 material from this card; your opponent cannot activate any card effects in their GY this turn.
- "Forbidden Lance" [Quick-Play Spell]: Target 1 face-up monster on the field; until the end of this turn, that target loses 800 ATK, but is unaffected by the effects of other Spells/Traps.
- "Beatrice, Lady of the Eternal" [LIGHT Fairy Rank 6 Effect/Xyz 2500/2800]: 2 Level 6 monsters
You can also Xyz Summon this card by sending 1 "Burning Abyss" monster from your hand to the GY, then using 1 "Dante" monster you control as material. (Transfer its materials to this card.) If Summoned this way, the following effect cannot be activated this turn. Once per turn (Quick Effect): You can detach 1 material from this card; send 1 card from your Deck to the GY. If this card in your possession is destroyed by your opponent's card and sent to your GY: You can Special Summon 1 "Burning Abyss" monster from your Extra Deck, ignoring its Summoning conditions.
- "Constellar Ptolemy M7" [LIGHT Machine Rank 6 Effect/Xyz 2700/2000]: 2 Level 6 monsters
You can also Xyz Summon this card by using a "Constellar" Xyz Monster you control as material, other than "Constellar Ptolemy M7". (Transfer its materials to this card.) If Summoned this way, the following effect cannot be activated this turn. Once per turn: You can detach 1 material from this card, then target 1 monster on the field or in either GY; return that target to the hand.
- "Condemned Witch" [DARK Fairy Lv4 Effect 100/2000]: When this card is Normal Summoned: You can add 1 "Forbidden" Quick-Play Spell from your Deck to your hand. During your opponent's Main Phase (Quick Effect): You can Tribute this card; Special Summon 1 Level 4 Fairy monster from your Deck, except "Condemned Witch". You can only use each effect of "Condemned Witch" once per turn.
- "Prayers of the Voiceless Voice" [Ritual Spell]: This card can be used to Ritual Summon any LIGHT Ritual Monster. You must also Tribute LIGHT monsters from your hand or field whose total Levels equal or exceed the Level of the Ritual Monster. If a face-up LIGHT Ritual Monster(s) you control leaves the field by an opponent's card effect (except during the Damage Step): You can banish this card from your GY; Special Summon 1 "Sauravis, the Ancient and Ascended", "Saffira, Queen of Dragons", or "Skull Guardian, Protector of the Voiceless Voice" from your hand or Deck, ignoring its Summoning conditions. You can only use this effect of "Prayers of the Voiceless Voice" once per turn.
- "Saffira, Queen of Dragons" [LIGHT Dragon Lv6 Effect/Ritual 2500/2400]: You can Ritual Summon this card with "Hymn of Light". During the End Phase, if this card was Ritual Summoned this turn, or if a LIGHT monster was sent from the hand or Deck to the Graveyard this turn while this card was face-up on the field: You can activate 1 of these effects;
● Draw 2 cards, then discard 1 card.
● Discard 1 random card from your opponent's hand.
● Add 1 LIGHT monster from your Graveyard to your hand.
You can only use 1 "Saffira, Queen of Dragons" effect per turn, and only once that turn.
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "Ghostrick Alucard" [DARK Zombie Rank 3 Effect/Xyz 1800/1600]: 2 Level 3 monsters
Monsters your opponent controls cannot target face-up "Ghostrick" monsters, or any face-down Defense Position monsters, for attacks, except this one. You can detach 1 Xyz Material from this card, then target 1 Set card your opponent controls; destroy that target. You can only use this effect of "Ghostrick Alucard" once per turn. If this card is sent to the Graveyard: You can target 1 other "Ghostrick" card in your Graveyard; add that target to your hand.
- "Cyber Angel Benten" [LIGHT Fairy Lv6 Effect/Ritual 1800/1500]: You can Ritual Summon this card with "Machine Angel Ritual". If this card destroys a monster by battle and sends it to the GY: Inflict damage to your opponent equal to that monster's original DEF in the GY. If this card is Tributed: You can add 1 LIGHT Fairy monster from your Deck to your hand.
- "Wind-Up Zenmaines" [FIRE Machine Rank 3 Effect/Xyz 1500/2100]: 2 Level 3 monsters
If this face-up card on the field would be destroyed, you can detach 1 Xyz Material from this card instead. Once per turn, during the End Phase, if this effect was used this turn: Target 1 card on the field; destroy it.
- "Hymn of Light" [Ritual Spell]: This card is used to Ritual Summon "Saffira, Queen of Dragons". You must also Tribute monsters from your hand or field whose total Levels equal 6 or more. If a Ritual Monster(s) you control would be destroyed by battle or card effect while this card is in your Graveyard, you can banish this card instead.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Castel, the Skyblaster Musketeer" [WIND Winged Beast Rank 4 Effect/Xyz 2000/1500]: 2 Level 4 monsters
You can detach 1 material from this card, then target 1 face-up monster on the field; change it to face-down Defense Position. You can detach 2 materials from this card, then target 1 other face-up card on the field; shuffle it into the Deck. You can only use 1 "Castel, the Skyblaster Musketeer" effect per turn, and only once that turn.
- "Manju of the Ten Thousand Hands" [LIGHT Fairy Lv4 Effect 1400/1000]: When this card is Normal or Flip Summoned: You can add 1 Ritual Monster or 1 Ritual Spell from your Deck to your hand.
- "Preparation of Rites" [Spell]: Add 1 Level 7 or lower Ritual Monster from your Deck to your hand, then you can add 1 Ritual Spell from your GY to your hand.
- "Effect Veiler" [LIGHT Spellcaster Lv1 Effect/Tuner 0/0]: During your opponent's Main Phase (Quick Effect): You can send this card from your hand to the GY, then target 1 Effect Monster your opponent controls; negate the effects of that face-up monster your opponent controls, until the end of this turn.
- "Jinzo - Layered" [DARK Machine Rank 6 Effect/Xyz 2400/1500]: 2 Level 6 monsters
You can detach 1 material from this card, then target 1 face-up monster your opponent controls; take control of it until the End Phase, but it cannot activate its effects or declare an attack. If a Trap is on the field: You can Tribute 1 monster, and if you do, destroy 1 face-up card on the field. You can only use each effect of "Jinzo - Layered" once per turn.

## Answers
A) [4] Attack with "Condemned Witch" (face-up Attack, ATK 100 / DEF 2000) (can attack directly)
   reason given: Chronocorder sends the damage from my next attack back to me, so I attack first with Condemned Witch (100 ATK) to use up that effect cheaply. After that, the two Saffiras and Manju deal 6400, and the opponent only has 4000 LP left. They have no monsters, so this is lethal.
B) [1] Attack with "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (can attack directly)
   reason given: The opponent has no monsters, 0 cards in hand, and 4000 LP, while my four attackers total 6500 ATK of direct damage. I'm starting with a Saffira attack and will keep declaring the other attackers (Saffira, Manju, Witch) to finish the duel. I'm holding Forbidden Lance, since it's not needed for lethal.
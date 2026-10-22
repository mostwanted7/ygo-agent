# Task: grade the answers in 1 position(s): p18.

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

# Position p18 (Saffira, a `effect_yn` decision)

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
"Tour Guide From the Underworld": your hand → your M1 (by rule)
You Normal/Flip Summon "Tour Guide From the Underworld" to M1 (face-up Attack).
CL1: You activate "Tour Guide From the Underworld" from your M1 — effect: "Special Summon"
"Djinn Releaser of Rituals": your Deck → your M2
You Special Summon "Djinn Releaser of Rituals" to M2 (face-up Defense).
   CL1 resolved.
"Hymn of Light": your hand → your S1 (by rule)
CL1: You activate "Hymn of Light" from your S1 — effect: "Ritual Summon"
"Tour Guide From the Underworld": your M1 → your GY (Tributed, by effect, as material, Ritual)
"Djinn Releaser of Rituals": your M2 → your GY (Tributed, by effect, as material, Ritual)
"Saffira, Queen of Dragons": your hand → your M1
You Special Summon "Saffira, Queen of Dragons" to M1 (face-up Attack).
   CL1 resolved.
"Hymn of Light": your S1 → your GY (by rule)
CL1: You activate "Saffira, Dragon Queen of the Voiceless Voice" from your hand — effect: "Send 1 Ritual Spell from your Deck to the GY"
"Saffira, Dragon Queen of the Voiceless Voice": your hand → your GY (as cost, discarded)
"Prayers of the Voiceless Voice": your Deck → your GY (by effect)
"Sauravis, the Ancient and Ascended": your Deck → your hand (by effect)
Revealed to the opponent: "Sauravis, the Ancient and Ascended" (your hand).
   CL1 resolved.
-- End Phase
CL1: You activate "Saffira, Queen of Dragons" from your M1 — effect: "Select effect"
You draw 2 card(s).
"Pre-Preparation of Rites": your hand → your GY (by effect, discarded)
   CL1 resolved.
=== TURN 2 (opponent's turn) ===
-- Draw Phase
Opponent draws 1 card(s).
-- Standby Phase
-- Main Phase 1
"Trade-In": opponent's hand → opponent's S3 (by rule)
CL1: Opponent activates "Trade-In" from opponent's S3
"Blue-Eyes Alternative White Dragon": opponent's hand → opponent's GY (as cost, discarded)
Opponent draws 2 card(s).
   CL1 resolved.
"Trade-In": opponent's S3 → opponent's GY (by rule)
-- End Phase

Card texts (not shown to you yet this turn):
- "Trade-In" [Spell]: Discard 1 Level 8 monster; draw 2 cards.
- "Blue-Eyes Alternative White Dragon" [LIGHT Dragon Lv8 Effect 3000/2500]: Cannot be Normal Summoned/Set. Must first be Special Summoned (from your hand) by revealing "Blue-Eyes White Dragon" in your hand. You can only Special Summon "Blue-Eyes Alternative White Dragon" once per turn this way. This card's name becomes "Blue-Eyes White Dragon" while it is on the field or in the Graveyard. Once per turn: You can target 1 monster your opponent controls; destroy it. This card cannot attack the turn this effect is activated.

CURRENT STATE
TURN 2 — OPPONENT'S turn — End Phase
LP: you 8000 | opponent 8000

YOUR HAND (3) "Sauravis, the Ancient and Ascended", "Honest", "Preparation of Rites"
YOUR MONSTERS: M1: "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400)
YOUR SPELLS/TRAPS: none
YOUR GY (6) "Tour Guide From the Underworld", "Djinn Releaser of Rituals", "Hymn of Light", "Saffira, Dragon Queen of the Voiceless Voice", "Prayers of the Voiceless Voice", "Pre-Preparation of Rites"
YOUR BANISHED none
YOUR DECK: 30 cards | YOUR EXTRA DECK (12) "Wind-Up Zenmaines", "Ghostrick Alucard", "Gagaga Cowboy", "Abyss Dweller", "Castel, the Skyblaster Musketeer", "Dark Rebellion Xyz Dragon", "Jinzo - Layered", "Beatrice, Lady of the Eternal", "Constellar Ptolemy M7", "Black Rose Dragon", "Clear Wing Synchro Dragon", "Dante, Pilgrim of the Burning Abyss"

OPPONENT HAND: 6 card(s)
OPPONENT MONSTERS: none
OPPONENT SPELLS/TRAPS: none
OPPONENT GY (2) "Blue-Eyes Alternative White Dragon", "Trade-In"
OPPONENT BANISHED none
OPPONENT DECK: 32 cards | OPPONENT EXTRA DECK: 15 card(s)

DECISION #22: Do you want to activate/use "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (your M1)? Reply [1] for yes or [0] for no.
>>>

## Texts of the deck's cards in this position
- "Sauravis, the Ancient and Ascended" [LIGHT Dragon Lv7 Effect/Ritual 2600/2800]: You can Ritual Summon this card with "Sprite's Blessing". When your opponent activates a card or effect that targets a monster you control (Quick Effect): You can discard this card; negate the activation. When your opponent would Special Summon a monster(s) (Quick Effect): You can return this card to the hand; negate the Special Summon, and if you do, banish that monster(s).
- "Djinn Releaser of Rituals" [DARK Fiend Lv3 Effect 1200/2000]: When you Ritual Summon a monster, you can banish this card from your Graveyard as 1 of the monsters required for the Ritual Summon. If a player Ritual Summons using this card, the other player cannot Special Summon while that Ritual Summoned monster is face-up on the field.
- "Tour Guide From the Underworld" [DARK Fiend Lv3 Effect 1000/600]: When this card is Normal Summoned: You can Special Summon 1 Level 3 Fiend monster from your hand or Deck, but negate its effects, also it cannot be used as Synchro Material.
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
- "Black Rose Dragon" [FIRE Dragon Lv7 Effect/Synchro 2400/1800]: 1 Tuner + 1+ non-Tuner monsters
When this card is Synchro Summoned: You can destroy all cards on the field. Once per turn: You can banish 1 Plant monster from your GY, then target 1 Defense Position monster your opponent controls; change that target to face-up Attack Position, and if you do, its ATK becomes 0 until the end of this turn.
- "Ghostrick Alucard" [DARK Zombie Rank 3 Effect/Xyz 1800/1600]: 2 Level 3 monsters
Monsters your opponent controls cannot target face-up "Ghostrick" monsters, or any face-down Defense Position monsters, for attacks, except this one. You can detach 1 Xyz Material from this card, then target 1 Set card your opponent controls; destroy that target. You can only use this effect of "Ghostrick Alucard" once per turn. If this card is sent to the Graveyard: You can target 1 other "Ghostrick" card in your Graveyard; add that target to your hand.
- "Wind-Up Zenmaines" [FIRE Machine Rank 3 Effect/Xyz 1500/2100]: 2 Level 3 monsters
If this face-up card on the field would be destroyed, you can detach 1 Xyz Material from this card instead. Once per turn, during the End Phase, if this effect was used this turn: Target 1 card on the field; destroy it.
- "Hymn of Light" [Ritual Spell]: This card is used to Ritual Summon "Saffira, Queen of Dragons". You must also Tribute monsters from your hand or field whose total Levels equal 6 or more. If a Ritual Monster(s) you control would be destroyed by battle or card effect while this card is in your Graveyard, you can banish this card instead.
- "Clear Wing Synchro Dragon" [WIND Dragon Lv7 Effect/Synchro 2500/2000]: 1 Tuner + 1+ non-Tuner monsters
Once per turn, when another Level 5 or higher monster activates its effect on the field (Quick Effect): You can negate the activation, and if you do, destroy it. Once per turn, when a monster effect is activated that targets 1 Level 5 or higher monster on the field (and no other cards) (Quick Effect): You can negate the activation, and if you do, destroy it. If this card's effect destroys a monster, this card gains ATK equal to the destroyed monster's original ATK until the end of this turn.
- "Castel, the Skyblaster Musketeer" [WIND Winged Beast Rank 4 Effect/Xyz 2000/1500]: 2 Level 4 monsters
You can detach 1 material from this card, then target 1 face-up monster on the field; change it to face-down Defense Position. You can detach 2 materials from this card, then target 1 other face-up card on the field; shuffle it into the Deck. You can only use 1 "Castel, the Skyblaster Musketeer" effect per turn, and only once that turn.
- "Preparation of Rites" [Spell]: Add 1 Level 7 or lower Ritual Monster from your Deck to your hand, then you can add 1 Ritual Spell from your GY to your hand.
- "Jinzo - Layered" [DARK Machine Rank 6 Effect/Xyz 2400/1500]: 2 Level 6 monsters
You can detach 1 material from this card, then target 1 face-up monster your opponent controls; take control of it until the End Phase, but it cannot activate its effects or declare an attack. If a Trap is on the field: You can Tribute 1 monster, and if you do, destroy 1 face-up card on the field. You can only use each effect of "Jinzo - Layered" once per turn.

## Answers
A) [1] yes
   reason given: Saffira's End Phase effect is available because a LIGHT monster was discarded this turn. I'll activate it and choose a mode at the next prompt.
B) [1] yes
   reason given: The opponent discarded Blue-Eyes Alternative, a LIGHT monster, from their hand while Saffira was face-up. That meets her End Phase condition, so I get a free extra activation on their turn.
C) [0] no
   reason given: Saffira, Queen of Dragons' End Phase effect needs either a Ritual Summon this turn or a LIGHT monster sent from hand/Deck to my GY this turn. Neither happened on the opponent's turn: she was summoned on my Turn 1, and the opponent's discard of Blue-Eyes Alternative was from their own hand. Activating now would waste her once-per-turn use, so I'll pass.
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

- **Blackbird Close** only negates effects activated by an opponent's monster on the field, not in hand/GY;
  it cannot stop Honest. It also needs a face-up Blackwing you can send to the GY as cost. Full Armor Master's
  immunity does not stop Honest boosting its attacker. Consider stopping a starter that enables a lock before
  it resolves, rather than saving Close for a response it cannot make (Tour Guide into Djinn Releaser).
  *(2026-10-22, tournament l1-r4-p1 vs Saffira)*
- Simoon or Vata used this turn → DARK-only Extra Deck. Sudri's Tribute effect → Synchro-only Extra Deck.
- Gofu and Simoon each need an empty board: decide which one starts.
- Black Whirlwind only triggers on **Normal** Summons, not Special Summons.
- Watch the 5 Main Monster Zones: Gofu tokens and extenders fill them fast.

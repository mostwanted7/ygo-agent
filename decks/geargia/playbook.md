## How to use this playbook

These are principles, not scripts: read the board, and when you see a better play, make it and say why in `why`.
Trust the engine's options over this text. Known pitfalls (at the bottom) are real mistakes from past games.

## Game plan

Rank 4 stun-beatdown. Each turn, turn a couple of Geargia or Gadgets into the bodies or Rank 4 Xyz the board needs,
keep traps Set behind them, and grind with monsters that replace themselves. Win by attacking every turn and with
sudden OTKs: Limiter Removal (one or two) on your Machines, finished with Gagaga Cowboy's burn.

## Card roles

- **Geargiarsenal**: Tribute it → a non-Arsenal Geargia from the Deck in Defense. No once-per-turn, so an Arsenal
  revived by Mk-II (not negated) can do it again. +200 ATK per face-up Geargia, itself included.
- **Geargiaccelerator**: summons itself from hand in Defense while you control a face-up Geargia (not Gear Gigant X
  or a Gadget). Sent from the field to the GY (destroyed, Limiter Removal) → add a Geargia from your GY. Not as Xyz
  Material, and it misses timing when sent as a cost.
- **Geargiarmor**: turns itself face-down once per turn; flipped face-up (attacked, Flip Summoned) → search a
  non-Armor Geargia. Face-down it is a 1900-DEF wall that replaces itself, but it can't be Xyz Material. On your turn,
  Flip Summon it (a search and an attacker) and turn it face-down again in Main Phase 2.
- **Geargiano Mk-II**: Normal or Flip Summon → a Geargia from hand or GY in Defense. **Geargiano**: Tribute it → a
  Lv4 Machine from your GY, negated. Both are Lv3 Geargia: the targets of Gear Gigant X's float.
- **Gold / Silver Gadget** (Lv4 Machines, not Geargia): Normal or Special Summoned → a Lv4 Machine from your hand,
  either position. Destroyed by battle or effect → the other Gadget from the Deck. Both effects share
  one use per turn: after its summon effect it doesn't float that turn.
- **Geargiagear** (Normal Trap, 1 per turn): two Geargiano-type monsters from the Deck at Lv4. Needs 2 still in the
  Deck and 2 free Monster Zones. It changes Levels, not ATK/DEF: Geargiano has 1000 DEF, Mk-II only 500.
  Check each body's actual stats before relying on them as blockers.
- **Gear Gigant X**: detach → a Lv4-or-lower Machine (a Gadget too) from Deck or GY (once per turn per copy). When it
  leaves the field face-up, its optional "When" effect can revive a Lv3-or-lower Geargia from your GY. Don't count
  on this after it is Tributed for a summon or sent as a cost: leaving the field is not the last event, so it misses timing.
- **Other Rank 4s.** Answers: Dark Rebellion (its materials have no other use: halve their best monster the turn
  you make it; both changes last), Castel, Number 101, Tornado Dragon, Photon Papilloperative, Ouroboros. Walls:
  Cairngorgon, Steelswarm Roach, Abyss Dweller, Shock Master (locks the declared type for BOTH players: never Trap
  while you rely on Solemns).
- **Traps**: Solemn Strike and Solemn Judgment for their starter or boss (neither answers a summon made inside a
  chain). Fiendish Chain and Forbidden Droplet need face-up **Effect** monsters: useless against Normal Blue-Eyes.
  Chain stops an attacker on their turn or a blocker on yours. Droplet also negates the chosen monsters' effects
  already on the chain. Imperial Iron Wall stops banishing for both players.

## Situational considerations

- **Gear Gigant X or not.** It turns two bodies into one 2300 body plus a search, and gives a body back only if a Lv3
  Geargia (Geargiano, Mk-II) is in your GY when it leaves. Consider it when one is there, or a free loop puts one
  there (Arsenal → Geargiano → Tribute Geargiano → Arsenal back), or when you need its search or its ATK. Without a
  float target, two bodies that replace themselves are often the better wall. When you can attack, attackers beat
  walls: run the lethal check first.
- **Gadget + Armor.** With a Gadget and Armor (or Arsenal, Tributed for Armor) in hand, consider ending on the Gadget
  and a face-down Armor: each replaces itself when removed (the Gadget floats, a flipped Armor searches), so you keep
  card advantage behind layered protection.
- **Free value first.** Use searches, Arsenal's Tribute and Mk-II's revive before you Xyz or Set.
- **Xyz for the job.** Make the Rank 4 the board needs: removal against a boss (Dark Rebellion, Castel, 101),
  Tornado against backrow, a wall going first, Gear Gigant X when its search or float matters. Use a new Xyz's effect
  before you end the turn if it improves the board.
- **Geargiagear** usually in the opponent's End Phase, so the two bodies survive into your turn as Xyz Material or
  Geargiano Tributes. Exceptions: their Battle Phase when you need blockers, in response to removal aimed at it, or
  your own turn when two Lv4s now win the game.
- **Searches.** Take what the next turn needs: Accelerator (an instant second Lv4), Mk-II (Normal Summon revives a
  Lv4), Armor (a wall).
- **Blockers.** With an empty field against attackers, Set a monster, even a hand trap, unless it must stop
  something specific next turn.

## Lethal check

Before "Go to the Battle Phase" and before ending your turn, count the most damage you can deal:
- Every attacker you can still have: Attack Position monsters, Xyz you can still make in Main Phase 1 (Gear Gigant X
  2300, Dark Rebellion 2500 plus what it takes), the Normal Summon on an Attack body (a Gadget adds a Lv4 from hand
  in Attack), a face-down Armor Flip Summoned (1100, and it searches), and monsters from earlier turns switched to
  Attack (neither needs a free Monster Zone). Self-summoned Accelerators come in Defense: materials, not attackers.
- **Limiter Removal** doubles the ATK every face-up Machine you control has when it resolves (Geargia, Gadgets, Gear
  Gigant X, Zenmaines; not Dark Rebellion, Castel or Gagaga). A second one doubles again (x4). It works in the Damage
  Step up to damage calculation. Every monster it doubled is destroyed in that End Phase (a Gadget whose effect is
  unused this turn floats), so play it for lethal or a battle you must win, after the summons it should boost.
- **Gagaga Cowboy** in **Defense Position**: detach → 800 damage (in Attack it only gains ATK). The finisher: in
  Main Phase 2, overlay two Lv4s that already attacked into it in Defense and burn: at 800 LP or less, any two Lv4s
  are lethal through any blockers. *(script-checked)*
- Nothing attacks directly until their last monster is destroyed, so each blocker costs one attack that surely
  destroys it (a face-down one's DEF is unknown: use a big attacker), unless Castel, Dark Rebellion, Droplet or
  Fiendish Chain removes it first. If the rest reaches their LP, make the summons and position changes in Main
  Phase 1, then attack: Special Summons and Xyz first, the Normal Summon last, on the best attacker a search gave you.
- The hidden 2300: a face-up Lv4 Geargia plus an Accelerator from hand make another Gear Gigant X, whose search
  adds the Normal Summon's attacker.

## Going second / breaking boards

- Harpie's Feather Duster first against two or more Set cards, before committing monsters.
- Against one big boss: Dark Rebellion (4000 into Blue-Eyes), Castel's shuffle, a Limiter Removal battle, or Number
  101 if it was Special Summoned.
- If you can't break through, build instead: a Rank 4 or Gadget + face-down Armor, traps Set, and grind.

## Known pitfalls (from reviewed games, newest first)

- **Negating a summon.** When Solemn Strike or Judgment is offered while an opponent's monster is being Special
  Summoned, the summon hasn't happened yet: that is the window to negate it. *(2026-10-21, r2-g2)*
- **Forbidden Droplet after an attack is declared.** If your monster already beats the halved attacker, pay the cost
  from the hand or the Spell/Trap Zone: a monster leaving your field replays the attack. *(2026-10-21, r2-g2)*
- **Forbidden Droplet facing a big attack.** Count every monster that can still attack you this turn (one in Defense
  can switch to Attack unless it was summoned this turn) against your blockers, and halve as many as you need to
  survive, usually the maximum: two cards left exact lethal on board. *(2026-10-21, r2-g1)*
- **Monsters that Tribute themselves to negate.** Stardust Dragon/Assault Mode negates one thing and returns only in
  the End Phase: feed it your least important activation, then make your real plays. *(2026-10-21, r1-g2)*

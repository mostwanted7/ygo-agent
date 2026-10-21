## Lessons from games (newest first; these override everything below)

### 2026-10-21 game r1-g2 (vs WindBot Dragunity, going second) — loss
1. **Use Dark Rebellion Xyz Dragon's effect the turn you Xyz Summon it, while the opponent's negater is in the GY if you can** (e.g. Stardust Dragon/Assault Mode after it Tributed itself). Halving a 2100 attacker makes Dark Rebellion 3550, which walls a 3000 boss. At 2500 it just dies to that boss.
2. **If your field is empty and they have attackers, Set any monster in hand as a blocker, even Ash Blossom (DEF 1800)**, unless you can name a specific search it will stop next turn. Holding Ash cost 5100 LP in one turn.
3. **Against Stardust Dragon/Assault Mode, or any monster that Tributes itself to negate, feed it your least important activation first.** It negates one thing and returns only in the End Phase, so make the real plays (removal, searches) while it is in the GY. Here it ate Maxx "C", Monster Reborn, Arsenal's Tribute and the Gear Gigant X float.

## Status of this playbook

Built from the card texts and scripts, then checked in lab rounds 1-2 and four games (r1-g1 win vs Blue-Eyes, r1-g2 loss vs Dragunity, r2-g1 loss vs Blue-Eyes, r2-g2 win vs Dragunity). Anything not marked *(verified ...)* is unverified: if the engine offers something different, trust its options.

## Game plan

Rank 4 stun/beatdown. Turn small Geargia combos into one Rank 4 Xyz, usually **Gear Gigant X**, behind Solemn Strike, Solemn Judgment, Fiendish Chain, Imperial Iron Wall and Geargiagear.
- **Ideal turn 1:** Gear Gigant X + 3-4 Set Traps, Ash Blossom / Maxx "C" in hand.
- **Grind:** a new Rank 4 each turn, Gear Gigant X searches, Accelerator / Gear Gigant X floats.
- **Close:** Limiter Removal, or Harpie's Feather Duster on their backrow.

## Engine cards

- **Geargiarsenal** (3): Tribute → non-Arsenal Geargia from Deck in Defense, no limit (script: no SetCountLimit). Targets: **Geargiano** (revives Arsenal), **Geargiarmor** (flips to search later), **Geargiaccelerator** (Lv4 body). Mk-II summoned this way does nothing. 200 ATK per face-up Geargia, itself included.
- **Geargiaccelerator** (3): summoning procedure from hand in Defense while you control a face-up Geargia (**Gear Gigant X is NOT a Geargia**). It doesn't chain, can't be negated as an effect, no limit: two in a row is fine. Its GY add triggers only when sent from the field (destroyed, Limiter Removal), NOT as Xyz Material/detached (script: `IsPreviousLocation(LOCATION_ONFIELD)`). It is an optional "when" trigger that can miss timing: **not offered** when sent as Forbidden Droplet's cost *(verified in game r2-g2)*. From your next turn on it can switch to Attack (1400).
- **Geargiarmor** (3): once per turn turns itself face-down; flipped face-up (Flip Summon, attacked, Photon Papilloperative) → add a non-Armor Geargia *(verified in game, also when attacked)*. Face-down it can't be Xyz Material: Flip Summon first (1100 attacker).
- **Geargiano Mk-II** (2, Lv3): only on Normal/Flip Summon → Geargia from hand or GY in Defense *(verified in game, reviving Arsenal/Armor)*. Prefer a GY target; Accelerator in hand summons itself anyway.
- **Geargiano** (2, Lv3): Tribute → Lv4 Machine from GY, negated. No limit; works at Lv4 via Geargiagear. Loop: Arsenal → Geargiano → Arsenal back, leaving Geargiano in GY for the float. The revived Arsenal is negated and can't Tribute again.
- **Geargiagear** (3): 2 Geargiano-type monsters from Deck, Lv4 on field. 1 per turn (script: oath limit); needs **2 Geargiano-type cards in Deck and 2 free zones**. Set turn 1, flip in their End Phase (or Battle Phase for blockers) *(verified in game)*.

## Support cards

- **Solemn Strike** (1500 LP): monster effect or Special Summon; spend on their starter or boss *(verified in game r2-g2, on a summon and on Crystal Wing's effect)*. **Solemn Judgment** (half LP): any Summon or Spell/Trap; spend on a wipe or a boss.
  - Neither answers a summon made inside a chain (script: `Duel.GetCurrentChain(true)==0`). Below ~3000 LP prefer Fiendish Chain / Droplet.
  - **Summon window:** a window right after "Opponent Special Summons X" that offers Solemn Strike but not your other Quick cards means the summon has NOT happened yet (script: `EVENT_SPSUMMON`). Negate the boss there; in r2-g2 the player passed on Crystal Wing thinking it had resolved.
- **Fiendish Chain:** face-up **Effect** monsters only (script: `IsType(TYPE_EFFECT)`), useless on Blue-Eyes White Dragon. Their turn: stop an attacker; your turn: chain to their boss before attacking.
- **Imperial Iron Wall:** stops banishing for BOTH players, including Ouroboros's GY mode. Activate in response to a banish.
- **Forbidden Droplet** (1 per turn): only if they control a face-up Effect monster; send up to N cards, N = their face-up Effect monsters (script: `TYPE_EFFECT` count). Negates the activation already on the chain *(verified in game r2-g1)*, works after an attack declaration *(verified in game r2-g2)*.
  - **Their turn, before attacks, send the maximum.** A weak Attack Position monster of yours (Mk-II 1000) is a good cost: Defense-only fields take no damage. In r2-g1, sending only 2 left Azure-Eyes at 2500 for exact lethal over Mk-II.
  - **After an attack declaration, if your monster beats the halved attacker, pay only with hand cards or Spells/Traps:** a monster leaving replays the attack. In r2-g2, sending Accelerator let a halved Crystal Wing switch from Gear Gigant X to Mk-II.
  - Good costs: dead hand cards, a spent Continuous Trap, a monster Limiter Removal will destroy.
- **Limiter Removal** (3): doubles your face-up Machines (Geargia, Gear Gigant X, Zenmaines; NOT Castel/Dark Rebellion), destroys them in the End Phase (triggers floats/adds). Only for lethal or a must-win battle; values in Going second.
- **Harpie's Feather Duster:** going second, before committing monsters *(verified in game r2-g2: 3 Set cards)*.
- **Monster Reborn:** their best monster or a Lv4 material. A revived Arsenal keeps its Tribute (Line 4).
- **Pot of Greed / Graceful Charity:** before the Normal Summon *(Charity → Harpie's verified in game)*. Charity: discard revivable Lv4 Geargia (Armor) before Traps.
- **Maxx "C":** chain to their first Spell/effect of the main phase *(verified in game r2-g1: 5 draws)*. **Ash:** Rank 3 material only if that wins.

## Extra Deck

- **Gear Gigant X** (2 Lv4 Machines), default. Once per turn per copy: detach → Lv4- Machine from Deck **or GY** (take from GY when possible). Order: Accelerator > Mk-II > Arsenal. Leaving the field face-up → revive a Lv3- Geargia, also when banished *(verified in game r1-g2)*: have Geargiano/Mk-II in the GY first.
- **3 Lv4s, spare body only:** **Number 16: Shock Master** locks the declared type for BOTH players (script: `SetTargetRange(1,1)`): declare Monster, never Trap while relying on Solemns. **Evilswarm Ouroboros**: bounce / random discard / GY banish, each once.
- **Removal:** **Castel** (1 mat: face-down; 2 mats: shuffle a face-up card; 1 per turn). **Dark Rebellion** (detach 2): any face-up monster; halves it and gains that, while both stay (script `RESETS_STANDARD`). **Number 101** (detach 2): attaches a Special Summoned Attack monster. **Tornado Dragon**: Quick Spell/Trap pop. **Photon Papilloperative**: Defense → Attack at -600, or flips your own face-down Armor to search.
- **Protection:** **Cairngorgon** redirects; **Steelswarm Roach** negates Lv5+ Special Summon; **Abyss Dweller** (Quick) stops GY effects, incl. Stardust/Assault Mode's return; **Gagaga Cowboy** burns 800.
- **Rank 3** (Mk-II + Geargiano at Lv3): **Wind-Up Zenmaines** (first destruction costs a material, then destroys a card that End Phase); **Break Sword** (destroy one of yours + one of theirs; its revive never works here).

## Main lines

**Rules:** Check the Deck still holds what you summon/search. Summon every Accelerator in hand while a Geargia is face-up. While holding Geargiagear keep 2 Geargiano-types in Deck (starts with 2 Geargiano + 2 Mk-II). Finish to the Xyz before Setting. **Never Xyz Gear Gigant X while a non-negated Arsenal could still loop for Geargiano.**

**Line 1: Arsenal + Accelerator** *(verified in lab)*
1. Normal Summon **Arsenal**, Special Summon **Accelerator**.
2. Tribute Arsenal → **Geargiano** (none left: **Armor**, go to step 4 with Accelerator + Armor).
3. Tribute Geargiano → revive Arsenal.
4. Xyz **Gear Gigant X**; detach Arsenal → **Accelerator** (already in hand: **Mk-II**).
5. Set Traps.
- **1R, + Monster Reborn** *(verified in lab)*: after step 4, Reborn Arsenal, summon Accelerator, Xyz Gear Gigant X #2, detach → **Arsenal from GY**.
- **1+, second Accelerator** *(verified in lab)*: summon both; loop **first**; Xyz with the 2 Accelerators, detach one → take it back, summon it, Xyz #2 with Arsenal + Accelerator, detach Arsenal → **Mk-II**.

**Line 2: Accelerator + Accelerator/Armor** *(verified in lab)*
1. Normal Summon the other Lv4 Geargia face-up, Special Summon Accelerator.
2. Xyz Gear Gigant X → Arsenal or Accelerator. Set Traps. A third Lv4: **Shock Master**, declare Monster.

**Line 3: Mk-II + a Lv4 Geargia**
1. Normal Summon **Mk-II** → Armor or Arsenal, from GY if there *(verified in game)*. Mk-II stays in Attack (1000), your weak point: use it as material or Droplet cost.
2. With **Accelerator**: summon it → Gear Gigant X *(verified in lab and game)*.
3. No Accelerator, Armor: Set Traps, Armor face-down; next turn Flip Summon → Accelerator → Rank 4 *(verified in game r1-g1)*.
4. No Accelerator, Arsenal *(unverified)*: Tribute Arsenal → Geargiano; Xyz **Wind-Up Zenmaines** with Mk-II + Geargiano; Set Traps.

**Line 4: lone Arsenal**
- **With Monster Reborn** *(verified in game r2-g1 up to the Xyz; loop script-checked, unverified)*:
  1. Normal Summon Arsenal → Tribute → **Accelerator**.
  2. **Monster Reborn** Arsenal (not negated).
  3. Tribute it → Geargiano → revive Arsenal. (Skipped in r2-g1: no float target, 5500 taken.)
  4. Xyz Gear Gigant X → Mk-II or Accelerator. Set Traps.
- **Without Reborn** *(verified in lab)*: Tribute Arsenal → **Armor**, turn it face-down, Set Traps; next turn Flip Summon → Accelerator → Rank 4. With another Lv4 Geargia for next turn, taking Accelerator is fine too, but face-down Armor blocks better (DEF 1900 vs 800).

**Line 5: Geargiagear (any line)** *(verified in lab and game)*
1. Set it; activate in their End Phase (Battle Phase for blockers).
2. Your turn: Gear Gigant X (or Castel/Dark Rebellion) → Accelerator.
3. Armor flip → Accelerator; two Accelerators → Gear Gigant X #2, detach an Accelerator and take it back. *(Reborn double Gear Gigant X verified in lab.)*

**No starter:** Pot/Charity first, Normal Set a Lv4 Geargia (Armor/Mk-II trigger on flip), Set every Trap. Going first, keep Harpie's in hand.

## Going second / breaking boards

1. **Harpie's Feather Duster first vs 2+ Set cards** *(verified in game r2-g2)*; otherwise bait Solemns with a small summon.
2. **Vs a Normal boss (Blue-Eyes):** Dark Rebellion (4000 vs 1500, *verified in lab*), Castel (also answers Call of the Haunted), Limiter Removal, Number 101, Ouroboros, Break Sword with a spare card of yours.
3. Make Gear Gigant X first when you need its search; search Accelerator while a Geargia is face-up.
4. **Lethal check before "Go to the Battle Phase":** add every Xyz still makeable (2300 each), the Normal Summon on an Attack body (Accelerator 1400, Armor 1100, Mk-II 1000), a Flip Summoned Armor (1100, searches), older Defense monsters switched to Attack. If it reaches their LP, do it all in Main Phase 1. In r2-g2 lethal was missed twice (2300+2300+1000+1400 = 7000 vs 7000; Armor/Accelerator left in Defense, opponent at 400).
5. **Limiter Removal:** Gear Gigant X 4600, Arsenal (3 Geargia) 4200, Mk-II 2000, Armor 2200. Activate after the attack declaration; in the Damage Step before damage calculation it is the only card offered and boosts the attack in progress *(verified in game r1-g1)*.
6. **Main phase ends with "Go to the Battle Phase", never "End your turn".** Summon attackers in Attack beforehand; Main Phase 2 is for Setting Traps and turning Armor face-down. Never Set Limiter Removal. Normal Summon Accelerator if it must attack. Check face-down DEF (Giant Soldier of Stone 2000: Gear Gigant X wins, Armor doesn't).
7. Can't break through: one Rank 4, Set Traps, grind.

**Line G1: Line 1 + Limiter Removal** *(Damage Step Limiter verified in game; vs Blue-Eyes unverified)*
1. Line 1 (or 1+ for two Gear Gigant X) with Gear Gigant X in Attack.
2. First Gear Gigant X attacks the face-down (2300 vs DEF 2000); the other attacks Blue-Eyes, Limiter in the Damage Step → 4600.
3. Main Phase 2: Set Traps. End Phase: each float needs its own Lv3 Geargia in the GY.

**Line G2: Armor/Accelerator + Accelerator vs a big Normal**
- **Dark Rebellion** *(verified in lab)*: Normal Summon Armor face-up, summon both Accelerators, Xyz Dark Rebellion, detach 2 → halve Blue-Eyes → attack (2500). Main Phase 2: Armor face-down.
- **Castel** *(unverified)*: Castel with Armor + Accelerator, detach 2 → shuffle the boss; Set Geargiagear + Fiendish Chain.

**Line G3: Mk-II + Accelerator + Armor, empty opposing board** *(verified in game r2-g2)*
1. Normal Summon Mk-II → Armor (GY or hand).
2. Accelerator; Gear Gigant X in Attack with Armor + Accelerator; detach → Accelerator → summon it.
3. Attack with Gear Gigant X + Mk-II.
4. Next turn, Main Phase 1: detach → Accelerator from GY → Gear Gigant X #2; again → **Normal Summon it in Attack**; attack with everything.

## Locks and once-per-turn rules to respect

- **Accelerator:** needs a face-up Geargia; no add as Xyz Material.
- **Geargiagear:** 1 per turn, Set a turn earlier, 2 Geargiano-types in Deck, 2 free zones.
- **Mk-II:** Normal/Flip Summon only.
- **Gear Gigant X:** one search per copy per turn; float needs a Lv3- Geargia in GY.
- **Shock Master** locks you too; **Iron Wall** blocks Ouroboros's banish; **Droplet** 1 per turn; **Castel** 1 effect per turn.

## General principles

- Set Traps every turn and keep a Solemn up for their boss.
- Leave a Geargiano or Mk-II in the GY before Gear Gigant X can leave the field.

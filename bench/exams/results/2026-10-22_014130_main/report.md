# Decision exam: main

40 positions graded by **opus** (blind) out of 40 asked (40 sampled; 0 excluded). Candidates: opus, sonnet, haiku. Each position is re-asked exactly as `ygo-agent replay` does: a fresh session with the duel history, today's playbook and rules. Generated 2026-10-22 01:57.

## Recommendation

**Standardise on opus** (confidence: medium; the self-preference flag is answered: the second judge (sonnet) also ranks opus 3.75 > sonnet 3.48 > haiku 3.25, the sign test vs sonnet is not below 0.05 (the interval excludes 0)).

- haiku scores below opus: -0.57 grade points (95% CI -1.02 to -0.17) over 40 positions.
- sonnet scores below opus: -0.42 grade points (95% CI -0.82 to -0.03) over 40 positions.
- opus: mean grade 3.73 of 4, mistakes or blunders in 5% of decisions, 9.9 s and $0.071 per exam decision; $1.15 per game in the benchmark.

## Leaderboard

Grades: best 4, good 3, acceptable 2, mistake 1, blunder 0. Intervals are 95% (bootstrap for the mean, Wilson for rates). "Agrees" = the judge would have played the same move.

| model | graded | mean grade | best | best/good | mistake+blunder | blunder | agrees | latency (mean / p95) | cost / decision | invalid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opus (claude-opus-5-5) | 40 | 3.73 (3.48–3.95) | 88% | 90% | 5% (1%–17%) | 0% | 90% | 9.9 / 17.8 s | $0.071 | 0 |
| sonnet (claude-sonnet-5-5) | 40 | 3.30 (2.92–3.65) | 72% | 75% | 15% (7%–29%) | 2% | 72% | 4.7 / 7.6 s | $0.031 | 0 |
| haiku (claude-haiku-5-5) | 40 | 3.15 (2.77–3.52) | 62% | 70% | 15% (7%–29%) | 2% | 65% | 7.5 / 16.1 s | $0.002 | 0 |

Latency includes the CLI start-up of a fresh session per position (in games, pre-warming hides it), and every exam decision is a turn's first message (the whole duel log), so cost per decision is higher than in a game.

## Paired comparisons

Every candidate answered the same positions, so the differences are per position (luck-free).

| A vs B | positions | mean grade A − B | A better | tie | B better | sign test p |
|---|---:|---:|---:|---:|---:|---:|
| opus vs sonnet | 40 | +0.42 (+0.03–+0.82) | 10 | 27 | 3 | 0.092 |
| opus vs haiku | 40 | +0.57 (+0.17–+1.02) | 12 | 26 | 2 | 0.013 |
| sonnet vs haiku | 40 | +0.15 (-0.30–+0.60) | 8 | 26 | 6 | 0.791 |

## By decision kind

Mean grade (mistake+blunder rate), n.

| | opus | sonnet | haiku |
|---|---:|---:|---:|
| battle | 4.00 (0%), 5 | 3.40 (20%), 5 | 3.40 (20%), 5 |
| chain | 3.38 (12%), 8 | 3.38 (12%), 8 | 3.75 (0%), 8 |
| effect_yn | 4.00 (0%), 4 | 3.25 (25%), 4 | 2.50 (50%), 4 |
| idle | 3.92 (0%), 12 | 3.25 (8%), 12 | 3.17 (8%), 12 |
| other | 3.33 (0%), 3 | 4.00 (0%), 3 | 3.33 (0%), 3 |
| select_card | 3.62 (12%), 8 | 3.00 (25%), 8 | 2.62 (25%), 8 |

## By deck

Mean grade (mistake+blunder rate), n.

| | opus | sonnet | haiku |
|---|---:|---:|---:|
| blackwing | 3.76 (5%), 21 | 3.05 (19%), 21 | 3.29 (14%), 21 |
| saffira | 3.68 (5%), 19 | 3.58 (11%), 19 | 3.00 (16%), 19 |

## Can the judge be trusted?

- **Self-preference.** The judge runs on opus, which is also the candidate opus. Graded best when its answer was the only one of its kind: opus 75% of 8, sonnet 12% of 8, haiku 10% of 10.
  - ⚠️ opus (the judge's own model) is graded best in 75% of the positions where its answer differs from every other candidate's, against at most 12% for the others. That gap may be real skill or self-preference: re-judge with another model (--judge sonnet on --resume) and compare.
- **Self-consistency.** 1 of 40 positions have a reply that contradicts itself (e.g. its own pick not graded best); e.g. p02: answer A is called equivalent to its own choice but graded good.
- **Probes.** The same move shown twice (with two candidates' different reasons) got the same grade 7/7 times, within one grade 7/7.
- **Confidence it reported:** high 24, low 1, medium 15.
- **Second judge sonnet** (40 positions): the same grade as opus 68%, within one 92%; mean grades opus 3.75, sonnet 3.48, haiku 3.25; paired: opus − sonnet +0.28 (+0.05–+0.53) (10–3, p 0.092); opus − haiku +0.50 (+0.25–+0.82) (12–1, p 0.003); sonnet − haiku +0.23 (-0.07–+0.55) (8–4, p 0.388).

## The most instructive disagreements

### p01: saffira idle (main1), turn 7

From `games/2026-10-21_211059_saffira-vs-mostwanted #31`. Main Phase: choose your next action. Reply with exactly one option index.

> **Judge** (high confidence): Opponent is at 2050 LP with no monsters and no Set cards. Fiendish Chain on Honest means it can't attack, so a plain Battle Phase only gets Geargiaccelerator's 1400 through. Overlaying Honest and the stolen Geargiaccelerator into Dark Rebellion (2500) gives a lethal direct attack. It also sends the Chain to the GY and keeps the stolen monster from going back to the opponent. That is the winning line. It would play [5] Special Summon "Dark Rebellion Xyz Dragon" from your Extra Deck (by its own summoning procedure).

- **opus: best** — [5] Special Summon "Dark Rebellion Xyz Dragon" from your Extra Deck (by its own summoning procedure)
  - its reason: "Fiendish Chain stops Honest from attacking, so I'll use it and the stolen Geargiaccelerator as material for Dark Rebellion Xyz Dragon. That gets rid of the Chain and puts the opponent's monster in their GY instead of letting it go back to them. A 2500 ATK direct attack is lethal against their 2050 LP, and they have no monsters and no Set cards."
  - judge: Finds the lethal: 2500 direct beats 2050, and it clears both the Chain and the stolen monster.
- **sonnet: best** — [5] Special Summon "Dark Rebellion Xyz Dragon" from your Extra Deck (by its own summoning procedure)
  - its reason: "Honest can't attack because of Fiendish Chain, and Geargiaccelerator alone deals only 1400. Xyz Summoning Dark Rebellion (2500 ATK) from Honest and Geargiaccelerator gives a fresh attacker that deals lethal against 2050 LP with no blockers."
  - judge (it graded this move once, shown with opus's reason): Finds the lethal: 2500 direct beats 2050, and it clears both the Chain and the stolen monster.
- **haiku: blunder** — [9] Go to the Battle Phase (attack available: your Attack Position monsters total 2500 ATK; opponent LP 2050; opponent has no monsters)
  - its reason: "The opponent has no monsters and 2050 LP. Honest (1100) and the Change of Heart-stolen Geargiaccelerator (1400) together deal 2500, which is lethal if unanswered. I'm keeping Ghost Ogre in hand as a hand trap, since it can destroy a card that activates in response."
  - judge: Misreads Fiendish Chain, which stops Honest from attacking. Only 1400 damage gets through, so a lethal turn is thrown away and Geargiaccelerator goes back to the opponent.

### p02: saffira idle (main1), turn 5

From `games/bench/2026-10-21_212557_readme/saffira--haiku--windbot-blue-eyes--003/2026-10-21_214659_saffira-vs-blue-eyes-ai #82`. Main Phase: choose your next action. Reply with exactly one option index.

> **Judge** (high confidence): The opponent is at 500 LP with one blocker, Blue-Eyes Alternative (3000). If Saffira attacks it with Honest still in hand, she goes to 5500 and deals 2500. That is lethal even if Return of the Dragon Lords in their GY saves the dragon. Going straight to battle is cleanest; switching Castel to Attack first is harmless. It would play [6] Go to the Battle Phase (attack available: your Attack Position monsters total 2500 ATK; opponent LP 500; opponent has 1 monster).

- **opus: good** — [4] Change the battle position of "Castel, the Skyblaster Musketeer" (face-up Defense, ATK 2000 / DEF 1500)
  - its reason: "The opponent is at 500 LP. Saffira attacks Blue-Eyes Alternative with Honest from hand (5500 vs 3000) for lethal. Switching Castel to Attack first gives me a second attacker for a direct hit if a trap stops the first line."
  - judge: It keeps Honest in hand, so the lethal is intact. Switching Castel adds little: it can't attack directly while Blue-Eyes is on the field.
- **haiku: good** — [4] Change the battle position of "Castel, the Skyblaster Musketeer" (face-up Defense, ATK 2000 / DEF 1500)
  - its reason: "Opponent is at 500 LP with one monster, Blue-Eyes Alternative White Dragon. Switching Castel to Attack Position gives me two attackers (Saffira 2500, Castel 2000), so one blocker can't stop 500 damage. If it blocks Saffira, Honest in hand can give her +3000 ATK in the Damage Step, and Castel's 2000 still hits for lethal."
  - judge (it graded this move once, shown with opus's reason): It keeps Honest in hand, so the lethal is intact. Switching Castel adds little: it can't attack directly while Blue-Eyes is on the field.
- **sonnet: blunder** — [1] Normal Summon "Honest" (from hand)
  - its reason: "Opponent is at 500 with one blocker, so I want three attackers: Honest, Castel switched to Attack, and Saffira. Only one can be blocked, so the others get through for lethal."
  - judge: It assumes extra attackers can go around the blocker, but no attack can be direct while the opponent has a monster. Summoning Honest also throws away its hand boost, which was the guaranteed lethal.

### p07: saffira battle (direct), turn 3

From `games/bench/2026-10-21_212557_readme/saffira--haiku--windbot-time-thief--003/2026-10-21_214920_saffira-vs-time-thief-ai #53`. Battle Phase: choose your next action. Reply with exactly one option index.

> **Judge** (high confidence): The opponent already tributed Chronocorder, so the next battle damage they would take is sent to you. Attacking first with Witch (100) uses up the redirect cheaply. Then 2500+2500+1400 = 6400 goes into 4000 LP, a 2400 margin. Leading with a Saffira sends 2500 back to you and leaves exactly 4000, so one stopped attack from the face-downs means no lethal. It would play [4] Attack with "Condemned Witch" (face-up Attack, ATK 100 / DEF 2000) (can attack directly).

- **opus: best** — [4] Attack with "Condemned Witch" (face-up Attack, ATK 100 / DEF 2000) (can attack directly)
  - its reason: "Chronocorder sends the damage from my next attack back to me, so I attack first with Condemned Witch (100 ATK) to use up that effect cheaply. After that, the two Saffiras and Manju deal 6400, and the opponent only has 4000 LP left. They have no monsters, so this is lethal."
  - judge: It correctly uses up Chronocorder's redirect with the 100-ATK Witch and keeps a 2400-damage margin for lethal.
- **sonnet: mistake** — [1] Attack with "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (can attack directly)
  - its reason: "The opponent has no monsters and 4000 LP. My attackers total 6500 ATK, so I attack with everything, starting with a Saffira."
  - judge (it graded this move once, shown with haiku's reason): It ignores Chronocorder: 2500 goes back to you and lethal becomes exactly 4000 with no margin, so the two face-down cards could stop it. The reasoning misreads the board.
- **haiku: mistake** — [1] Attack with "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (can attack directly)
  - its reason: "The opponent has no monsters, 0 cards in hand, and 4000 LP, while my four attackers total 6500 ATK of direct damage. I'm starting with a Saffira attack and will keep declaring the other attackers (Saffira, Manju, Witch) to finish the duel. I'm holding Forbidden Lance, since it's not needed for lethal."
  - judge: It ignores Chronocorder: 2500 goes back to you and lethal becomes exactly 4000 with no margin, so the two face-down cards could stop it. The reasoning misreads the board.

### p18: saffira effect_yn (optional), turn 2

From `games/native-smoke/2026-10-21_195052_saffira-vs-blue-eyes-ai #22`. Do you want to activate/use "Saffira, Queen of Dragons" (face-up Attack, ATK 2500 / DEF 2400) (your M1)? Reply [1] for yes or [0] for no.

> **Judge** (high confidence): Saffira's End Phase trigger fires when any LIGHT monster goes from hand or Deck to the GY while she is face-up. The script doesn't check whose card it was, so the opponent discarding Blue-Eyes Alternative to Trade-In counts. The effect is free and her once-per-turn use resets each turn, so activating gives free card advantage on the opponent's turn: draw 2 and discard 1, or randomly discard from their 6-card hand. Saying yes is clearly right. It would play [1] yes.

- **opus: best** — [1] yes
  - its reason: "The opponent discarded Blue-Eyes Alternative, a LIGHT monster, from their hand while Saffira was face-up. That meets her End Phase condition, so I get a free extra activation on their turn."
  - judge: Correct activation, and it names the right trigger: the opponent's LIGHT Blue-Eyes Alternative went from their hand to the GY while Saffira was face-up.
- **sonnet: best** — [1] yes
  - its reason: "Saffira's End Phase effect is available because a LIGHT monster was discarded this turn. I'll activate it and choose a mode at the next prompt."
  - judge (it graded this move once, shown with opus's reason): Correct activation, and it names the right trigger: the opponent's LIGHT Blue-Eyes Alternative went from their hand to the GY while Saffira was face-up.
- **haiku: mistake** — [0] no
  - its reason: "Saffira, Queen of Dragons' End Phase effect needs either a Ritual Summon this turn or a LIGHT monster sent from hand/Deck to my GY this turn. Neither happened on the opponent's turn: she was summoned on my Turn 1, and the opponent's discard of Blue-Eyes Alternative was from their own hand. Activating now would waste her once-per-turn use, so I'll pass."
  - judge: It misreads the condition. The LIGHT monster doesn't have to go to your own GY, and the once-per-turn use resets every turn, so declining throws away a free card-advantage effect.

### p37: blackwing effect_yn (optional), turn 2

From `games/bench/2026-10-21_212557_readme/blackwing--haiku--windbot-blue-eyes--002/2026-10-21_214202_blackwing-vs-blue-eyes-ai #32`. Do you want to activate/use "Blackwing - Harmattan the Dust" (face-up Attack, ATK 800 / DEF 800) (your M4)? Reply [1] for yes or [0] for no.

> **Judge** (high confidence): Gofu (Lv5 Blackwing Tuner) + Harmattan at Lv2 makes 7, so Blackwing Armor Master can still be Synchro Summoned this turn. If Harmattan copies Sudri, Gofu or Nothung, it becomes Lv6, 7 or 8. Gofu plus that is 11, 12 or 13, and nothing in the Extra Deck matches, so the Synchro option is gone. The boost gains nothing and costs that line. Declining is right. It would play [0] no.

- **opus: best** — [0] no
  - its reason: "I'm keeping Harmattan at Level 2 because Gofu (Level 5 Blackwing Tuner) plus Harmattan (2) makes exactly 7, which is Blackwing Armor Master. If Harmattan copied another Blackwing's Level, that total wouldn't work."
  - judge (it graded this move once, shown with sonnet's reason): Declining keeps Harmattan at Lv2, which keeps the Gofu + Harmattan Armor Master Synchro open. The move is right. The reason is wrong, though: a Synchro is still possible this turn.
- **sonnet: best** — [0] no
  - its reason: "Harmattan's level boost has no use now, because I'm not Synchro Summoning again this turn. I'll skip it and set up Twin Shadow and Blackbird Close."
  - judge: Declining keeps Harmattan at Lv2, which keeps the Gofu + Harmattan Armor Master Synchro open. The move is right. The reason is wrong, though: a Synchro is still possible this turn.
- **haiku: mistake** — [1] yes
  - its reason: "Harmattan's summon trigger is optional and costs nothing, so I'm using it. Its Level 2 can absorb a Blackwing's Level (Nothung 6 or Gofu 5) to reach a more useful Level for a later Synchro. The opponent's board is empty after Alternative White's destruction, so there is no reason to hold back."
  - judge: After the boost, Gofu + Harmattan totals 11 or more, which matches no Extra Deck monster. That throws away the Lv7 Armor Master Synchro. The 'more useful Level' argument is a misread.


## Whole-game reviews

A blind review of whole logged games (model names removed) that counts the significant mistakes. Like-for-like games are the same deal (deck, opponent, seed) for every candidate.

| model | games (like-for-like) | wins | mistakes / game | significant / game | blunders / game |
|---|---:|---:|---:|---:|---:|
| opus | 4 (4) | 4 | 0.2 | 0.2 | 0.0 |
| sonnet | 4 (4) | 3 | 1.5 | 1.0 | 0.2 |
| haiku | 4 (4) | 1 | 2.8 | 2.0 | 0.2 |

**opus, worst mistakes:**
- major, blackwing vs windbot:Time Thief (win), decision #14: Passed on Special Summoning Dark Armed Dragon at #14 and again at #17, while the GY held exactly 3 DARK monsters (Vata, Kris, Chinook). The player kept it 'for later', but the Synchros that followed sent Sudri, Sharnga and Harmattan to the GY. That left 6 DARKs there, so DAD could never be summoned again and stayed dead in hand. Better: Summon DAD before Synchroing. There was a free zone (Sudri M1, BWD M2, Sharnga M3), and it costs one more Maxx C draw. DAD gives a 2800 attacker plus repeatable destruction by banishing DARKs from the GY. On turn 3 that means 3200 + 3000 + 2800 = 9000 against 6600 LP, which is lethal, and its destruction effect would also have answered the opponent's turn-2 plays.

**sonnet, worst mistakes:**
- blunder, blackwing vs windbot:Blue-Eyes (loss), decision #21: With Sharnga in hand and Black-Winged Dragon (2800) on the field, the player set Delta Crow and ended the turn. Sharnga stayed in hand and the Synchro extension went unused. Better: Special Summon Sharnga (it was offered at #21 and #23 because a 2000+ ATK monster was out). Then Synchro Summon Boreastorm with Sharnga (Lv2 Tuner) + Sudri (Lv4) and send Harmattan or Chinook so it becomes Lv2. Boreastorm (Lv2 Blackwing Tuner) + BWD (Lv8) makes Full Armor Master, and banishing Boreastorm + BWD from the GY makes Black-Winged Assault Dragon. That board is FAM + Assault + Dark Armed Dragon. FAM is unaffected by Alternative White Dragon, and Assault would have burned each monster effect on turn 2 (Alternative, both White Stones and more) and reached a wipe. Instead BWD was destroyed for free and the opponent's whole turn-2 combo went through.
- major, blackwing vs windbot:Blue-Eyes (loss), decision #40: The player passed on Sharnga's once-per-duel GY destroy at #37, #39 and #40 while Boreastorm was on the field, then banished Boreastorm for Assault Dragon. Assault Dragon is not a 'Blackwing' Synchro, so Sharnga's effect could no longer be used. Better: Before summoning Assault Dragon, banish Sharnga to destroy Number 38 Titanic Galaxy (Sharnga is a monster effect, which its Spell negation can't stop). Titanic Galaxy later negated Enemy Controller and dealt the final 3000. The 'save it' reason didn't hold, because the next summon removed the Blackwing Synchro the effect needs.
- major, blackwing vs windbot:Blue-Eyes (loss), decision #51: The player Tributed Assault Dragon for the field wipe on turn 4. Azure-Eyes Silver Dragon had been Special Summoned in their own End Phase, so its protection ('cannot be destroyed by card effects until the end of the next turn') still covered Azure-Eyes and Titanic Galaxy. Only the two Spirit Dragons died, and the player was left with an empty board. Better: Hold the wipe. Soul Charge had already locked the opponent out of the Battle Phase on turn 4, so Assault Dragon was safe in battle. It would keep burning 700 per monster effect with the opponent at 4200, could attack on turn 5, and could wipe on turn 6 once Azure-Eyes' protection had expired and every Dragon could be destroyed.

**haiku, worst mistakes:**
- blunder, blackwing vs windbot:Blue-Eyes (loss), decision #6: Put both 0/0 Vague Shadow Tokens in face-up Attack Position (decisions #6 and #8). Better: Choose face-up Defense, which was offered both times. The tokens would have blocked for free. Instead, Titanic Galaxy and Blue-Eyes Spirit Dragon attacked them for 5500 damage, dropping the player to 1900 LP and making turn 4 lethal.
- major, saffira vs windbot:Time Thief (win), decision #99: Went straight to the Battle Phase and held Change of Heart, because it believed a monster taken with Change of Heart can't attack that turn. The opponent was at 4100 with Redoer (2400) and Chronocorder (1000). Better: Change of Heart has no attack restriction. Activate the Set Forbidden Lance first to draw out the revealed Time Thief Retrograde, which works only once per turn and only while they control a Time Thief Xyz. Then Change of Heart takes Redoer. Attacks: Saffira 2500 + Saffira 2500 + Redoer 2400. Any two of the three deal at least 4900, even if Chronocorder reflects one attack, and if Chronocorder stays to block, the line does 6400. That is lethal against 4100. Even without lethal, stealing Redoer and swinging was better than holding the card.
- major, saffira vs windbot:Blue-Eyes (loss), decision #33: Ended turn 3 without attacking, saying Saffira would lose to the 3000-ATK Blue-Eyes and Number 38, even though Honest was in hand and 'Go to the Battle Phase' was an option. Better: Attack with Saffira and send Honest from hand in the Damage Step. She becomes 5500 against a 3000-ATK monster. If Number 38 redirects the attack, it is also 3000, so either way she destroys a boss and deals 2500 damage (6000 to 3500). Nothing on their field could stop it: Number 38 negates only Spells, and Spirit Dragon negates only GY effects. Honest going from hand to GY would also turn on Saffira's End Phase effect, which gets Honest back. That is a 3000-ATK monster and 2500 LP for free, a turn earlier.

## Positions

| id | deck | kind | from | opus | sonnet | haiku |
|---|---|---|---|---|---|---|
| p01 | saffira | idle/main1 | 2026-10-21_211059_saffira-vs-mostwanted #31 | best | best | blunder |
| p02 | saffira | idle/main1 | saffira--haiku--windbot-blue-eyes--003 #82 | good | blunder | good |
| p03 | saffira | idle/main1 | saffira--haiku--windbot-time-thief--002 #26 | best | best | best |
| p04 | saffira | idle/main1 | saffira--opus--windbot-time-thief--001 #39 | best | best | best |
| p05 | saffira | idle/main1 | saffira--sonnet--windbot-blue-eyes--001 #55 | best | best | best |
| p06 | saffira | idle/main2 | 2026-10-21_195052_saffira-vs-blue-eyes-ai #58 | best | good | acceptable |
| p07 | saffira | battle/direct | saffira--haiku--windbot-time-thief--003 #53 | best | mistake | mistake |
| p08 | saffira | battle/attack-target | saffira--sonnet--windbot-blue-eyes--001 #39 | best | best | best |
| p09 | saffira | chain/own-turn | saffira--haiku--windbot-time-thief--003 #61 | best | best | best |
| p10 | saffira | chain/opp-activation | saffira--opus--windbot-blue-eyes--001 #23 | mistake | best | best |
| p11 | saffira | chain/own-turn | saffira--opus--windbot-blue-eyes--001 #48 | best | best | best |
| p12 | saffira | chain/opp-attack | saffira--sonnet--windbot-time-thief--003 #45 | best | best | best |
| p13 | saffira | select_card/search | saffira--haiku--windbot-blue-eyes--003 #55 | best | best | best |
| p14 | saffira | select_card/search | saffira--haiku--windbot-time-thief--001 #74 | best | best | acceptable |
| p15 | saffira | select_card/search | saffira--opus--windbot-time-thief--001 #27 | best | best | acceptable |
| p16 | saffira | select_card/cost | saffira--sonnet--windbot-blue-eyes--002 #35 | best | best | best |
| p17 | saffira | effect_yn/optional | saffira--haiku--windbot-blue-eyes--003 #46 | best | best | best |
| p18 | saffira | effect_yn/optional | 2026-10-21_195052_saffira-vs-blue-eyes-ai #22 | best | best | mistake |
| p19 | saffira | other/option | saffira--sonnet--windbot-time-thief--002 #41 | acceptable | best | acceptable |
| p20 | blackwing | idle/main1 | 2026-10-21_203748_blackwing-vs-saffira-sonnet #13 | best | acceptable | best |
| p21 | blackwing | idle/main1 | blackwing--haiku--windbot-blue-eyes--001 #13 | best | best | best |
| p22 | blackwing | idle/main1 | blackwing--haiku--windbot-blue-eyes--003 #27 | best | best | acceptable |
| p23 | blackwing | idle/main1 | blackwing--opus--windbot-blue-eyes--001 #37 | best | best | best |
| p24 | blackwing | idle/main1 | blackwing--opus--windbot-time-thief--001 #17 | best | acceptable | good |
| p25 | blackwing | idle/main1 | blackwing--sonnet--windbot-time-thief--003 #5 | best | best | best |
| p26 | blackwing | battle/attack-target | blackwing--haiku--windbot-time-thief--002 #50 | best | best | best |
| p27 | blackwing | battle/direct | blackwing--opus--windbot-blue-eyes--001 #51 | best | best | best |
| p28 | blackwing | battle/attack-target | blackwing--sonnet--windbot-blue-eyes--002 #46 | best | best | best |
| p29 | blackwing | chain/opp-activation | 2026-10-21_203748_blackwing-vs-saffira-sonnet #18 | acceptable | best | best |
| p30 | blackwing | chain/opp-activation | blackwing--haiku--windbot-time-thief--003 #45 | best | mistake | best |
| p31 | blackwing | chain/opp-activation | blackwing--haiku--windbot-time-thief--003 #72 | best | acceptable | acceptable |
| p32 | blackwing | chain/opp-activation | blackwing--opus--windbot-blue-eyes--001 #40 | best | best | best |
| p33 | blackwing | select_card/material | blackwing--haiku--windbot-time-thief--001 #16 | mistake | mistake | mistake |
| p34 | blackwing | select_card/material | blackwing--haiku--windbot-time-thief--002 #34 | best | mistake | mistake |
| p35 | blackwing | select_card/cost | blackwing--opus--windbot-time-thief--001 #23 | best | acceptable | good |
| p36 | blackwing | select_card/search | blackwing--sonnet--windbot-blue-eyes--001 #8 | best | best | best |
| p37 | blackwing | effect_yn/optional | blackwing--haiku--windbot-blue-eyes--002 #32 | best | best | mistake |
| p38 | blackwing | effect_yn/optional | blackwing--sonnet--windbot-time-thief--002 #89 | best | mistake | best |
| p39 | blackwing | other/option | blackwing--haiku--windbot-blue-eyes--003 #43 | best | best | best |
| p40 | blackwing | other/option | blackwing--sonnet--windbot-time-thief--002 #23 | best | best | best |

## Notes

- Prompt versions (sha256 prefixes): describe `9c6914ae08eb`, prompts `b2dbe996da5f`, general `d2abd3505f54`, saffira/playbook `472d46ae1130`, saffira/rules `06e05a624969`, blackwing/playbook `82473112a47b`, blackwing/rules `0877fe171b91`.
- Sampled with seed 1 from 1982 usable decisions in 35 logged games (haiku 13, opus 5, sonnet 17).
- A candidate's answer is graded once per distinct move: copies of the same card and the same cards in another order count as one move, so identical choices always get the same grade.

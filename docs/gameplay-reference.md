# Bards Hall gameplay reference

This reference lists the mod's current gameplay values. Times are simulation
seconds, so game speed changes their real-time length. Distances are Majesty
world units. Damage ranges below are before the defender's mitigation and
other active effects; `1dN` means a uniform roll from 1 through N.

## Bards Hall

| Completed level | Construction / upgrade price | Building HP | Shared hero capacity | Offerings |
| --- | ---: | ---: | ---: | --- |
| 1 | 800 | 300 | 4 | All three hero types; paid hiring |
| 2 | 2,500 | 500 | 6 | Ballad of Renown, Street Spectacle, Prize Duel |
| 3 | 3,500 | 700 | 8 | Epic Chronicles research |

All bard types cost **500 gold**. Capacity is shared across the three types.
Upgrade benefits become available when construction finishes. Each Hall has
175 sight range. Prices are base values before any applicable game modifiers.

### Epic Chronicles

Research costs **3,000 gold**, once per kingdom, at a completed level-3 Hall.
It grants **15% additional earned gold and experience** to that kingdom's
heroes while at least one owned, living, completed level-3 Hall exists.
Multiple Halls do not stack the bonus. Allied players' heroes do not receive it.

Losing the last qualifying Hall suspends the benefit without erasing the
research. Completing another level-3 Hall restores it without repurchasing.
An active Hall displays the Golden Chorus effect at its spire.

Gold transfers, refunds, withdrawals of stored gold, starting purses, building
revenue and treasury income are excluded. Direct level assignment and restored
levels are excluded from the experience bonus.

## Hero statistics

These are unmodified level-1 values. Attack, Parry, Dodge and Magic Resistance
are stock ratings, not independent guarantees or a single combined hit chance.

| Attribute | Troubadour | Spellsinger | Blade Dancer |
| --- | ---: | ---: | ---: |
| Starting HP | 14 | 11 | 16 |
| Strength | 1 | 3 | 9 |
| Vitality | 12 | 8 | 16 |
| Intelligence | 22 | 21 | 15 |
| Willpower | 20 | 10 | 14 |
| Artifice | 3 | 15 | 25 |
| Attack | 15 | 35 | 55 |
| Parry | 25 | 20 | 65 |
| Dodge | 40 | 30 | 55 |
| Magic Resistance | 15 | 20 | 0 |
| Base armor | 3 | 0 | 3 |
| Sight range | 220 | 260 | 200 |
| Primary attribute | Intelligence | Intelligence | Vitality |
| Movement timing | Ranger | Rogue | Rogue |
| Native Speed attribute | 3 | 3 | 3 |
| Attack range | Melee (1) | 200 | Melee (1) |
| Casting range | 250 | 200 | 75; Flourish remains melee |
| Recruitment time | 10 seconds | 7 seconds | 6 seconds |
| Base XP threshold | 900 | 1,157 | 800 |
| Low-HP retreat threshold | 35% | 35% | 25% |
| Loyalty | 95 | 5 | 30 |
| Greed | 1 | 5 | 12 |
| Luck | 15 | 19 | 16 |
| Weapon-upgrade decision chance | 10% | 85% | 100% |
| Armor-upgrade decision chance | 100% | 0% | 100% |
| Enemy assessment multiplier | 10.0 | 0.85 | 0.7 |
| Self assessment multiplier | 0.5 | 1.6 | 1.7 |

Upgrade chances apply when the corresponding ordinary shopping decision is
eligible, not as a purchase frequency. All three have zero autonomous
poison-weapon shopping chance. Spellsinger damage uses Intelligence and spell
resolution, rather than its physical Attack rating or Strength.
Assessment multipliers are inputs to the hero's danger evaluator, not flee
percentages. Singers and Dancers choose suitable hunting targets across the
map, favoring nearer opponents; champion calls retain priority. Their ordinary
enemy-hero hunts exclude civilians. Singers can kite; Troubadours and Dancers
use melee weapon positioning and do not kite.

### Growth and experience

The primary attribute rises by one at odd new levels, starting at level 3.
Stock leveling also increases melee Attack, Parry and Dodge by one while each
is below 98. HP gained per level is a random integer from `q + 1` through
`2q`, where `q = max(1, floor(current Vitality / 4))`. HP is awarded before
that level's primary-attribute increase.

| Level | Troubadour HP / INT | Spellsinger HP / INT | Blade Dancer HP / VIT |
| --- | --- | --- | --- |
| 1 | 14 / 22 | 11 / 21 | 16 / 16 |
| 5 | 30–38 / 24 | 23–27 / 23 | 36–48 / 18 |
| 8 | 42–56 / 25 | 32–39 / 24 | 51–72 / 19 |
| 10 | 50–68 / 26 | 38–47 / 25 | 62–90 / 20 |

These HP bounds assume ordinary leveling without other stat changes. Raw XP
awards enter Majesty's normal experience function: the award is divided by
the recipient's current level using integer division before entering the XP
bar. The threshold is the hero's base XP value above; level-up processing also
rescales leftover XP. Thus 250 raw XP is not necessarily 250 visible XP at a
higher level.

## Troubadour

Troubadours follow and support active heroes, with a preference for Spellsingers.
They cannot choose another Troubadour as their support target, and one hero
cannot be reserved by two ordinary Troubadour followers. They favor support
over personal combat, fighting for defense or suitable rewards and quests.

### Songs

| Ability | Hero level | Effect | Duration | Cooldown |
| --- | ---: | --- | ---: | ---: |
| **Ballad of Valor** | 1 | Nearby allied heroes gain melee and ranged accuracy, Parry, Dodge and Magic Resistance. | 8 seconds | 6 seconds |
| **Marching Song** | 3 | Nearby allied heroes move 15% faster and their primary action timing becomes approximately 10% faster. | 8 seconds | 6 seconds |
| **Cutting Satire** | 5 | Weakens an enemy's Strength and slows movement and primary actions by approximately 15%. | 6 seconds | 8 seconds |
| **Heroic Refrain** | 8 | Allied heroes deal 3 additional damage and take 3 less damage from combat hits. | 10 seconds | 30 seconds |

Friendly songs cover allied heroes within **180** of the caster, including
the Troubadour. They are timed buffs, so moving after casting does not remove
them. Different songs can overlap; copies of the same song do not add together.
Weaker Valor or Satire casts cannot overwrite or refresh a stronger active
effect. Equal-potency casts can refresh it; stronger casts replace its potency.

Valor's melee and ranged bonuses are **accuracy**, not damage. Intelligence
changes Valor and Satire as follows; March and Refrain retain their fixed values.

| Caster INT | Valor: melee/ranged accuracy, Parry and Dodge | Valor: Magic Resistance | Satire: Strength reduction |
| --- | ---: | ---: | ---: |
| 23 or less | +8 each | +10 | −5 |
| 24–25 | +9 each | +11 | −5 |
| 26–27 | +10 each | +12 | −6 |
| 28–29 | +11 each | +13 | −6 |
| 30 or more | +12 each | +14 | −7 |

Satire targets a hostile opponent near supported combat, with Strength above
5 and Magic Resistance below 100, and respects spell resistance and Magic
Mirror. Stock action-period rounding affects its slow and March's action
bonus; March's movement bonus uses continuous 15% movement scaling.

Refrain's outgoing bonus follows the affected hero through normal weapon,
direct spell and caster-attributed delayed spell damage. Its incoming
reduction applies to combat hits and cannot reduce damage below zero; periodic
poison and other periodic environmental damage are excluded. Stock physical
critical effects retain their separate resolution rather than receiving the
ordinary damage modifiers.

Combat songs require a relevant fight, including an engaged followed hero.
March may also be used during travel and on the Troubadour alone. Refrain has
priority when ready; other eligible songs are chosen by how long they have
been waiting. Completed songs have at least two seconds between them.
The caster prioritizes buffs while positioning for enemy spells without
leaving its followed hero outside song range.

### Support experience

An active Troubadour follower within **360** receives **50% of its leader's
raw combat and exploration XP**, rounded down, without taking XP away from
the leader. The Troubadour's own level divisor then applies. Quest payouts and
another bard's song rewards are not shared. The follower must be alive,
outside and unfrozen; catching up during support travel remains eligible.

Completed useful casts also grant raw XP once per cast, independent of how
many recipients were affected: Valor **25**, March **75**, Satire **125**,
Refrain **200**. These awards also use normal level-based XP scaling.

### Ballad of Renown — completed Hall level 2

Supported victories create earnings which are collected when the Troubadour
visits a friendly owned, completed level-2-or-higher Hall.

| Supported event | Gold | Raw XP |
| --- | ---: | ---: |
| Attack bounty of any positive value | 25 | 75 |
| Lair destroyed | 50 | 150 |
| Monster defeated or successfully captured for the Zoo, with threat at least the Troubadour's level or threat 6+ | 75 | 250 |

Only the highest qualifying reward applies to one event. Each qualifying
Troubadour receives its own award after actual recorded support and must be
within **300** of the target at completion. At **300 pending gold**, the hero
seeks a turn-in during a peaceful decision rather than interrupting an active
hire, accepted quest or the leader's combat.

Monster threat ranks 1–8 use LevelXP boundaries of 230, 400, 500, 900, 1,500,
2,000 and 3,500, with values above 3,500 belonging to rank 8.

## Spellsinger

Spellsingers fight with ranged magical attacks, explore, buy equipment and
perform for town audiences. Their basic combat is Arcane Note; passive echoes
and shared enemy Resonance create increasing pressure before Burst releases it.

| Ability / effect | Hero level | Mechanics | Duration / cooldown |
| --- | ---: | --- | --- |
| **Arcane Note** | 1 | Magical projectile: `1d10 + floor(INT/4) + weapon quality + enchantment + existing Resonance stacks`. | 1-second spell cooldown |
| **Reverberation** | 3 | A damaging Note can echo to one other hostile target within 80 of impact. Echo damage is `1d10 + floor(INT/4)`. | At most once per 6 seconds |
| **Resonance** | 3 | Positive Note and echo hits add one shared stack to the enemy, up to 6. Existing stacks add +1 damage each to subsequent primary Notes. | 10 seconds after the latest stack-building hit |
| **Countermelody** | 5 | One enemy loses 20 melee and ranged accuracy and cannot use eligible special casts; ordinary attacks remain available. | 8 seconds; 45-second cooldown |
| **Resonant Burst** | 8 | Damages enemies within 70 of its target: `1d(15 + hero level) + floor(INT/4)`. A single enemy is sufficient. | 12-second cooldown |
| **Crescendo** | 8 | A damaging Burst consumes the victim's Resonance and stuns it for half a second per consumed stack. | 0.5–3 seconds |

Resonance belongs to the **enemy**, not the Singer. Multiple Singers build the
same six-stack pool and any Singer's Burst can consume it. At the cap, another
positive stack-building hit refreshes expiry. New stacks can build immediately
after Burst. Burst can damage buildings, but buildings and lairs are not stunned.

At starting INT 21, an unmodified Note or echo rolls **6–15 damage**. Fully
upgraded and enchanted equipment adds +6 to the primary Note; six Resonance
stacks add another +6. Those bonuses do not affect echoes or Burst. At level 8
with ordinary INT growth to 24, Burst rolls **7–29** before other effects.
Echoes do not bounce again and require a second target to deal extra damage.

Notes, echoes and Burst use normal spell-hit and Magic Resistance resolution.
Heroic Refrain adds +3 to all three; Roused adds +2 to the primary Note only.
Countermelody targets hostile heroes or monsters with more than 5 HP, below
100 Magic Resistance, without Magic Mirror or an existing Countermelody.
It suppresses supported special casts, not basic projectiles, ordinary weapon
attacks, items, potions or player powers.

### Street Spectacle — completed Hall level 2

An eligible Singer already near town has a **40%** chance to choose a
performance before ordinary hunting or exploration. It needs a completed,
owned Palace, Marketplace or Bards Hall within **180**, and no enemy in sight.
Urgent duties, recuperation, shopping and current hires take priority.

The show lasts **20 seconds**, with **60 seconds** between show starts.
Listeners must remain within **100** for **3 continuous seconds**:

| Listener | Tip | Raw XP for the Singer |
| --- | ---: | ---: |
| Another owned non-bard hero, carrying at least 53 gold | 3 gold from that hero, leaving at least 50 | 5 |
| An owned peasant | 1 gold of performance income | 5 |

A show accepts at most **10 listeners** and **30 gold**. Each listener has a
60-second tip cooldown. Leaving before the listening period finishes cancels
that attempt. Bards, tax collectors and caravans do not count as listeners.

## Blade Dancer

Blade Dancers hunt, undertake quests, explore when appropriate and compete
in town. Their saber and dagger are resolved as one weapon attack, with one
hit check and one application of armor and equipment bonuses.

| Ability / effect | Hero level | Mechanics | Duration / cooldown |
| --- | ---: | --- | --- |
| **Duelist Training** | 1 | The Dancer's starting Parry 65 and Dodge 55 provide her defensive training. | Passive; already included in base stats |
| **Riposte** | 3 | A successful parry against a hostile melee attacker triggers one normal counterattack, which can itself miss or be defended. | At most once per 4 seconds |
| **Deflect** | 5 | Negates an eligible missile or direct magical attack before normal Dodge or spell-resistance avoidance. | 8-second shared cooldown |
| **Dueling Flourish** | 8 | Every third successful hit against the same enemy gains +3 damage and halves its armor value for that hit. Uses the cast animation instead of the ordinary attack. | Hit chain; no time limit |
| **Rousing Finale** | 8 | Personally defeating a prepared target queues a celebratory cast, granting herself Encore and nearby allied heroes Roused. | Triggered after the killing attack completes |
| **Encore** | 8 | Banks one charge. Her next actual attack attempt against a monster or enemy hero consumes it and prepares that target for Finale immediately. | Remains until consumed |
| **Roused** | 8 | Allied heroes gain +5 Parry and Dodge, +2 ordinary weapon / primary Arcane Note damage, and greater resistance to fear-driven flight. | 120 seconds |

Deflect excludes melee, siege projectiles and ongoing area/periodic damage;
direct magical protection applies at supported spell impact callbacks.
Riposte and Deflect show their reaction effects without interrupting the
current action for an extra cast.

Flourish counts successful hits, not swings. Missing the same enemy preserves
the count; attacking a different target resets it. A Flourish prepares a
monster of **any threat rank** for Finale. A star above the enemy identifies
preparation. A later personal killing hit can trigger Finale; the Flourish
itself does not have to kill. Encore can also prepare an enemy hero.

Encore is consumed on an actual attack attempt even if it misses, not when
choosing or travelling toward a target. Buildings and Prize Duels do not
consume it. Switching targets discards the previous preparation. Each new
Finale restores Encore, allowing a chain of victories.

Finale's Roused effect covers allied heroes within **180**, including the
Dancer. It does not stack, but another application refreshes its duration.
When ordinary fear evaluation would cause retreat, Roused gives a **25% chance
to resist that decision**, except when low HP requires retreat. It does not
remove the low-HP safety behavior. A frozen or low-HP Dancer postpones her
queued Finale cast until able to perform it.

### Weapon damage

An ordinary hit rolls:

`1d12 + 1d8 + floor(Strength / 8) + quality bonus + enchantment bonus`

At starting Strength 9, this is **3–21 damage**, averaging **12**, before
armor and buffs. Maximum quality and enchantment add +6 once to the combined
attack, giving **9–27**. Flourish adds +3 once. Strength remains low while the
second weapon supplies the additional roll. Stock critical-effect resolution
is separate from these ordinary damage rolls.

### Prize Duel — completed Hall level 2

Near an eligible friendly completed venue, the Dancer has a **25%** chance
to choose a Prize Duel after champion calls and before ordinary hunting.
The venue must be within **180**: a qualifying combat guild, Adventurers
Guild, Fairgrounds or Embassy. An actual opponent visitor is not required.

The visit lasts **15 seconds**. Winning has a **65% chance** and grants
**100 gold** of generated prize income, without deducting another hero's purse,
building coffers or the treasury. Losing grants **250 raw XP** of practice.
This activity is not a real combat attack and does not trigger combat skills.

## Equipment and potions

Troubadours and Spellsingers use **Instrument** equipment; Blade Dancers use
**Dual Wield**. Each quality tier uses the corresponding ordinary Blacksmith
weapon research. Quality and Wizard Guild enchantment are independent.

| Quality rank | Weapon bonus | Purchase price | Troubadour | Spellsinger | Blade Dancer |
| --- | ---: | ---: | --- | --- | --- |
| 0 | +0 | Starting equipment | Travel Lute | Resonance Fork | Saber & Dagger |
| 1 | +1 | 100 | Fine Lute | Silver Resonator | Balanced Blades |
| 2 | +2 | 200 | Concert Lute | Crystal Resonator | Duelist's Pair |
| 3 | +3 | 300 | Masterwork Lute | Harmonic Conductor | Masterwork Blades |

| Enchantment | Additional weapon bonus | Purchase price | Required Wizard Guild level |
| --- | ---: | ---: | ---: |
| None | +0 | — | — |
| +1 | +1 | 200 | 1 |
| +2 | +2 | 400 | 2 |
| +3 | +3 | 800 | 3 |

Prices are the configured purchase price for that rank. A Troubadour's ordinary
weapon rolls `1d4 + floor(STR/8)` before equipment and buffs; instrument
upgrades do not amplify songs. The Singer's displayed weapon base is 4, but
its actual Arcane Note damage follows the spell formula above. Instrument
quality and enchantment improve the primary Note, not echoes or Burst.

Troubadours and Dancers wear stock **Leather**, with normal armor upgrades and
enchanting. Spellsingers are **unarmored** and exclude weapon coatings,
including poison and oil. Physical weapon interactions remain available where
supported by the game's equipment services.

| Bazaar potion | Troubadour | Spellsinger | Blade Dancer |
| --- | --- | --- | --- |
| Speed, Regeneration, Invisibility | Enabled | Enabled | Enabled |
| Strength | Disabled | Disabled | Enabled |
| Fire Balm | Disabled | Disabled | Disabled |
| Shapeshift | Medusa | Medusa | Minotaur |

## Paid hiring

An eligible non-bard hero can hire an existing bard for **200 gold**:
**100 to the Hall and 100 to the bard**. The patron needs at least **250 gold**,
retaining 50 after payment. The contract lasts **120 simulation seconds**,
about **two game days**. All three bard types can accompany a patron.

Hiring requires an owned, completed Hall with hiring open, an available living
member and a healthy patron without another bard contract. The patron considers
hiring at most once per **30 seconds**, with a **25%** selection chance at an
eligible decision. The recruitment subpanel's **Hiring: Open / Closed** toggle
controls new contracts without cancelling existing ones.

Available bards may be peacefully deciding, wandering, exploring or travelling
with a support target. Combat, fleeing, shopping, performances, accepted quests
and existing hires take precedence. A member resting inside its own Hall must
be fully healed before leaving for a hire. This is not a general requirement
that outdoor bards be stationary or at full health.

| Patron | Preferred bard |
| --- | --- |
| Wizard, Priestess, Healer | Blade Dancer |
| Ranged heroes, including Ranger, Elf and Rogue | Spellsinger |
| Other eligible heroes | Troubadour |

These are preferences, not exclusive matches. Nearby or home members are
preferred over distant available members. A hired bard follows its patron;
if the patron enters a building, it can travel there and wait. The action text
identifies this as **Supporting as a hired hand**.

## Source of values

Hero attributes come from [hero_profiles.json](../src/hero_profiles.json).
Ability descriptions and combat formulas are assembled by
[bards_abilities.py](../src/bards_abilities.py), with behavior in the
[GPL source](../src/gpl). Equipment tiers are defined in
[equipment_content.json](../src/equipment_content.json), and kingdom research
in [epic_chronicles_content.json](../src/epic_chronicles_content.json).
For resource identities, integration and packaging, see
[technical details](technical-details.md).

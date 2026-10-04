# Bards Hall technical details

For complete hero stats, growth, spells, skills, effects, damage formulas,
equipment progression and economy rules, see the
**[gameplay reference](gameplay-reference.md)**. This page covers resource
identities and implementation integration.

Bards Hall is a Manager-dependent Majesty Gold HD mod. It contains private
building and hero descriptions, GPL behavior, CAM resources and typed Manager
feature declarations. The Manager supplies native integration that ordinary
Workshop resource replacement cannot provide, including the custom recruitment
controller, equipment, shared activities and kingdom research.

## Identity and construction

| Resource | Identity |
| --- | --- |
| Mod GUID | `{e277a34f-bfb6-54ec-bfec-565d735edc37}` |
| Package namespace | `CustomGuildBards` |
| Building family | `Bards_Hall`, descriptions `Bards_Hall1/2/3` |
| Building IDs | `BDG1`, `BDG2`, `BDG3` |
| Troubadour | `BDT1` |
| Spellsinger | `BDS1` |
| Blade Dancer | `BDD1` |
| Authored primary/recruitment panels | `CGBD`, `BDRC` |

Stock construction and upgrade completion own building state. Completed levels
provide 4/6/8 shared recruit places; beginning an upgrade does not grant the
next tier's capacity. Recruitment costs 500 gold for every bard type.

## Hero behavior

Each hero has explicit native and GPL attributes in `src/hero_profiles.json`,
private decision trees, and private danger evaluators. Common movement, task
arrival, shopping, retreat and action completion retain stock lifecycles.
Source-class activities such as Rogue theft and Cultist resource planting are
not inherited.

Troubadours prioritize following active heroes and prefer Spellsingers when
suitable. Ordinary support cannot target another Troubadour or reserve a hero
already supported by another Troubadour. Nearby active support earns half the
leader's combat and exploration XP without reducing the leader's reward.
Quest payouts are not included in that support XP.

Spellsingers and Blade Dancers use stock-derived hunting with nearest viable
selection. Native queries remain mapwide, stock assessment gates suitability,
champion calls retain priority, and ordinary enemy-hero hunts exclude civilian
subtypes. A Troubadour retains its support/defense role rather than ordinary
autonomous hunting.

Troubadours start with 14 HP and Vitality 12. Troubadour movement uses Ranger
timing; Singer and Dancer movement uses Rogue timing. Blade Dancers roll primary
and secondary weapon damage within one attack, retaining one hit resolution.

## Songs and combat

| Hero | Level | Ability |
| --- | --- | --- |
| Troubadour | 1 / 3 / 5 / 8 | Valor / March / Satire / Heroic Refrain |
| Spellsinger | 1 | Arcane Note |
| Spellsinger | 3 | Reverberation and shared Resonance |
| Spellsinger | 5 | Countermelody |
| Spellsinger | 8 | Resonant Burst and Crescendo |
| Blade Dancer | 1 / 3 / 5 | Duelist Training / Riposte / Deflect |
| Blade Dancer | 8 | Dueling Flourish, Rousing Finale and Encore |

Songs use normal cast actions and timed effectors. Stronger song potency cannot
be overwritten or prolonged by weaker casts. March uses the Manager's overlay
movement scaling to represent a consistent 15% movement bonus.

Heroic Refrain reduces incoming combat-hit damage and adds outgoing damage for
affected heroes, including attributed delayed spell effects. Periodic poison
damage is excluded from its incoming reduction. Outgoing caster attribution
must resolve to an actual hero; player ownership alone does not qualify.

Arcane Notes and echoes build per-enemy Resonance shared by all Spellsingers,
capped at six stacks. Further notes benefit from those stacks. Resonant Burst
consumes them to apply Crescendo's stun. Countermelody reduces accuracy and
suppresses eligible special spellcasting while retaining basic attack fallback.

Riposte reacts to parrying. Deflect precedes normal avoidance and blocks eligible
missiles/direct magical attacks. Every third successful same-enemy hit becomes
a Flourish cast. A qualifying killing blow queues the normal Finale cast after
the attack finishes, inspiring nearby allies with Roused and banking Encore.
Encore is consumed on the next eligible attack attempt against a monster or
enemy hero; attacking a building or performing a Prize Duel does not consume it.

## Economy and shared services

Completed level 2 unlocks Ballad of Renown, Street Spectacle and Prize Duel.
Renown records supported victories and settles earnings at home. Street
Spectacle uses timed outdoor performance and passing listeners. Prize Duel has
a 65% win chance; victory earns gold and losing earns practice XP.

Economy jobs are opportunistic near town. Eligible Street Spectacle selection
has a 40% chance before ordinary hunts/exploration. Prize Duel selection has a
25% chance after champion calls and before ordinary hunts, querying eligible
venues within 180 units. Neither job sends a hero back from the wilds to seek
work; urgent duties and purchasing retain priority.

Hiring lasts about two game days and costs 200 gold, split 100 to the Hall and
100 to the hired bard, with a 50-gold patron reserve. A recruitment-panel toggle
controls new hiring. Saved contracts, cancellation and inside-building patron
travel use the Manager's shared activity contract.

Epic Chronicles is one-time 3000-gold research at completed level 3. Its 15%
earned gold/XP bonus applies to the owner's heroes while at least one completed
level-3 Hall survives. Research knowledge persists through loss of the halls;
rebuilding to completed level 3 restores the bonus without another payment.

Custom equipment follows normal shops and enchanting. Troubadour and Dancer
use stock leather; Singer is unarmored and excludes weapon coatings. Typed
Bazaar potion policy assigns custom heroes appropriate native potion behavior.

## Packaging and validation

`src/build_bards_hall.py` compiles the owned GPL and creates the resource package.
`src/validate_bards_hall.py` checks its inventories, private identities, stock
clones, media authority and Manager declarations. These are source/package
checks, separate from native gameplay testing.

The Manager requires the manifest's GPL/DAT inputs to prepare compatible
profiles. Workshop content therefore includes those inputs, the referenced game
resources, `mod-definition.json` and launcher instructions. Review galleries,
compiler projects and media source masters are excluded from that content.

Public GitHub source excludes all media, packaged CAM/BCD files, internal notes,
diagnostic captures and Workshop upload metadata. The current typed declarations
are published in `mod-definition.json`; player installation is in the README.

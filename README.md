# Custom Guild: Bards Hall

Bring music, magic and daring swordplay to your Majesty Gold HD kingdom with a
three-level Bards Hall and three distinct heroes.

## The bards

| Hero | Role |
| --- | --- |
| **Troubadour** | Follows fellow heroes, inspiring them with protective songs, quickening their travel and weakening their enemies. Shares experience from their adventures. |
| **Spellsinger** | A ranged caster whose musical attacks build Resonance, disrupt enemies and unleash a stunning Crescendo. |
| **Blade Dancer** | A saber-and-dagger duelist with parries, ripostes and dramatic finishing moves that inspire nearby allies. |

Each hero learns new abilities as they level up. The mod includes custom
building and hero artwork, portraits, spell effects and voiced reactions.

### Abilities

| Hero | Level | Spells and skills |
| --- | ---: | --- |
| Troubadour | 1 | **Ballad of Valor:** improves allied accuracy, Parry, Dodge and Magic Resistance. |
| Troubadour | 3 | **Marching Song:** increases movement speed and quickens actions. |
| Troubadour | 5 | **Cutting Satire:** weakens and slows an enemy. |
| Troubadour | 8 | **Heroic Refrain:** adds 3 outgoing damage and reduces incoming combat-hit damage by 3. |
| Spellsinger | 1 | **Arcane Note:** an Intelligence-based magical projectile, improved by instrument upgrades. |
| Spellsinger | 3 | **Reverberation / Resonance:** notes echo to a second enemy and build shared stacks that increase subsequent Note damage. |
| Spellsinger | 5 | **Countermelody:** reduces enemy accuracy and suppresses special casting. |
| Spellsinger | 8 | **Resonant Burst / Crescendo:** area damage consumes Resonance to stun enemies. |
| Blade Dancer | 1 | **Duelist Training:** high starting Parry and Dodge. |
| Blade Dancer | 3 | **Riposte:** counterattacks after a successful melee parry. |
| Blade Dancer | 5 | **Deflect:** blocks an eligible missile or direct spell attack. |
| Blade Dancer | 8 | **Dueling Flourish:** every third successful same-enemy hit deals extra damage through reduced armor. **Rousing Finale** inspires allies after a prepared kill; **Encore** prepares the next opponent, and **Roused** improves allied offense, defense and bravery. |

### Starting stats

| Hero | HP | STR | VIT | INT | WILL | Artifice | Attack | Parry | Dodge | Magic Resistance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Troubadour | 14 | 1 | 12 | 22 | 20 | 3 | 15 | 25 | 40 | 15 |
| Spellsinger | 11 | 3 | 8 | 21 | 10 | 15 | 35 | 20 | 30 | 20 |
| Blade Dancer | 16 | 9 | 16 | 15 | 14 | 25 | 55 | 65 | 55 | 0 |

See the **[complete gameplay reference](docs/gameplay-reference.md)** for every
spell and effect, durations and cooldowns, Intelligence scaling, damage formulas,
level growth, equipment tiers and prices, income rewards, and hiring requirements.

## Hall progression

All three bard types cost **500 gold** and are available from level 1.

| Hall level | Shared recruit places | New offerings |
| --- | --- | --- |
| 1 | 4 | All three heroes and bard hiring |
| 2 | 6 | Ballad of Renown, Street Spectacle and Prize Duel |
| 3 | 8 | Epic Chronicles research |

- **Ballad of Renown:** Troubadours earn gold and experience by supporting
  their companions' victories.
- **Street Spectacle:** Spellsingers perform in town for tips and experience.
- **Prize Duel:** Blade Dancers visit friendly venues to compete for cash
  prizes and gain practice experience.

**Epic Chronicles** costs **3,000 gold** and gives your kingdom's heroes
**15% more earned gold and experience** while a completed level-3 Bards Hall
survives. Once researched, rebuilding a lost hall to level 3 restores the bonus
without another payment.

## Hiring and equipment

Heroes can hire a bard to accompany them for about **two game days**, paying
**200 gold** split between the hall and bard. Hiring can be opened or closed
from the recruitment panel.

Troubadours and Spellsingers use **Instruments**; Blade Dancers use **Dual Wield**
weapons. Their equipment can be upgraded and enchanted through the kingdom's
ordinary shops.

## Installation

Requires [Majesty Mod Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=3793024054).

1. Make the package available in the Manager's local Mods or Workshop catalog.
2. Select **Custom Guild: Bards Hall**, along with your other compatible mods.
3. Choose **Prepare Selected Mods**.
4. Use **Launch Majesty** inside the Manager.

The recruitment interface, equipment and shared systems depend on the Manager
runtime. Launching the raw package through Majesty's ordinary mod selector does
not supply those features.

Supports Original Majesty and Northern Expansion content.

## Voice credits

- **Troubadour:** [Teatarouva (@serrizawa)](https://www.fiverr.com/serrizawa/be-a-voice-in-your-project)
- **Spellsinger:** [Jake (@jakewn)](https://www.fiverr.com/jakewn)
- **Blade Dancer:** [Char C (@chardoesva)](https://www.fiverr.com/chardoesva/be-your-female-character-voice-actor)

## Source repository

The public repository contains gameplay and build source, text configuration,
tests and [technical details](docs/technical-details.md). Artwork, audio and
development media remain private. The playable package is distributed through
Workshop; see [building from source](docs/building-from-source.md) for build
requirements.

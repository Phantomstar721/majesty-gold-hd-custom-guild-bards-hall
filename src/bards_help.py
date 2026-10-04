"""Player-facing help for each guild stage and each private hero."""

HERO_HELP = {
    b'hBDT': (
        'Troubadour\n'
        'A travelling musician who follows active allied heroes and strengthens them with songs. '
        'He favors support over fighting, sharing in his companion\'s combat and exploration experience. '
        'He wears leather armor and carries an Instrument.\n\n'
        'Ballad of Valor improves nearby allies\' accuracy, dodge, parry and resistance to magic. '
        'At level 3, Marching Song quickens movement and actions, including his own travels. '
        'At level 5, Cutting Satire weakens an enemy and slows its movement and actions. '
        'At level 8, Heroic Refrain increases all damage dealt by allies and reduces damage from enemy hits.\n\n'
        'A level-2 home guild unlocks Ballad of Renown. Supporting successful attack bounties, '
        'destroyed lairs and noteworthy monster victories earns gold and bonus experience, '
        'collected on a visit to a friendly Bards Hall of level 2 or higher. '
        'Monsters of his own level or higher qualify, as do all monsters of threat rank 6 or higher.'),
    b'hBDS': (
        'Spellsinger\n'
        'A wandering caster who turns music into magical force. He explores, fights and entertains '
        'the town. Intelligence strengthens his magic; Instrument upgrades and enchanting improve '
        'Arcane Note. He wears no armor and does not use weapon coatings.\n\n'
        'Arcane Note strikes an enemy with magical sound. At level 3, Reverberation echoes to '
        'another nearby enemy. Notes and echoes build Resonance, making further Arcane Notes '
        'more damaging. All Spellsingers share this buildup. At level 5, Countermelody disrupts '
        'special spellcasting and reduces weapon accuracy. At level 8, Resonant Burst damages '
        'nearby enemies and consumes their Resonance for a stunning Crescendo.\n\n'
        'A level-2 home guild unlocks Street Spectacle. Outdoor performances near the town\'s '
        'Palace, Marketplace or Bards Hall earn tips and experience from passing listeners.'),
    b'hBDD': (
        'Blade Dancer\n'
        'An agile duelist who makes combat a performance. She hunts worthy opponents with a '
        'saber and dagger, striking with both weapons in one attack. She wears leather armor; '
        'Vitality is her primary attribute.\n\n'
        'Duelist Training gives her skill at dodging missiles and parrying melee attacks. '
        'At level 3, Riposte answers a parried melee attack with a counterattack. At level 5, '
        'Deflect turns aside missiles and direct magical attacks.\n\n'
        'At level 8, Dueling Flourish makes every third successful hit against one opponent '
        'a stronger, armor-piercing strike. A Flourish against any monster prepares Rousing '
        'Finale, marked by a star above the enemy. If she lands the killing blow, nearby allies '
        'become braver and gain damage, dodge and parry bonuses. She also gains Encore: her next '
        'attack against a monster or enemy hero prepares another Finale.\n\n'
        'A level-2 home guild unlocks Prize Duel. She visits friendly combat guilds, the '
        'Adventurers Guild, Fairgrounds or Embassy to compete. Victory earns a cash prize; '
        'defeat gives practice experience.'),
}

def help_pages():
    pages = dict(HERO_HELP)
    stages = {
        1: 'This guild has four shared places. Upgrade it to house more bards and unlock their paid pursuits. At level 3, it can research Epic Chronicles to increase your heroes\' earnings and experience.',
        2: 'This guild has six shared places. Its bards can earn through Ballad of Renown, Street Spectacle and Prize Duel. Upgrade it to unlock Epic Chronicles.',
        3: 'This guild has eight shared places and supports all three paid pursuits. Epic Chronicles can be researched here for a one-time cost of 3000 gold.',
    }
    for level, stage in stages.items():
        pages[f'hBG{level}'.encode()] = (
            f'Bards Hall - Level {level}\n'
            'Home to Troubadours, Spellsingers and Blade Dancers. Each recruit costs 500 gold. '
            + stage + '\n\n'
            'Heroes may hire an available bard for about two days for 200 gold: '
            '100 goes to the guild and 100 to the bard.\n\n'
            + ('Epic Chronicles increases gold and experience earned by your kingdom\'s heroes '
               'by 15%. It requires a completed level-3 Bards Hall. If the last such guild is '
               'lost, the benefit returns when another reaches level 3; research need not be '
               'purchased again.' if level == 3 else
               'New recruitment places and guild benefits become available when upgrade construction finishes.'))
    return pages

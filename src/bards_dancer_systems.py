"""Stock Visit_Building/Gambling_Hall lifecycle with approved duel rewards."""
import re
from bards_abilities import replace_once


def dancer_systems(sdk, extract):
    root = sdk / 'GPLMx'
    def function(path, name):
        return extract((root / path).read_text(encoding='cp1252'), name)

    choose = function('DecisionTrees/Modules/mx_Visit_Building.gpl', 'Visit_Building')
    choose = choose.replace('Visit_Building (agent ThisAgent, string Building, integer Chance)',
                            'Bards_Prize_Duel_Check (agent ThisAgent, integer Chance)')
    choose = replace_once(choose, 'list \t\tPotentials;', 'string Building;\n\tlist Candidates;\n\tagent Candidate;\n\tlist \t\tPotentials;')
    choose = re.sub(r'(?im)^Begin\s*$', lambda m: m[0] + '\n\tif ($Bards_Jobs_Unlocked(ThisAgent) == FALSE) return FALSE;\n\tBuilding = "Prize Duel";\n', choose, count=1)
    choose = replace_once(choose,
        '$ListObjects (ThisAgent, "Building", -1, Potentials, #CheckTitles, Building, #ATTRIB_FirstStageBuilt, 1);',
        '$ListObjects (ThisAgent, "Building", 180, Candidates, #MyTeam, #ATTRIB_FirstStageBuilt, 1);\n'
        '\tforeach Candidate in Candidates do\n\t\tif ($Bards_Prize_Venue(ThisAgent, Candidate)) Potentials << Candidate;')
    choose = choose.replace('"Visiting"', '"Bards_Prize_Duel"').replace('$Use_Building;', '$Bards_Prize_Use;')
    start = choose.index('\t\t\t//If the building is a Marketplace')
    end = choose.index('\t\t\treturn True;', start)
    choose = choose[:start] + '\t\t\t$SpecifyIntent(ThisAgent, #Bards_Intent_Prize_Duel);\n\n' + choose[end:]

    use = function('TaskModules/Characters/mx_Use_Building.gpl', 'use_building')
    use = use.replace('use_building', 'Bards_Prize_Use')
    use = replace_once(use, 'if ($isdead(target))', 'if ($Bards_Prize_Venue(thisagent, target) == FALSE)')
    use = replace_once(use, '$reset_tasks(thisagent);', '$Bards_Prize_Cancel(thisagent, target);')
    use = replace_once(use, 'target\'s "visited_script"', '$Bards_Prize_Visit')

    visit = function('TaskModules/Buildings/mx_Gambling_Hall.gpl', 'Gambling_Hall')
    visit = visit.replace('Gambling_Hall', 'Bards_Prize_Visit').replace('Exit_Bards_Prize_Visit', 'Bards_Prize_Exit')
    visit = replace_once(visit, 'Target = ThisAgent\'s "Target";', 'Target = ThisAgent\'s "Target";\n'
        '\tif ($Bards_Prize_Venue(ThisAgent, Target) == FALSE)\n'
        '\t\tbegin\n\t\t\t$Bards_Prize_Cancel(ThisAgent, Target);\n\t\t\treturn;\n\t\tend')
    visit = visit.replace('#intent_gambling', '#Bards_Intent_Prize_Duel').replace('Target\'s "Sleep_For"', '15000')
    visit = visit.replace('$IncrementStatCounter( thisagent, "gutter" );', '')

    leave = function('TaskModules/Buildings/mx_Gambling_Hall.gpl', 'Exit_Gambling_Hall')
    leave = leave.replace('Exit_Gambling_Hall', 'Bards_Prize_Exit')
    start = leave.index('\tLuck =')
    end = leave.index('\t//Set ThisAgent', start)
    leave = leave[:start] + '''\tif ($Bards_Prize_Venue(ThisAgent, Target) == FALSE)
        begin
            $Bards_Prize_Cancel(ThisAgent, Target);
            return;
        end
    Won = ($RandomNumber(100) < 65);

''' + leave[end:]
    start = leave.index('\tIf (Won)')
    leave = leave[:start] + '''\tIf (Won) $Give_Gold(ThisAgent, 100);
    Else $give_exp(ThisAgent, 250);
End
'''
    morale = function('DecisionTrees/Modules/mx_target_eval.gpl', 'should_I_run')
    anchor = '\tif (killorbekilled < 1)\n\t\tbegin'
    morale = replace_once(morale, anchor, anchor + '\n\t\t\tif ($Bards_Roused_Stand(ThisAgent)) return FALSE;')
    arrival = function('TaskModules/Characters/mx_Travel_to.gpl', 'gettargetrange')
    anchor = '(thisagent\'s "backscript" == $use_building_safe)'
    arrival = replace_once(arrival, anchor, anchor + ' || (thisagent\'s "backscript" == $Bards_Prize_Use)')
    return '\n'.join((choose, use, visit, leave, morale, arrival))

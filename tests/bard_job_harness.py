"""Shared real GPL dependencies and home fixtures for job eligibility tests."""
from test_hiring import ROOT, agent
from build_bards_hall import extract_function


def job_source(include_hiring=True):
    result = (ROOT / 'src/gpl/Bards_Hall_Jobs.gpl').read_text()
    if include_hiring:
        source = (ROOT / 'src/gpl/Bards_Hiring.gpl').read_text()
        result += ''.join(extract_function(source, name) for name in
                          ('Bards_Is_Bard', 'Bards_Hire_Alive', 'Bards_Hire_Guild'))
    return result


def home(level=2, player=1, complete=True):
    # Level is the completed GPL template tier, not the native Description's
    # destination tier while an upgrade is still under construction.
    return agent(title='Bards_Hall', Level=level, player=player, ATTRIB_HP=500,
                 ATTRIB_FirstStageBuilt=1, ATTRIB_CurrentStageBuilt=int(complete))

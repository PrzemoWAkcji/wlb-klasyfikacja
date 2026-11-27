import unittest
from unittest.mock import patch
from monitor import snapshot
from monitor import notifications, podiums, baseline

def row(aid=1, t=89000, status='Ok'):
    return dict(event='60m', gender='Male', yob=2016, name=f'Zawodnik {aid}', club='Klub', athleteId=aid, result=t, status=status, startStatus='Ok', label='')

def meet(rows, i=10):
    return {'meeting':{'meetingId':i,'startDateTime':f'2026-{i:02d}-01 10:00:00','season':'Indoor'}, 'rows':rows}

K='60-M-10-H'
class MonitorTest(unittest.TestCase):
    def apply(self, state, changes):
        for group, key, value, _ in changes:
            if value is None: state.setdefault(group,{}).pop(key,None)
            else: state.setdefault(group,{})[key]=value
    def test_record_restart_equal_correction_dq(self):
        state={}; live=meet([row()]); base={K:900}
        changes,_=notifications(state,live,set(),[],base)
        self.assertEqual(len(changes),1); self.apply(state,changes)
        self.assertFalse(notifications(state,live,set(),[],base)[0])
        live['rows'] += [row(2,89500)]
        self.assertFalse(notifications(state,live,set(),[],base)[0])
        live['rows'][-1]=row(2,89000)
        changes,_=notifications(state,live,set(),[],base)
        self.assertEqual(len(changes),1); self.assertIn('WYRÓWNANY',changes[0][3]); self.apply(state,changes)
        live['rows'][0]=row(status='Disqualified')
        changes,_=notifications(state,live,set(),[],base)
        self.assertEqual(len(changes),1); self.assertIsNone(changes[0][2])
    def test_podium_seven_rounds_and_completion(self):
        history=[meet([row(1),row(2,91000),row(3,92000),row(4,93000)],i) for i in range(1,7)]
        live=meet([row(1),row(2,91000),row(3,92000),row(4,93000)])
        self.assertEqual(podiums(history,live,set()),{})
        text=podiums(history,live,{K})[K]
        self.assertIn('1. Zawodnik 1',text); self.assertIn('7 pkt',text); self.assertNotIn('Zawodnik 4',text)
        self.assertIn('Brak zawodników',podiums(history[:-1],live,{K})[K])
    def test_archive_excludes_final_and_stadium(self):
        archive={K:{'2025':{'t':900},'2026':{'t':800}},'60-M-10-S':{'2025':{'t':700}}}
        self.assertEqual(baseline(archive,[],2026,'2026-12-13'),{K:900})
    def test_completion_requires_all_heats(self):
        details={'season':'Indoor','organisationId':315,'sportEvents':[{'eventIdPk':1,'eventName':'60m'}], 'ageGroups':[{'ageGroupIdPk':1,'rangeType':'Age','rangeStart':10,'rangeEnd':10}]}
        parent={'meetingEventIdPk':1,'eventIdFk':1,'ageGroupIdFk':1,'gender':'Male','resultsComplete':True,'hasResults':False}
        child={**parent,'meetingEventIdPk':2,'parentMeetingEventIdFk':1,'resultsComplete':False}
        schedule={'data':[{'entityDto':parent},{'entityDto':child}]}
        with patch('monitor.req',side_effect=[details,schedule,schedule]):
            _,ready=snapshot(meet([])['meeting'])
        self.assertNotIn(K,ready)
        child['resultsComplete']=True
        with patch('monitor.req',side_effect=[details,schedule,schedule]):
            _,ready=snapshot(meet([])['meeting'])
        self.assertIn(K,ready)

    def test_reopened_podium(self):
        changes,_=notifications({'podiums':{K:'old'}},meet([]),set(),[],{})
        self.assertIsNone(changes[0][2])

if __name__=='__main__': unittest.main()

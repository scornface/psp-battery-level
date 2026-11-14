from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from summarize_runtime import FIELDS,summarize


def record(**changes):
    row=dict.fromkeys(FIELDS,0)
    row.update(build_id=0x30002,context=2,start_us=7,time_us=100,published=1,
               drawn=1,captures=1,presented=1,shown=41,width=32)
    row.update(changes)
    return 'runtime '+' '.join(f'{k}={v:08x}' for k,v in row.items())+' end_runtime'


class RuntimeLogTests(unittest.TestCase):
    def test_previous_and_current_builds_stay_distinct(self):
        for build_id in (0x30002,0x30004):
            result=summarize(record(build_id=build_id))
            self.assertEqual(result['build_id'],f'{build_id:08x}')
        result=summarize(record()+'\n'+record(build_id=0x30004))
        self.assertIsNone(result['build_id'])
        self.assertEqual(result['build_ids'],['00030002','00030004'])
        self.assertEqual(len(result['sessions']),2)
        self.assertEqual([s['build_id'] for s in result['sessions']],result['build_ids'])

    def test_context_cycle_and_sampled_recovery(self):
        text='\n'.join([record(context=1,start_us=1,published=0,presented=0,terminal=1),record(),
            record(time_us=200,drawn=4,restores=3,retired=3),
            record(context=1,start_us=2,published=0,presented=0,terminal=1)])
        result=summarize(text)
        self.assertEqual([s['context'] for s in result['sessions']],['VSH','GAME','VSH'])
        self.assertEqual(result['sessions'][1]['retired'],3)
        self.assertEqual(result['sessions'][1]['geometry'],[(446,32)])
        self.assertFalse(result['sessions'][1]['change_budget_reached'])

    def test_malformed_counter_geometry_and_clock_rejected(self):
        for text in (record(build_id=0x2000f),record(width=48),record(shown=101),record(context=3),
                     record().replace(' end_runtime',' width=00000020 end_runtime'),
                     record()+'\n'+record(time_us=99),record()+'\n'+record(time_us=200,drawn=0)):
            with self.subTest(text=text),self.assertRaises(ValueError):summarize(text)

    def test_partial_wrap_and_budget(self):
        result=summarize(record(time_us=0xfffffff0)+'\n'+record(time_us=0x10)+'\npartial')
        self.assertEqual(result['incomplete_lines'],1)
        self.assertEqual(result['sessions'][0]['sampled_span_seconds'],32/1000000)
        result=summarize('\n'.join(record(time_us=i+1,drawn=i) for i in range(256)))
        self.assertTrue(result['sessions'][0]['change_budget_reached'])

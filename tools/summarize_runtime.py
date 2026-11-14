#!/usr/bin/env python3
"""Summarize sampled bootstrap/GAME diagnostics, not a complete execution trace."""
import argparse
import json
from pathlib import Path
import re
from prx_libraries import bounded_read

FIELDS=set('build_id context outcome published fault fault_site drawn restores captures retired conflicts presented suspended shown width terminal start_us time_us'.split())
COUNTERS=('drawn','restores','captures','retired','conflicts')
BUILD_IDS={0x30002,0x30004} # Same schema; retain the previous hardware return.


def summarize(text):
    groups=[];incomplete=0
    for line in text.splitlines():
        if not line.strip():continue
        if not line.startswith('runtime ') or not line.endswith(' end_runtime'):
            incomplete+=1;continue
        row={}
        for token in line.split()[1:-1]:
            if '=' not in token:raise ValueError('Malformed runtime field')
            key,value=token.split('=',1)
            if key in row or not re.fullmatch('[0-9a-f]{8}',value):raise ValueError('Duplicate/malformed runtime field')
            row[key]=int(value,16)
        if set(row)!=FIELDS or row['build_id'] not in BUILD_IDS:raise ValueError('Unknown runtime build/schema')
        if row['context'] not in (0,1,2) or any(row[k] not in (0,1) for k in ('published','presented','suspended','terminal')):
            raise ValueError('Unexpected runtime state')
        if row['presented'] and (row['shown']>100 or not 0<row['width']<=47):raise ValueError('Invalid presented geometry/value')
        key=(row['build_id'],row['context'],row['start_us'])
        if not groups or groups[-1][0]!=key:groups.append((key,[]))
        records=groups[-1][1]
        if records:
            delta=(row['time_us']-records[-1]['time_us'])&0xffffffff
            if not 0<delta<0x80000000:raise ValueError('Reversed/ambiguous runtime clock')
            if any(row[k]<records[-1][k] for k in COUNTERS):raise ValueError('Reversed runtime counters')
        records.append(row)
    if not groups:raise ValueError('No complete runtime records')
    sessions=[]
    for (build_id,context,start),rows in groups:
        last=rows[-1];visible=[r for r in rows if r['presented']]
        sessions.append(dict(build_id=f'{build_id:08x}',context=('unsupported','VSH','GAME')[context],session_key=f'{start:08x}',records=len(rows),
            sampled_span_seconds=((last['time_us']-rows[0]['time_us'])&0xffffffff)/1000000,
            outcomes=sorted({f"{r['outcome']:08x}" for r in rows}),faults=sorted({r['fault'] for r in rows}),
            **{k:last[k] for k in COUNTERS},presented=last['presented'],suspended=last['suspended'],
            shown_values=sorted({r['shown'] for r in visible}),
            geometry=sorted({(478-r['width'],r['width']) for r in visible}),
            change_budget_reached=sum(not r['terminal'] for r in rows)>=256))
    build_ids=sorted({s['build_id'] for s in sessions})
    return dict(build_id=build_ids[0] if len(build_ids)==1 else None,build_ids=build_ids,
        incomplete_lines=incomplete,sessions=sessions,
        limitations='Change-only worker snapshots, not every callback. VSH zero GAME counters are normal; terminal means bootstrap worker completion, not child unload. No optical or live-unload proof; clock wraps and unlogged intervals limit timing coverage.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);args=p.parse_args()
    try:print(json.dumps(summarize(bounded_read(args.log,8*1024*1024).decode('ascii')),indent=2))
    except (OSError,ValueError,UnicodeError) as error:raise SystemExit(str(error)) from error

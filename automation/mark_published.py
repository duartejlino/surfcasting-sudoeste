#!/usr/bin/env python3
"""Confirma a publicação depois do primeiro push do workflow."""
import datetime as dt, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
published=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
for path in (ROOT/'status.json',ROOT/'data'/'status.json'):
    state=json.loads(path.read_text(encoding='utf-8')); state['publication']={'status':'published','prepared_at':state.get('publication',{}).get('prepared_at'),'at':published}
    temporary=path.with_suffix(path.suffix+'.tmp'); temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); temporary.replace(path)
print(published)

#!/usr/bin/env python3
"""Executa recolha, cálculo, validação e preparação atómica da publicação."""
from __future__ import annotations
import argparse, datetime as dt, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATUS_PATHS=(ROOT/'status.json',ROOT/'data'/'status.json')

def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def old_status():
    try:return json.loads(STATUS_PATHS[1].read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return {}

def write_status(status, paths=STATUS_PATHS):
    raw=json.dumps(status,ensure_ascii=False,indent=2)+'\n'
    for path in paths:
        path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+'.tmp'); temp.write_text(raw,encoding='utf-8'); temp.replace(path)

def run(args):
    subprocess.run(args,cwd=ROOT,check=True)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--dry-run',action='store_true'); parser.add_argument('--source-dir',type=Path); parser.add_argument('--keep-temp',action='store_true'); args=parser.parse_args()
    previous=old_status(); started=now(); temp_obj=tempfile.TemporaryDirectory(prefix='mar-sudoeste-')
    temp=Path(temp_obj.name); sources=args.source_dir.resolve() if args.source_dir else temp/'sources'; candidate=temp/'forecast.json'
    status={'schema_version':'mar-sudoeste-automation-status-v1','run_started_at':started,'collection':{'status':'running','at':None},'calculation':{'status':'pending','at':None},'publication':{'status':'not_attempted','at':previous.get('publication',{}).get('at')},'last_valid_forecast_at':previous.get('last_valid_forecast_at'),'stale':True,'incomplete_sources':[],'errors':[]}
    try:
        if not args.source_dir: run([sys.executable,'collect_sources_14_spots.py','--out',str(sources)])
        manifest=json.loads((sources/'manifest.json').read_text(encoding='utf-8'))
        status['collection']={'status':'complete' if not manifest.get('source_failures') else 'partial','at':manifest.get('generated_at_utc')}
        status['incomplete_sources']=manifest.get('source_failures',[])
        run([sys.executable,'automation/generate_forecast.py',str(sources),str(candidate),'--previous',str(ROOT/'data'/'forecast.json')])
        run([sys.executable,'automation/validate_forecast.py',str(candidate)])
        generated=json.loads(candidate.read_text(encoding='utf-8'))['generated_at']; status['calculation']={'status':'valid','at':generated}; status['last_valid_forecast_at']=generated; status['stale']=False
        if args.dry_run:
            status['publication']={'status':'dry_run','at':previous.get('publication',{}).get('at')}; print(json.dumps(status,ensure_ascii=False,indent=2)); return 0
        for destination in (ROOT/'forecast.json',ROOT/'data'/'forecast.json'):
            copy=destination.with_suffix(destination.suffix+'.tmp'); shutil.copyfile(candidate,copy); copy.replace(destination)
        status['publication']={'status':'prepared','prepared_at':generated,'at':previous.get('publication',{}).get('at')}; write_status(status)
        print(json.dumps(status,ensure_ascii=False,indent=2)); return 0
    except Exception as exc:
        status['errors'].append({'at':now(),'message':str(exc)[:600]}); status['calculation']['status']='failed' if status['calculation']['status']=='pending' else status['calculation']['status']; status['publication']['status']='previous_forecast_preserved'; status['stale']=True
        if not args.dry_run: write_status(status)
        print(json.dumps(status,ensure_ascii=False,indent=2),file=sys.stderr); return 1
    finally:
        if args.keep_temp: print('temporary_directory='+str(temp),file=sys.stderr); temp_obj.cleanup=lambda:None
        temp_obj.cleanup()
if __name__=='__main__': raise SystemExit(main())

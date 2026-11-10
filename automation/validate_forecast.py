#!/usr/bin/env python3
"""Validação estrita dos artefactos automatizados."""
from __future__ import annotations
import argparse, datetime as dt, json, math
from pathlib import Path

PERIODS={'Madrugada','Amanhecer','Manhã','Tarde','Anoitecer','Noite'}
SPECIES={'Geral','Robalo','Sargo','Dourada'}
ACTIVITIES={'surf','spinning','sub','mare'}
SURFCASTING_BEACHES={'santo-andre','sao-torpes','porto-covo','aivados','malhao','furnas-mira','areao','morgavel','vieirinha','ilha-pessegueiro','farol-milfontes'}

def iso(value):
    try: dt.datetime.fromisoformat(str(value).replace('Z','+00:00')); return True
    except ValueError: return False

def validate(data):
    errors=[]
    if data.get('schema_version')!=3: errors.append('schema_version não é 3')
    if not iso(data.get('generated_at')): errors.append('generated_at inválido')
    beaches=data.get('beaches'); evaluations=data.get('evaluations'); activities=data.get('activity_evaluations')
    if not isinstance(beaches,dict) or len(beaches)!=14: errors.append('são necessárias exatamente 14 zonas')
    if not isinstance(evaluations,list) or not evaluations: errors.append('evaluations vazio')
    if not isinstance(activities,list) or not activities: errors.append('activity_evaluations vazio')
    seen=set()
    for index,e in enumerate(evaluations or []):
        key=(e.get('date'),e.get('beach_id'),e.get('period'),e.get('species'))
        if key in seen: errors.append(f'avaliação duplicada {key}')
        seen.add(key)
        if e.get('beach_id') not in (beaches or {}) or e.get('period') not in PERIODS or e.get('species') not in SPECIES: errors.append(f'avaliação {index} com chave inválida')
        try: dt.date.fromisoformat(e.get('date',''))
        except ValueError: errors.append(f'avaliação {index} com data inválida')
        if not isinstance(e.get('score'),(int,float)) or not math.isfinite(e['score']) or not 0<=e['score']<=10: errors.append(f'avaliação {index} com nota inválida')
        factors=e.get('factors') or []
        if abs(sum(float(f.get('weight',0)) for f in factors)-1)>.011: errors.append(f'avaliação {index} com pesos inválidos')
        if any(f.get('value') is None for f in factors): errors.append(f'avaliação {index} preencheu fator sem valor explícito')
    seen=set(); kinds=set()
    for index,a in enumerate(activities or []):
        key=(a.get('date'),a.get('activity'),a.get('beach_id'),a.get('period'),a.get('surf_level',''))
        if key in seen: errors.append(f'atividade duplicada {key}')
        seen.add(key); kinds.add(a.get('activity'))
        if a.get('activity') not in ACTIVITIES or a.get('period') not in PERIODS or a.get('beach_id') not in (beaches or {}): errors.append(f'atividade {index} inválida')
        try: dt.date.fromisoformat(a.get('date',''))
        except ValueError: errors.append(f'atividade {index} com data inválida')
        if a.get('score') is not None and (not isinstance(a['score'],(int,float)) or not 0<=a['score']<=10): errors.append(f'atividade {index} com nota inválida')
        if a.get('activity')=='surf' and a.get('surf_level') not in {'iniciante','intermedio','experiente'}: errors.append(f'surf {index} sem nível')
    if kinds!=ACTIVITIES: errors.append(f'modalidades ausentes: {ACTIVITIES-kinds}')
    dates={e.get('date') for e in evaluations or []}
    evaluated_beaches={e.get('beach_id') for e in evaluations or []}
    if evaluated_beaches!=SURFCASTING_BEACHES: errors.append(f'cobertura de surfcasting incompleta: {sorted(SURFCASTING_BEACHES-evaluated_beaches)}')
    for date in dates:
        if {e['period'] for e in evaluations if e['date']==date}!=PERIODS: errors.append(f'{date} não contém seis períodos')
    if not data.get('source_registry'): errors.append('source_registry vazio')
    if data.get('automation',{}).get('human_equivalence_claimed') is not False: errors.append('motor não declara explicitamente ausência de equivalência humana')
    return errors

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('forecast',type=Path); args=parser.parse_args()
    data=json.loads(args.forecast.read_text(encoding='utf-8')); errors=validate(data)
    print(json.dumps({'file':str(args.forecast),'errors':errors,'beaches':len(data.get('beaches',{})),'evaluations':len(data.get('evaluations',[])),'activity_evaluations':len(data.get('activity_evaluations',[]))},ensure_ascii=False,indent=2))
    return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())

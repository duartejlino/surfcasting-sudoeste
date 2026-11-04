#!/usr/bin/env python3
"""Verificador do contrato do ficheiro forecast.json do Mar Sudoeste v4.3.
Uso: python tools/verificar_forecast.py data/forecast.json
"""
import sys, json, math, datetime
from pathlib import Path
P={'Madrugada','Amanhecer','Manhã','Tarde','Anoitecer','Noite'}
SP={'Geral','Robalo','Sargo','Dourada'}
ACT={'surf','spinning','sub','mare'}

def valid_time(s):
    try:datetime.datetime.fromisoformat(s.replace('Z','+00:00')); return True
    except (TypeError,ValueError):return False

def main(path):
    x=json.loads(Path(path).read_text(encoding='utf-8'))
    issues=[]; warns=[]
    if x.get('schema_version')!=3:issues.append('schema_version tem de ser 3')
    if not valid_time(x.get('generated_at')):issues.append('generated_at inválido')
    bs=x.get('beaches') or {};evs=x.get('evaluations') or []
    if not isinstance(bs,dict) or not bs:issues.append('beaches vazio/inválido')
    if not isinstance(evs,list) or not evs:issues.append('evaluations vazio/inválido')
    seen=set()
    for idx,e in enumerate(evs):
        key=(e.get('date'),e.get('beach_id'),e.get('period'),e.get('species'))
        if key in seen:issues.append(f'avaliação duplicada: {key}')
        seen.add(key)
        if e.get('beach_id') not in bs or e.get('period') not in P or e.get('species') not in SP:issues.append(f'avaliação {idx}: chave inválida')
        for k in ('score','confidence'):
            v=e.get(k)
            if not isinstance(v,(int,float)) or not math.isfinite(v) or not (0<=v<= (10 if k=='score' else 100)):issues.append(f'avaliação {idx}: {k} fora do intervalo')
        factors=e.get('factors')
        if not isinstance(factors,list) or not factors:
            issues.append(f'avaliação {idx}: fatores ausentes');continue
        total=sum(float(f.get('weight') or 0) for f in factors)
        if abs(total-1)>0.011:issues.append(f'avaliação {idx}: soma dos pesos {total:.3f}')
        for f in factors:
            for k in ('score','weight','impact'):
                if not isinstance(f.get(k),(float,int)) or not math.isfinite(float(f[k])):issues.append(f'avaliação {idx}: {k} inválido em {f.get("id")}')
    aes=x.get('activity_evaluations')
    if aes is None:warns.append('Sem activity_evaluations: a app usa fórmulas locais provisórias para outras quatro atividades')
    else:
        if not isinstance(aes,list) or not aes:issues.append('activity_evaluations presente mas vazio/inválido')
        else:
            keys=set()
            for i,a in enumerate(aes):
                key=(a.get('date'),a.get('activity'),a.get('beach_id'),a.get('period'),a.get('surf_level',''))
                if key in keys:issues.append(f'activity_evaluations duplicada: {key}')
                keys.add(key)
                if a.get('activity') not in ACT or a.get('beach_id') not in bs or a.get('period') not in P:issues.append(f'activity_evaluations {i}: chave inválida')
                if a.get('activity')=='surf' and a.get('surf_level') not in {'iniciante','intermedio','experiente'}:issues.append(f'activity_evaluations {i}: falta nível de surf')
                if a.get('score') is not None and not isinstance(a.get('score'),(int,float)):issues.append(f'activity_evaluations {i}: score inválido')
                if not isinstance(a.get('confidence'),(int,float)) or not (0<=a['confidence']<=100):issues.append(f'activity_evaluations {i}: confiança inválida')
            warns.append(f'{len(aes)} avaliações de outras atividades')
    if not x.get('source_registry'):warns.append('Sem source_registry: não existe auditoria de valores brutos por modelo neste ficheiro')
    print(f'Ficheiro: {path}\nData geração: {x.get("generated_at")}\nPraias: {len(bs)} | Surfcasting: {len(evs)} | Atividades pré-calculadas: {len(aes or [])}')
    print(f'Erros: {len(issues)} | Avisos: {len(warns)}')
    for m in issues[:40]:print('ERRO:',m)
    for m in warns[:40]:print('AVISO:',m)
    if len(issues)>40:print('... erros adicionais omitidos')
    return 1 if issues else 0
if __name__=='__main__':sys.exit(main(sys.argv[1] if len(sys.argv)>1 else 'data/forecast.json'))

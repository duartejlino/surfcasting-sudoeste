#!/usr/bin/env python3
"""Gera forecast.json determinístico a partir das fontes brutas validadas.

O motor calcula potencial ambiental. Não estima observações ausentes, peixe,
visibilidade, segurança do acesso ou legalidade. Essas lacunas permanecem
explícitas nas limitações e podem anular a nota de atividades críticas.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PERIODS = {
    'Madrugada': (0, 6), 'Amanhecer': (6, 8), 'Manhã': (8, 12),
    'Tarde': (12, 17), 'Anoitecer': (17, 19), 'Noite': (19, 24),
}
SPECIES = ('Geral', 'Robalo', 'Sargo', 'Dourada')
SURF_LEVELS = ('iniciante', 'intermedio', 'experiente')
ACTIVITY_BEACHES = {
    'surfcasting': {'santo-andre','sao-torpes','porto-covo','aivados','malhao','furnas-mira','areao','morgavel','vieirinha','ilha-pessegueiro','farol-milfontes'},
    'surf': {'santo-andre','sao-torpes','porto-covo','aivados','malhao','areao','vieirinha','burrinho','ilha-pessegueiro','farol-milfontes'},
    'spinning': None,
    'sub': {'sao-torpes','porto-covo','samoqueira','aivados','malhao','burrinho','ilha-pessegueiro'},
    'mare': {'sao-torpes','porto-covo','samoqueira','malhao','burrinho','ilha-pessegueiro'},
}
PROFILES = {
    'santo-andre': ('Costa de Santo André','Areal atlântico exposto','Areia',6.5),
    'sao-torpes': ('São Torpes','Praia relativamente abrigada com rocha pontual','Areia e rocha',7.5),
    'porto-covo': ('Praia Grande de Porto Covo','Areal e estrutura costeira','Areia e rocha',8.0),
    'aivados': ('Praia dos Aivados','Areal atlântico exposto','Areia',7.0),
    'malhao': ('Praia do Malhão','Areal exposto com setores rochosos','Areia e rocha',7.7),
    'furnas-mira': ('Furnas / Foz do Mira','Praia junto à embocadura do Mira','Areia e canal',6.8),
    'samoqueira': ('Samoqueira','Enseada rochosa; surfcasting excluído','Rocha e areia',8.4),
    'areao': ('Praia do Areão','Areal aberto muito exposto','Areia',6.5),
    'morgavel': ('Praia de Morgavel','Areal com estrutura local por confirmar','Areia',6.0),
    'vieirinha': ('Praia da Vieirinha / Vale Figueiros','Areal exposto','Areia',6.5),
    'burrinho': ('Praia do Burrinho','Pequena praia rochosa','Rocha e areia',8.3),
    'ilha-pessegueiro': ('Praia da Ilha do Pessegueiro','Areal, canal e recife são setores distintos','Areia e rocha',8.0),
    'patacho': ('Praia do Patacho · Milfontes','Areal pequeno sob falésia; acesso por validar','Areia e rocha',5.0),
    'farol-milfontes': ('Praia do Farol · Milfontes','Margem norte da foz do Mira','Areia e canal',6.2),
}

def clamp(value, low=0.0, high=10.0):
    return max(low, min(high, float(value)))

def optimum(value, ideal, scale):
    return clamp(10 - abs(value - ideal) / scale * 5)

def median(values):
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return statistics.median(clean) if clean else None

def key_for(hourly, name):
    return name if name in hourly else next((k for k in hourly if k.startswith(name + '_')), None)

def period_values(data, variable, date, bounds):
    hourly = data.get('hourly') or {}
    key = key_for(hourly, variable)
    if not key:
        return []
    result=[]
    for stamp,value in zip(hourly.get('time',[]), hourly.get(key,[])):
        if not stamp.startswith(date) or value is None:
            continue
        try: hour=int(stamp[11:13])
        except (ValueError,IndexError): continue
        if bounds[0] <= hour < bounds[1] and isinstance(value,(int,float)):
            result.append(value)
    return result

def direction_name(degrees):
    if degrees is None: return '—'
    names=('N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW')
    return names[round(float(degrees)/22.5)%16]

def load_tides(path):
    if not path.exists(): return None
    data=json.loads(path.read_text(encoding='utf-8'))
    return data

def tide_for(tides, date, mid_hour):
    if not tides or date[:7] != f"{tides.get('year'):04d}-{tides.get('month'):02d}": return None
    events=(tides.get('events') or {}).get(str(int(date[-2:])),[])
    rows=[]
    for clock,height in events:
        minute=int(clock[:2])*60+int(clock[3:]); rows.append((minute,float(height),clock))
    lows=[]
    for i,row in enumerate(rows):
        before=rows[i-1][1] if i else 99; after=rows[i+1][1] if i+1<len(rows) else 99
        if row[1] < before and row[1] < after:
            adjacent=[x[1] for x in rows[max(0,i-1):i+2] if x[1]>row[1]]
            lows.append((row, max(adjacent)-row[1] if adjacent else None))
    if not lows:return None
    (minute,height,clock),amplitude=min(lows,key=lambda x:abs(x[0][0]-mid_hour*60))
    distance=abs(minute-mid_hour*60)
    phase='perto da baixa-mar' if distance<=70 else ('enchente' if minute>mid_hour*60 else 'vazante')
    return {'low_time':clock,'low_height':height,'range':round(amplitude,2) if amplitude is not None else None,'distance_min':round(distance),'phase':phase,'source':tides.get('source'),'url':tides.get('url')}

def consensus(beach, date, period, rain_72h):
    bounds=PERIODS[period]
    models=[v for v in beach['marine_models'].values() if v.get('ok')]
    weather=beach['weather'].get('data') if beach.get('weather',{}).get('ok') else None
    extras=beach.get('marine_extras',{})
    extras=extras.get('data') if extras.get('ok') else None
    def marine(name):
        per_model=[median(period_values(m['data'],name,date,bounds)) for m in models]
        return median(per_model)
    def meteo(name): return median(period_values(weather,name,date,bounds)) if weather else None
    def extra(name): return median(period_values(extras,name,date,bounds)) if extras else None
    wave=marine('wave_height'); period_s=marine('wave_period'); wave_dir=marine('wave_direction')
    wind=meteo('wind_speed_10m'); wind_dir=meteo('wind_direction_10m')
    required=(wave,period_s,wind)
    if any(v is None for v in required): return None
    return {
      'wave_offshore_m':round(wave,2),'effective_wave_m':round(wave,2),
      'wave_period_s':round(period_s,1),'wave_direction':direction_name(wave_dir),
      'wind_kmh':round(wind,1),'wind_direction':direction_name(wind_dir),
      'wind_gust_kmh':None if meteo('wind_gusts_10m') is None else round(meteo('wind_gusts_10m'),1),
      'water_temp_c':None if extra('sea_surface_temperature') is None else round(extra('sea_surface_temperature'),1),
      'current_kmh':None if extra('ocean_current_velocity') is None else round(extra('ocean_current_velocity'),2),
      'pressure_hpa':None if meteo('pressure_msl') is None else round(meteo('pressure_msl'),1),
      'cloud_pct':None if meteo('cloud_cover') is None else round(meteo('cloud_cover')),
      'rain_mira_72h_mm':rain_72h,
      'model_count':len(models),'data_origin_level':'consenso de modelos na coordenada',
      'primary_source':'Open-Meteo Marine/Weather; centros identificados em source_registry',
      'missing_observations':['rebentação na praia','visibilidade subaquática','acesso seguro','presença de peixe','legalidade local em tempo real'],
    }

def factor(fid,label,value,unit,score,weight,reason,source='Open-Meteo · consenso por coordenada'):
    return {'id':fid,'label':label,'value':value,'unit':unit,'score':round(clamp(score),2),'weight':weight,
            'impact':round(clamp(score)*weight,3),'source':source,'confidence':0.62,'reason':reason}

def surfcasting(date,bid,period,species,window,c,profile):
    h,p,w=c['wave_offshore_m'],c['wave_period_s'],c['wind_kmh']
    species_wave={'Geral':1.0,'Robalo':1.15,'Sargo':0.9,'Dourada':0.65}[species]
    light=9 if period in ('Amanhecer','Anoitecer') else 6.5 if period in ('Madrugada','Noite') else 7.2
    structure=profile[3]
    tide_score=7.5 if c.get('tide_phase')=='enchente' else 6.5
    factors=[
      factor('onda','Altura da onda',h,'m',optimum(h,species_wave,1.0),.23,'Faixa indicativa por espécie; altura offshore não é rebentação.'),
      factor('periodo','Período da onda',p,'s',optimum(p,11.5,8),.14,'Energia do mar; período longo também aumenta risco.'),
      factor('vento','Vento',w,'km/h',clamp(10-w*.27),.16,'Vento forte penaliza lançamento e leitura.'),
      factor('luz','Período do dia',period,'',light,.14,'A luz altera atividade e operação, sem provar presença de peixe.'),
      factor('fundo_estrutura','Estrutura provável',profile[2],'',structure,.18,'Perfil estático; bancos e canais não são observados.'),
      factor('mare','Maré regional',c.get('tide_phase','sem maré oficial'),'',tide_score,.15,'Maré de Sines quando disponível; não é medição na praia.',c.get('tide_source','Sem fonte oficial disponível')),
    ]
    score=round(sum(f['impact'] for f in factors),1)
    if h>=2.7 or w>=35: score=min(score,4.0)
    confidence=max(35,min(72,44+c['model_count']*6-(8 if c.get('tide_phase') is None else 0)))
    return {'date':date,'beach_id':bid,'period':period,'species':species,'window':window,'score':score,'confidence':confidence,
      'summary':f"Potencial determinístico para {species.lower()}; mar e vento modelados, sem observação de peixe ou do pesqueiro.",
      'why_not_10':'Faltam observações locais de bancos, correntes, segurança, atividade de peixe e acessos.',
      'conditions':c,'factors':factors,'sensitivities':[],
      'source_audit':{'model_count':c['model_count'],'method':'mediana entre centros independentes disponíveis; sem preencher valores ausentes'}}

def activity(date,bid,period,window,c,profile,kind,level=None):
    h,p,w=c['wave_offshore_m'],c['wave_period_s'],c['wind_kmh']; daylight=period in ('Amanhecer','Manhã','Tarde','Anoitecer')
    common={'date':date,'activity':kind,'beach_id':bid,'period':period,'window':window,'confidence':min(65,40+c['model_count']*5),
      'conditions':c,'observation':f"Mar regional {h} m / {p} s; vento {w} km/h; sem observação local.",
      'origin':'motor determinístico sobre modelos na coordenada','source':'Open-Meteo + IPMA quando disponível','reasons':[],
      'limits':['Potencial ambiental; confirmar condições, acesso, regras e segurança no local.'],'factors':[],'risky':False}
    if level: common['surf_level']=level
    def add(name,value,unit,grade,weight,reason): common['factors'].append({'name':name,'value':value,'unit':unit,'score':round(clamp(grade),2),'weight':weight,'impact':round(clamp(grade)*weight,3),'reason':reason})
    if kind=='surf':
        target={'iniciante':.6,'intermedio':1.05,'experiente':1.65}[level]
        add('Altura estimada',h,'m',optimum(h,target,.45 if level=='iniciante' else .9),.45,'Altura offshore; não mede a onda a quebrar.')
        add('Período',p,'s',optimum(p,11.5,7),.2,'Energia e formação indicativas.')
        add('Vento',w,'km/h',clamp(10-w*.3),.25,'Direção local pode divergir por relevo.')
        add('Luz',period,'',9 if daylight else 0,.1,'Surf noturno não é recomendado.')
        score=round(sum(x['impact'] for x in common['factors']),1) if daylight else None
        risky=not daylight or w>=35 or (level=='iniciante' and h>1.25)
        if risky and score is not None: score=min(score,3.0)
        return {**common,'score':score,'potential':score,'status':'Potencial indicativo' if score is not None else 'Evitar à noite','risky':risky,'reasons':['Altura, período, vento e luz avaliados sem observar bancos ou agueiros.']}
    if kind=='spinning':
        add('Espuma / mar útil',h,'m',optimum(h,.85,.95),.3,'Mar moderado pode criar espuma; não prova peixe.')
        add('Período',p,'s',optimum(p,11.3,8),.15,'Período longo aumenta ressaca.')
        add('Vento',w,'km/h',clamp(10-w*.28),.2,'Controlo da amostra.')
        add('Luz',period,'',10 if period in ('Amanhecer','Anoitecer') else 7,.2,'Janelas de transição favorecidas como heurística explícita.')
        add('Estrutura provável',profile[2],'',profile[3],.15,'Estrutura estática não observada nesta recolha.')
        score=round(sum(x['impact'] for x in common['factors']),1); risky=h>=1.25 or w>=35
        return {**common,'score':min(score,5) if risky else score,'potential':score,'status':'Cuidado nas rochas' if risky else 'Potencial indicativo','risky':risky,'reasons':['Combinação determinística de mar, vento, luz e perfil estático.']}
    if kind=='sub':
        add('Mar na entrada',h,'m',clamp(10-h*7.8),.34,'Menos ondulação pode ajudar, sem medir visibilidade.')
        add('Período / ressaca',p,'s',clamp(10-max(0,p-8)*1.25),.22,'Movimento junto a pedra.')
        add('Vento',w,'km/h',clamp(10-w*.34),.2,'Condições de superfície.')
        add('Fundo provável',profile[2],'',profile[3],.09,'Sem mapa submerso validado.')
        add('Visibilidade real','ausente','',0,.15,'Dado crítico não medido; a nota final fica indisponível.')
        potential=round(sum(x['impact'] for x in common['factors']),1); risky=not daylight or h>=.85 or p>=14 or w>=25
        return {**common,'score':None,'potential':potential,'status':'Visibilidade e segurança por validar','risky':risky,
          'reasons':['O potencial usa apenas mar e vento; não existe medição de visibilidade.'],
          'limits':common['limits']+['Sem visibilidade real, entrada/saída e zona legal confirmadas, não é atribuída nota final.']}
    tide_ok=c.get('tide_low_height_m') is not None
    add('Altura oficial da baixa-mar',c.get('tide_low_height_m','ausente'),'m',clamp((1.45-c.get('tide_low_height_m',1.45))/1.25*10) if tide_ok else 0,.35,'Tabela oficial IH/Sines; não mede a plataforma.')
    add('Amplitude',c.get('tide_range_m','ausente'),'m',clamp((c.get('tide_range_m',1.35)-1.35)/1.55*10) if tide_ok else 0,.2,'Amplitude oficial regional.')
    add('Ressaca',h,'m',clamp(10-h*9),.25,'Ondulação pode tornar rochas perigosas.')
    add('Vento',w,'km/h',clamp(10-w*.35),.1,'Equilíbrio e spray.')
    add('Plataforma provável',profile[2],'',profile[3],.1,'Acesso não verificado.')
    potential=round(sum(x['impact'] for x in common['factors']),1); risky=h>=.85 or p>=14 or w>=22
    score=potential if tide_ok and daylight and not risky else None
    return {**common,'score':score,'potential':potential,'status':'Janela potencial · validar rochas e legalidade' if score is not None else 'Sem recomendação segura','risky':risky,
      'reasons':['Maré oficial regional combinada com mar, vento e luz.'],
      'limits':common['limits']+(['Sem tabela oficial para esta data; não se estima maré.'] if not tide_ok else ['Acesso e legalidade de apanha não verificados.'])}

def generate(source_dir: Path, previous: Path|None=None, days=7):
    manifest=json.loads((source_dir/'manifest.json').read_text(encoding='utf-8'))
    beach_data={bid:json.loads((source_dir/f'{bid}.json').read_text(encoding='utf-8')) for bid in manifest['beaches']}
    rain=json.loads((source_dir/'rain_mira.json').read_text(encoding='utf-8'))
    tides=load_tides(ROOT/'data'/'tides_sines_2026_11.json')
    dates=sorted({t[:10] for b in beach_data.values() for m in b['marine_models'].values() if m.get('ok') for t in (m.get('data',{}).get('hourly',{}).get('time') or [])})
    today=dt.datetime.now(ZoneInfo('Europe/Lisbon')).date().isoformat(); dates=[d for d in dates if d>=today][:days]
    if not dates: raise ValueError('fontes sem datas futuras válidas')
    rain_values=[]
    for point in rain.get('points',{}).values():
        if point.get('ok'):
            h=point['data'].get('hourly',{}); rain_values.extend(v for v in h.get('precipitation',[])[:72] if isinstance(v,(int,float)))
    rain_72h=round(sum(rain_values),1) if rain_values else None
    beaches={}
    for bid,b in beach_data.items():
        name,profile,bottom,structure=PROFILES[bid]
        beaches[bid]={'name':name,'lat':b['coordinate_requested']['lat'],'lon':b['coordinate_requested']['lon'],'profile':profile,'depth':'Não medida nesta recolha','bottom':bottom,'structure':structure,'exposure':None,'best_for':[],'where':'Confirmar no local.','ideal':'Potencial calculado por modelos; validar condições reais.','avoid':'Não usar a nota como autorização ou garantia de segurança.','rig':'Sem recomendação automática de montagem.'}
    evaluations=[]; activities=[]
    for bid,b in beach_data.items():
      profile=PROFILES[bid]
      for date in dates:
       for period,bounds in PERIODS.items():
        c=consensus(b,date,period,rain_72h)
        if not c: continue
        window=f'{bounds[0]:02d}:00–{bounds[1]%24:02d}:00'; tide=tide_for(tides,date,(bounds[0]+bounds[1])/2)
        if tide: c.update({'tide_phase':tide['phase'],'tide_low_height_m':tide['low_height'],'tide_range_m':tide['range'],'tide_low_time':tide['low_time'],'tide_source':tide['url']})
        if bid in ACTIVITY_BEACHES['surfcasting']:
            evaluations.extend(surfcasting(date,bid,period,s,window,dict(c),profile) for s in SPECIES)
        for kind in ('surf','spinning','sub','mare'):
            eligible=ACTIVITY_BEACHES[kind] is None or bid in ACTIVITY_BEACHES[kind]
            if not eligible: continue
            if kind=='surf': activities.extend(activity(date,bid,period,window,dict(c),profile,kind,lvl) for lvl in SURF_LEVELS)
            else: activities.append(activity(date,bid,period,window,dict(c),profile,kind))
    if len(beaches)!=14 or not evaluations: raise ValueError('cobertura insuficiente para gerar previsão')
    source_registry=[]
    for bid,b in beach_data.items():
        for model,v in b['marine_models'].items():
            if v.get('ok'): source_registry.append({'beach_id':bid,'source':model,'requested_at':v.get('retrieved_at_utc'),'endpoint':v.get('request_url'),'coverage':v.get('coverage')})
        if b.get('weather',{}).get('ok'): source_registry.append({'beach_id':bid,'source':'Open-Meteo Weather','requested_at':b['weather'].get('retrieved_at_utc'),'endpoint':b['weather'].get('request_url'),'coverage':b['weather'].get('coverage')})
    now=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    result={'schema_version':3,'generated_at':now,'generator':'Mar Sudoeste deterministic-engine-v1 (sem IA/API paga)','area':'Sudoeste de Portugal',
      'notes':['Motor determinístico; não demonstrou equivalência à análise humana.','Valores ausentes não são estimados.','Notas representam potencial ambiental, não segurança, captura ou autorização.'],
      'weights':{'onda':.23,'periodo':.14,'vento':.16,'luz':.14,'fundo_estrutura':.18,'mare':.15},
      'beaches':beaches,'evaluations':evaluations,'activity_evaluations':activities,'source_registry':source_registry,
      'source_failures':manifest.get('source_failures',[]),'automation':{'version':1,'source_snapshot_generated_at':manifest.get('generated_at_utc'),'forecast_days':len(dates),'method':'medianas por período e centro; regras fixas documentadas no código','human_equivalence_claimed':False}}
    if previous and previous.exists():
        old=json.loads(previous.read_text(encoding='utf-8')); old_scores=[e['score'] for e in old.get('evaluations',[]) if isinstance(e.get('score'),(int,float))]
        new_scores=[e['score'] for e in evaluations]
        result['automation']['comparison_with_previous']={'previous_generated_at':old.get('generated_at'),'previous_evaluations':len(old.get('evaluations',[])),'new_evaluations':len(evaluations),'previous_mean_score':round(statistics.mean(old_scores),2) if old_scores else None,'new_mean_score':round(statistics.mean(new_scores),2),'equivalence_demonstrated':False,'note':'Horizontes e fontes diferem; comparação é diagnóstico, não validação contra verdade observada.'}
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('source_dir',type=Path); parser.add_argument('output',type=Path); parser.add_argument('--previous',type=Path); parser.add_argument('--days',type=int,default=7)
    args=parser.parse_args(); forecast=generate(args.source_dir,args.previous,args.days); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(forecast,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); print(json.dumps({'output':str(args.output),'beaches':len(forecast['beaches']),'evaluations':len(forecast['evaluations']),'activity_evaluations':len(forecast['activity_evaluations'])}))
if __name__=='__main__': main()

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

def tide_events(tides):
    """Devolve extremos cronológicos, classificados pelos vizinhos reais."""
    if not tides:return []
    year,month=tides.get('year'),tides.get('month'); rows=[]
    for day,events in (tides.get('events') or {}).items():
        for clock,height in events:
            try: when=dt.datetime(year,month,int(day),int(clock[:2]),int(clock[3:]),tzinfo=dt.timezone.utc)
            except (TypeError,ValueError):continue
            rows.append({'when':when,'clock':clock,'height':float(height)})
    rows.sort(key=lambda row:row['when'])
    for index,row in enumerate(rows):
        before=rows[index-1]['height'] if index else None; after=rows[index+1]['height'] if index+1<len(rows) else None
        if before is not None and after is not None: row['kind']='low' if row['height']<before and row['height']<after else 'high' if row['height']>before and row['height']>after else None
        elif after is not None: row['kind']='low' if row['height']<after else 'high'
        elif before is not None: row['kind']='low' if row['height']<before else 'high'
    return [row for row in rows if row.get('kind')]

def tide_for(tides, date, mid_hour):
    if not tides or date[:7] != f"{tides.get('year'):04d}-{tides.get('month'):02d}": return None
    events=tide_events(tides); reference=dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc)+dt.timedelta(hours=mid_hour)
    previous=next((row for row in reversed(events) if row['when']<=reference),None); following=next((row for row in events if row['when']>reference),None)
    nearest=min(events,key=lambda row:abs((row['when']-reference).total_seconds()),default=None)
    if not nearest:return None
    near_minutes=abs((nearest['when']-reference).total_seconds())/60
    if near_minutes<=70: phase='perto da baixa-mar' if nearest['kind']=='low' else 'perto da preia-mar'
    elif previous and following: phase='enchente' if previous['kind']=='low' and following['kind']=='high' else 'vazante' if previous['kind']=='high' and following['kind']=='low' else 'fase indeterminada'
    else: phase='fase indeterminada'
    lows=[row for row in events if row['kind']=='low']; low=min(lows,key=lambda row:abs((row['when']-reference).total_seconds()),default=None)
    if not low:return None
    low_index=events.index(low); adjacent=[row for row in (events[low_index-1:low_index]+events[low_index+1:low_index+2]) if row['kind']=='high']
    amplitude=max((row['height']-low['height'] for row in adjacent),default=None)
    return {'low_time':low['clock'],'low_date':low['when'].date().isoformat(),'low_height':low['height'],'range':round(amplitude,2) if amplitude is not None else None,
      'distance_min':round(abs((low['when']-reference).total_seconds())/60),'phase':phase,
      'previous_extreme':{'time':previous['when'].isoformat(),'kind':previous['kind'],'height':previous['height']} if previous else None,
      'next_extreme':{'time':following['when'].isoformat(),'kind':following['kind'],'height':following['height']} if following else None,
      'source':tides.get('source'),'url':tides.get('url')}

def parse_local(value):
    try:
        parsed=dt.datetime.fromisoformat(value)
        return parsed.replace(tzinfo=ZoneInfo('Europe/Lisbon')) if parsed.tzinfo is None else parsed.astimezone(ZoneInfo('Europe/Lisbon'))
    except (TypeError,ValueError):return None

def rain_history(rain, reference):
    """Agrega cada estação separadamente; nunca soma estações entre si."""
    start=reference-dt.timedelta(hours=72); station_totals={}; missing=[]
    for station,point in (rain.get('points') or {}).items():
        if not point.get('ok'):
            missing.append(station);continue
        hourly=(point.get('data') or {}).get('hourly') or {}; values=[]
        for stamp,value in zip(hourly.get('time',[]),hourly.get('precipitation',[])):
            when=parse_local(stamp)
            if when and start < when <= reference and isinstance(value,(int,float)) and math.isfinite(value): values.append(float(value))
        if values: station_totals[station]=round(sum(values),2)
        else: missing.append(station)
    amount=round(statistics.median(station_totals.values()),2) if station_totals else None
    return {'amount_mm':amount,'station_totals_mm':station_totals,'missing_stations':missing,'window_start':start.isoformat(),'window_end':reference.isoformat(),'origin':'previsão/hindcast de modelo por estação; não observações pluviométricas'}

def daylight(weather,date,bounds):
    daily=(weather or {}).get('daily') or {}; times=daily.get('time',[])
    try:index=times.index(date)
    except ValueError:return {'minutes':None,'fraction':None,'sunrise':None,'sunset':None,'error':'nascer/pôr do sol ausentes'}
    try:sunrise=parse_local(daily.get('sunrise',[])[index]); sunset=parse_local(daily.get('sunset',[])[index])
    except IndexError:return {'minutes':None,'fraction':None,'sunrise':None,'sunset':None,'error':'nascer/pôr do sol incompletos'}
    if not sunrise or not sunset:return {'minutes':None,'fraction':None,'sunrise':None,'sunset':None,'error':'nascer/pôr do sol inválidos'}
    zone=ZoneInfo('Europe/Lisbon'); start=dt.datetime.fromisoformat(date).replace(tzinfo=zone)+dt.timedelta(hours=bounds[0]); end=dt.datetime.fromisoformat(date).replace(tzinfo=zone)+dt.timedelta(hours=bounds[1])
    minutes=max(0,(min(end,sunset)-max(start,sunrise)).total_seconds()/60); duration=(end-start).total_seconds()/60
    return {'minutes':round(minutes),'fraction':round(minutes/duration,3),'sunrise':sunrise.isoformat(),'sunset':sunset.isoformat(),'error':None}

def consensus(beach, date, period, rain):
    bounds=PERIODS[period]
    models=[v for v in beach['marine_models'].values() if v.get('ok')]
    weather=beach['weather'].get('data') if beach.get('weather',{}).get('ok') else None
    extras=beach.get('marine_extras',{})
    extras=extras.get('data') if extras.get('ok') else None
    expected=bounds[1]-bounds[0]
    def marine(name):
        complete=[values for m in models if len(values:=period_values(m['data'],name,date,bounds))==expected]
        return median([median(values) for values in complete]),len(complete)
    def meteo(name):
        values=period_values(weather,name,date,bounds) if weather else []
        return median(values) if len(values)==expected else None
    def extra(name): return median(period_values(extras,name,date,bounds)) if extras else None
    wave,wave_models=marine('wave_height'); period_s,period_models=marine('wave_period'); wave_dir,_=marine('wave_direction')
    wind=meteo('wind_speed_10m'); wind_dir=meteo('wind_direction_10m')
    missing=[name for name,value in (('wave_height',wave),('wave_period',period_s),('wind_speed_10m',wind)) if value is None]
    if missing:return None,missing
    reference=dt.datetime.fromisoformat(date).replace(tzinfo=ZoneInfo('Europe/Lisbon'))+dt.timedelta(hours=(bounds[0]+bounds[1])/2)
    rain72=rain_history(rain,reference); light=daylight(weather,date,bounds)
    if light['error'] is not None:return None,[light['error']]
    noncritical=[]
    if wave_dir is None:noncritical.append('wave_direction')
    if wind_dir is None:noncritical.append('wind_direction_10m')
    if rain72['amount_mm'] is None:noncritical.append('rain_mira_72h')
    return {
      'wave_offshore_m':round(wave,2),'effective_wave_m':round(wave,2),
      'wave_period_s':round(period_s,1),'wave_direction':direction_name(wave_dir),
      'wind_kmh':round(wind,1),'wind_direction':direction_name(wind_dir),
      'wind_gust_kmh':None if meteo('wind_gusts_10m') is None else round(meteo('wind_gusts_10m'),1),
      'water_temp_c':None if extra('sea_surface_temperature') is None else round(extra('sea_surface_temperature'),1),
      'current_kmh':None if extra('ocean_current_velocity') is None else round(extra('ocean_current_velocity'),2),
      'pressure_hpa':None if meteo('pressure_msl') is None else round(meteo('pressure_msl'),1),
      'cloud_pct':None if meteo('cloud_cover') is None else round(meteo('cloud_cover')),
      'rain_mira_72h_mm':rain72['amount_mm'],'rain_mira_72h':rain72,
      'daylight_minutes':light['minutes'],'daylight_fraction':light['fraction'],'sunrise':light['sunrise'],'sunset':light['sunset'],
      'model_count':min(wave_models,period_models),'coverage_expected_hours':expected,'data_origin_level':'consenso de modelos na coordenada',
      'primary_source':'Open-Meteo Marine/Weather; centros identificados em source_registry',
      'missing_observations':['rebentação na praia','visibilidade subaquática','acesso seguro','presença de peixe','legalidade local em tempo real'],
    },noncritical

def factor(fid,label,value,unit,score,weight,reason,source='Open-Meteo · consenso por coordenada'):
    return {'id':fid,'label':label,'value':value,'unit':unit,'score':round(clamp(score),2),'weight':weight,
            'impact':round(clamp(score)*weight,3),'source':source,'confidence':0.62,'reason':reason}

def surfcasting(date,bid,period,species,window,c,profile):
    h,p,w=c['wave_offshore_m'],c['wave_period_s'],c['wind_kmh']
    species_wave={'Geral':1.0,'Robalo':1.15,'Sargo':0.9,'Dourada':0.65}[species]
    light_fraction=c.get('daylight_fraction'); light=clamp(4+6*light_fraction) if light_fraction is not None else 5
    structure=profile[3]
    tide_score=7.5 if c.get('tide_phase')=='enchente' else 6.5
    factors=[
      factor('onda','Altura da onda',h,'m',optimum(h,species_wave,1.0),.23,'Faixa indicativa por espécie; altura offshore não é rebentação.'),
      factor('periodo','Período da onda',p,'s',optimum(p,11.5,8),.14,'Energia do mar; período longo também aumenta risco.'),
      factor('vento','Vento',w,'km/h',clamp(10-w*.27),.16,'Vento forte penaliza lançamento e leitura.'),
      factor('luz','Luz solar no período',c.get('daylight_minutes','ausente'),'min',light,.14,'Sobreposição calculada com nascer e pôr do sol recolhidos; não prova presença de peixe.'),
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
    h,p,w=c['wave_offshore_m'],c['wave_period_s'],c['wind_kmh']; light_fraction=c.get('daylight_fraction'); daylight=light_fraction is not None and light_fraction>=.75
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
        add('Luz',c.get('daylight_minutes','ausente'),'min',clamp((light_fraction or 0)*10),.1,'Sobreposição com nascer/pôr do sol; surf sem luz suficiente não é recomendado.')
        score=round(sum(x['impact'] for x in common['factors']),1) if daylight else None
        risky=not daylight or w>=35 or (level=='iniciante' and h>1.25)
        if risky and score is not None: score=min(score,3.0)
        return {**common,'score':score,'potential':score,'status':'Potencial indicativo' if score is not None else 'Evitar à noite','risky':risky,'reasons':['Altura, período, vento e luz avaliados sem observar bancos ou agueiros.']}
    if kind=='spinning':
        add('Espuma / mar útil',h,'m',optimum(h,.85,.95),.3,'Mar moderado pode criar espuma; não prova peixe.')
        add('Período',p,'s',optimum(p,11.3,8),.15,'Período longo aumenta ressaca.')
        add('Vento',w,'km/h',clamp(10-w*.28),.2,'Controlo da amostra.')
        add('Luz',c.get('daylight_minutes','ausente'),'min',clamp(5+5*(light_fraction or 0)),.2,'Luz calculada; transições mantêm-se uma heurística explícita.')
        add('Estrutura provável',profile[2],'',profile[3],.15,'Estrutura estática não observada nesta recolha.')
        score=round(sum(x['impact'] for x in common['factors']),1); risky=h>=1.25 or w>=35
        return {**common,'score':min(score,5) if risky else score,'potential':score,'status':'Cuidado nas rochas' if risky else 'Potencial indicativo','risky':risky,'reasons':['Combinação determinística de mar, vento, luz e perfil estático.']}
    if kind=='sub':
        add('Mar na entrada',h,'m',clamp(10-h*7.8),.34,'Menos ondulação pode ajudar, sem medir visibilidade.')
        add('Período / ressaca',p,'s',clamp(10-max(0,p-8)*1.25),.22,'Movimento junto a pedra.')
        add('Vento',w,'km/h',clamp(10-w*.34),.2,'Condições de superfície.')
        add('Fundo provável',profile[2],'',profile[3],.09,'Sem mapa submerso validado.')
        add('Visibilidade real','ausente','',0,.15,'Dado crítico não medido; a nota final fica indisponível.')
        potential=round(sum(x['impact'] for x in common['factors']),1); safe_light=light_fraction is not None and light_fraction>=.95; risky=not safe_light or h>=.85 or p>=14 or w>=25
        return {**common,'score':None,'potential':potential,'status':'Visibilidade e segurança por validar','risky':risky,
          'reasons':['O potencial usa apenas mar e vento; não existe medição de visibilidade.'],
          'limits':common['limits']+['Sem visibilidade real, entrada/saída e zona legal confirmadas, não é atribuída nota final.','A janela exige luz integral segundo nascer e pôr do sol recolhidos.']}
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

def generate(source_dir: Path, previous: Path|None=None, days=16):
    manifest=json.loads((source_dir/'manifest.json').read_text(encoding='utf-8'))
    beach_data={bid:json.loads((source_dir/f'{bid}.json').read_text(encoding='utf-8')) for bid in manifest['beaches']}
    rain=json.loads((source_dir/'rain_mira.json').read_text(encoding='utf-8'))
    tides=load_tides(ROOT/'data'/'tides_sines_2026_11.json')
    candidate_dates=sorted({t[:10] for b in beach_data.values() for m in b['marine_models'].values() if m.get('ok') for t in (m.get('data',{}).get('hourly',{}).get('time') or [])})
    today=dt.datetime.now(ZoneInfo('Europe/Lisbon')).date().isoformat(); candidate_dates=[d for d in candidate_dates if d>=today][:min(16,days)]
    if not candidate_dates: raise ValueError('fontes sem datas futuras válidas')
    beaches={}
    for bid,b in beach_data.items():
        name,profile,bottom,structure=PROFILES[bid]
        beaches[bid]={'name':name,'lat':b['coordinate_requested']['lat'],'lon':b['coordinate_requested']['lon'],'profile':profile,'depth':'Não medida nesta recolha','bottom':bottom,'structure':structure,'exposure':None,'best_for':[],'where':'Confirmar no local.','ideal':'Potencial calculado por modelos; validar condições reais.','avoid':'Não usar a nota como autorização ou garantia de segurança.','rig':'Sem recomendação automática de montagem.'}
    evaluations=[]; activities=[]; published_dates=[]; coverage_gaps=[]
    for date in candidate_dates:
      date_conditions={}; date_gaps=[]
      for bid,b in beach_data.items():
       for period,bounds in PERIODS.items():
        c,missing=consensus(b,date,period,rain)
        if c is None: date_gaps.append({'date':date,'beach_id':bid,'period':period,'missing':missing});continue
        if missing: c['noncritical_gaps']=missing
        window=f'{bounds[0]:02d}:00–{bounds[1]%24:02d}:00'; tide=tide_for(tides,date,(bounds[0]+bounds[1])/2)
        if tide: c.update({'tide_phase':tide['phase'],'tide_low_height_m':tide['low_height'],'tide_range_m':tide['range'],'tide_low_time':tide['low_time'],'tide_low_date':tide['low_date'],'tide_previous_extreme':tide['previous_extreme'],'tide_next_extreme':tide['next_extreme'],'tide_source':tide['url']})
        date_conditions[(bid,period)]=(c,window)
      if date_gaps:
        coverage_gaps.extend(date_gaps);continue
      published_dates.append(date)
      for bid,b in beach_data.items():
       profile=PROFILES[bid]
       for period in PERIODS:
        c,window=date_conditions[(bid,period)]
        if bid in ACTIVITY_BEACHES['surfcasting']:
            evaluations.extend(surfcasting(date,bid,period,s,window,dict(c),profile) for s in SPECIES)
        for kind in ('surf','spinning','sub','mare'):
            eligible=ACTIVITY_BEACHES[kind] is None or bid in ACTIVITY_BEACHES[kind]
            if not eligible: continue
            if kind=='surf': activities.extend(activity(date,bid,period,window,dict(c),profile,kind,lvl) for lvl in SURF_LEVELS)
            else: activities.append(activity(date,bid,period,window,dict(c),profile,kind))
    if len(beaches)!=14 or not evaluations: raise ValueError('cobertura insuficiente para gerar previsão: '+json.dumps(coverage_gaps[:3],ensure_ascii=False))
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
      'source_failures':manifest.get('source_failures',[]),'automation':{'version':2,'source_snapshot_generated_at':manifest.get('generated_at_utc'),'forecast_days':len(published_dates),'available_dates':published_dates,'candidate_dates':candidate_dates,'coverage_gaps':coverage_gaps,'method':'medianas por período e centro com cobertura horária completa; regras e pesos preservados','human_equivalence_claimed':False}}
    if previous and previous.exists():
        old=json.loads(previous.read_text(encoding='utf-8')); old_scores=[e['score'] for e in old.get('evaluations',[]) if isinstance(e.get('score'),(int,float))]
        new_scores=[e['score'] for e in evaluations]
        result['automation']['comparison_with_previous']={'previous_generated_at':old.get('generated_at'),'previous_evaluations':len(old.get('evaluations',[])),'new_evaluations':len(evaluations),'previous_mean_score':round(statistics.mean(old_scores),2) if old_scores else None,'new_mean_score':round(statistics.mean(new_scores),2),'equivalence_demonstrated':False,'note':'Horizontes e fontes diferem; comparação é diagnóstico, não validação contra verdade observada.'}
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('source_dir',type=Path); parser.add_argument('output',type=Path); parser.add_argument('--previous',type=Path); parser.add_argument('--days',type=int,default=16)
    args=parser.parse_args(); forecast=generate(args.source_dir,args.previous,args.days); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(forecast,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); print(json.dumps({'output':str(args.output),'beaches':len(forecast['beaches']),'evaluations':len(forecast['evaluations']),'activity_evaluations':len(forecast['activity_evaluations'])}))
if __name__=='__main__': main()

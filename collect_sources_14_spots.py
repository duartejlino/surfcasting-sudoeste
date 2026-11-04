#!/usr/bin/env python3
"""Recolha de dados brutos para o Mar Sudoeste (não calcula recomendações).

API pública Open-Meteo Marine + Weather e IPMA. Usa apenas standard library.
Guarda valores e falhas sem inventar dados. As previsões do passado são saídas
modelo (hindcast), NÃO observações instrumentais.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime as dt
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'data' / 'source_snapshots' / 'latest'
BEACHES = {
  'santo-andre': (38.11432,-8.79823,'Costa de Santo André'),
  'sao-torpes': (37.92579,-8.80752,'São Torpes'),
  'porto-covo': (37.85721,-8.79361,'Praia Grande de Porto Covo'),
  'aivados': (37.806233,-8.796916,'Praia dos Aivados'),
  'malhao': (37.786833,-8.80215,'Praia do Malhão'),
  'furnas-mira': (37.716078,-8.786874,'Furnas / Foz do Mira'),
  'samoqueira': (37.86728,-8.79315,'Samoqueira'),
  'areao': (38.008139,-8.845139,'Praia do Areão'),
  'morgavel': (37.907278,-8.799722,'Praia de Morgavel'),
  'vieirinha': (37.89583,-8.79751,'Praia da Vieirinha / Vale Figueiros'),
  'burrinho': (37.878237,-8.795806,'Praia do Burrinho'),
  'ilha-pessegueiro': (37.835324,-8.790786,'Praia da Ilha do Pessegueiro'),
  'patacho': (37.725596,-8.792988,'Praia do Patacho · Milfontes'),
  'farol-milfontes': (37.71849,-8.79046,'Praia do Farol · Milfontes'),
}
BASIN = {
  'santa-clara-a-velha': (37.512,-8.476),
  'odemira': (37.598,-8.639),
  'sao-luis': (37.715,-8.664),
}
MODELS = {
  'ncep_gfswave016': 'NOAA NCEP GFS Wave (0,16 graus)',
  'ecmwf_wam': 'ECMWF WAM (~9 km)',
  'dwd_ewam': 'DWD EWAM (~5 km)',
  'meteofrance_wave': 'Météo-France MFWAM (~8 km)',
}
WAVE_GROUPS = [
  'wave_height,wave_direction,wave_period,wave_peak_period,swell_wave_height,swell_wave_direction,swell_wave_period,secondary_swell_wave_height,secondary_swell_wave_direction,secondary_swell_wave_period',
  'wave_height,wave_direction,wave_period,wave_peak_period,swell_wave_height,swell_wave_direction,swell_wave_period',
  'wave_height,wave_direction,wave_period',
]
EXTRAS = [
  'sea_surface_temperature,ocean_current_velocity,ocean_current_direction,sea_level_height_msl',
  'sea_surface_temperature,sea_level_height_msl',
  'sea_surface_temperature',
]
WEATHER_VARS = 'wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl,cloud_cover,precipitation,temperature_2m'
API_MARINE = 'https://marine-api.open-meteo.com/v1/marine'
API_WEATHER = 'https://api.open-meteo.com/v1/forecast'
API_IPMA = 'https://api.ipma.pt/open-data/forecast/oceanography/daily/hp-daily-sea-forecast-day{}.json'
UTC = dt.timezone.utc
NOW = lambda: dt.datetime.now(UTC).isoformat(timespec='seconds')


def make_url(endpoint: str, params: dict) -> str:
    return endpoint + '?' + urllib.parse.urlencode(params, safe=',')


def fetch_json(url: str) -> dict:
    err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent':'MarSudoeste/1.0 (personal non-commercial forecast research)',
                'Accept': 'application/json'})
            with urllib.request.urlopen(req,timeout=25) as rsp:
                raw = rsp.read(2_400_000)
                if len(raw) >= 2_400_000:
                    raise ValueError('resposta demasiado grande')
            data=json.loads(raw)
            if not isinstance(data,dict) or data.get('error'):
                raise ValueError('API: '+str(data.get('reason', 'resposta não é objeto'))[:400])
            return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError,
                json.JSONDecodeError) as ex:
            err=ex
            if isinstance(ex, urllib.error.HTTPError) and ex.code in (400,401,403,404):
                break
            if attempt < 2:
                time.sleep((attempt+1)*1.2 + random.random()*0.3)
    raise RuntimeError(str(err)[:450])


def compact_api(response:dict) ->dict:
    # Sem fabricar dados em falta ou utilizar tempo de geração da API como hora do modelo.
    return {k:response.get(k) for k in ('latitude','longitude','timezone','utc_offset_seconds','hourly_units','hourly','daily_units','daily') if k in response}


def coverage(data: dict, required='wave_height')->dict:
    h=data.get('hourly') or {}
    times=h.get('time',[])
    # Quando a API sufixa o nome da variável com o identificador do modelo,
    # identificamos a chave presente sem alterar o conteúdo bruto.
    resolved = required if required in h else next((k for k in h if k.startswith(required+'_')), None)
    vals=h.get(resolved,[]) if resolved else []
    valid=[i for i,v in enumerate(vals) if v is not None and i<len(times)]
    return {'variable':required,'resolved_json_key':resolved,'valid_points':len(valid),
            'first_valid':times[valid[0]] if valid else None,
            'last_valid':times[valid[-1]] if valid else None,
            'requested_hours':len(times),
            'sampled_model_grid':{'latitude':data.get('latitude'),'longitude':data.get('longitude')}}


def get_model(beach, coords, model, fetch=fetch_json):
    lat,lon,_=coords
    failures=[]
    for vars in WAVE_GROUPS:
        params={'latitude':lat,'longitude':lon,'hourly':vars,'timezone':'Europe/Lisbon',
                'forecast_days':16,'past_days':3,'cell_selection':'sea','models':model}
        url=make_url(API_MARINE,params)
        try:
            result=compact_api(fetch(url))
            stat=coverage(result)
            if stat['valid_points']<12:
                failures.append({'variables':vars,'issue':'menos de 12 horas válidas'})
                continue
            return {'ok':True,'model':model,'centre':MODELS[model],
                    'retrieved_at_utc':NOW(),'request_url':url,'used_variables':vars.split(','),
                    'coverage':stat,'data':result,
                    'caveat':'Uma coordenada não garante resolução de uma praia; célula marítima retornada está registada.'}
        except Exception as ex:
            failures.append({'variables':vars,'issue':str(ex)[:250]})
    return {'ok':False,'model':model,'centre':MODELS[model],
            'retrieved_at_utc':NOW(),'attempts':failures,'data':None}


def get_extras(beach,coords, fetch=fetch_json):
    lat,lon,_=coords
    failures=[]
    for vars in EXTRAS:
        url=make_url(API_MARINE,{'latitude':lat,'longitude':lon,'hourly':vars,
                        'timezone':'Europe/Lisbon','forecast_days':16,'past_days':3,
                        'cell_selection':'sea'})
        try:
            data=compact_api(fetch(url))
            if data.get('hourly',{}).get('time'):
                return {'ok':True,'retrieved_at_utc':NOW(),'request_url':url,
                        'used_variables':vars.split(','),'data':data,
                        'caveat':'Altura do nível médio do mar (MSL), NÃO zero hidrográfico. Não usar para altura oficial da baixa-mar.'}
        except Exception as ex:failures.append({'variables':vars,'issue':str(ex)[:250]})
    return {'ok':False,'retrieved_at_utc':NOW(),'attempts':failures,'data':None}


def get_weather(coords,fetch=fetch_json, basindata=False):
    lat,lon=coords[:2]
    params={'latitude':lat,'longitude':lon,'hourly':'precipitation' if basindata else WEATHER_VARS,
            'timezone':'Europe/Lisbon','forecast_days':16,'past_days':3}
    if not basindata: params['daily']='sunrise,sunset'
    url=make_url(API_WEATHER,params)
    try:
        data=compact_api(fetch(url))
        if not (data.get('hourly') or {}).get('time'):
            raise ValueError('sem série horária')
        return {'ok':True,'retrieved_at_utc':NOW(),'request_url':url,'data':data,
                'coverage':coverage(data,'precipitation' if basindata else 'wind_speed_10m')}
    except Exception as ex:return {'ok':False,'retrieved_at_utc':NOW(),'request_url':url,
                                  'error':str(ex)[:450],'data':None}


def get_ipma(d,fetch=fetch_json):
    url=API_IPMA.format(d)
    try:
        body=fetch(url)
        matches=[]
        for row in body.get('data',[]):
            try: ident=int(row.get('globalIdLocal',-1))
            except Exception: ident=-1
            if ident==1151326: matches.append(row)
        # Ainda que o ID de Sines mude, não selecionar uma estação de outra região por engano.
        local_today=dt.datetime.now(dt.timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Europe/Lisbon')).date()
        expected=(local_today+dt.timedelta(days=d)).isoformat()
        is_current=(body.get('forecastDate')==expected)
        return {'ok':bool(matches) and is_current,'retrieved_at_utc':NOW(),'source':'IPMA, previsão diária zona Sines',
                'request_url':url,'forecastDate':body.get('forecastDate'),
                'dataUpdate':body.get('dataUpdate'),'station_id':1151326,
                'sines_row':matches[0] if matches else None,
                'expected_forecastDate':expected,
                'error': ('Estação 1151326 não encontrada; sem validação oficial' if not matches else (None if is_current else 'Data IPMA divergente da data pedida; não usar como validação atual'))}
    except Exception as ex:
        return {'ok':False,'retrieved_at_utc':NOW(),'request_url':url,'error':str(ex)[:450]}


def collect(fetch=fetch_json):
    start=NOW()
    jobs={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for b,coords in BEACHES.items():
            for model in MODELS:
                jobs[('model',b,model)]=pool.submit(get_model,b,coords,model,fetch)
            jobs[('extras',b,None)]=pool.submit(get_extras,b,coords,fetch)
            jobs[('weather',b,None)]=pool.submit(get_weather,coords,fetch)
        for b,coords in BASIN.items():
            jobs[('basin',b,None)]=pool.submit(get_weather,coords,fetch,True)
        for d in range(3):jobs[('ipma',str(d),None)]=pool.submit(get_ipma,d,fetch)
        results={key:f.result() for key,f in jobs.items()}
    beaches={}
    for b,(lat,lon,name) in BEACHES.items():
        beaches[b]={
           'beach_id':b,'name':name,'coordinate_requested':{'lat':lat,'lon':lon},
           'marine_models':{m:results[('model',b,m)] for m in MODELS},
           'marine_extras':results[('extras',b,None)],
           'weather':results[('weather',b,None)],
           'data_origin':'modelo por coordenada; NÃO sensor ou observação na praia',
        }
    basin={b:results[('basin',b,None)] for b in BASIN}
    ipma={str(d):results[('ipma',str(d),None)] for d in range(3)}
    good_weather=sum(int(b['weather']['ok']) for b in beaches.values())
    good_beaches=sum(any(m['ok'] for m in b['marine_models'].values()) for b in beaches.values())
    if good_weather < 4 or good_beaches < 4:
        raise RuntimeError('Falha crítica de recolha: apenas '+str(good_weather)+
                           ' praias com tempo e '+str(good_beaches)+
                           ' com mar; mantenho fotografia anterior sem substituição.')
    failed=[]
    manifest={
      'schema_version':'mar-sudoeste-raw-sources-v1',
      'generated_at_utc':NOW(),'requested_at_utc':start,
      'role':'DADOS BRUTOS / apoio à análise manual no ChatGPT; NÃO É forecast.json da app',
      'tz':'Europe/Lisbon','forecast_days_requested':16,'past_days_requested':3,
      'past_days_are':'reconstrução/modelo, não observação instrumental de boia',
      'centres':MODELS,'beaches':{},
      'availability':{'weather_beaches':good_weather,'marine_beaches':good_beaches,
                      'of_total_beaches':len(BEACHES),'basin_rain_points':sum(v['ok'] for v in basin.values()),
                      'ipma_days':sum(v['ok'] for v in ipma.values())},
      'limitations':[
        'A fase e a amplitude oficial da maré devem ser calculadas na tabela do IH/Sines, não a partir do nível MSL do Open-Meteo.',
        'Surfline, Surfnerd e Windguru são confirmações manuais opcionais; este recolhedor NÃO faz scraping desses sites.',
        'Células offshore e resolução dos modelos não equivalem à rebentação, visibilidade ou segurança no spot.',
        'Confrontar as mesmas variáveis/unidades e horas. A hora de recolha não é a inicialização da corrida do modelo.',
        'Restrições do PNSACV, licenças, interdições de bivalves e condições de entrada requerem verificação local.',
        'A fonte gratuita Open-Meteo requer uso não comercial, fair use e atribuição (CC BY 4.0).'
      ],
      'attribution':{'Open-Meteo':'https://open-meteo.com/',
        'NOAA NCEP':'https://www.ncei.noaa.gov/',
        'ECMWF':'https://www.ecmwf.int/',
        'DWD':'https://www.dwd.de/',
        'Météo-France':'https://meteofrance.com/',
        'IPMA':'https://api.ipma.pt/'},
    }
    for b,info in beaches.items():
        cov={m:info['marine_models'][m]['coverage'] if info['marine_models'][m]['ok'] else None for m in MODELS}
        manifest['beaches'][b]={
          'name':info['name'],'file':f'data/source_snapshots/latest/{b}.json',
          'model_coverage':cov,
          'weather_coverage':info['weather'].get('coverage') if info['weather']['ok'] else None,
          'returned_grid':{m:(v['coverage']['sampled_model_grid'] if v['ok'] else None)
                            for m,v in info['marine_models'].items()},
          'status':'completo' if all(v['ok'] for v in info['marine_models'].values()) and info['weather']['ok'] else 'parcial'
        }
        for m,v in info['marine_models'].items():
            if not v['ok']:failed.append({'beach':b,'source':m,'error':v.get('attempts',[])})
        if not info['weather']['ok']:failed.append({'beach':b,'source':'weather','error':info['weather'].get('error')})
    for b,v in basin.items():
        if not v['ok']:failed.append({'rain_basin_point':b,'source':'weather','error':v.get('error')})
    for day,v in ipma.items():
        if not v['ok']:failed.append({'ipma_day':day,'source':'ipma','error':v.get('error')})
    manifest['source_failures']=failed
    OUT.mkdir(parents=True,exist_ok=True)
    # As outras fotografias são preservadas se esta recolha falhar antes deste ponto.
    for b,info in beaches.items():
        (OUT/f'{b}.json').write_text(json.dumps(info,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (OUT/'rain_mira.json').write_text(json.dumps({'points':basin,'region':'Bacia do Mira; só indicador de chuva, não caudal medido'},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (OUT/'ipma_sines.json').write_text(json.dumps(ipma,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'generated_at_utc':manifest['generated_at_utc'],
      'availability':manifest['availability'],'failed':len(failed),'output':str(OUT)},ensure_ascii=False))
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',default=None,help='Pasta de destino, opcional')
    args=p.parse_args()
    global OUT
    if args.out:OUT=Path(args.out).resolve()
    try:collect()
    except Exception as ex:
        print('ERRO: '+str(ex),file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':sys.exit(main())

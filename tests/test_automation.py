from __future__ import annotations
import datetime as dt, hashlib, json, tempfile, unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

import collect_sources_14_spots as collector
from automation.generate_forecast import PERIODS, PROFILES, generate, load_tides, rain_history, tide_for
from automation.validate_forecast import validate

def hourly(variable, date, value):
    times=[f'{date}T{hour:02d}:00' for hour in range(24)]
    return {'latitude':38.0,'longitude':-8.8,'hourly':{'time':times,variable:[value]*24}}

def make_sources(root: Path, missing_wave=False, days=1):
    start=dt.datetime.now(dt.timezone.utc).date(); dates=[(start+dt.timedelta(days=i)).isoformat() for i in range(days)]; today=dates[0]
    def series(variable,value):
        times=[f'{date}T{hour:02d}:00' for date in dates for hour in range(24)]
        return {'latitude':38.0,'longitude':-8.8,'hourly':{'time':times,variable:[value]*len(times)}}
    beaches={}; failures=[]
    for bid,(lat,lon,name) in collector.BEACHES.items():
        models={}
        for index,model in enumerate(collector.MODELS):
            data=series('wave_height',1.0+index*.05); count=len(data['hourly']['time'])
            data['hourly']['wave_period']=[11]*count; data['hourly']['wave_direction']=[315]*count
            if missing_wave and bid=='santo-andre': data['hourly']['wave_height']=[None]*count
            models[model]={'ok':True,'retrieved_at_utc':today+'T00:00:00+00:00','request_url':'https://marine-api.open-meteo.com/test','coverage':{'valid_points':count},'data':data}
        weather=series('wind_speed_10m',10); count=len(weather['hourly']['time']); weather['hourly']['wind_direction_10m']=[45]*count; weather['hourly']['wind_gusts_10m']=[15]*count; weather['hourly']['pressure_msl']=[1015]*count; weather['hourly']['cloud_cover']=[30]*count
        weather['daily']={'time':dates,'sunrise':[date+'T07:00' for date in dates],'sunset':[date+'T17:30' for date in dates]}
        extra=series('sea_surface_temperature',17); extra['hourly']['ocean_current_velocity']=[.2]*count
        body={'beach_id':bid,'name':name,'coordinate_requested':{'lat':lat,'lon':lon},'marine_models':models,'marine_extras':{'ok':True,'data':extra},'weather':{'ok':True,'retrieved_at_utc':today+'T00:00:00+00:00','request_url':'https://api.open-meteo.com/test','coverage':{'valid_points':24},'data':weather}}
        (root/f'{bid}.json').write_text(json.dumps(body),encoding='utf-8'); beaches[bid]={'name':name}
    rain={'points':{'odemira':{'ok':True,'data':series('precipitation',0)}}}; (root/'rain_mira.json').write_text(json.dumps(rain),encoding='utf-8')
    manifest={'generated_at_utc':today+'T00:00:00+00:00','beaches':beaches,'source_failures':failures}; (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    return today

class RetryTests(unittest.TestCase):
    def test_retryable_status_set_is_exact(self):
        self.assertEqual(collector.RETRYABLE_HTTP,{408,429,500,502,503,504})

    def test_retryable_http_uses_four_attempts_and_progressive_delays(self):
        error=HTTPError('https://example.test',503,'temporary',{},None)
        response=mock.MagicMock(); response.__enter__.return_value.read.return_value=b'{}'
        with mock.patch('urllib.request.urlopen',side_effect=[error,error,error,response]) as request, mock.patch('time.sleep') as sleep:
            self.assertEqual(collector.fetch_json('https://example.test'),{})
        self.assertEqual(request.call_count,4); self.assertEqual([c.args[0] for c in sleep.call_args_list],[2,5,10])

    def test_network_failure_is_retried_but_non_retryable_http_is_not(self):
        response=mock.MagicMock(); response.__enter__.return_value.read.return_value=b'{}'
        with mock.patch('urllib.request.urlopen',side_effect=[URLError('reset'),response]) as request, mock.patch('time.sleep') as sleep:
            collector.fetch_json('https://example.test')
        self.assertEqual(request.call_count,2); sleep.assert_called_once_with(2)
        with mock.patch('urllib.request.urlopen',side_effect=HTTPError('https://example.test',404,'missing',{},None)) as request:
            with self.assertRaises(RuntimeError): collector.fetch_json('https://example.test')
        self.assertEqual(request.call_count,1)

class ForecastTests(unittest.TestCase):
    def test_generates_14_zones_five_modalities_six_periods_and_valid_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); date=make_sources(source)
            forecast=generate(source,Path('data/forecast.json'),days=1)
        self.assertEqual(len(forecast['beaches']),14)
        self.assertEqual({e['period'] for e in forecast['evaluations']},set(PERIODS))
        self.assertEqual({e['species'] for e in forecast['evaluations']},{'Geral','Robalo','Sargo','Dourada'})
        self.assertEqual({a['activity'] for a in forecast['activity_evaluations']},{'surf','spinning','sub','mare'})
        self.assertEqual({'surfcasting'}|{a['activity'] for a in forecast['activity_evaluations']},{'surfcasting','surf','spinning','sub','mare'})
        self.assertFalse(validate(forecast),validate(forecast))
        self.assertFalse(forecast['automation']['human_equivalence_claimed'])
        self.assertFalse(forecast['automation']['comparison_with_previous']['equivalence_demonstrated'])
        self.assertEqual(forecast['weights'],{'onda':.23,'periodo':.14,'vento':.16,'luz':.14,'fundo_estrutura':.18,'mare':.15})
        self.assertTrue(all(e['date']==date and 0<=e['score']<=10 for e in forecast['evaluations']))

    def test_missing_critical_wave_data_is_not_estimated(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); make_sources(source,missing_wave=True)
            with self.assertRaisesRegex(ValueError,'cobertura insuficiente'): generate(source,days=1)

    def test_sub_has_no_final_score_without_measured_visibility(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); make_sources(source); forecast=generate(source,days=1)
        sub=[a for a in forecast['activity_evaluations'] if a['activity']=='sub']
        self.assertTrue(sub); self.assertTrue(all(a['score'] is None for a in sub))
        self.assertTrue(all('Visibilidade' in a['status'] for a in sub))

    def test_failed_dry_run_does_not_replace_published_forecast(self):
        target=Path('data/forecast.json'); before=hashlib.sha256(target.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            result=__import__('subprocess').run([__import__('sys').executable,'automation/update_forecast.py','--dry-run','--source-dir',folder],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0); self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),before)

    def test_horizon_reaches_16_days_when_all_periods_are_covered(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); make_sources(source,days=16); forecast=generate(source,days=16)
        self.assertEqual(len(forecast['automation']['available_dates']),16)
        self.assertEqual(forecast['automation']['forecast_days'],16)
        self.assertFalse(forecast['automation']['coverage_gaps'])

    def test_incomplete_period_excludes_the_date_and_records_the_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); make_sources(source,days=2)
            path=source/'santo-andre.json'; body=json.loads(path.read_text()); body['weather']['data']['hourly']['wind_speed_10m'][0]=None; path.write_text(json.dumps(body))
            forecast=generate(source,days=2)
        self.assertEqual(len(forecast['automation']['available_dates']),1)
        self.assertTrue(any(g['beach_id']=='santo-andre' and g['period']=='Madrugada' and 'wind_speed_10m' in g['missing'] for g in forecast['automation']['coverage_gaps']))

    def test_rain_uses_previous_72_hours_and_does_not_sum_stations(self):
        zone=dt.timezone.utc; reference=dt.datetime(2026,11,10,12,tzinfo=zone); times=[(reference-dt.timedelta(hours=i)).isoformat() for i in range(71,-1,-1)]
        rain={'points':{'a':{'ok':True,'data':{'hourly':{'time':times,'precipitation':[1]*72}}},'b':{'ok':True,'data':{'hourly':{'time':times,'precipitation':[3]*72}}},'missing':{'ok':False}}}
        result=rain_history(rain,reference)
        self.assertEqual(result['station_totals_mm'],{'a':72.0,'b':216.0}); self.assertEqual(result['amount_mm'],144.0)
        self.assertEqual(result['missing_stations'],['missing']); self.assertIn('modelo',result['origin'])

    def test_twilight_is_not_treated_as_a_fully_daylight_period(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); date=make_sources(source); forecast=generate(source,days=1)
        row=next(a for a in forecast['activity_evaluations'] if a['date']==date and a['period']=='Anoitecer' and a['activity']=='surf')
        self.assertEqual(row['conditions']['daylight_minutes'],30); self.assertEqual(row['conditions']['daylight_fraction'],.25); self.assertIsNone(row['score'])

class TideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.tides=load_tides(Path('data/tides_sines_2026_11.json'))

    def test_before_low_is_ebb_and_after_low_is_flood(self):
        self.assertEqual(tide_for(self.tides,'2026-11-10',5)['phase'],'vazante')
        self.assertEqual(tide_for(self.tides,'2026-11-10',12)['phase'],'enchente')

    def test_near_low_and_high_are_named(self):
        self.assertEqual(tide_for(self.tides,'2026-11-10',8.7)['phase'],'perto da baixa-mar')
        self.assertEqual(tide_for(self.tides,'2026-11-10',14.9)['phase'],'perto da preia-mar')

    def test_consecutive_extremes_cross_midnight(self):
        before=tide_for(self.tides,'2026-11-15',22); after=tide_for(self.tides,'2026-11-16',1.5)
        self.assertEqual(before['phase'],'vazante'); self.assertEqual(before['low_date'],'2026-11-16')
        self.assertEqual(after['phase'],'enchente'); self.assertEqual(after['previous_extreme']['kind'],'low')

class WorkflowTests(unittest.TestCase):
    def test_workflow_has_minimal_write_permission_schedule_dispatch_and_concurrency(self):
        text=Path('.github/workflows/update-forecast.yml').read_text(encoding='utf-8')
        self.assertIn("cron: '17 */6 * * *'",text); self.assertIn('workflow_dispatch:',text); self.assertIn('contents: write',text)
        self.assertIn('cancel-in-progress: false',text); self.assertNotIn('pull-requests: write',text); self.assertNotIn('push:',text.split('permissions:')[0])
        self.assertIn('[skip ci]',text)

    def test_collector_uses_three_workers_and_requires_all_zones(self):
        text=Path('collect_sources_14_spots.py').read_text(encoding='utf-8')
        self.assertIn('ThreadPoolExecutor(max_workers=3)',text)
        self.assertIn('good_weather < len(BEACHES)',text)

    def test_service_worker_network_first_for_forecast_and_status(self):
        text=Path('sw.js').read_text(encoding='utf-8')
        self.assertIn("path.endsWith('/data/forecast.json')",text); self.assertIn("path.endsWith('/data/status.json')",text); self.assertIn("cache:'no-store'",text)
        self.assertIn("caches.match(key)",text); self.assertIn("c.put(key,copy)",text)

    def test_status_exposes_collection_calculation_publication_and_staleness(self):
        state=json.loads(Path('data/status.json').read_text(encoding='utf-8'))
        self.assertEqual(state['schema_version'],'mar-sudoeste-automation-status-v1')
        self.assertTrue({'collection','calculation','publication','last_valid_forecast_at','stale','incomplete_sources','errors'}<=state.keys())

    def test_automatic_forecast_is_default_and_manual_override_is_reversible(self):
        app=Path('app.js').read_text(encoding='utf-8'); html=Path('index.html').read_text(encoding='utf-8')
        self.assertIn("forecastSource:'automatic'",app); self.assertIn("localStorage.getItem(STORAGE_FORECAST_SOURCE)==='imported'",app)
        self.assertIn("localStorage.setItem(STORAGE_FORECAST_SOURCE,'imported')",app); self.assertIn("localStorage.setItem(STORAGE_FORECAST_SOURCE,'automatic')",app)
        self.assertIn('id="useAutomaticForecast"',html); self.assertIn('id="activeForecastSource"',html)

    def test_publication_is_confirmed_only_after_push(self):
        workflow=Path('.github/workflows/update-forecast.yml').read_text(encoding='utf-8'); marker=Path('automation/mark_published.py').read_text(encoding='utf-8')
        self.assertIn('Confirmar hora efetiva da publicação',workflow); self.assertIn("status':'published'",marker)

if __name__=='__main__': unittest.main()

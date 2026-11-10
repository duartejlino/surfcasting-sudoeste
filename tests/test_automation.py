from __future__ import annotations
import datetime as dt, hashlib, json, tempfile, unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

import collect_sources_14_spots as collector
from automation.generate_forecast import PERIODS, PROFILES, generate
from automation.validate_forecast import validate

def hourly(variable, date, value):
    times=[f'{date}T{hour:02d}:00' for hour in range(24)]
    return {'latitude':38.0,'longitude':-8.8,'hourly':{'time':times,variable:[value]*24}}

def make_sources(root: Path, missing_wave=False):
    today=dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone.utc).date().isoformat()
    beaches={}; failures=[]
    for bid,(lat,lon,name) in collector.BEACHES.items():
        models={}
        for index,model in enumerate(collector.MODELS):
            data=hourly('wave_height',today,1.0+index*.05)
            data['hourly']['wave_period']=[11]*24; data['hourly']['wave_direction']=[315]*24
            if missing_wave and bid=='santo-andre': data['hourly']['wave_height']=[None]*24
            models[model]={'ok':True,'retrieved_at_utc':today+'T00:00:00+00:00','request_url':'https://marine-api.open-meteo.com/test','coverage':{'valid_points':24},'data':data}
        weather=hourly('wind_speed_10m',today,10); weather['hourly']['wind_direction_10m']=[45]*24; weather['hourly']['wind_gusts_10m']=[15]*24; weather['hourly']['pressure_msl']=[1015]*24; weather['hourly']['cloud_cover']=[30]*24
        extra=hourly('sea_surface_temperature',today,17); extra['hourly']['ocean_current_velocity']=[.2]*24
        body={'beach_id':bid,'name':name,'coordinate_requested':{'lat':lat,'lon':lon},'marine_models':models,'marine_extras':{'ok':True,'data':extra},'weather':{'ok':True,'retrieved_at_utc':today+'T00:00:00+00:00','request_url':'https://api.open-meteo.com/test','coverage':{'valid_points':24},'data':weather}}
        (root/f'{bid}.json').write_text(json.dumps(body),encoding='utf-8'); beaches[bid]={'name':name}
    rain={'points':{'odemira':{'ok':True,'data':hourly('precipitation',today,0)}}}; (root/'rain_mira.json').write_text(json.dumps(rain),encoding='utf-8')
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
        self.assertTrue(all(e['date']==date and 0<=e['score']<=10 for e in forecast['evaluations']))

    def test_missing_critical_wave_data_is_not_estimated(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder); make_sources(source,missing_wave=True); forecast=generate(source,days=1)
        self.assertFalse(any(e['beach_id']=='santo-andre' for e in forecast['evaluations']))
        self.assertTrue(any('cobertura de surfcasting incompleta' in error for error in validate(forecast)))

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

if __name__=='__main__': unittest.main()

const assert=require('node:assert/strict');
const fs=require('node:fs');
const test=require('node:test');
const vm=require('node:vm');

const source=fs.readFileSync('collector.js','utf8');

function validHourly(key){
  const time=Array.from({length:12},(_,i)=>'2026-11-09T'+String(i).padStart(2,'0')+':00');
  return {hourly:{time,[key]:time.map(()=>1)}};
}

function responseFor(url){
  if(url.includes('api.ipma.pt'))return {data:[{globalIdLocal:1151326}],forecastDate:'2026-11-09',dataUpdate:'2026-11-09'};
  if(url.includes('precipitation')&&!url.includes('wind_speed_10m'))return validHourly('precipitation');
  if(url.includes('/forecast'))return validHourly('wind_speed_10m');
  if(url.includes('models=best_match'))return validHourly('sea_surface_temperature');
  return validHourly('wave_height');
}

function makeHarness(fetchImpl,{holdRetryTimers=false}={}){
  const ids=['collectorStart','collectorCancel','collectorDownload','collectorProgress','collectorSummary','collectorProgressLabel','collectorLog','collectorImportForecast','forecastFile','openCollectorBtn'];
  const elements=Object.fromEntries(ids.map(id=>[id,{id,textContent:'',hidden:false,disabled:false,value:0,listeners:{},addEventListener(type,fn){this.listeners[type]=fn},removeAttribute(name){delete this[name]},click(){return this.listeners.click?.()}}]));
  const retryDelays=[];
  const retryTimers=[];
  let timerId=0;
  const setTimeoutFake=(fn,delay)=>{
    const id=++timerId;
    if(delay===25000)return id;
    retryDelays.push(delay);
    if(holdRetryTimers)retryTimers.push(fn);else queueMicrotask(fn);
    return id;
  };
  let exportedBlob=null;
  const context={
    AbortController,Blob,Date,Error,JSON,Number,Object,Promise,Set,String,TypeError,URLSearchParams,
    clearTimeout(){},console,fetch:fetchImpl,queueMicrotask,setTimeout:setTimeoutFake,
    document:{getElementById:id=>elements[id]||null,querySelector:()=>null},
    window:{addEventListener(){}},
    URL:{createObjectURL(blob){exportedBlob=blob;return 'blob:test'},revokeObjectURL(){}}
  };
  vm.runInNewContext(source,context,{filename:'collector.js'});
  return {elements,retryDelays,retryTimers,get exportedBlob(){return exportedBlob}};
}

async function settle(harness){
  await harness.elements.collectorStart.click();
  await new Promise(resolve=>setImmediate(resolve));
}

test('recupera em quatro tentativas com esperas 2, 5 e 10 s e limita a concorrência a três',async()=>{
  let active=0,maxActive=0,targetCalls=0;
  const target='latitude=38.11432&longitude=-8.79823';
  const statuses=[408,429,500];
  const fetchImpl=async url=>{
    active++;maxActive=Math.max(maxActive,active);
    await Promise.resolve();
    active--;
    if(url.includes(target)&&url.includes('models=ncep_gfswave016')&&targetCalls<statuses.length){
      const status=statuses[targetCalls++];
      return {ok:false,status,json:async()=>({})};
    }
    return {ok:true,status:200,json:async()=>responseFor(url)};
  };
  const harness=makeHarness(fetchImpl);
  await settle(harness);
  assert.deepEqual(harness.retryDelays,[2000,5000,10000]);
  assert.equal(targetCalls,3);
  assert.ok(maxActive<=3,'concorrência observada: '+maxActive);
  assert.match(harness.elements.collectorLog.textContent,/Recuperadas após nova tentativa: santo-andre · ncep_gfswave016/);
  const output=JSON.parse(await harness.exportedBlob.text());
  assert.equal(output.schema_version,'mar-sudoeste-browser-source-snapshot-v1');
  assert.deepEqual(Object.keys(output).sort(),['beaches','errors','forecast_days_requested','generated_at_utc','ipma','notes','past_days_requested','rain_mira','schema_version'].sort());
});

test('repete falhas temporárias de rede e assinala pedidos ainda indisponíveis após quatro tentativas',async()=>{
  const target='latitude=38.11432&longitude=-8.79823';
  let networkCalls=0,unavailableCalls=0;
  const fetchImpl=async url=>{
    if(url.includes(target)&&url.includes('models=ncep_gfswave016')&&networkCalls++===0)throw new TypeError('ligação interrompida');
    if(url.includes(target)&&url.includes('/forecast')){
      unavailableCalls++;
      return {ok:false,status:[502,503,504,503][Math.min(unavailableCalls-1,3)],json:async()=>({})};
    }
    return {ok:true,status:200,json:async()=>responseFor(url)};
  };
  const harness=makeHarness(fetchImpl);
  await settle(harness);
  assert.equal(unavailableCalls,4);
  assert.match(harness.elements.collectorLog.textContent,/Recuperadas após nova tentativa: santo-andre · ncep_gfswave016/);
  assert.match(harness.elements.collectorLog.textContent,/Continuam indisponíveis: santo-andre · tempo/);
});

test('não marca como recuperada uma resposta repetida que falha a validação dos dados',async()=>{
  const target='latitude=38.11432&longitude=-8.79823';
  let targetCalls=0;
  const fetchImpl=async url=>{
    if(url.includes(target)&&url.includes('models=ncep_gfswave016')){
      targetCalls++;
      if(targetCalls===1)throw new TypeError('ligação interrompida');
      if(targetCalls===2)return {ok:true,status:200,json:async()=>({hourly:{time:['2026-11-09T00:00'],wave_height:[1]}})};
    }
    return {ok:true,status:200,json:async()=>responseFor(url)};
  };
  const harness=makeHarness(fetchImpl);
  await settle(harness);
  assert.equal(targetCalls,3,'deve usar o grupo de variáveis seguinte após rejeitar os dados insuficientes');
  assert.match(harness.elements.collectorLog.textContent,/Recuperadas após nova tentativa: nenhuma/);
  assert.doesNotMatch(harness.elements.collectorLog.textContent,/Recuperado · santo-andre · ncep_gfswave016/);
  const output=JSON.parse(await harness.exportedBlob.text());
  assert.equal(output.beaches['santo-andre'].marine_models.ncep_gfswave016.ok,true);
});

test('o botão cancelar interrompe imediatamente uma espera de nova tentativa',async()=>{
  const harness=makeHarness(async()=>({ok:false,status:503,json:async()=>({})}),{holdRetryTimers:true});
  const collection=harness.elements.collectorStart.click();
  while(harness.retryTimers.length<3)await Promise.resolve();
  harness.elements.collectorCancel.click();
  await collection;
  assert.equal(harness.elements.collectorSummary.textContent,'Recolha cancelada. Não foi exportada uma previsão incompleta.');
  assert.equal(harness.exportedBlob,null);
});

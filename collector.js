/* Mar Sudoeste v5.0 — recolha manual de fontes; NUNCA calcula nem importa notas IA. */
(()=>{'use strict';
  const BEACHES={
    'santo-andre':[38.11432,-8.79823], 'sao-torpes':[37.92579,-8.80752],
    'porto-covo':[37.85721,-8.79361], 'aivados':[37.806233,-8.796916],
    'malhao':[37.786833,-8.80215], 'furnas-mira':[37.716078,-8.786874],
    'samoqueira':[37.86728,-8.79315], 'areao':[38.008139,-8.845139],
    'morgavel':[37.907278,-8.799722], 'vieirinha':[37.89583,-8.79751],
    'burrinho':[37.878237,-8.795806], 'ilha-pessegueiro':[37.835324,-8.790786],
    'patacho':[37.725596,-8.792988], 'farol-milfontes':[37.71849,-8.79046]
  };
  const BASIN={'santa-clara-a-velha':[37.512,-8.476], 'odemira':[37.598,-8.639], 'sao-luis':[37.715,-8.664]};
  const MODELS=['ncep_gfswave016','ecmwf_wam','dwd_ewam','meteofrance_wave'];
  const WGROUPS=[
    'wave_height,wave_direction,wave_period,wave_peak_period,swell_wave_height,swell_wave_direction,swell_wave_period,secondary_swell_wave_height,secondary_swell_wave_direction,secondary_swell_wave_period',
    'wave_height,wave_direction,wave_period,wave_peak_period,swell_wave_height,swell_wave_direction,swell_wave_period',
    'wave_height,wave_direction,wave_period'
  ];
  const WEATHER='wind_speed_10m,wind_direction_10m,wind_gusts_10m,pressure_msl,cloud_cover,precipitation,temperature_2m';
  const $=id=>document.getElementById(id);
  const start=$('collectorStart'),cancel=$('collectorCancel'),download=$('collectorDownload'),progress=$('collectorProgress'),summary=$('collectorSummary'),counter=$('collectorProgressLabel'),log=$('collectorLog');
  if(!start || !cancel || !download || !progress || !summary || !counter || !log)return;
  let current=null,blobUrl=null;
  function makeUrl(base,args){return base+'?'+new URLSearchParams(args).toString()}
  function marine(c,model,vars){return makeUrl('https://marine-api.open-meteo.com/v1/marine',{latitude:c[0],longitude:c[1],hourly:vars,models:model,forecast_days:16,past_days:3,timezone:'Europe/Lisbon',cell_selection:'sea'})}
  function weather(c,basin){return makeUrl('https://api.open-meteo.com/v1/forecast',{latitude:c[0],longitude:c[1],hourly:basin?'precipitation':WEATHER,forecast_days:16,past_days:3,timezone:'Europe/Lisbon',...(basin?{}:{daily:'sunrise,sunset'})})}
  function coverage(data,key){
    const h=data?.hourly||{},k=Object.hasOwn(h,key)?key:Object.keys(h).find(x=>x.startsWith(key+'_'));
    if(!k)return {points:0,key:null,first:null,last:null};
    const t=Array.isArray(h.time)?h.time:[],vals=Array.isArray(h[k])?h[k]:[];
    let first=null,last=null,points=0;
    for(let i=0;i<t.length&&i<vals.length;i++)if(Number.isFinite(vals[i])){first??=t[i];last=t[i];points++}
    return {points,key:k,first,last};
  }
  const MAX_ATTEMPTS=4,RETRY_DELAYS=[2000,5000,10000],RETRYABLE_HTTP=new Set([408,429,500,502,503,504]);
  function waitForRetry(ms,run){
    return new Promise(resolve=>{
      if(run.cancelled){resolve(false);return}
      const waiter={timer:null,finish:ok=>{clearTimeout(waiter.timer);run.waiters.delete(waiter);resolve(ok)}};
      waiter.timer=setTimeout(()=>waiter.finish(!run.cancelled),ms);
      run.waiters.add(waiter);
    });
  }
  async function getJson(url,run,label=url){
    for(let attempt=1;attempt<=MAX_ATTEMPTS;attempt++){
      if(run.cancelled)throw new Error('Recolha cancelada');
      const controller=new AbortController();run.controllers.add(controller);
      let timedOut=false;
      const timeout=setTimeout(()=>{timedOut=true;controller.abort()},25000);
      try{
        const response=await fetch(url,{signal:controller.signal,cache:'no-store'});
        if(!response.ok){const error=new Error('HTTP '+response.status);error.httpStatus=response.status;throw error}
        const data=await response.json();
        if(data?.error)throw new Error(data.reason||'Erro API');
        if(attempt>1){
          run.recovered.push({source:label,attempts:attempt});
          render('Pedido recuperado após '+attempt+' tentativas · '+label);
        }
        return data;
      }catch(e){
        if(run.cancelled)throw new Error('Recolha cancelada');
        const retryable=RETRYABLE_HTTP.has(e?.httpStatus)||timedOut||e instanceof TypeError||(e?.name==='AbortError'&&timedOut);
        if(!retryable||attempt===MAX_ATTEMPTS){
          run.unavailable.push({source:label,attempts:attempt,error:String(e).slice(0,180)});
          render('Pedido indisponível após '+attempt+' tentativa'+(attempt===1?'':'s')+' · '+label+' · '+String(e).slice(0,120));
          throw e;
        }
        const delay=RETRY_DELAYS[attempt-1];
        render('Falha temporária · '+label+' · tentativa '+attempt+'/'+MAX_ATTEMPTS+'; nova tentativa em '+(delay/1000)+' s');
        const resumed=await waitForRetry(delay,run);
        if(!resumed)throw new Error('Recolha cancelada');
      }finally{clearTimeout(timeout);run.controllers.delete(controller)}
    }
    throw new Error('Pedido sem resultado');
  }
  async function getModel(c,m,run,id){
    const problems=[];
    for(const vars of WGROUPS){
      if(run.cancelled)break;
      const url=marine(c,m,vars);
      try{
        const data=await getJson(url,run,id+' · '+m+' · ondas ['+vars+']'),cvg=coverage(data,'wave_height');
        if(cvg.points<12)throw new Error('menos de 12 horas válidas');
        return {ok:true,url,retrieved_at_utc:new Date().toISOString(),coverage:cvg,data};
      }catch(e){problems.push({variables:vars,error:String(e).slice(0,210)})}
    }
    return {ok:false,problems};
  }
  async function getExtras(c,run,id){
    for(const vars of ['sea_surface_temperature,ocean_current_velocity,ocean_current_direction,sea_level_height_msl','sea_surface_temperature,sea_level_height_msl','sea_surface_temperature']){
      if(run.cancelled)break;
      const url=marine(c,'best_match',vars);
      try{const data=await getJson(url,run,id+' · extras ['+vars+']');if(data?.hourly?.time?.length)return {ok:true,url,data}}catch(e){}
    }
    return {ok:false,error:'SST / corrente / nível indisponíveis'};
  }
  async function getWeather(c,basin,run,id){
    const url=weather(c,basin);
    try{
      const data=await getJson(url,run,basin?'chuva Mira · '+id:'tempo · '+id);
      const cvg=coverage(data,basin?'precipitation':'wind_speed_10m');
      return {ok:cvg.points>=12,url,data,coverage:cvg};
    }catch(e){return {ok:false,url,error:String(e)}}
  }
  async function getIpma(day,run){
    const url='https://api.ipma.pt/open-data/forecast/oceanography/daily/hp-daily-sea-forecast-day'+day+'.json';
    try{
      const data=await getJson(url,run,'IPMA · dia '+day);
      const row=(data?.data||[]).find(x=>Number(x.globalIdLocal)===1151326)||null;
      return {ok:!!row,url,forecastDate:data.forecastDate,dataUpdate:data.dataUpdate,sines_row:row,error:row?null:'Estação de Sines não encontrada'};
    }catch(e){return {ok:false,url,error:String(e)}}
  }
  function render(logLine){
    if(logLine){const old=log.textContent||'';log.textContent=(old==='Ainda não começou.'?'':old+'\n')+logLine;const lines=log.textContent.split('\n');if(lines.length>75)log.textContent=lines.slice(-75).join('\n')}
  }
  function revoke(){if(blobUrl){URL.revokeObjectURL(blobUrl);blobUrl=null}download.hidden=true;download.removeAttribute('href')}
  async function collect(){
    if(current)return;
    revoke();
    const run={controllers:new Set(),waiters:new Set(),cancelled:false,recovered:[],unavailable:[]};current=run;
    start.disabled=true;cancel.hidden=false;progress.value=0;log.textContent='A iniciar…';
    const out={schema_version:'mar-sudoeste-browser-source-snapshot-v1',generated_at_utc:null,forecast_days_requested:16,past_days_requested:3,notes:[
      'Dados brutos por coordenada; NÃO são notas de pesca',
      'Past days = dados de modelo, NÃO observações',
      'Fonte IPMA diária não equivale a validação horária',
      'Nível do mar MSL não equivale à tabela oficial de marés IH/Sines',
      'Surfline, Surfnerd e Windguru só para consulta manual; não recolhidos pelo script'
    ],beaches:{},rain_mira:{},ipma:{},errors:[]};
    const jobs=[];
    for(const [id,c] of Object.entries(BEACHES)){
      out.beaches[id]={coordinate_requested:{latitude:c[0],longitude:c[1]},marine_models:{}};
      for(const m of MODELS)jobs.push({name:id+' · '+m,run:async()=>{const v=await getModel(c,m,run,id);out.beaches[id].marine_models[m]=v;return v.ok}});
      jobs.push({name:id+' · tempo',run:async()=>{const v=await getWeather(c,false,run,id);out.beaches[id].weather=v;return v.ok}});
      jobs.push({name:id+' · extras',run:async()=>{const v=await getExtras(c,run,id);out.beaches[id].extras=v;return v.ok}});
    }
    for(const [id,c] of Object.entries(BASIN))jobs.push({name:'Mira · '+id,run:async()=>{const v=await getWeather(c,true,run,id);out.rain_mira[id]=v;return v.ok}});
    for(let day=0;day<3;day++)jobs.push({name:'IPMA · dia '+day,run:async()=>{const v=await getIpma(day,run);out.ipma[''+day]=v;return v.ok}});
    let next=0,completed=0;
    progress.max=jobs.length;
    counter.textContent='0 / '+jobs.length+' consultas';
    summary.textContent='A recolher previsões em tempo real… Mantém esta página aberta.';
    log.textContent='Consultas de 14 zonas, 4 modelos oceânicos e meteorologia. Não são calculadas notas IA.';
    async function worker(){
      while(!run.cancelled && next<jobs.length){
        const job=jobs[next++];let good=false;
        try{good=await job.run()}catch(e){if(!run.cancelled)out.errors.push({source:job.name,error:String(e).slice(0,180)})}
        if(run.cancelled)break;
        if(!good)out.errors.push({source:job.name,error:'Indisponível ou incompleto'});
        completed++;progress.value=completed;
        counter.textContent=completed+' / '+jobs.length+' consultas · '+run.recovered.length+' pedidos recuperados · '+run.unavailable.length+' pedidos indisponíveis';
        if(completed===jobs.length||completed%5===0)summary.textContent='A recolher: '+completed+' de '+jobs.length+' fontes; '+run.recovered.length+' pedidos recuperados, '+run.unavailable.length+' ainda indisponíveis.';
        render(completed+'/'+jobs.length+' · '+job.name+' · '+(good?'OK':'indisponível'));
      }
    }
    try{
      await Promise.all(Array.from({length:3},()=>worker()));
      if(run.cancelled){summary.textContent='Recolha cancelada. Não foi exportada uma previsão incompleta.';render('Recolha cancelada.');return}
      const good=Object.values(out.beaches).filter(b=>b.weather?.ok && Object.values(b.marine_models).some(m=>m.ok)).length;
      if(good<7){summary.textContent='Falha: apenas '+good+' das 14 zonas têm dados suficientes. Não foi criado um ficheiro enganador. Confere os detalhes e tenta novamente.';render('Menos de 7 zonas com tempo e ondas.');return}
      out.generated_at_utc=new Date().toISOString();
      const blob=new Blob([JSON.stringify(out)],{type:'application/json'});
      blobUrl=URL.createObjectURL(blob);
      download.href=blobUrl;
      download.download='Mar_Sudoeste_FONTES_'+new Date().toISOString().slice(0,10)+'.json';
      download.hidden=false;
      summary.textContent=(good===14?'Recolha concluída!':'Recolha parcial concluída.')+' '+good+'/14 zonas com ondas e meteorologia; '+run.recovered.length+' pedidos recuperados, '+run.unavailable.length+' indisponíveis após as tentativas. Descarrega o JSON e envia-o ao ChatGPT para recalcular as notas.';
      render('Ficheiro de fontes pronto: '+good+' zonas / 14. Não é forecast IA.');
    }catch(e){summary.textContent='Não foi possível concluir a recolha: '+String(e).slice(0,160);render('Erro: '+String(e))}
    finally{current=null;start.disabled=false;cancel.hidden=true}
  }
  start.addEventListener('click',collect);
  cancel.addEventListener('click',()=>{if(!current)return;current.cancelled=true;current.controllers.forEach(c=>c.abort());for(const waiter of [...current.waiters])waiter.finish(false);summary.textContent='A cancelar as consultas…'});
  $('collectorImportForecast')?.addEventListener('click',()=>$('forecastFile')?.click());
  $('openCollectorBtn')?.addEventListener('click',()=>{const tab=document.querySelector('.tab[data-tab="collector"]');tab?.click()});
  window.addEventListener('pagehide',()=>{if(current){current.cancelled=true;current.controllers.forEach(c=>c.abort());for(const waiter of [...current.waiters])waiter.finish(false)}revoke()});
})();

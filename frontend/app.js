import {cubeSVG,cubeNet,COLORS,SOLVED} from './cube.js';
const $=id=>document.getElementById(id);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(x,d=1)=>x===null||x===undefined?'N/A':Number(x).toFixed(d);
const cost=b=>!b||!b.request_count?'No paid requests':b.known_cost_usd==null?`Cost unknown (${b.unknown_cost_requests} requests)`:`Known $${Number(b.known_cost_usd).toFixed(6)}${b.unknown_cost_requests?` + ${b.unknown_cost_requests} unknown`:''}`;
const colors=['#6252d4','#368fbb','#319d83','#d08a42'];
const questions=['Which model makes the fastest decisions?','Which has the highest solve rate?','Which finds the shortest solutions?','Is fastest also highest quality?','What would you choose in practice?'];
let config,puzzle,runId=null,busy=false,source=null,queue=[],pumping=false,selectedStats;
let activeTrials=[],displayMode='simulated';
async function api(path,options={}) {
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}
function notice(text,error=false){$('notice').textContent=text;$('notice').hidden=!text;$('notice').classList.toggle('error',error);}
function modeBadge(mode){displayMode=mode;$('mode-label').textContent=mode.toUpperCase();$('mode-label').classList.toggle('live',mode==='live');}
function setBusy(value){busy=value;for(const id of ['start','suite','generate','tier','seed','mode','puzzles'])$(id).disabled=value;$('abort').disabled=!value;}
function switchTab(name){for(const view of document.querySelectorAll('.view'))view.hidden=view.id!==name;for(const tab of document.querySelectorAll('.tab')){tab.classList.toggle('active',tab.dataset.tab===name);tab.setAttribute('aria-current',tab.dataset.tab===name?'page':'false');}document.body.classList.toggle('presentation-mode',name==='presentation');document.querySelector('.intro').hidden=name!=='arena';$('live-plan').hidden=name==='presentation'||$('mode').value!=='live';if(name!=='arena')refreshStats().catch(e=>notice(e.message,true));}
function decorate(container){
  for(const net of container.querySelectorAll('.net span')){net.style.background=COLORS[net.dataset.color];net.style.gridRow=net.dataset.row;net.style.gridColumn=net.dataset.col;}
}
function drawCards(state){
  activeTrials=config.models.map(()=>({state,moves:[],requests:[],status:'READY',elapsed_ms:null,rank:null}));
  $('cards').innerHTML=config.models.map((m,i)=>`<article class="race-card" id="card-${i}"><div class="card-header"><span class="agent-icon">0${i+1}</span><div><h3>${escape(m.label)}</h3><span class="category">${displayMode==='simulated'?'SIMULATED · ':''}${m.interface==='chat'?'LLM':'System-1'}<span id="provider-${i}">${displayMode==='live'?' · '+(i===1&&config.luna_provider==='openai'?'OpenAI':'OpenRouter'):''}</span></span></div><span class="rank" id="rank-${i}">—</span></div><div class="card-body"><div id="cube-${i}">${cubeSVG(state)}</div><div><div class="card-status" id="status-${i}">READY</div><div class="card-metrics"><div><strong id="moves-${i}">0<span>/30</span></strong><span>Moves · HTM</span></div><div><strong id="time-${i}">—</strong><span>Attempt · sec</span></div><div><strong id="latency-${i}">N/A</strong><span>API · ms</span></div></div><div class="track"><span id="track-${i}"></span></div><div class="current">Current move <b id="current-${i}">—</b></div><div class="card-error" id="error-${i}"></div></div></div><div class="move-history" id="history-${i}">No moves</div><details class="card-net"><summary>Six-face view</summary><div id="net-${i}">${cubeNet(state)}</div></details></article>`).join('');
  config.models.forEach((_,i)=>$(`card-${i}`).style.setProperty('--card-color',colors[i]));
  decorate($('cards'));
}
function drawTrial(i,t){
  activeTrials[i]=t;
  if(t.mode==='live'||displayMode==='live'){const req=t.requests||[];if(req.length)$(`provider-${i}`).textContent=' · '+(req.at(-1).provider_route==='direct_openai_decisions'?'OpenAI':'OpenRouter');}
  $(`cube-${i}`).innerHTML=cubeSVG(t.state);
  $(`net-${i}`).innerHTML=cubeNet(t.state);decorate($(`net-${i}`));
  $(`moves-${i}`).innerHTML=`${t.moves.length}<span>/30</span>`;
  $(`time-${i}`).textContent=t.elapsed_ms==null?'—':fmt(t.elapsed_ms/1000,2);
  const req=t.requests||[],lat=req.filter(q=>q.latency_ms!=null);
  $(`latency-${i}`).textContent=t.avg_api_latency_ms!=null?fmt(t.avg_api_latency_ms,0):lat.length?fmt(lat.reduce((a,b)=>a+b.latency_ms,0)/lat.length,0):'N/A';
  $(`current-${i}`).textContent=t.moves.at(-1)||'—';
  $(`history-${i}`).textContent=t.moves.join('  ')||'No moves';
  $(`status-${i}`).textContent=t.status.replaceAll('_',' ');
  $(`status-${i}`).classList.toggle('solved',t.status==='SOLVED');
  $(`rank-${i}`).textContent=t.rank?`#${t.rank}`:'—';
  $(`track-${i}`).style.width=`${t.moves.length/30*100}%`;
  $(`error-${i}`).textContent=t.error||'';
}
function showPuzzle(p){puzzle=p;$('scramble').textContent=p.scramble.join(' ');$('optimum').textContent=p.shortest_distance==null?'Exact reference: unproven · N/A':`Proven shortest: ${p.shortest_distance} HTM`;$('seed').value=p.seed;}
async function generate(){const p=await api(`/api/puzzle?seed=${Number($('seed').value)}&tier=${$('tier').value}`);showPuzzle(p);drawCards(p.initial_state);$('progress').textContent='Ready';notice('');}
function updatePlan(){
  const n=Number($('puzzles').value)||5, per=config.models.length*30*(1+config.retries);
  $('suite-plan').textContent=`${$('mode').value.toUpperCase()} · ${$('tier').selectedOptions[0].textContent.split(' · ')[0]} · seed ${$('seed').value} · ${n*4} trials`;
  $('persistent-billing').textContent=`Requests ${config.budget_used}/${config.budget_limit} · ${cost(config.billing)}`;
  $('recommended-cap').textContent=`Recommended cap: race ${per} · suite ${n*per} requests.`;
  $('live-plan').hidden=document.body.classList.contains('presentation-mode')||$('mode').value!=='live';
  $('call-plan').textContent=`Paid API requests · ${config.retries} retries · ${config.luna_provider==='openai'?'Luna: OpenAI; other models: OpenRouter.':'OpenRouter.'}`;
  $('budget').textContent=`Persistent requests: ${config.budget_used} / ${config.budget_limit} · ${cost(config.billing)}`;
}
async function start(kind){
  const mode=$('mode').value, count=kind==='suite'?Number($('puzzles').value):1;
  if(mode==='live'&&!$('paid-confirm').checked)throw new Error('Check the paid-call authorization in the plan below before starting live.');
  const approved=mode==='live'&&$('paid-confirm').checked;$('paid-confirm').checked=false;
  setBusy(true);$('abort').disabled=true;runId=null;modeBadge(mode);queue=[];
  try{
    const run=await api('/api/runs',{method:'POST',body:JSON.stringify({mode,kind,puzzles:count,tier:$('tier').value,seed:Number($('seed').value),call_cap:mode==='live'?Number($('call-cap').value):0,confirm_paid_calls:approved})});
    runId=run.id;$('abort').disabled=false;switchTab('arena');notice(mode==='simulated'?'SIMULATED · Synthetic results':'LIVE · Race running');
    $('paid-confirm').checked=false;connect(runId);
  }catch(e){setBusy(false);throw e;}
}
function connect(id){
  if(source)source.close();
  source=new EventSource(`/api/runs/${id}/events`);
  for(const type of ['race_started','move_decided','move_applied','model_finished','race_finished','error','aborted','run_finished']){
    source.addEventListener(type,e=>{if(!e.data)return;queue.push({type,data:JSON.parse(e.data)});pump();if(type==='run_finished'||type==='aborted')source.close();});
  }
  source.onerror=()=>{if(source.readyState===EventSource.CLOSED&&busy&&queue.length===0){api(`/api/runs/${id}`).then(r=>{if(r.status!=='RUNNING')finish(r.status);}).catch(e=>notice(e.message,true));}else if(busy)notice('Reconnecting to event stream…');};
}
async function pump(){
  if(pumping)return;pumping=true;
  try{while(queue.length){const {type,data}=queue.shift();
    if(type==='race_started'){modeBadge(data.mode);showPuzzle(data.puzzle);drawCards(data.puzzle.initial_state);$('progress').textContent=`Puzzle ${data.race+1} · seed ${data.puzzle.seed}`;}
    if(type==='move_applied'){
      const t=activeTrials[data.model];drawTrial(data.model,{...t,state:data.state,moves:[...t.moves,data.move],elapsed_ms:data.elapsed_ms,avg_api_latency_ms:data.avg_api_latency_ms,status:'RUNNING'});
      await new Promise(r=>setTimeout(r,110/Number($('speed').value)));
    }
    if(type==='model_finished')drawTrial(data.model,data.trial);
    if(type==='race_finished')data.trials.forEach((t,i)=>drawTrial(i,t));
    if(type==='error')notice(`${config.models[data.model].label}: ${data.status}. ${data.message}`,true);
    if(type==='run_finished'||type==='aborted')await finish(data.status);
  }}catch(e){notice(`Playback error: ${e.message}. Saved server results remain available.`,true);setBusy(false);}finally{pumping=false;}
}
async function finish(status){$('progress').textContent=status;notice(`${displayMode.toUpperCase()} · ${status.replaceAll('_',' ')}`);config=await api('/api/config');updatePlan();await refreshStats();setBusy(false);}
function presentAnswer(answer){
  if(answer==='Simulated UI fixtures are not evidence of OpenRouter model performance.')return 'Not evaluated with live models.';
  if(answer==='Insufficient live measured data; no model conclusion is supported.')return 'Insufficient live data.';
  return answer;
}
function tableRows(stats){return stats.rows.map(r=>`<tr><td><strong>${escape(r.label)}</strong><small>${r.solved}/${r.attempted} solved · ${r.planned} planned</small></td><td>${r.solve_rate==null?'N/A':fmt(r.solve_rate)+'%'}</td><td>${r.avg_api_latency_ms==null?'N/A':fmt(r.avg_api_latency_ms)+' ms'}<small>${r.request_count} requests</small></td><td>${r.avg_attempt_ms==null?'N/A':fmt(r.avg_attempt_ms/1000,2)+' s'}</td><td>${fmt(r.mean_moves_all,2)}</td><td>${fmt(r.mean_moves_solved,2)}</td><td>${fmt(r.mean_optimality_gap,2)}<small>${r.proven_solved_count} proven solved</small></td><td>${r.malformed||r.retries?`<small>${r.malformed} malformed · ${r.retries} retries</small>`:''}${r.billing?.request_count?`<small>${escape(cost(r.billing))}</small>`:''}<small>${escape(Object.entries(r.statuses).map(([k,v])=>`${k}: ${v}`).join(' · ')||'Not run')}</small></td></tr>`).join('');}
function bars(rows,key,unit,target,max){
  const measured=rows.map(r=>r[key]).filter(v=>v!=null), peak=max||Math.max(...measured,1);
  $(target).innerHTML=rows.map((r,i)=>`<div class="bar-row"><span>${escape(r.label)}</span><div class="bar-bg"><div class="bar-fill" id="${target}-${i}"></div></div><span class="bar-value">${r[key]==null?'N/A':fmt(r[key])+unit}</span></div>`).join('');
  rows.forEach((r,i)=>{$(`${target}-${i}`).style.width=`${(r[key]||0)/peak*100}%`;$(`${target}-${i}`).style.background=colors[i];});
}
async function refreshStats(){
  const mode=$('stats-mode').value,tier=$('stats-tier').value;
  const [stats,runs]=await Promise.all([api(`/api/stats?mode=${mode}&tier=${tier}`),api('/api/runs')]);selectedStats=stats;
  const trials=stats.rows.reduce((s,r)=>s+r.attempted,0),solved=stats.rows.reduce((s,r)=>s+r.solved,0);
  $('summary').innerHTML=[[stats.suite_count,'Saved suites'],[trials,'Completed attempts'],[solved,'Solved trials'],[mode==='live'?'LIVE':'SIMULATED','Evidence source']].map(([v,k])=>`<div class="tile"><strong>${v}</strong><span>${k}</span></div>`).join('');
  const tierLabel={primary:'Primary Benchmark',warmup:'Warm-up',extension:'Extension'}[tier];
  const puzzles=Math.max(0,...stats.rows.map(r=>r.planned));
  const context=`${mode.toUpperCase()} · ${tierLabel} · ${puzzles} ${puzzles===1?'Puzzle':'Puzzles'}${mode==='live'&&puzzles?' · '+(stats.request_policy?.luna_route?.provider==='OpenAI'?'Luna: OpenAI; others: OpenRouter':'OpenRouter'):''}`;
  $('table-caption').textContent=`${context}${mode==='simulated'?' · Synthetic results':''}${stats.excluded_policy_suites?` · ${stats.excluded_policy_suites} suites excluded (different settings)`:''}`;
  $('table-caption').title=stats.denominator;
  $('suite-billing').textContent=`Selected suites: ${stats.billing.request_count} requests · ${cost(stats.billing)}`;
  $('stats-rows').innerHTML=tableRows(stats);
  bars(stats.rows,'solve_rate','%','solve-chart',100);bars(stats.rows,'avg_api_latency_ms',' ms','latency-chart');
  $('answers').innerHTML=stats.analysis.map((a,i)=>`<li><strong>${questions[i]}</strong><br>${escape(presentAnswer(a))}</li>`).join('');
  $('slide-provenance').textContent=context;
  $('slide-note').textContent=`${mode==='simulated'?'Synthetic results; no model performance measured. ':trials?'Descriptive results; no significance claim. ':'No live results recorded. '}Solve rate includes started failures; NOT_RUN excluded. Gap: proven solved trials only.`;
  $('slide-results').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Agent</th><th>Solve rate</th><th>API latency</th><th>Attempt time</th><th>Moves, all</th><th>Moves, solved</th><th>Proven gap</th><th>Diagnostics</th></tr></thead><tbody>${tableRows(stats)}</tbody></table></div>`;
  $('slide-answers').innerHTML=$('answers').innerHTML;
  $('history').innerHTML=runs.length?runs.map(r=>`<div class="saved-run"><span><b>${escape(r.mode.toUpperCase())}</b> · ${escape(r.tier)} · ${r.puzzle_count} puzzle(s)${r.mode==='live'?' · '+(r.request_policy?.luna_route?.provider==='OpenAI'?'Luna: OpenAI':'OpenRouter'):''} · ${escape(r.status)} · ${escape(cost(r.billing))}<br>${escape(r.timestamp)} · ${r.id.slice(0,8)}</span><span><button class="secondary replay" data-id="${r.id}" ${busy?'disabled':''}>Replay</button>${['json','csv','steps.csv','requests.csv'].map(f=>`<a href="/api/runs/${r.id}/export/${f}">${f.toUpperCase()}</a>`).join('')}</span></div>`).join(''):'No saved runs.';
  for(const button of document.querySelectorAll('.replay'))button.onclick=()=>safe(async()=>{const run=await api(`/api/runs/${button.dataset.id}`);if(run.status==='RUNNING')throw new Error('Wait for the run to finish before replaying.');queue=run.events.map(e=>({type:e.event,data:e.data}));runId=run.id;modeBadge(run.mode);switchTab('arena');setBusy(true);$('abort').disabled=true;notice('Replaying saved run');pump();});
}
async function safe(action){try{await action();}catch(e){notice(e.message,true);}}
async function boot(){
  config=await api('/api/config');
  $('mode').querySelector('[value="live"]').disabled=!config.live_enabled;
  $('mode').querySelector('[value="live"]').textContent=config.live_source_label||'Live OpenRouter';
  for(const button of document.querySelectorAll('.tab'))button.onclick=()=>switchTab(button.dataset.tab);
  $('generate').onclick=()=>safe(async()=>{$('paid-confirm').checked=false;$('seed').value=Number($('seed').value)+1;await generate();updatePlan();});
  $('tier').onchange=()=>{$('paid-confirm').checked=false;safe(async()=>{await generate();updatePlan();});};$('seed').onchange=()=>{$('paid-confirm').checked=false;safe(async()=>{await generate();updatePlan();});};
  $('start').onclick=()=>safe(()=>start('race'));$('suite').onclick=()=>safe(()=>start('suite'));
  $('abort').onclick=()=>safe(async()=>{
    if(!runId)return;
    await api(`/api/runs/${runId}/abort`,{method:'POST',body:'{}'});
    if(source)source.close();queue=[];
    const run=await api(`/api/runs/${runId}`);
    const race=[...run.races].reverse().find(r=>r.trials.some(t=>t.status!=='NOT_RUN'))||run.races[0];
    modeBadge(run.mode);showPuzzle(race);drawCards(race.initial_state);race.trials.forEach((t,i)=>drawTrial(i,t));
    await finish(run.status);
    if(run.status==='COMPLETED')notice('Playback stopped · Run completed');
  });
  $('mode').onchange=()=>{modeBadge($('mode').value);drawCards(puzzle?.initial_state||SOLVED);$('paid-confirm').checked=false;updatePlan();};
  $('puzzles').oninput=()=>{$('paid-confirm').checked=false;updatePlan();};
  $('call-cap').oninput=()=>{$('paid-confirm').checked=false;};
  for(const id of ['stats-mode','stats-tier'])$(id).onchange=()=>safe(refreshStats);
  $('refresh').onclick=()=>safe(refreshStats);
  $('fullscreen').onclick=()=>safe(async()=>{if(!document.fullscreenElement)await document.documentElement.requestFullscreen();else await document.exitFullscreen();});
  updatePlan();await generate();await refreshStats();
}
safe(boot);

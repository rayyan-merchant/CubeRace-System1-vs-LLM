const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

test('Abort waits for the new run ID instead of targeting a previous run',async()=>{
  const source=fs.readFileSync(path.join(__dirname,'../frontend/app.js'),'utf8');
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,disabled:false});return elements.get(id);};
  $('mode').value='simulated';
  $('tier').value='primary';
  $('seed').value='2026';
  let resolve;
  const response=new Promise(r=>{resolve=r;});
  const context=vm.createContext({$,api:()=>response,modeBadge:()=>{},switchTab:()=>{},notice:()=>{},connect:()=>{}});
  vm.runInContext('let busy=false,runId="previous",queue=[];'+
    source.slice(source.indexOf('function setBusy('),source.indexOf('\n',source.indexOf('function setBusy(')))+
    source.slice(source.indexOf('async function start('),source.indexOf('\nfunction connect(')),context);
  const pending=vm.runInContext('start("race")',context);
  assert.equal($('abort').disabled,true,'Abort must be disabled while POST /api/runs is pending');
  assert.equal(vm.runInContext('runId',context),null);
  resolve({id:'new-run'});
  await pending;
  assert.equal(vm.runInContext('runId',context),'new-run');
  assert.equal($('abort').disabled,false);
});

test('Historical refusal displays REFUSED without changing saved status',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../frontend/app.js'),'utf8');
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{classList:{toggle(){}},style:{}});return elements.get(id);};
  const context=vm.createContext({$,cubeSVG:()=>'',cubeNet:()=>'',decorate:()=>{},fmt:String});
  vm.runInContext('let activeTrials=[],displayMode="live";'+source.slice(source.indexOf('function drawTrial('),source.indexOf('\nfunction showPuzzle(')),context);
  const trial={mode:'live',status:'API_ERROR',state:'',moves:[],elapsed_ms:null,
    requests:[{outcome:'REFUSED',provider_route:'direct_openai_decisions',latency_ms:null}]};
  context.trial=trial;
  vm.runInContext('drawTrial(1,trial)',context);
  assert.equal($('status-1').textContent,'REFUSED');
  assert.match($('provider-1').textContent,/OpenAI/);
  assert.equal(trial.status,'API_ERROR');
  trial.requests[0].outcome='HTTP_ERROR';
  vm.runInContext('drawTrial(1,trial)',context);
  assert.equal($('status-1').textContent,'API ERROR');
});

test('Historical output-limit record remains a budget failure rather than a connectivity error',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../frontend/app.js'),'utf8');
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{classList:{toggle(){}},style:{}});return elements.get(id);};
  const context=vm.createContext({$,cubeSVG:()=>'',cubeNet:()=>'',decorate:()=>{},fmt:String});
  vm.runInContext('let activeTrials=[],displayMode="live";'+source.slice(source.indexOf('function drawTrial('),source.indexOf('\nfunction showPuzzle(')),context);
  const trial={mode:'live',status:'API_ERROR',state:'',moves:[],elapsed_ms:null,requests:[{outcome:'OUTPUT_LIMIT',latency_ms:null}]};
  context.trial=trial;vm.runInContext('drawTrial(3,trial)',context);
  assert.equal($('status-3').textContent,'OUTPUT LIMIT');
  assert.equal(trial.status,'API_ERROR');
});

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../agent_world/static/leaderboard.js'),'utf8');
const context=vm.createContext({data:{launches:[{run_id:'test',supervisor_thread_id:'monitor',monitor_reviewed:false,error:'internal error'}]},esc:String,number:String,relative:()=> '10m ago'});
vm.runInContext(source.slice(source.indexOf('const stateLabel'),source.indexOf('function renderActivity')),context);
context.run={id:'test',model:'Gemini',ranked:false,warnings:[],cells:[{seed:11,tick:11,target:60,state:'status_stale',operational_state:'needs_attention',attention:'decisions_unusable'}]};
let html=vm.runInContext('studyMarkup(run)',context);
assert.doesNotMatch(html,/working on a fix/);
assert.match(html,/follow-up is pending/);
context.data.launches[0].monitor_event_state='working';
html=vm.runInContext('studyMarkup(run)',context);
assert.match(html,/Repair in progress/);
assert.match(html,/monitoring agent is working on a fix/);
assert.doesNotMatch(html,/Status out of date/);
assert.ok(html.indexOf('decisions_unusable')>html.indexOf('<details'));
context.data.launches[0].monitor_reviewed=true;
context.data.launches[0].monitor_event_state='completed';
context.data.launches[0].monitor_resolution_reason='Provider login required';
html=vm.runInContext('studyMarkup(run)',context);
assert.doesNotMatch(html,/working on a fix/);
assert.match(html,/Provider login required/);
context.run.cells[0]={seed:11,tick:60,target:60,state:'completed',operational_state:'completed'};
html=vm.runInContext('studyMarkup(run)',context);
assert.doesNotMatch(html,/Repair in progress|internal error/);
console.log('Repair copy, diagnostic disclosure and resolved-state checks passed');

context.run.cells=[11,41].map(seed=>({seed,tick:12,target:60,state:'status_stale',operational_state:'waiting_quota',retry_at:'2026-09-07T01:22:11Z',reset_at:'2026-09-07T01:21:11Z',reset_at:'2026-09-07T01:21:11Z'}));
html=vm.runInContext('studyMarkup(run)',context);
assert.equal((html.match(/Quota paused/g)||[]).length,1);
assert.equal((html.match(/Continues/g)||[]).length,1);
assert.doesNotMatch(html,/Quota resets|Next retry/);
assert.doesNotMatch(html,/Status out of date|paused checkpoint|working on a fix/);
context.run.cells[1].retry_at='2026-09-07T02:22:11Z';
html=vm.runInContext('studyMarkup(run)',context);
assert.equal((html.match(/Continues/g)||[]).length,2);
context.run.cells[1].operational_state='running';context.run.cells[1].state='running';
html=vm.runInContext('studyMarkup(run)',context);
assert.match(html,/Seed 11<\/a> · Quota paused/);assert.match(html,/Seed 41<\/a> · Running/);
context.run.cells[0].retry_at=null;context.run.cells[0].reset_at=null;
html=vm.runInContext('studyMarkup(run)',context);
assert.match(html,/Continuation time not yet reported/);
console.log('Shared, mixed, separate and unknown quota timing checks passed');

context.run.cells=[11,41].map(seed=>({seed,tick:12,target:60,state:'waiting_quota',retry_at:'2026-09-07T01:22:11Z',reset_at:'2026-09-07T01:21:11Z'}));
context.run.connector='antigravity';context.run.connector_label='Antigravity';
html=vm.runInContext('activityMarkup([run,{...run,id:"second",model:"Gemini 3.7 Flash"}])',context);
assert.equal((html.match(/Quota paused/g)||[]).length,1);
assert.equal((html.match(/Continues/g)||[]).length,1);
assert.match(html,/Gemini 3.7 Flash/);
html=vm.runInContext('activityMarkup([run,{...run,id:"second",connector:"muse"}])',context);
assert.equal((html.match(/Quota paused/g)||[]).length,2);

context.run.cells=[{seed:11,tick:27,target:60,state:'needs_attention',attention:'execution_payload_changed_evidence_decision'}];
html=vm.runInContext('studyMarkup(run)',context);
assert.match(html,/Continuation needs approval/);
assert.doesNotMatch(html,/Quota paused|Continues/);

// An incomplete run is not an admission decision. Keep meaningful warnings,
// and retain diagnostic classification once all seeds have actually completed.
context.run.warnings=['diagnostic only','diagnostic only','Specific evidence concern'];
context.run.cells=[{seed:11,tick:54,target:60,state:'running'}, {seed:41,tick:60,target:60,state:'completed'}];
html=vm.runInContext('studyMarkup(run)',context);
assert.doesNotMatch(html,/diagnostic only/);
assert.match(html,/Specific evidence concern/);
context.run.cells[0].state='waiting_quota';
html=vm.runInContext('studyMarkup(run)',context);
assert.doesNotMatch(html,/diagnostic only/);
context.run.cells[0].state='completed';context.run.cells[0].tick=60;
html=vm.runInContext('studyMarkup(run)',context);
assert.equal((html.match(/diagnostic only/g)||[]).length,1);
console.log('Diagnostic labels distinguish unfinished and completed studies');

context.data.launches=[{run_id:'test',monitor_reviewed:true,monitor_resolution:'external_blocker',monitor_event_state:'completed'}];
context.run.cells=[{seed:11,tick:0,target:60,state:'stopped',operational_state:'needs_attention',attention:'authentication_required'},
 {seed:41,tick:null,target:60,state:'waiting_startup_gate'}];
html=vm.runInContext('studyMarkup(run)',context);
assert.equal((html.match(/Startup blocked/g)||[]).length,2);
assert.doesNotMatch(html,/follow-up is pending|working on a fix/);
assert.match(html,/Monitoring review stopped/);
console.log('Shared startup blocker and completed monitor review render correctly');

context.run.cells[0].id="custom-cell";
html=vm.runInContext("studyMarkup(run)",context);
assert.match(html,/cell=custom-cell/);

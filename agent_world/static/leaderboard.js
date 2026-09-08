'use strict';
const $ = id => document.getElementById(id);
const esc = text => String(text ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});
const money = value => value == null ? '—' : '$' + number(value,2);
let data, selected = new URL(location.href).searchParams.get('board'), sortKey, sortAsc = false;
const laboratoryPage = location.pathname.replace(/\/$/,'') === '/laboratory' || (location.pathname === '/' && !new URL(location.href).searchParams.has('board'));
const experimentsPage = location.pathname.replace(/\/$/,'') === '/experiments';
const board = () => data?.boards.find(b => b.id === selected || b.study_groups?.some(g=>g.id===selected)) || data?.boards[0];
function relative(iso) {
  if(!iso) return 'No update recorded';
  const mins = Math.max(0, Math.floor((Date.now() - Date.parse(iso))/60000));
  return mins < 1 ? 'just now' : mins < 60 ? mins + 'm ago' : mins < 1440 ? Math.floor(mins/60) + 'h ago' : Math.floor(mins/1440) + 'd ago';
}
function changeBoard(id) {
  selected=id; sortKey=null; sortAsc=false; $('search').value='';
  const url=new URL(location.href);url.searchParams.set('board',id);history.replaceState(null,'',url);render();
}
function render() {
  if(experimentsPage){renderExperiments();return;}
  const b=board(); if(!b){$('loading').textContent='No benchmark evidence is available yet.';return;}
  selected=b.id;$('loading').hidden=true;$('dashboard').hidden=false;
  $('versions').innerHTML=data.boards.map(item => '<button class="version-button" aria-current="'+(item.id===b.id)+'" data-board="'+esc(item.id)+'">'+esc(item.title)+(item.source==='Canonical metrics database'?' <span class="version-count">Established</span>':' <span class="version-count">'+item.rows.length+' models</span>')+'</button>').join('');
  $('versions').querySelectorAll('button').forEach(el => el.onclick=()=>changeBoard(el.dataset.board));
  const primary=b.columns[0];
  $('ranking-caption').textContent='Ranked by '+primary[1].toLowerCase()+' · '+(b.scoring_caption || b.source.toLowerCase());
  $('table-note').textContent='Select a model for evidence and seed details.';
  $('updated').textContent='Evidence updated '+relative(b.updated_at);
  $('methodology').innerHTML='<p>'+esc(b.method || 'Final reports are scored using their original recipe. Incomplete studies remain in the activity panel.')+'</p><p>Versions and recipe fingerprints are kept separate. New studies are ranked only when the original scorer accepts a complete set of required seeds. Rankings within different versions are not directly comparable.</p><p>Cost / run is a token-derived API-list-price equivalent, not a subscription charge. A dash means unavailable. Reasoning estimates are marked with ~.</p><p>Recipe: <code>'+esc(b.recipe)+'</code>'+(b.digest?' · Fingerprint: <code>'+esc(b.digest)+'</code>':'')+'</p>'+b.warnings.map(w=>'<p class="warning">'+esc(w)+'</p>').join('');
  renderAdditionalStudies();renderTable();renderActivity();if(typeof renderLaunches==='function')renderLaunches(data.launches||[]);
}
function renderAdditionalStudies() {
  const groups=board().study_groups||[];
  $('additional-studies').hidden=!groups.length;
  $('additional-study-list').innerHTML='<p class="muted">These studies retain separate recipe evidence and rankings. They do not replace the established table above.</p>'+groups.map(g=>
    '<section><h3>'+esc(g.rows.map(r=>r.model).join(', ')||'Ongoing studies')+'</h3><p class="small muted">'+esc(g.recipe)+' · '+esc(g.digest?.slice(0,8)||'Historical evidence')+'</p><div class="table-scroll"><table><thead><tr><th>Model</th>'+g.columns.map(c=>'<th>'+esc(c[1])+'</th>').join('')+'<th>Cost / run</th></tr></thead><tbody>'+g.rows.map(r=>'<tr><td><button class="model-button" data-model="'+esc(r.id)+'">'+esc(r.model)+'</button></td>'+g.columns.map(c=>'<td>'+number(r.scores[c[0]])+'</td>').join('')+'<td>'+money(r.cost)+'</td></tr>').join('')+'</tbody></table></div>'+g.runs.filter(r=>!r.archived&&!r.ranked).map(r=>studyMarkup(r)).join('')+'</section>').join('');
  $('additional-study-list').querySelectorAll('[data-model]').forEach(el=>el.onclick=()=>showModel(el.dataset.model));
}
function renderTable() {
  const b=board(); if(!b)return;
  const primary=b.columns[0][0], key=sortKey || primary;
  const columns=[['rank','#'],['model','Model'],...b.columns,['cost','Cost / run']];
  $('table-head').innerHTML='<tr>'+columns.map(([k,title])=>'<th scope="col"'+(k===key?' aria-sort="'+(sortAsc?'ascending':'descending')+'"':'')+'><button data-sort="'+esc(k)+'">'+esc(title)+(k===key?(sortAsc?' ↑':' ↓'):'')+'</button></th>').join('')+'</tr>';
  $('table-head').querySelectorAll('button').forEach(button=>button.onclick=()=>{
    sortAsc=key===button.dataset.sort?!sortAsc:['model','rank','cost'].includes(button.dataset.sort);
    sortKey=button.dataset.sort;renderTable();
  });
  const query=$('search').value.trim().toLowerCase();
  const rows=b.rows.filter(r=>r.model.toLowerCase().includes(query)).slice();
  const value=r=>r.scores[key]??r[key];
  rows.sort((a,c)=>{
    const av=value(a),cv=value(c);
    if(av==null)return cv==null?0:1;if(cv==null)return -1;
    const diff=typeof av==='string'?av.localeCompare(cv):av-cv;
    return (sortAsc?diff:-diff)||a.rank-c.rank;
  });
  const max=Math.max(100,...b.rows.map(r=>r.scores[primary]||0));
  $('table-body').innerHTML=rows.map(r=>'<tr><td>'+r.rank+'</td><td><button class="model-button" data-model="'+esc(r.id)+'"><span class="model-avatar" title="'+esc(r.lab?.name||'Lab unspecified')+'"><img src="/labs/'+esc(r.lab?.id||'unknown')+'.svg" alt="'+esc(r.lab?.name||'Lab unspecified')+'" width="20" height="20"></span><span><span class="model-name">'+esc(r.model)+'</span><span class="model-meta">'+esc(r.status)+'</span></span></button></td>'+b.columns.map(([k])=>'<td'+(k===primary?' class="primary-score"':'')+'>'+number(r.scores[k])+(k===primary&&r.scores[k]!=null?'<progress class="score-rail" value="'+r.scores[k]+'" max="'+max+'" aria-label="'+esc(r.model)+' '+esc(b.columns[0][1])+'"></progress>':'')+'</td>').join('')+'<td>'+money(r.cost)+'</td></tr>').join('');
  $('no-results').hidden=rows.length>0;
  $('no-results').textContent=b.rows.length?'No models match your search.':'Replicated rankings will appear here as studies finish.';
  $('table-body').querySelectorAll('button').forEach(el=>el.onclick=()=>showModel(el.dataset.model));
}
const stateLabel = state => ({running:'Running',completed:'Completed',status_stale:'Status out of date',waiting_quota:'Quota paused',paused_provider:'Provider paused',waiting_startup_gate:'Waiting for startup',blocked_startup_gate:'Startup blocked',needs_attention:'Needs attention',not_started:'Queued',unknown:'Status unavailable'})[state] || state.replaceAll('_',' ');
function quotaTiming(cell) {
  const date=new Date(cell.retry_at);
  if(!cell.retry_at||!Number.isFinite(date.getTime()))return cell.quota_wait_exhausted?'Waiting for quota. Continuation is not yet scheduled.':'Continuation time not yet reported.';
  const today=new Date().toDateString()===date.toDateString();
  return 'Continues '+date.toLocaleString(undefined,{...(today?{}:{month:'short',day:'numeric'}),hour:'numeric',minute:'2-digit',timeZoneName:'short'});
}
function studyMarkup(run, grouped=false) {
  const request=(data?.launches||[]).find(r=>r.run_id===run.id);
  const cellState=c=>c.operational_state||c.state;
  const issue=c=>!['completed','waiting_quota'].includes(cellState(c)) &&
    (Boolean(c.attention)||['needs_attention','paused_provider','paused','failed','invalid'].includes(cellState(c)));
  const affected=run.cells.some(issue),quota=run.cells.some(c=>cellState(c)==='waiting_quota');
  const allQuota=run.cells.length>0&&run.cells.every(c=>cellState(c)==='waiting_quota');
  const sharedTiming=allQuota&&new Set(run.cells.map(quotaTiming)).size===1;
  const repairing=affected&&request?.supervisor_thread_id&&!request.monitor_reviewed;
  const provenanceReview=run.readiness_status==='needs_provenance_review';
  const reviewedEvidence=provenanceReview&&request?.monitor_reviewed&&request?.monitor_resolution==='evidence_decision';
  const finishedExperiment=run.is_experiment&&run.cells.length&&run.cells.every(c=>cellState(c)==='completed');
  const status=finishedExperiment?'Completed':reviewedEvidence?'Evidence incomplete':provenanceReview?'Provenance review needed':run.ranked?'Ranked':repairing?'Repair in progress':affected?'Run paused':quota?'Quota paused':'In study';
  const message=repairing?'Run paused after an issue. The monitoring agent is working on a fix.':
    affected?(request?.monitor_resolution_reason||'Run paused after an issue. Monitoring attention is needed.') : '';
  const diagnostics=run.cells.filter(c=>c.attention).map(c=>'Seed '+c.seed+': '+c.attention);
  if(affected&&request?.error)diagnostics.push(request.error);
  if(quota&&request?.monitor_resolution_reason)diagnostics.push(request.monitor_resolution_reason);
  if(affected&&run.cells.some(c=>c.state==='status_stale'))diagnostics.push('Controller updates are paused while the run is stopped.');
  return '<article class="study"><div class="study-head"><span>'+esc(run.model)+'</span><span class="study-status">'+(grouped?'':status)+'</span></div>'+
    run.cells.map(c=>'<div class="study-state"><span>Seed '+esc(c.seed)+(allQuota?'':' · '+esc(issue(c)?'Paused after an issue':stateLabel(cellState(c)==='waiting_quota'?'waiting_quota':c.state)))+'</span><span>'+number(c.tick,0)+' / '+esc(c.target??'—')+'</span></div><progress class="cell-progress" value="'+Math.max(0,Math.min(c.tick||0,c.target||1))+'" max="'+(c.target||1)+'" aria-label="'+esc(run.model)+' seed '+esc(c.seed)+' progress"></progress>').join('')+
    (message?'<p class="study-repair">'+esc(message)+'</p>':'')+
    (reviewedEvidence?'<p class="study-note">'+esc(request.monitor_resolution_reason)+'</p>':'')+
    (!sharedTiming?[...new Set(run.cells.filter(c=>cellState(c)==='waiting_quota').map(c=>quotaTiming(c)))].map(t=>'<p class="study-note">'+esc(t)+'</p>').join(''):'')+
    (sharedTiming&&!grouped?'<p class="study-note">'+esc(quotaTiming(run.cells[0]))+'</p>':'')+
    [...new Set(run.warnings)].filter(w=>!provenanceReview||w!=='diagnostic only').map(w=>'<p class="attention">'+esc(w)+'</p>').join('')+
    (diagnostics.length?'<details class="study-diagnostics"><summary>Technical details</summary>'+diagnostics.map(d=>'<p>'+esc(d)+'</p>').join('')+'</details>':'')+
    '<p class="study-note">'+(affected?'Last run update ':'Controller updated ')+esc(relative(run.checked_at))+'</p></article>';
}

function activityMarkup(runs) {
  const groups=new Map();
  for(const run of runs){
    const times=run.cells.map(quotaTiming);
    const shared=run.connector&&run.cells.length&&run.cells.every(c=>(c.operational_state||c.state)==='waiting_quota')&&new Set(times).size===1;
    const key=shared?run.connector+'|'+times[0]:run.id;
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(run);
  }
  return [...groups.values()].map(group=>group.length<2?studyMarkup(group[0]):
    '<section class="quota-group"><div class="study-head"><strong>'+esc(group[0].connector_label||group[0].connector)+'</strong><span class="study-status">Quota paused</span></div>'+
    group.map(r=>studyMarkup(r,true)).join('')+'<p class="study-note">'+esc(quotaTiming(group[0].cells[0]))+'</p></section>').join('');
}
function renderActivity(){
  const runs=board().runs, open=runs.filter(r=>!r.ranked&&!r.archived), complete=runs.filter(r=>r.ranked&&!r.archived), archived=runs.filter(r=>r.archived);
  $('activity-list').innerHTML=(open.length?activityMarkup(open):'<div><p class="activity-empty">All quiet in<br>the laboratory.</p><p class="small muted">No pending studies in this leaderboard.</p></div>')+(complete.length?'<details class="completed-studies"><summary>'+complete.length+' completed studies</summary>'+complete.map(r=>studyMarkup(r)).join('')+'</details>':'')+(archived.length?'<details class="completed-studies"><summary>'+archived.length+' archived studies</summary>'+archived.map(r=>studyMarkup(r)).join('')+'</details>':'');
}
function showModel(id) {
  const primary=board(),b=[primary,...(primary.study_groups||[])].find(g=>g.rows.some(row=>row.id===id));if(!b)return;const r=b.rows.find(row=>row.id===id);
  $('model-details').innerHTML='<p class="eyebrow">PARTICIPANT '+esc(b.title.toUpperCase())+' · RANK '+r.rank+'</p><h2 class="detail-title">'+esc(r.model)+'</h2><span class="badge">'+esc(r.status)+'</span><div class="detail-scores">'+b.columns.map(([k,title])=>'<div><span>'+esc(title)+'</span><strong>'+number(r.scores[k])+'</strong></div>').join('')+'</div>'+b.columns.map(([k,title])=>'<p class="detail-line"><strong>'+esc(title)+':</strong> '+esc(r.formulas[k])+'</p>').join('')+(r.reanalysis?'<p class="detail-line">Final population health: '+number(r.reanalysis.capability.endpoint)+' · Winter health lost: '+number(r.reanalysis.capability.winter_damage)+' · Extra winter penalty: '+number(r.reanalysis.capability.winter_surcharge)+' · Original full-run average: '+number(r.reanalysis.capability.original_full_horizon)+'</p>':'')+'<p class="detail-line">Seeds '+esc(r.seeds.join(', '))+' · '+money(r.cost)+' / run</p><p class="detail-line">Reasoning / decision: '+(r.reasoning_estimated?'~':'')+number(r.reasoning,0)+' tokens'+(r.latency!=null?' · Median response: '+number(r.latency)+'s':'')+'</p>'+(r.note?'<p class="detail-line warning">'+esc(r.note)+'</p>':'')+'<div class="detail-seeds">'+r.seed_scores.map(s=>'<div><p class="detail-line">Seed '+s.seed+'</p>'+b.columns.map(([k,title])=>'<p>'+esc(title)+' '+number(s.scores[k])+'</p>').join('')+'</div>').join('')+'</div>'+(r.commit?'<p class="detail-line muted">Launch commit · '+esc(r.commit.slice(0,12))+'</p>':'<p class="detail-line muted">Source · canonical model metrics database</p>');
  $('model-dialog').showModal();
}
async function refresh(){
  $('refresh').disabled=true;
  try{
    const response=await fetch(experimentsPage?'/api/experiments':'/api/leaderboards',{cache:'no-store',signal:AbortSignal.timeout(120000)});
    if(!response.ok)throw new Error('Unavailable');
    data=await response.json();render();
    $('error').hidden=!data.warnings.length;$('error').textContent=data.warnings.join(' ');
    $('sync-status').textContent='Updated '+relative(data.updated_at)+' · refreshes every '+data.refresh_seconds+'s';
  }catch(error){
    $('error').hidden=false;$('error').textContent=data?'Connection interrupted. Showing the last successful update; retrying automatically.':'Could not reach the leaderboard. Check that the host is awake and Tailscale is connected.';
    $('loading').hidden=true;$('sync-status').textContent='Connection interrupted';
  }finally{$('refresh').disabled=false;}
}
const experimentDetailState = new Map();
function experimentStartTime(iso){
  if(!iso || Number.isNaN(Date.parse(iso)))return 'Not recorded';
  return new Intl.DateTimeFormat(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(iso));
}
function renderExperiments(){
  $('experiment-list').querySelectorAll('details[data-experiment-id]').forEach(d=>experimentDetailState.set(d.dataset.experimentId,d.open));
  $('loading').hidden=true;$('dashboard').hidden=false;
  const query=$('experiment-search').value.trim().toLowerCase(),filter=$('experiment-filter').value;
  const runs=(data.experiments||[]).filter(r=>{
    const completed=r.cells.length&&r.cells.every(c=>(c.operational_state||c.state)==='completed');
    return (filter==='all'||(filter==='completed'?completed:!completed))&&
      [r.model,r.question,r.id,r.connector_label].join(' ').toLowerCase().includes(query);
  });
  $('experiment-count').textContent=runs.length+' '+(runs.length===1?'experiment':'experiments');
  $('experiment-list').innerHTML=runs.map(r=>{
    const request=(data.launches||[]).find(x=>x.run_id===r.id);
    const monitor=request?.monitor_reviewed?'Monitoring paused':request?.supervisor_thread_id?'Event monitoring active':'Local controller';
    return '<section class="card experiment-card"><div class="experiment-context"><img src="/labs/'+esc(r.lab?.id||'unknown')+'.svg" width="24" height="24" alt="'+esc(r.lab?.name||'Model provider')+'"><span>'+esc(r.connector_label||r.connector||'Mixed population')+' · '+esc(r.effort||'Default')+' effort</span><span class="small muted">'+esc(monitor)+'</span></div>'+studyMarkup(r)+
      '<details class="experiment-details" data-experiment-id="'+esc(r.id)+'"'+(experimentDetailState.get(r.id)?' open':'')+'><summary>Experiment details</summary><p class="experiment-started"><span class="small muted">Started</span><strong>'+esc(experimentStartTime(r.created_at))+'</strong></p><p>'+esc(r.question||'No experiment question recorded.')+'</p><p class="small muted">'+esc(r.id)+'</p>'+
      (r.agents?'<p>'+esc(r.agents)+' agents · '+esc(r.cells[0]?.target||'—')+' ticks</p>':'')+
      (Object.keys(r.world_overrides||{}).length?'<dl>'+Object.entries(r.world_overrides).map(([k,v])=>'<dt>'+esc(k.replaceAll('_',' '))+'</dt><dd>'+esc(typeof v==='object'?JSON.stringify(v):v)+'</dd>').join('')+'</dl>':'')+'</details></section>';
  }).join('')||'<div class="card empty">'+(query?'No experiments match your search.':filter==='completed'?'No completed experiments yet.':'No ongoing experiments. Experiments launched from your agents appear here automatically.')+'</div>';
  $('updated').textContent='Updated '+relative(data.updated_at);
}
$('current-page').textContent=experimentsPage?'Experiments':'Leaderboards';
if(laboratoryPage){
  document.title='Agent World · Laboratory';
  $('laboratory-panel').hidden=false;$('study-heading').hidden=true;$('versions').hidden=true;$('loading').hidden=true;
  $('current-page').hidden=true;document.querySelector('.page-crumb').hidden=true;
  $('nav-laboratory').setAttribute('aria-current','page');
}
if(experimentsPage){
  document.title='Agent World · Experiments';
  document.querySelector('#study-heading h1').innerHTML='Experiments<span class="title-dot">.</span>';
  $('new-benchmark').hidden=true;$('versions').hidden=true;
  $('loading').textContent='Loading experiments…';
  $('refresh').setAttribute('aria-label','Refresh experiments');$('refresh').title='Refresh experiments';
  document.querySelector('.content-grid').hidden=true;document.querySelector('.methodology').hidden=true;
  $('experiments-panel').hidden=false;
}
$('experiment-search').addEventListener('input',()=>{if(data)renderExperiments();});
$('experiment-filter').addEventListener('change',()=>{if(data)renderExperiments();});
$('search').addEventListener('input',renderTable);
$('refresh').onclick=refresh;
$('close-dialog').onclick=()=>$('model-dialog').close();
$('model-dialog').addEventListener('click',event=>{if(event.target===$('model-dialog')&&event.offsetX<0)$('model-dialog').close();});
if(!laboratoryPage)refresh();
setInterval(()=>{if(!laboratoryPage&&!document.hidden&&!$('refresh').disabled)refresh();},30000);
document.addEventListener('visibilitychange',()=>{if(!laboratoryPage&&!document.hidden&&!$('refresh').disabled)refresh();});

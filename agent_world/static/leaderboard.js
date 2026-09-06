'use strict';
const $ = id => document.getElementById(id);
const esc = text => String(text ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});
const money = value => value == null ? '—' : '$' + number(value,2);
let data, selected = new URL(location.href).searchParams.get('board'), sortKey, sortAsc = false;
const board = () => data?.boards.find(b => b.id === selected) || data?.boards[0];
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
  const b=board(); if(!b){$('loading').textContent='No benchmark evidence is available yet.';return;}
  selected=b.id;$('loading').hidden=true;$('dashboard').hidden=false;
  $('versions').innerHTML=data.boards.map(item => '<button class="version-button" aria-current="'+(item.id===b.id)+'" data-board="'+esc(item.id)+'">'+esc(item.title)+(item.source==='Canonical metrics database'?' <span class="version-count">Established</span>':' <span class="version-count">'+item.rows.length+' models</span>')+'</button>').join('');
  $('versions').querySelectorAll('button').forEach(el => el.onclick=()=>changeBoard(el.dataset.board));
  const top=b.rows[0], primary=b.columns[0];
  $('board-state').textContent=b.state;
  $('leader-name').textContent=top?.model || 'The field is taking shape';
  $('leader-meta').textContent=top ? top.status : 'Results appear after completed replications';
  $('leader-score').textContent=number(top?.scores[primary[0]]);
  $('leader-metric').textContent=primary[1];
  $('leader-seeds').textContent=top ? top.seeds.length+' seeds · #1' : 'Awaiting results';
  $('ranked-count').textContent=b.rows.length;$('active-count').textContent=b.active_count;
  $('field-caption').textContent=b.source==='Canonical metrics database'?'Includes labeled controlled variants.':'Completed, replicated results in this recipe.';
  $('ranking-caption').textContent='Ranked by '+primary[1].toLowerCase()+' · '+b.source.toLowerCase();
  $('table-note').textContent='Select a model for evidence and seed details.';
  $('updated').textContent='Evidence updated '+relative(b.updated_at);
  $('methodology').innerHTML='<p>'+esc(b.method || 'Final reports are scored using their original recipe. Incomplete studies remain in the activity panel.')+'</p><p>Versions and recipe fingerprints are kept separate. New studies are ranked only when the original scorer accepts a complete set of required seeds. Rankings within different versions are not directly comparable.</p><p>Cost / run is a token-derived API-list-price equivalent, not a subscription charge. A dash means unavailable. Reasoning estimates are marked with ~.</p><p>Recipe: <code>'+esc(b.recipe)+'</code>'+(b.digest?' · Fingerprint: <code>'+esc(b.digest)+'</code>':'')+'</p>'+b.warnings.map(w=>'<p class="warning">'+esc(w)+'</p>').join('');
  renderTable();renderActivity();if(typeof renderLaunches==='function')renderLaunches(data.launches||[]);
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
  const time=value=>value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}) : null;
  const reset=time(cell.reset_at),retry=time(cell.retry_at);
  return [reset?'Quota resets '+reset:'',retry?'Next retry '+retry:''].filter(Boolean).join(' · ') || 'Waiting for quota; retry time has not been reported.';
}
function studyMarkup(run) {
  const request=(data?.launches||[]).find(r=>r.run_id===run.id);
  const cellState=c=>c.operational_state||c.state;
  const issue=c=>!['completed','waiting_quota'].includes(cellState(c)) &&
    (Boolean(c.attention)||['needs_attention','paused_provider','paused','failed','invalid'].includes(cellState(c)));
  const affected=run.cells.some(issue),quota=run.cells.some(c=>cellState(c)==='waiting_quota');
  const allQuota=run.cells.length>0&&run.cells.every(c=>cellState(c)==='waiting_quota');
  const sharedTiming=allQuota&&new Set(run.cells.map(quotaTiming)).size===1;
  const repairing=affected&&request?.supervisor_thread_id&&!request.monitor_reviewed;
  const status=run.ranked?'Ranked':repairing?'Repair in progress':affected?'Run paused':quota?'Quota paused':'In study';
  const message=repairing?'Run paused after an issue. The monitoring agent is working on a fix.':
    affected?(request?.monitor_resolution_reason||'Run paused after an issue. Monitoring attention is needed.') : '';
  const diagnostics=run.cells.filter(c=>c.attention).map(c=>'Seed '+c.seed+': '+c.attention);
  if(affected&&request?.error)diagnostics.push(request.error);
  if(affected&&run.cells.some(c=>c.state==='status_stale'))diagnostics.push('Controller updates are paused while the run is stopped.');
  return '<article class="study"><div class="study-head"><span>'+esc(run.model)+'</span><span class="study-status">'+status+'</span></div>'+
    (message?'<p class="study-repair">'+esc(message)+'</p>':'')+
    run.cells.map(c=>'<div class="study-state"><span>Seed '+esc(c.seed)+(allQuota?'':' · '+esc(issue(c)?'Paused after an issue':stateLabel(cellState(c)==='waiting_quota'?'waiting_quota':c.state)))+'</span><span>'+number(c.tick,0)+' / '+esc(c.target??'—')+'</span></div><progress class="cell-progress" value="'+Math.max(0,Math.min(c.tick||0,c.target||1))+'" max="'+(c.target||1)+'" aria-label="'+esc(run.model)+' seed '+esc(c.seed)+' progress"></progress>'+(cellState(c)==='waiting_quota'&&!sharedTiming?'<p class="study-note">'+esc(quotaTiming(c))+'</p>':'')).join('')+
    (sharedTiming?'<p class="study-note">'+esc(quotaTiming(run.cells[0]))+'</p>':'')+
    run.warnings.map(w=>'<p class="attention">'+esc(w)+'</p>').join('')+
    (diagnostics.length?'<details class="study-diagnostics"><summary>Technical details</summary>'+diagnostics.map(d=>'<p>'+esc(d)+'</p>').join('')+'</details>':'')+
    '<p class="study-note">'+(affected?'Last run update ':'Controller updated ')+esc(relative(run.checked_at))+'</p></article>';
}

function renderActivity(){
  const runs=board().runs, open=runs.filter(r=>!r.ranked), complete=runs.filter(r=>r.ranked);
  $('activity-list').innerHTML=(open.length?open.map(studyMarkup).join(''):'<div><p class="activity-empty">All quiet in<br>the laboratory.</p><p class="small muted">No pending studies in this leaderboard.</p></div>')+(complete.length?'<details class="completed-studies"><summary>'+complete.length+' completed studies</summary>'+complete.map(studyMarkup).join('')+'</details>':'');
}
function showModel(id) {
  const b=board(),r=b.rows.find(row=>row.id===id);if(!r)return;
  $('model-details').innerHTML='<p class="eyebrow">PARTICIPANT '+esc(b.title.toUpperCase())+' · RANK '+r.rank+'</p><h2 class="detail-title">'+esc(r.model)+'</h2><span class="badge">'+esc(r.status)+'</span><div class="detail-scores">'+b.columns.map(([k,title])=>'<div><span>'+esc(title)+'</span><strong>'+number(r.scores[k])+'</strong></div>').join('')+'</div>'+b.columns.map(([k,title])=>'<p class="detail-line"><strong>'+esc(title)+':</strong> '+esc(r.formulas[k])+'</p>').join('')+'<p class="detail-line">Seeds '+esc(r.seeds.join(', '))+' · '+money(r.cost)+' / run</p><p class="detail-line">Reasoning / decision: '+(r.reasoning_estimated?'~':'')+number(r.reasoning,0)+' tokens'+(r.latency!=null?' · Median response: '+number(r.latency)+'s':'')+'</p>'+(r.note?'<p class="detail-line warning">'+esc(r.note)+'</p>':'')+'<div class="detail-seeds">'+r.seed_scores.map(s=>'<div><p class="detail-line">Seed '+s.seed+'</p>'+b.columns.map(([k,title])=>'<p>'+esc(title)+' '+number(s.scores[k])+'</p>').join('')+'</div>').join('')+'</div>'+(r.commit?'<p class="detail-line muted">Launch commit · '+esc(r.commit.slice(0,12))+'</p>':'<p class="detail-line muted">Source · canonical model metrics database</p>');
  $('model-dialog').showModal();
}
async function refresh(){
  $('refresh').disabled=true;
  try{
    const response=await fetch('/api/leaderboards',{cache:'no-store',signal:AbortSignal.timeout(120000)});
    if(!response.ok)throw new Error('Unavailable');
    data=await response.json();render();
    $('error').hidden=!data.warnings.length;$('error').textContent=data.warnings.join(' ');
    $('sync-status').textContent='Updated '+relative(data.updated_at)+' · refreshes every '+data.refresh_seconds+'s';
  }catch(error){
    $('error').hidden=false;$('error').textContent=data?'Connection interrupted. Showing the last successful update; retrying automatically.':'Could not reach the leaderboard. Check that the host is awake and Tailscale is connected.';
    $('loading').hidden=true;$('sync-status').textContent='Connection interrupted';
  }finally{$('refresh').disabled=false;}
}
$('search').addEventListener('input',renderTable);
$('refresh').onclick=refresh;
$('close-dialog').onclick=()=>$('model-dialog').close();
$('model-dialog').addEventListener('click',event=>{if(event.target===$('model-dialog')&&event.offsetX<0)$('model-dialog').close();});
refresh();
setInterval(()=>{if(!document.hidden&&!$('refresh').disabled)refresh();},30000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!$('refresh').disabled)refresh();});

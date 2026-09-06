'use strict';
const launchState = {options:null, preview:null, busy:false};
const launchEl = id => document.getElementById(id);
function launchError(message) {
  launchEl('launch-error').hidden=!message;
  launchEl('launch-error').textContent=message||'';
}
function launchRecipe() {
  return launchState.options?.recipes.find(r=>r.id===launchEl('launch-recipe').value);
}
function launchConditions() {
  const r=launchRecipe();
  launchEl('launch-conditions').textContent=r
    ? r.defaults.agents+' agents · '+r.defaults.ticks+' ticks · seeds '+r.seeds.join(' + ')+' · '+r.defaults.reasoning_effort+' reasoning'
    : 'No clean launch source is available for this recipe.';
}
function launchModels() {
  const r=launchRecipe(),brain=launchEl('launch-brain').value;
  launchEl('launch-models').innerHTML=(r?.models||[]).filter(m=>m.brain===brain)
    .map(m=>'<option value="'+esc(m.id)+'"></option>').join('');
}
function chooseRecipe() {
  const r=launchRecipe();
  launchEl('launch-brain').innerHTML=(r?.brains||[]).map(b=>'<option value="'+esc(b)+'">'+esc(({codex:'Codex',claude:'Claude Code',openrouter:'OpenRouter',grok:'Grok',muse:'Muse',antigravity:'Antigravity',cursor:'Cursor',zcode:'ZCode',devin:'Devin'})[b]||b)+'</option>').join('');
  if(r?.brains.includes('codex'))launchEl('launch-brain').value='codex';
  launchModels();launchConditions();
}
async function openLaunch() {
  launchEl('launch-dialog').showModal();
  launchState.preview=null;launchState.options=null;
  launchEl('launch-form').hidden=false;launchEl('launch-review').hidden=true;
  launchEl('launch-loading').hidden=false;launchEl('review-launch').disabled=true;
  launchError('');
  try {
    const response=await fetch('/api/launch/options',{cache:'no-store',signal:AbortSignal.timeout(120000)});
    const options=await response.json();
    if(!response.ok)throw new Error(options.error||'Could not load benchmark options.');
    launchState.options=options;
    launchEl('launch-recipe').innerHTML=options.recipes.map(r=>'<option value="'+esc(r.id)+'">'+esc(r.recipe_id.replace('participant-','Participant ').replaceAll('-',' '))+'</option>').join('');
    const current=board();
    const match=options.recipes.find(r=>r.id===current?.id)||
      options.recipes.find(r=>r.recipe_id===current?.recipe);
    if(match)launchEl('launch-recipe').value=match.id;
    chooseRecipe();
    launchEl('review-launch').disabled=!options.enabled||!options.recipes.length;
    if(options.blocker)launchError(options.blocker);
  } catch(error) {launchError(error.message);}
  finally {launchEl('launch-loading').hidden=true;}
}
async function launchPost(path,payload) {
  const response=await fetch(path,{method:'POST',
    headers:{'Content-Type':'application/json','X-Leaderboard-Token':launchState.options.token},
    body:JSON.stringify(payload),signal:AbortSignal.timeout(120000)});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'The request could not be completed.');
  return result;
}
async function reviewLaunch(event) {
  event.preventDefault();if(launchState.busy)return;
  launchState.busy=true;launchEl('review-launch').disabled=true;launchError('');
  try {
    const preview=await launchPost('/api/launch/preview',{
      recipe:launchEl('launch-recipe').value,brain:launchEl('launch-brain').value,
      model:launchEl('launch-model').value.trim()});
    launchState.preview=preview;
    launchEl('launch-review-summary').innerHTML='<h3>'+esc(preview.model)+'</h3><p>'+esc(preview.recipe_id.replace('participant-','Participant '))+' · '+esc(preview.brain)+'</p><dl><div><dt>Population</dt><dd>'+preview.defaults.agents+' agents</dd></div><div><dt>Duration</dt><dd>'+preview.defaults.ticks+' ticks per seed</dd></div><div><dt>Required seeds</dt><dd>'+esc(preview.seeds.join(', '))+'</dd></div><div><dt>Model reasoning</dt><dd>'+esc(preview.defaults.reasoning_effort)+'</dd></div><div><dt>Supervisor</dt><dd>GPT-6 Astra · Low</dd></div></dl>';
    launchEl('launch-form').hidden=true;launchEl('launch-review').hidden=false;
    launchEl('confirm-launch').focus();
  } catch(error) {launchError(error.message);}
  finally {launchState.busy=false;launchEl('review-launch').disabled=false;}
}
async function confirmLaunch() {
  if(launchState.busy||!launchState.preview)return;
  launchState.busy=true;launchEl('confirm-launch').disabled=true;launchError('');
  try {
    const request=await launchPost('/api/launch/start',{request_id:launchState.preview.id});
    launchEl('launch-dialog').close();
    const current=data?.launches||[];
    renderLaunches([request,...current.filter(r=>r.id!==request.id)]);
    refresh();
  } catch(error) {
    launchError(error.message+' You can retry this same reviewed request without creating a duplicate run.');
  } finally {launchState.busy=false;launchEl('confirm-launch').disabled=false;}
}
function renderLaunches(requests=[]) {
  launchEl('launch-history').hidden=!requests.length;
  launchEl('launch-history-list').innerHTML=requests.map(r=>
    '<article class="launch-entry"><div class="study-head"><span>'+esc(r.model)+'</span><span class="badge">'+esc(({queued:'Queued',launching:'Starting',supervising:'In progress',completed:'Complete',needs_attention:'Needs attention'})[r.state]||r.state)+'</span></div><p class="small muted">'+esc(r.recipe_id.replace('participant-','Participant '))+' · '+esc(r.brain)+'</p><p class="supervisor-label"><span class="dot"></span> Astra · Low <span class="muted">/ '+esc((r.supervisor_state||'pending').replaceAll('_',' '))+'</span></p>'+
    (r.error?'<p class="attention">'+esc(r.error)+'</p>':'')+
    (r.can_reconnect?'<button class="secondary-button reconnect-supervisor" data-request="'+esc(r.id)+'">Reconnect supervisor</button>':'')+
    (r.supervisor_message?'<details><summary>Supervisor notes</summary><p class="supervisor-note">'+esc(r.supervisor_message)+'</p></details>':'')+
    '<p class="study-note">Requested '+esc(relative(r.created_at))+'</p></article>').join('');
  launchEl('launch-history-list').querySelectorAll('.reconnect-supervisor').forEach(button=>button.onclick=async()=>{
    button.disabled=true;
    try {
      if(!launchState.options){
        const response=await fetch('/api/launch/options',{cache:'no-store'});
        if(!response.ok)throw new Error('Cannot connect to the launcher.');
        launchState.options=await response.json();
      }
      await launchPost('/api/launch/reconnect',{request_id:button.dataset.request});
      refresh();
    } catch(error) {button.textContent=error.message;}
    finally{button.disabled=false;}
  });
}
launchEl('new-benchmark').onclick=openLaunch;
launchEl('close-launch').onclick=()=>{if(!launchState.busy)launchEl('launch-dialog').close();};
launchEl('launch-recipe').onchange=chooseRecipe;
launchEl('launch-brain').onchange=launchModels;
launchEl('launch-form').onsubmit=reviewLaunch;
launchEl('confirm-launch').onclick=confirmLaunch;
launchEl('edit-launch').onclick=()=>{
  launchState.preview=null;launchEl('launch-form').hidden=false;launchEl('launch-review').hidden=true;launchError('');
};

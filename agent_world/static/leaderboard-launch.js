'use strict';
const launchState = {options:null, preview:null, busy:false, selected:new Set(), outcomes:new Map()};
const launchEl = id => document.getElementById(id);
const recipeName = id => 'Participant '+(id==='participant-v8-revised'?'v8.1':id.replace('participant-','').replaceAll('-',' '));
const modelLogo = (lab,name) => '<span class="model-avatar"><img src="/labs/'+esc(lab||'unknown')+'.svg" alt="'+esc(name||'')+'"></span>';
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
function pickerOpen(open) {
  launchEl('model-picker-panel').hidden=!open;
  launchEl('model-picker-toggle').setAttribute('aria-expanded',String(open));
  if(open)launchEl('model-search').focus();
}
const nativeConnectors={openai:'codex',anthropic:'claude',google:'antigravity',meta:'muse',xai:'grok',zai:'zcode'};
const catalogIdentity=name=>(name||'').toLowerCase().replace(/^(?:anthropic: ?|claude )/,'').replace(/ (?:low|medium|high|xhigh|max)$/,'').replace(/[^a-z0-9]/g,'').replace(/^(?:meta)?(musespark[0-9]+)contributor$/,'$1');
function browseModels(models,recipe,boards,{query='',lab='',mode='next'}={}) {
  const study=boards.find(b=>b.recipe===recipe);
  const seen=new Set([...(study?.rows||[]),...(study?.runs||[])].map(r=>catalogIdentity(r.model)));
  const activeMuse=new Set((study?.runs||[]).filter(r=>!r.ranked&&r.cells?.some(c=>!['completed','failed','stopped','invalid','cancelled'].includes(c.operational_state||c.state))).map(r=>catalogIdentity(r.model)).filter(id=>id.startsWith('musespark')));
  const native=m=>nativeConnectors[m.lab]===m.brain;
  return models.filter(m=>!activeMuse.has(catalogIdentity(m.name))&&(!lab||m.lab===lab)&&(!query||(m.name+' '+m.lab+' '+m.connector).toLowerCase().includes(query))&&
    (query||mode==='all'||(native(m)&&!seen.has(catalogIdentity(m.name)))))
    .sort((a,b)=>Number(native(b))-Number(native(a))||Number(seen.has(catalogIdentity(a.name)))-Number(seen.has(catalogIdentity(b.name)))||a.name.localeCompare(b.name,undefined,{numeric:true}));
}
function launchModels() {
  const models=launchRecipe()?.models||[],query=launchEl('model-search').value.trim().toLowerCase();
  const mode=launchEl('model-browse').value||'next';
  const visible=browseModels(models,launchRecipe()?.recipe_id,data?.boards||[],{query,mode,lab:launchEl('model-lab').value});
  launchEl('model-browse-note').textContent=visible.length+' models · '+(query?'Searching the full catalog.':mode==='all'?'Native connectors first.':'Native models without a result or study in this recipe. Search or choose All models for the full catalog.');
  launchEl('model-options').innerHTML=visible.map(m=>'<label class="model-option">'+
    '<input type="checkbox" value="'+esc(m.key)+'" '+(launchState.selected.has(m.key)?'checked':'')+'>'+
    modelLogo(m.lab,'')+'<span class="model-option-copy"><strong>'+esc(m.name)+'</strong><span>'+esc(m.connector)+'</span></span></label>').join('')||
    '<p class="small muted">No matching models. Choose All models or adjust your search and lab filter.</p>';
  launchEl('model-options').querySelectorAll('input').forEach(input=>input.onchange=()=>{
    if(input.checked)launchState.selected.add(input.value);else launchState.selected.delete(input.value);
    updateSelected();
  });
  updateSelected();
}
function updateSelected() {
  const models=(launchRecipe()?.models||[]).filter(m=>launchState.selected.has(m.key));
  const count=models.length;
  launchEl('model-picker-count').textContent=count?count+' model'+(count===1?'':'s')+' selected':'Choose models';
  launchEl('selected-models').innerHTML=models.map(m=>'<span class="selected-model">'+modelLogo(m.lab,'')+
    '<span>'+esc(m.name)+'<small>'+esc(m.connector)+'</small></span><button type="button" data-key="'+esc(m.key)+'" aria-label="Remove '+esc(m.name)+'">×</button></span>').join('');
  launchEl('selected-models').querySelectorAll('button').forEach(button=>button.onclick=()=>{
    launchState.selected.delete(button.dataset.key);launchModels();
  });
  launchEl('review-launch').disabled=launchState.busy||!launchState.options?.enabled||!count;
  launchEl('review-launch').textContent='Review '+(count||'')+' benchmark'+(count===1?'':'s')+' →';
}
function chooseRecipe() {
  const allowed=new Set((launchRecipe()?.models||[]).map(m=>m.key));
  launchState.selected=new Set([...launchState.selected].filter(k=>allowed.has(k)));
  launchModels();launchConditions();
}
async function openLaunch() {
  if(launchState.busy)return;
  launchEl('launch-dialog').showModal();
  launchState.preview=null;launchState.options=null;launchState.selected.clear();launchState.outcomes.clear();
  launchEl('launch-form').hidden=false;launchEl('launch-review').hidden=true;
  launchEl('launch-loading').hidden=false;launchEl('review-launch').disabled=true;
  launchEl('launch-recipe').innerHTML='';launchEl('model-options').innerHTML='';
  launchEl('selected-models').innerHTML='';launchEl('model-picker-count').textContent='Choose models';
  launchEl('model-search').value='';launchEl('model-browse').value='next';launchEl('model-lab').value='';pickerOpen(false);launchError('');
  try {
    const response=await fetch('/api/launch/options',{cache:'no-store',signal:AbortSignal.timeout(120000)});
    const options=await response.json();
    if(!response.ok)throw new Error(options.error||'Could not load benchmark options.');
    launchState.options=options;
    launchEl('launch-recipe').innerHTML=options.recipes.map(r=>'<option value="'+esc(r.id)+'">'+esc(r.title||recipeName(r.recipe_id))+'</option>').join('');
    const current=board();
    const match=options.recipes.find(r=>r.id===current?.id)||options.recipes.find(r=>r.recipe_id===current?.recipe);
    if(match)launchEl('launch-recipe').value=match.id;
    chooseRecipe();
    if(options.blocker)launchError(options.blocker);
    else if(options.warnings?.length)launchError(options.warnings.join(' '));
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
function renderReview() {
  const previews=launchState.preview||[],first=previews[0];
  if(!first)return;
  launchEl('launch-review-summary').innerHTML='<h3>'+previews.length+' benchmark'+(previews.length===1?'':'s')+'</h3>'+
    '<p>'+esc(first.recipe_title||recipeName(first.recipe_id))+'</p>'+
    '<div class="review-models">'+previews.map(p=>{
      const outcome=launchState.outcomes.get(p.id);
      return '<div class="review-model">'+modelLogo(p.lab,'')+'<div><strong>'+esc(p.model_name||p.model)+'</strong>'+
        '<p class="small muted">'+esc(p.brain)+' · '+esc(outcome?.error||outcome?.label||'Ready to start')+'</p></div></div>';
    }).join('')+'</div><dl><div><dt>Population</dt><dd>'+first.defaults.agents+' agents per run</dd></div><div><dt>Duration</dt><dd>'+first.defaults.ticks+' ticks per seed</dd></div><div><dt>Required seeds</dt><dd>'+esc(first.seeds.join(', '))+'</dd></div><div><dt>Model reasoning</dt><dd>'+esc(first.defaults.reasoning_effort)+'</dd></div><div><dt>Each supervisor</dt><dd>GPT-6 Astra · Low</dd></div></dl>';
  const pending=previews.filter(p=>!launchState.outcomes.get(p.id)?.ok).length;
  launchEl('confirm-launch').textContent=launchState.outcomes.size?'Retry remaining ('+pending+')':'Start '+previews.length+' benchmark'+(previews.length===1?'':'s');
}
async function reviewLaunch(event) {
  event.preventDefault();if(launchState.busy||!launchState.selected.size)return;
  if(launchState.selected.size>20){launchError('Select up to 20 models per batch.');return;}
  launchState.busy=true;updateSelected();launchError('');pickerOpen(false);
  launchEl('launch-recipe').disabled=true;launchEl('model-picker-toggle').disabled=true;
  const recipe=launchEl('launch-recipe').value,keys=[...launchState.selected];
  try {
    const previews=[];
    for(const key of keys){
      launchEl('review-launch').textContent='Reviewing '+(previews.length+1)+' of '+keys.length+'…';
      previews.push(await launchPost('/api/launch/preview',{recipe,model_key:key}));
    }
    launchState.preview=previews;launchState.outcomes.clear();renderReview();
    launchEl('launch-form').hidden=true;launchEl('launch-review').hidden=false;
    launchEl('edit-launch').disabled=false;launchEl('confirm-launch').focus();
  } catch(error) {launchError(error.message);}
  finally {
    launchState.busy=false;launchEl('launch-recipe').disabled=false;launchEl('model-picker-toggle').disabled=false;updateSelected();
  }
}
async function confirmLaunch() {
  if(launchState.busy||!launchState.preview||launchState.preview.every(p=>launchState.outcomes.get(p.id)?.ok))return;
  launchState.busy=true;launchEl('confirm-launch').disabled=true;launchEl('edit-launch').disabled=true;launchError('');
  try {
    const pending=launchState.preview.filter(p=>!launchState.outcomes.get(p.id)?.ok);
    try {
      const batch=await launchPost('/api/launch/start-batch',{request_ids:pending.map(p=>p.id)});
      for(const result of batch.results){
        launchState.outcomes.set(result.id,result.error?{ok:false,error:result.error}:{ok:true,label:'Requested'});
      }
    } catch(error) {
      for(const p of pending)launchState.outcomes.set(p.id,{ok:false,error:error.message});
    }
    renderReview();
    const failed=launchState.preview.some(p=>!launchState.outcomes.get(p.id)?.ok);
    if(failed)launchError('Some runs could not start. Retry uses the same reviewed requests; successful launches are skipped. Close and reopen to make a new selection if a review has expired.');
    else launchEl('launch-dialog').close();
    refresh();
  } finally {launchState.busy=false;launchEl('confirm-launch').disabled=false;}
}
function renderLaunches(requests=[]) {
  const inActivity=new Set((data?.boards||[]).flatMap(b=>(b.runs||[]).map(r=>r.id)));
  requests=requests.filter(r=>!inActivity.has(r.run_id));
  launchEl('launch-history').hidden=!requests.length;
  launchEl('launch-history-list').innerHTML=requests.map(r=>
    '<article class="launch-entry"><div class="study-head"><span>'+esc(r.model_name||r.model)+'</span><span class="badge">'+esc(({queued:'Queued',launching:'Starting',supervising:'In progress',completed:'Complete',needs_attention:'Needs attention'})[r.state]||r.state)+'</span></div><p class="small muted">'+esc(r.recipe_title||recipeName(r.recipe_id))+' · '+esc(r.brain)+'</p><p class="supervisor-label"><span class="dot"></span> Astra · Low <span class="muted">/ '+esc((r.supervisor_state||'pending').replaceAll('_',' '))+'</span></p>'+
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
      await launchPost('/api/launch/reconnect',{request_id:button.dataset.request});refresh();
    } catch(error) {button.textContent=error.message;}
    finally{button.disabled=false;}
  });
}
launchEl('new-benchmark').onclick=openLaunch;
launchEl('close-launch').onclick=()=>{if(!launchState.busy)launchEl('launch-dialog').close();};
launchEl('launch-dialog').addEventListener('cancel',event=>{
  if(launchState.busy){event.preventDefault();return;}
  if(!launchEl('model-picker-panel').hidden){event.preventDefault();pickerOpen(false);launchEl('model-picker-toggle').focus();}
});
launchEl('model-picker-toggle').onclick=()=>pickerOpen(launchEl('model-picker-panel').hidden);
launchEl('model-search').oninput=launchModels;
launchEl('model-search').onkeydown=event=>{if(event.key==='Enter')event.preventDefault();};
launchEl('launch-dialog').addEventListener('click',event=>{if(!event.target.closest('.model-picker'))pickerOpen(false);});
launchEl('launch-recipe').onchange=chooseRecipe;
launchEl('launch-form').onsubmit=reviewLaunch;
launchEl('confirm-launch').onclick=confirmLaunch;
launchEl('edit-launch').onclick=()=>{
  if(launchState.busy||launchState.outcomes.size)return;
  launchState.preview=null;launchEl('launch-form').hidden=false;launchEl('launch-review').hidden=true;launchError('');
};

launchEl('model-browse').onchange=launchModels;
launchEl('model-lab').onchange=launchModels;

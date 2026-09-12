'use strict';
(() => {
  const $=id=>document.getElementById(id),params=new URL(location.href).searchParams;
  const run=params.get('run')||'demo',cell=params.get('cell');
  const titleCase=value=>String(value||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
  const stateLabels={running:'LIVE WORLD',completed:'COMPLETED',waiting_quota:'QUOTA PAUSED',status_stale:'LAST SNAPSHOT',unknown:'LAST SNAPSHOT',paused_provider:'PROVIDER PAUSED',needs_attention:'RUN PAUSED',paused_checkpoint:'RUN PAUSED'};
  let payload,busy=false,pollTimer;
  const renderer=new WorldRenderer($('world-canvas'),{onRotate:({northAngle})=>{
    $('compass-needle').setAttribute('transform','rotate('+northAngle+' 25 25)');
  },onInspect:info=>{
    const visible=info&&(info.agents.length||info.structures.length);
    $('tile-inspection').hidden=!visible;
    if(!visible)return;
    $('inspection-title').textContent=[...info.structures.map(s=>titleCase(s.type)+(s.status!=='complete'?' · Under construction':'')),...info.agents.map(a=>a.name+(a.alive?'':' · Deceased'))].join(' · ');
    $('inspection-detail').textContent=titleCase(info.tile.terrain)+' · '+info.x+', '+info.y+
      (info.structures.some(s=>s.type==='farm_plot')?' · '+(info.tile.resources?.food||0)+' food growing':'');
  }});
  function render(next){
    const {world,snapshot}=next;
    renderer.setSnapshot(snapshot);
    $('world-title').textContent=world.demo?world.title:friendlyName(world.title);
    document.title=$('world-title').textContent+' · Agent World';
    $('world-subtitle').textContent=(world.demo?'Standard world':snapshot.config.width+' × '+snapshot.config.height+' world')+' · Seed '+world.seed;
    $('source-badge').textContent=world.demo?'DEMO SNAPSHOT':stateLabels[world.state]||titleCase(world.state).toUpperCase();
    $('source-badge').classList.toggle('live',world.state==='running');
    $('tick-label').replaceChildren(document.createTextNode('Tick '+snapshot.tick+' '));
    const horizon=document.createElement('span');horizon.textContent='/ '+(world.target_ticks??'—');$('tick-label').append(horizon);
    const inhabitants=Object.values(snapshot.agents).filter(a=>a.alive).length;
    $('population-label').textContent=inhabitants+' '+(inhabitants===1?'inhabitant':'inhabitants');
    $('scene-caption').textContent=world.demo?'A settlement, taking shape.':world.state==='completed'?'A world, at rest.':'Life in the laboratory.';
    $('scene-note').textContent=world.demo?'Curated demo · Partway through a 120-tick world.':world.state==='running'?'Latest saved state · Updates every 30 seconds.':'Showing the latest saved state.';
    const counts={};Object.values(snapshot.structures).forEach(s=>counts[titleCase(s.type)]=(counts[titleCase(s.type)]||0)+1);
    $('world-description').textContent=world.title+'. '+(world.demo?'Curated demonstration snapshot. ':'')+'Tick '+snapshot.tick+' of '+world.target_ticks+'. '+snapshot.config.width+' by '+snapshot.config.height+' tiles. '+inhabitants+' living agents. '+Object.entries(counts).map(([k,v])=>v+' '+k).join(', ')+'. '+Object.values(snapshot.agents).map(a=>a.name+' at '+a.position.x+', '+a.position.y).join('; ')+'.';
    $('stage-message').hidden=true;
    $('world-selection').textContent=world.demo?'Willowbank · Demo':friendlyName(world.title)+' · Seed '+world.seed;
    payload=next;
  }
  async function refresh(){
    if(busy||document.hidden)return;
    busy=true;
    try{
      const query=new URLSearchParams({run});if(cell)query.set('cell',cell);
      const response=await fetch('/api/world?'+query,{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error(response.status===404?'This world could not be found. Choose another world above.':'The world snapshot is not available yet.');
      render(await response.json());
    }catch(error){
      $('stage-message').textContent=payload?'Connection interrupted. Keeping the last snapshot; retrying automatically.':error.name==='TimeoutError'?'The host is taking a little longer. Retrying automatically.':error.message==='Failed to fetch'?'Could not reach the laboratory. Retrying automatically.':error.message;
      $('stage-message').classList.toggle('connection-error',Boolean(payload));$('stage-message').hidden=false;
      if(payload&&!payload.world.demo){$('source-badge').textContent='CONNECTION INTERRUPTED';$('source-badge').classList.remove('live');}
    }finally{
      busy=false;clearTimeout(pollTimer);
      // A loaded demo is a fixed snapshot, not a secretly running simulation.
      if(run!=='demo'||!payload)pollTimer=setTimeout(refresh,30000);
    }
  }
  const friendlyName=value=>String(value||'World').replace(/\[1m\]/ig,'').replace(/-\d{8}$/,'').replace(/-medium$/,'').replace(/^claude-/,'').replace(/^gpt-/,'GPT-').replace(/^(GPT-\d+(?:\.\d+)?)-/,'$1 ').replace(/^(gemini|grok|opus|sonnet|haiku|fable|muse)-/i,'$1 ').replace(/-(flash|spark|sol|terra|luna|astra|mini|codex)/g,' $1').replace(/(\d)-(\d)/g,'$1.$2').replace(/-(?=[a-z0-9])/gi,' ').replace(/^GPT /,'GPT-').replace(/\b[a-z]/g,c=>c.toUpperCase());
  const statusName=state=>({running:'Running',completed:'Completed',waiting_quota:'Quota paused',status_stale:'Last snapshot',needs_attention:'Paused',waiting_startup:'Waiting',paused_checkpoint:'Paused',paused_provider:'Paused'}[state]||titleCase(state));
  let worlds=[],worldFilter='all',discoveryBusy=false,discoveryError=false;
  const terminal=world=>['completed','failed','stopped','cancelled','invalid'].includes(world.state);
  function worldLink(world){return '/world?'+new URLSearchParams({run:world.run_id,cell:world.cell_id});}
  function renderPicker(){
    const query=$('world-search').value.trim().toLowerCase(),container=$('world-options');container.replaceChildren();
    if(worldFilter==='all'&&(!query||'willowbank demo'.includes(query))){
      const demo=document.createElement('a');demo.className='picker-demo';demo.href='/world';demo.textContent='Willowbank';
      const note=document.createElement('span');note.textContent='Demo world';demo.append(note);container.append(demo);
    }
    const groups=new Map();
    for(const world of worlds){
      if(worldFilter==='active'&&terminal(world)||worldFilter==='completed'&&world.state!=='completed')continue;
      if(query&&![friendlyName(world.title),world.run_id,world.recipe,world.seed].join(' ').toLowerCase().includes(query))continue;
      if(!groups.has(world.run_id))groups.set(world.run_id,[]);groups.get(world.run_id).push(world);
    }
    for(const cells of groups.values()){
      const world=cells[0],card=document.createElement('section');card.className='picker-study';
      const heading=document.createElement('h3');heading.textContent=friendlyName(world.title);card.append(heading);
      const meta=document.createElement('p');
      const date=new Date(world.created_at),dateText=Number.isNaN(date.getTime())?'':date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
      meta.textContent=[world.recipe?({'participant-v8-revised':'v8.1','participant-v6-1':'v6.1'}[world.recipe]||world.recipe.replace(/^participant-/,'').replaceAll('-',' ')):world.run_id.replace(/-20\d{6}.*$/,'').replaceAll('-',' '),dateText].filter(Boolean).join(' · ');card.append(meta);
      const seeds=document.createElement('div');seeds.className='picker-seeds';
      for(const item of cells){
        const link=document.createElement('a');link.href=worldLink(item);link.className='picker-seed';link.dataset.state=item.state;
        if(item.run_id===run&&(!cell||item.cell_id===cell)){link.setAttribute('aria-current','page');}
        const label=document.createElement('strong');label.textContent='Seed '+item.seed;
        const state=document.createElement('span');state.textContent=statusName(item.state);link.append(label,state);seeds.append(link);
      }
      card.append(seeds);container.append(card);
    }
    $('world-picker-status').textContent=discoveryError?'Could not refresh worlds. Showing the available list.':discoveryBusy&&!worlds.length?'Loading saved worlds…':groups.size+' '+(groups.size===1?'study':'studies');
    if(!container.children.length){const empty=document.createElement('p');empty.className='picker-empty';empty.textContent='No matching worlds.';container.append(empty);}
  }
  async function loadWorlds(){
    if(discoveryBusy)return;discoveryBusy=true;
    try{
      const response=await fetch('/api/worlds',{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error('Discovery failed');
      const data=await response.json();worlds=data.worlds;discoveryError=false;
    }catch{discoveryError=true;}finally{discoveryBusy=false;if($('world-picker').open)renderPicker();}
  }
  $('world-picker-open').addEventListener('click',()=>{$('world-picker').showModal();renderPicker();$('world-search').focus();loadWorlds();});
  $('world-picker-close').addEventListener('click',()=>$('world-picker').close());
  $('world-picker').addEventListener('click',event=>{if(event.target===$('world-picker')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
  $('world-search').addEventListener('input',renderPicker);
  document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{worldFilter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));renderPicker();}));
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden)clearTimeout(pollTimer);
    else {if(run!=='demo'||!payload)refresh();loadWorlds();}
  });
  window.addEventListener('pagehide',()=>{clearTimeout(pollTimer);renderer.destroy();});
  refresh();loadWorlds();
})();

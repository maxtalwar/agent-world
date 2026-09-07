'use strict';
(() => {
  const $=id=>document.getElementById(id),params=new URL(location.href).searchParams;
  const run=params.get('run')||'demo',cell=params.get('cell');
  const titleCase=value=>String(value||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
  const stateLabels={running:'LIVE WORLD',completed:'COMPLETED',waiting_quota:'QUOTA PAUSED',status_stale:'LAST SNAPSHOT',unknown:'LAST SNAPSHOT',paused_provider:'PROVIDER PAUSED',needs_attention:'RUN PAUSED',paused_checkpoint:'RUN PAUSED'};
  let payload,busy=false,pollTimer;
  if(run!=='demo'){
    const value=JSON.stringify([run,cell]);
    $('world-select').add(new Option('Loading selected world…',value));
    $('world-select').value=value;
  }
  const renderer=new WorldRenderer($('world-canvas'),{onInspect:info=>{
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
    $('world-title').textContent=world.title;
    document.title=world.title+' · Agent World';
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
    const value=world.demo?'demo':JSON.stringify([world.run_id,world.cell_id]);
    if(![...$('world-select').options].some(o=>o.value===value)){
      $('world-select').add(new Option(world.title+' · Seed '+world.seed,value));
    }
    $('world-select').value=value;
    for(const option of [...$('world-select').options])if(option.textContent==='Loading selected world…'&&option.value!==value)option.remove();
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
  async function loadWorlds(){
    try{
      const response=await fetch('/api/worlds',{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(!response.ok)return;
      const data=await response.json(),select=$('world-select'),selected=select.value;
      const current=[...select.options].find(o=>o.value===selected);
      const counts=new Map();
      for(const world of data.worlds){const key=world.title+'|'+world.seed;counts.set(key,(counts.get(key)||0)+1);}
      select.replaceChildren(new Option('Willowbank · Demo','demo'));
      const active=document.createElement('optgroup'),finished=document.createElement('optgroup');
      active.label='In progress & paused';finished.label='Completed worlds';
      for(const world of data.worlds){
        const value=JSON.stringify([world.run_id,world.cell_id]);
        const duplicate=counts.get(world.title+'|'+world.seed)>1;
        const label=world.title+' · Seed '+world.seed+' · '+titleCase(world.state)+(duplicate?' · '+world.run_id:'');
        const terminal=['completed','failed','stopped','cancelled','invalid'].includes(world.state);
        (terminal?finished:active).append(new Option(label,value));
      }
      if(active.children.length)select.append(active);if(finished.children.length)select.append(finished);
      if(current&&![...select.options].some(o=>o.value===selected))select.add(current);
      select.value=selected;
    }catch{/* Demo and an explicitly linked world remain usable during discovery failure. */}
  }
  $('world-select').addEventListener('focus',loadWorlds);
  $('world-select').addEventListener('change',()=>{
    const value=$('world-select').value;
    if(value==='demo'){location.href='/world';return;}
    const [run,cell]=JSON.parse(value);location.href='/world?'+new URLSearchParams({run,cell});
  });
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden)clearTimeout(pollTimer);
    else {if(run!=='demo'||!payload)refresh();loadWorlds();}
  });
  window.addEventListener('pagehide',()=>{clearTimeout(pollTimer);renderer.destroy();});
  refresh();loadWorlds();
})();

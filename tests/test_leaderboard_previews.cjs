const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('agent_world/static/leaderboard.js','utf8');
const nodes=new Map(),loaded=[],urls=[];
function element(id){
  if(!nodes.has(id))nodes.set(id,{innerHTML:'',value:'',showModal(){this.open=true},querySelectorAll(){return []},
    parentElement:{querySelector(){return {textContent:'',classList:{add(){}}}}},
    addEventListener(){},setAttribute(){}});
  return nodes.get(id);
}
const context=vm.createContext({document:{getElementById:element},location:{href:'http://localhost/leaderboards',pathname:'/leaderboards'},
  URL,URLSearchParams,AbortController,AbortSignal,console,
  WorldRenderer:class{setSnapshot(snapshot){loaded.push(snapshot.tick)}destroy(){loaded.push('destroyed')}},
  fetch:async url=>{urls.push(url);return {ok:true,json:async()=>({snapshot:{tick:60}})}}});
vm.runInContext(source.slice(0,source.indexOf("$('current-page').textContent")),context);
const row={id:'fable',model:'Fable 5.1',rank:1,scores:{capability:85},formulas:{capability:'Final health formula'},
  status:'Provisional · 1 seed',seeds:[41],note:'Internal authorization note',cost:53.99,reasoning:255,
  worlds:[{run_id:'exact-run',cell_id:'custom-cell-41',seed:41}]};
context.fixture={boards:[{id:'v8',title:'v8.1',columns:[['capability','Capability']],rows:[row],study_groups:[]}]};
vm.runInContext('data=fixture;showModel("fable");showScoringInfo()',context);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  const html=element('model-details').innerHTML;
  assert.match(html,/run=exact-run&amp;cell=custom-cell-41/);
  assert.match(html,/Only one seed completed; result is provisional/);
  assert.doesNotMatch(html,/Final health formula|Internal authorization|53.99|255|Launch commit/);
  assert.match(element('scoring-details').innerHTML,/Final health formula/);
  assert.deepEqual(urls,['/api/world?run=exact-run&cell=custom-cell-41']);
  assert.deepEqual(loaded,[60]);
  row.status='Replicated';row.seeds=[11,41];row.worlds.unshift({run_id:'exact-run',cell_id:'custom-cell-11',seed:11});
  vm.runInContext('showModel("fable")',context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal((element('model-details').innerHTML.match(/class="run-preview"/g)||[]).length,2);
  assert.doesNotMatch(element('model-details').innerHTML,/provisional/);
  assert.ok(loaded.includes('destroyed'),'Previous renderers are released');
  context.fetch=async()=>({ok:false});
  vm.runInContext('showModel("fable")',context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(loaded.filter(v=>v===60).length,3,'Unavailable evidence never renders a demo');
  console.log('Exact seed previews, shared formulas, provisional copy and renderer cleanup passed');
})().catch(error=>{console.error(error);process.exitCode=1});

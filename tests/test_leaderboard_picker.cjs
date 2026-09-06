// No provider calls: exercise partial-batch retries in the actual page script.
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const elements=new Map();
const element=id=>{
  if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,textContent:'',value:'',
    innerHTML:'',addEventListener(){},setAttribute(){},querySelectorAll(){return []},
    close(){this.closed=true},focus(){}});
  return elements.get(id);
};
const context=vm.createContext({document:{getElementById:element},Set,Map,AbortSignal,
  data:{boards:[{runs:[{id:'visible-run'}]}]},esc:s=>String(s),refresh(){},board(){return null},relative:s=>s});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../agent_world/static/leaderboard-launch.js'),'utf8'),context);

const browse=vm.runInContext('browseModels',context);
const choices=[{name:'Claude Opus 4.8',brain:'claude',lab:'anthropic',connector:'Claude Code'},
 {name:'GPT-6 Astra',brain:'codex',lab:'openai',connector:'Codex'},
 {name:'Some hosted model',brain:'openrouter',lab:'unknown',connector:'OpenRouter'}];
const history=[{recipe:'v8',rows:[{model:'GPT-6 Astra'}],runs:[]}];
assert.deepEqual(Array.from(browse(choices,'v8',history),m=>m.name),['Claude Opus 4.8']);
assert.equal(browse(choices,'v6',history).length,2);
assert.equal(browse(choices,'v8',history,{mode:'all'}).length,3);
assert.equal(browse(choices,'v8',history,{query:'hosted'}).length,1);
assert.equal(browse(choices,'v8',history,{mode:'all',lab:'anthropic'}).length,1);

const muse=[{name:'Muse Spark 1.2',brain:'muse',lab:'meta',connector:'Muse'},
 {name:'Muse Spark 1.2 Contributor',brain:'muse',lab:'meta',connector:'Muse'},
 {name:'Muse Spark 1.3',brain:'muse',lab:'meta',connector:'Muse'}];
const museHistory=[{recipe:'v8',rows:[],runs:[{model:'Muse Spark 1.2',ranked:false,cells:[{operational_state:'waiting_quota'}]}]}];
for(const options of [{},{mode:'all'},{query:'muse'}])
 assert.deepEqual(Array.from(browse(muse,'v8',museHistory,options),m=>m.name),['Muse Spark 1.3']);
assert.equal(browse(muse,'v6',museHistory).length,3);
museHistory[0].runs[0].model='Muse Spark 1.2 Contributor';
assert.equal(browse(muse,'v8',museHistory).length,1);
(async()=>{
  await vm.runInContext(`(async()=>{
    launchState.preview=[{id:'first'},{id:'second'}];
    renderReview=()=>{};
    globalThis.calls=[];globalThis.fail=true;
    launchPost=async(path,payload)=>{
      calls.push([...payload.request_ids]);
      return {results:payload.request_ids.map(id=>id==='second'&&fail?
        {id,error:'Temporary failure'}:{id,request:{state:'queued'}})};
    };
    await confirmLaunch();
  })()`,context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.calls)),[['first','second']]);
  assert.equal(element('launch-dialog').closed,undefined);
  assert.match(element('launch-error').textContent,/Some runs could not start/);
  await vm.runInContext('fail=false;confirmLaunch()',context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.calls)),[['first','second'],['second']]);
  assert.equal(element('launch-dialog').closed,true);
  await vm.runInContext('confirmLaunch()',context);
  assert.deepEqual(JSON.parse(JSON.stringify(context.calls)),[['first','second'],['second']]);
  vm.runInContext(`
    launchState.options={enabled:true,recipes:[{id:'v8',models:[{key:'astra'},{key:'gemini'}]},
      {id:'v6',models:[{key:'astra'}]}]};
    launchState.selected=new Set(['astra','gemini']);
    launchEl('launch-recipe').value='v6';
    launchModels=()=>{};launchConditions=()=>{};chooseRecipe();
  `,context);
  assert.deepEqual(Array.from(vm.runInContext('[...launchState.selected]',context)),['astra']);
  vm.runInContext("renderLaunches([{run_id:'visible-run'}])",context);
  assert.equal(element('launch-history').hidden,true);
  console.log('Batch retries, recipe selection and duplicate-card suppression passed');
})().catch(error=>{console.error(error);process.exitCode=1});

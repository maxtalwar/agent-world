// Exercise the entire page render with populated additional studies, not just helpers.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../agent_world/static/leaderboard.js'),'utf8');
const elements=new Map();
function element(id){
  if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,value:'',textContent:'',innerHTML:'',
    querySelectorAll(){return []},setAttribute(){},addEventListener(){}});
  return elements.get(id);
}
const errors=[];
const context=vm.createContext({document:{getElementById:element},location:{href:'http://localhost/leaderboards',pathname:'/leaderboards'},
  URL,AbortSignal,console:{error(...args){errors.push(args)}}});
vm.runInContext(source.slice(0,source.indexOf("$('current-page').textContent")),context);
const row={id:'gemini',model:'Gemini 3.8 Flash',rank:1,scores:{capability:57.57},status:'Reviewed recovery',cost:null,mean_decision_seconds:21.49};
const group={id:'extra',recipe:'participant-v8-revised',digest:'reviewed',columns:[['capability','Capability']],rows:[row],runs:[]};
const board={...group,id:'main',title:'v8.1',source:'Canonical metrics database',warnings:[],study_groups:[group]};
const fixture={boards:[board],warnings:[],updated_at:new Date().toISOString(),refresh_seconds:30};
context.payload=fixture;
context.fetch=async()=>({ok:true,json:async()=>context.payload});
(async()=>{
  await vm.runInContext('refresh()',context);
  assert.equal(errors.length,0,'Full page render must not throw');
  assert.equal(element('error').hidden,true);
  assert.match(element('table-body').innerHTML,/Gemini 3.8 Flash/);
  assert.match(element('additional-study-list').innerHTML,/Time \/ decision/);
  assert.match(element('table-head').innerHTML,/Time \/ decision/);
  assert.equal(element('refresh').disabled,false);
  if(process.argv[2]){
    context.payload=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
    await vm.runInContext('refresh()',context);
    assert.equal(errors.length,0,'Live payload must render without errors');
    const live=context.payload.boards.find(b=>b.recipe==='participant-v8-revised');
    for(const version of ['3.6','3.7','3.8']){
      const name=`Gemini ${version} Flash`;
      const matches=live.rows.filter(r=>r.model===name);
      assert.equal(matches.length,1,`${name} must appear once on the main leaderboard`);
      assert.ok(matches[0].cost>0,`${name} must have a cost/run`);
      assert.ok(element('table-body').innerHTML.includes(name));
    }
    assert.ok(live.rows.length>=17,'Previously admitted models must remain visible');
    assert.equal(element('error').hidden,true);
  }
  context.payload=fixture;
  group.recipe='participant-v6';
  await vm.runInContext('refresh()',context);
  assert.doesNotMatch(element('additional-study-list').innerHTML,/Time \/ decision|21.49 s/);
  group.recipe='participant-v8-revised';
  context.payload={...fixture,boards:[{...board,columns:undefined}]};
  await vm.runInContext('refresh()',context);
  assert.equal(element('sync-status').textContent,'Display error');
  assert.doesNotMatch(element('error').textContent,/Connection interrupted/);
  assert.equal(errors.length,1);
  context.fetch=async()=>{throw new Error('offline')};
  await vm.runInContext('refresh()',context);
  assert.equal(element('sync-status').textContent,'Connection interrupted');
  assert.equal(element('refresh').disabled,false);
  console.log('Full page rendering, additional-study columns, and distinct error handling passed');
})().catch(error=>{console.error(error);process.exitCode=1});

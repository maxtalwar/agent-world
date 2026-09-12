const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../agent_world/static/leaderboard.js'),'utf8');
const storage=new Map();
function page(){
 const elements=new Map();
 const get=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',value:'',querySelectorAll(){return []}});return elements.get(id)};
 const context=vm.createContext({document:{getElementById:get},URL,location:{href:'http://localhost/leaderboards',pathname:'/leaderboards'},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}});
 vm.runInContext(source.slice(0,source.indexOf("$('current-page').textContent")),context);
 const rows=[{id:'a',model:'A',rank:1,status:'Certified',scores:{capability:80,execution:90},reasoning:1234,reasoning_estimated:true,cost:10,mean_decision_seconds:5},
 {id:'b',model:'B',rank:2,status:'Provisional · 1 seed',scores:{capability:60,execution:80},reasoning:null,cost:20,mean_decision_seconds:10}];
 context.fixture={id:'v81',recipe:'participant-v8-revised',columns:[['capability','Capability'],['execution','Execution']],rows,runs:[],study_groups:[]};
 vm.runInContext('data={boards:[fixture]};renderTable();renderAdditionalStudies()',context);
 return {context,get,run:code=>vm.runInContext(code,context)};
}
let p=page();
assert.match(p.get('table-head').innerHTML,/Reasoning tokens \/ decision/);
assert.match(p.get('table-body').innerHTML,/~1,234/);
assert.match(p.get('column-options').innerHTML,/data-column="model" checked disabled/);
const count=()=>[...p.get('table-head').innerHTML.matchAll(/<th /g)].length;
const original=count();
p.run("sortKey='cost';setColumnVisible('cost',false)");
assert.equal(count(),original-1);
assert.doesNotMatch(p.get('table-head').innerHTML,/Cost \/ run/);
assert.doesNotMatch(p.get('table-body').innerHTML,/\$10/);
p.run('renderTable()');assert.equal(count(),original-1);
p=page();assert.equal(count(),original-1); // Persist after reload.
p.run("setColumnVisible('cost',true);setColumnVisible('reasoning',false)");
assert.doesNotMatch(p.get('table-body').innerHTML,/~1,234/);
p.run("setColumnVisible('reasoning',true);setColumnVisible('capability',false)");
assert.ok(p.get('table-body').innerHTML.indexOf('data-model="a"')<p.get('table-body').innerHTML.indexOf('data-model="b"'));
p.run("setColumnVisible('model',false)");assert.match(p.get('table-head').innerHTML,/>Model/);
p.run("fixture.study_groups=[{...fixture,id:'other',study_groups:[]}];setColumnVisible('reasoning',false)");
assert.doesNotMatch(p.get('additional-study-list').innerHTML,/Reasoning tokens/);
p.run("setColumnVisible('reasoning',true)");assert.match(p.get('additional-study-list').innerHTML,/Reasoning tokens/);
console.log('Reasoning values, column visibility, persistence, sorting and additional tables passed');

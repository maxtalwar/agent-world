// Camera geometry and input regression tests; no browser or model calls.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const callbacks=new Map();let frameId=0;
const context2d=new Proxy({},{get:(_target,key)=>()=>{}});
function canvas(){
  const listeners=new Map(),captured=new Set(),classes=new Set();
  return {width:0,height:0,listeners,captured,classes,
    getContext:()=>context2d,getBoundingClientRect:()=>({width:1280,height:720,left:0,top:0}),
    addEventListener:(key,value)=>listeners.set(key,value),removeEventListener:key=>listeners.delete(key),
    classList:{add:key=>classes.add(key),remove:key=>classes.delete(key)},
    setPointerCapture:id=>captured.add(id),hasPointerCapture:id=>captured.has(id),releasePointerCapture:id=>captured.delete(id),focus(){}};
}
const window={},reduced={matches:true,addEventListener(){},removeEventListener(){}};
const scope=vm.createContext({window,document:{hidden:false,createElement:canvas,addEventListener(){},removeEventListener(){}},
  matchMedia:()=>reduced,ResizeObserver:class{observe(){}disconnect(){}},devicePixelRatio:1,performance:{now:()=>0},
  requestAnimationFrame:fn=>{callbacks.set(++frameId,fn);return frameId;},cancelAnimationFrame:id=>callbacks.delete(id)});
vm.runInContext(fs.readFileSync('agent_world/static/world-renderer.js','utf8'),scope);
const Renderer=window.WorldRenderer;
const surface=canvas();let inspected,rotation;
const viewer=new Renderer(surface,{onInspect:value=>inspected=value,onRotate:value=>rotation=value});
const snapshot=JSON.parse(fs.readFileSync('agent_world/static/world-demo.json','utf8')).snapshot;
const original=JSON.stringify(snapshot);viewer.setSnapshot(snapshot);
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,a+' != '+b);
function flush(){const work=[...callbacks.values()];callbacks.clear();for(const fn of work)fn(0);}
function yaw(angle){viewer.setYaw(angle);flush();}
const initialScale=viewer.scale;
for(let step=0;step<=24;step++){
  const angle=step*Math.PI/12;yaw(angle);
  close(viewer.scale,initialScale);
  const [cx,cy]=viewer.project(snapshot.config.width/2,snapshot.config.height/2);
  close(viewer.ox+cx*viewer.scale,viewer.w/2);
  close(viewer.oy+cy*viewer.scale,viewer.h/2+41*viewer.scale+12);
  for(const [x,y] of [[0,0],[5.25,10.25],[15.99,15.99]]){
    const p=viewer.project(x,y),q=viewer.unproject(...p);close(q[0],x);close(q[1],y);
    const raised=viewer.project(x,y,30);close(raised[0],p[0]);close(raised[1],p[1]-30);
  }
  const [sx,sy]=viewer.project(5.5,10.5);
  viewer.inspect({clientX:viewer.ox+sx*viewer.scale,clientY:viewer.oy+sy*viewer.scale});
  assert.equal(inspected.x,5);assert.equal(inspected.y,10);
  assert.ok(inspected.structures.some(s=>s.type==='farm_plot'));
  assert.ok(Number.isFinite(rotation.northAngle));
}
yaw(Math.PI/2);
const [x90,y90]=viewer.project(2,3);close(x90,-190);close(y90,-19);
assert.equal(JSON.stringify(snapshot),original,'Orbit must never mutate a snapshot');
const depth0=()=>viewer.project(1,1)[1]-viewer.project(4,4)[1];
yaw(0);assert.ok(depth0()<0);yaw(Math.PI);assert.ok(depth0()>0);
const pointer={button:0,isPrimary:true,pointerId:1,clientX:200,clientY:200};
viewer.pointerDown(pointer);
const start=viewer.yaw;viewer.pointerMove({...pointer,clientY:600});flush();close(viewer.yaw,start);
viewer.pointerMove({...pointer,pointerId:2,clientX:600});flush();close(viewer.yaw,start);
viewer.pointerMove({...pointer,clientX:400});flush();assert.notEqual(viewer.yaw,start);
viewer.pointerUp({...pointer,pointerId:2});assert.ok(viewer.drag);
viewer.pointerUp(pointer);assert.equal(viewer.drag,null);assert.equal(surface.captured.size,0);
assert.ok(!surface.classes.has('rotating'));
let prevented=false;
surface.listeners.get('keydown')({key:'Home',preventDefault(){prevented=true;}});flush();
assert.ok(prevented);close(viewer.yaw,0);
surface.listeners.get('keydown')({key:'ArrowRight',preventDefault(){}});flush();close(viewer.yaw,Math.PI/12);
viewer.setSnapshot(snapshot);close(viewer.yaw,Math.PI/12);
const rectangular=JSON.parse(JSON.stringify(snapshot));rectangular.config.width=8;rectangular.tiles=rectangular.tiles.map(row=>row.slice(0,8));
rectangular.agents={};rectangular.structures={};
viewer.setSnapshot(rectangular);
for(const angle of [0,Math.PI/2,Math.PI,Math.PI*1.5]){
  yaw(angle);
  for(const [x,y] of [[0,0],[8,0],[8,16],[0,16]]){
    const [sx,sy]=viewer.project(x,y);const px=viewer.ox+sx*viewer.scale,py=viewer.oy+sy*viewer.scale;
    assert.ok(px>=0&&px<=viewer.w);assert.ok(py>=0&&py+22*viewer.scale<=viewer.h);
  }
}
const preview=new Renderer(canvas(),{preview:true});preview.setSnapshot(snapshot);preview.setYaw(1);close(preview.yaw,0);
viewer.pointerDown(pointer);viewer.destroy();preview.destroy();flush();
assert.equal(surface.listeners.size,0);assert.equal(surface.captured.size,0);
console.log('Full-circle projection, fixed elevation, hit testing, bounds, input, refresh and cleanup passed.');


// Grouped residents must stay at the same ground points throughout an orbit.
const crowdCanvas=canvas(),crowd=new Renderer(crowdCanvas),crowdSnapshot=JSON.parse(JSON.stringify(snapshot));
crowdSnapshot.agents=Object.fromEntries(Object.values(crowdSnapshot.agents).slice(0,4).map((agent,i)=>{
  const id='resident-'+i;return [id,{...agent,id,position:{x:8,y:8}}];
}));
const crowdOriginal=JSON.stringify(crowdSnapshot);
crowd.setSnapshot(crowdSnapshot);
let groundAt,drawn=[];
const nativeAt=crowd.at,nativeAgent=crowd.agent;
crowd.at=function(x,y,draw){groundAt={x:x+.5,y:y+.5};nativeAt.call(this,x,y,draw);};
crowd.agent=function(agent){drawn.push({id:agent.id,...groundAt});};
const anchors=new Map();
let forwardOrder;
for(const angle of [0,Math.PI/4,Math.PI/2,Math.PI,Math.PI*1.5]){
  crowd.setYaw(angle);flush();drawn=[];crowd.paint(0);
  assert.equal(drawn.length,4);
  for(const point of drawn){
    assert.ok(point.x>8&&point.x<9&&point.y>8&&point.y<9,'Feet must stay within the occupied tile');
    if(!anchors.has(point.id))anchors.set(point.id,point);
    const fixed=anchors.get(point.id);close(point.x,fixed.x);close(point.y,fixed.y);
  }
  const depths=drawn.map(point=>crowd.project(point.x,point.y)[1]);
  for(let i=1;i<depths.length;i++)assert.ok(depths[i]>=depths[i-1]-1e-8);
  if(angle===Math.PI/2)forwardOrder=drawn.map(point=>point.id);
  if(angle===Math.PI*1.5)assert.deepEqual(drawn.map(point=>point.id),forwardOrder.slice().reverse());
}
assert.equal(JSON.stringify(crowdSnapshot),crowdOriginal);
// Reordering JSON and another resident departing/arriving cannot shuffle bystanders.
const reordered=JSON.parse(JSON.stringify(crowdSnapshot));
reordered.agents=Object.fromEntries(Object.entries(reordered.agents).reverse());
delete reordered.agents['resident-0'];
reordered.agents.newcomer={...Object.values(reordered.agents)[0],id:'newcomer'};
crowd.setSnapshot(reordered);drawn=[];crowd.paint(0);
for(const point of drawn.filter(point=>point.id!=='newcomer')){
  close(point.x,anchors.get(point.id).x);close(point.y,anchors.get(point.id).y);
}
// Idle animation can move the torso but not the feet.
crowd.agent=nativeAgent;
const nativeRect=crowd.rect,feet=[];
let translateY=0;
crowd.c=new Proxy({},{get:(_target,key)=>key==='translate'?(x,y)=>{translateY+=y;}:()=>{}});
crowd.rect=function(x,y,w,h,color){if(color==='#4c5953')feet.push(y+h+translateY);};
reduced.matches=false;
for(const time of [0,3,11]){
  translateY=0;crowd.agent(Object.values(reordered.agents)[0],0,time);
}
assert.equal(feet.length,6);feet.forEach(value=>close(value,0));
crowd.rect=nativeRect;crowd.destroy();reduced.matches=true;
console.log('World-anchored crowd positions, occlusion order, stable slots and planted feet passed.');

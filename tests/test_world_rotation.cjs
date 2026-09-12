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
  if(angle===Math.PI/2)forwardOrder=drawn.map(point=>({...point,depth:crowd.project(point.x,point.y)[1]}));
  if(angle===Math.PI*1.5)for(let i=0;i<forwardOrder.length;i++)for(let j=i+1;j<forwardOrder.length;j++){
    if(Math.abs(forwardOrder[i].depth-forwardOrder[j].depth)>1e-8)
      assert.ok(drawn.findIndex(p=>p.id===forwardOrder[i].id)>drawn.findIndex(p=>p.id===forwardOrder[j].id));
  }
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

// Shelter/storage arrangements are fixed in world space and preserve native structures.
const buildings=new Renderer(canvas(),{preview:true});buildings.setSnapshot(snapshot);
const pair=[{id:'hut',type:'shelter',status:'complete',position:{x:8,y:8}},
  {id:'supplies',type:'storage',status:'complete',position:{x:8,y:8}}];
const sourcePair=JSON.stringify(pair),layout=()=>JSON.stringify(buildings.structureLayout(pair));
const fixedLayout=layout();
for(let step=0;step<24;step++){
  buildings.yaw=step*Math.PI/12;
  assert.equal(layout(),fixedLayout);
  assert.equal(JSON.stringify(buildings.structureLayout(pair.slice().reverse())),fixedLayout);
}
const variants=new Set();
for(let x=0;x<16;x++){
  const items=buildings.structureLayout(pair.map(s=>({...s,position:{x,y:8}})));
  variants.add(JSON.stringify(items.map(({dx,dy})=>[dx,dy])));
  const bounds=items.map(({structure,dx,dy,scale})=>{
    const radius=(structure.type==='shelter'?.41:.24)*scale;
    assert.ok(Math.abs(dx)+radius<.5&&Math.abs(dy)+radius<.5,'Footprints stay inside their tile');
    return {dx,dy,radius};
  });
  assert.ok(Math.abs(bounds[0].dx-bounds[1].dx)>bounds[0].radius+bounds[1].radius||
    Math.abs(bounds[0].dy-bounds[1].dy)>bounds[0].radius+bounds[1].radius,'Hut and crate footprints do not intersect');
}
assert.equal(variants.size,4);
assert.equal(JSON.stringify(pair),sourcePair);
assert.equal(buildings.structureLayout([pair[0]])[0].scale,buildings.structureLayout(pair).find(s=>s.structure.type==='shelter').scale);
let icon;
buildings.storage=()=>icon='crate';buildings.house=type=>icon=type;buildings.construction=()=>icon='construction';
buildings.structure(pair[1],{});assert.equal(icon,'crate');
buildings.structure(pair[0],{});assert.equal(icon,'shelter');
buildings.structure({...pair[1],status:'under_construction'},{});assert.equal(icon,'construction');
buildings.destroy();
console.log('Distinct storage/shelter icons, four stable layouts, separate footprints and construction status passed.');

const yard=new Renderer(canvas(),{preview:true}),yardState=JSON.parse(JSON.stringify(crowdSnapshot));
yardState.structures=Object.fromEntries(pair.map(s=>[s.id,s]));
yard.setSnapshot(yardState);
const yardAnchors=new Map(yard.agents.map(a=>[a.id,{...yard.agentAnchor(a)}]));
for(const a of yard.agents){
  const anchor=yard.agentAnchor(a);
  for(const part of yard.structureLayout(pair)){
    const radius=(part.structure.type==='storage'?.24:.41)*part.scale;
    const clearance=Math.hypot(Math.max(0,Math.abs(anchor.x-part.dx)-radius),Math.max(0,Math.abs(anchor.y-part.dy)-radius));
    assert.ok(clearance>=.065,'Residents need clearance from the hut and crate');
  }
}
yard.yaw=1.7;yard.setSnapshot(yardState);
for(const a of yard.agents)assert.deepEqual({...yard.agentAnchor(a)},yardAnchors.get(a.id));
yardState.agents['aaa-new']={...yard.agents[0],id:'aaa-new'};
yard.setSnapshot(yardState);
for(const a of yard.agents.filter(a=>a.id!=='aaa-new'))assert.deepEqual({...yard.agentAnchor(a)},yardAnchors.get(a.id));
yard.destroy();
console.log('Residents clear both buildings and retain their places after rotation, refresh, and arrivals.');

// Mountain geometry is shared, deterministic, and display-only.
let mountainInspection;
const mountains=new Renderer(canvas(),{onInspect:value=>mountainInspection=value}),mountainSnapshot=JSON.parse(JSON.stringify(snapshot));
const savedSnapshot=JSON.stringify(mountainSnapshot);
mountains.setSnapshot(mountainSnapshot);
const geometry=JSON.stringify(mountains.mountainFaces),terrainKey=mountains.mountainKey;
assert.ok(mountains.mountainFaces.length>100);
const vertexHeights=new Map();
for(const face of mountains.mountainFaces){
  for(const [x,y,z] of face.points){
    const key=x+','+y;
    if(vertexHeights.has(key))close(vertexHeights.get(key),z);
    vertexHeights.set(key,z);assert.ok(z>=0&&Number.isFinite(z));
  }
  const [a,b,c]=face.points,cx=(a[0]+b[0]+c[0])/3,cy=(a[1]+b[1]+c[1])/3;
  close(mountains.terrainHeight(cx,cy),(a[2]+b[2]+c[2])/3);
}
close(mountains.terrainHeight(0.5,0.5),0);
mountainSnapshot.agents={};
for(const [i,x,y] of [[0,10,4],[1,13,2],[2,8,4]]){
  mountainSnapshot.agents['climber-'+i]={id:'climber-'+i,name:'Climber '+i,position:{x,y},alive:true};
}
mountains.setSnapshot(mountainSnapshot);
const nativeMountainAgent=mountains.agent,nativeMountainAt=mountains.at;
let drawnClimbers=[],objectPosition,vertical;
mountains.at=function(x,y,draw){
  objectPosition={x:x+.5,y:y+.5};
  return nativeMountainAt.call(this,x,y,()=>{
    vertical=0;const context=this.c;
    this.c=new Proxy(context,{get(target,key){
      if(key==='translate')return (dx,dy)=>{vertical+=dy;target.translate(dx,dy);};
      return target[key];
    }});
    draw();this.c=context;
  });
};
mountains.agent=function(a){
  const height=this.terrainHeight(objectPosition.x,objectPosition.y);
  close(vertical,-height);
  drawnClimbers.push({id:a.id,...objectPosition,height});
};
for(let step=0;step<24;step++){
  mountains.setYaw(step*Math.PI/12);flush();drawnClimbers=[];mountains.paint(0);
  assert.equal(drawnClimbers.length,3);
  assert.equal(JSON.stringify(mountains.mountainFaces),geometry,'Orbit cannot regenerate the range');
  for(const climber of drawnClimbers){
    const p=mountains.project(climber.x,climber.y,climber.height);
    assert.ok(Number.isFinite(p[0])&&Number.isFinite(p[1]));
    mountains.inspect({clientX:mountains.ox+p[0]*mountains.scale,clientY:mountains.oy+(p[1]-12)*mountains.scale});
    assert.ok(mountainInspection.agents.some(a=>a.id===climber.id),'Raised residents remain inspectable');
  }
  assert.ok(drawnClimbers.some(a=>a.height>30),'Peak residents are lifted to the visible terrain');
}
mountains.agent=nativeMountainAgent;mountains.at=nativeMountainAt;
mountains.setSnapshot(snapshot);
assert.equal(JSON.stringify(snapshot),savedSnapshot,'Rendering never changes simulation terrain or positions');
const otherSeed=JSON.parse(JSON.stringify(snapshot));otherSeed.config.seed=42;mountains.setSnapshot(otherSeed);
assert.notEqual(mountains.mountainKey,terrainKey);
assert.notEqual(JSON.stringify(mountains.mountainFaces),geometry);
mountains.destroy();
console.log('Connected mountain seams, exact surface heights, seeded geometry, residents and full-circle stability passed.');

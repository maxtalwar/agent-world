/* Native snapshot -> a quiet isometric diorama. No simulation state is mutated. */
'use strict';
(function (global) {
  const C = {grass:['#a8bd79','#aec37e','#a6bc77','#b3c682'], forest:['#829e65','#8ba66b','#91ac70'], mountain:['#a4ac8c','#abb295','#b2b79b'], water:['#79b7ba','#7dbbbd','#80bdbf']};
  const hash = (x,y,n=0) => {let v=Math.imul(x+71,374761393)^Math.imul(y+37,668265263)^Math.imul(n+11,1274126177);v=Math.imul(v^(v>>>13),1274126177);return ((v^(v>>>16))>>>0)/4294967295;};
  const SHELTER_SCALE=0.54,STORAGE_SCALE=0.54; // Fixed sizes, including on shared tiles.
  const colors=['#c97b55','#69879a','#b8849f','#c8a653','#7d9671','#b76b64','#7e80a4','#5c9690','#d19b6b','#8e9dba'];
  class WorldRenderer {
    constructor(canvas,{preview=false,onInspect=()=>{},onRotate=()=>{}}={}) {
      this.canvas=canvas;this.ctx=canvas.getContext('2d');this.preview=preview;this.onInspect=onInspect;this.onRotate=onRotate;this.yaw=0;this.agentSlots=new Map();this.drag=null;this.rotationFrame=0;
      this.reduced=matchMedia('(prefers-reduced-motion: reduce)');this.snapshot=null;this.frame=0;this.lastPaint=0;
      this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(canvas);
      this.motionListener=()=>this.restart();this.reduced.addEventListener('change',this.motionListener);
      this.visibilityListener=()=>this.restart();document.addEventListener('visibilitychange',this.visibilityListener);
      this.pointerListener=e=>this.pointerMove(e);this.leaveListener=()=>this.onInspect(null);
      this.downListener=e=>this.pointerDown(e);this.upListener=e=>this.pointerUp(e);
      this.keyListener=e=>{
        this.canvas.classList.remove('pointer-focus');
        if(!['ArrowLeft','ArrowRight','Home'].includes(e.key))return;
        e.preventDefault();this.setYaw(e.key==='Home'?0:this.yaw+(e.key==='ArrowLeft'?-1:1)*Math.PI/12);
      };
      if(!preview){canvas.addEventListener('pointermove',this.pointerListener);canvas.addEventListener('pointerleave',this.leaveListener);
        canvas.addEventListener('pointerdown',this.downListener);canvas.addEventListener('pointerup',this.upListener);
        canvas.addEventListener('pointercancel',this.upListener);canvas.addEventListener('lostpointercapture',this.upListener);
        canvas.addEventListener('keydown',this.keyListener);}
    }
    setSnapshot(snapshot) {
      this.snapshot=snapshot;this.structures=Object.values(snapshot.structures||{});
      this.agents=Object.values(snapshot.agents||{});this.occupied=new Map();
      for(const a of this.agents){const k=a.position.x+','+a.position.y;if(!this.occupied.has(k))this.occupied.set(k,[]);this.occupied.get(k).push(a);}
      // Keep each resident's display slot while they remain on the same tile.
      // Sub-tile positions are presentation only; the native snapshot is untouched.
      const nextSlots=new Map();
      for(const [tile,party] of this.occupied){
        const used=new Set();
        for(const agent of party){
          const previous=this.agentSlots.get(agent.id);
          if(previous?.tile===tile){nextSlots.set(agent.id,previous);used.add(previous.slot);}
        }
        for(const agent of party.slice().sort((a,b)=>a.id.localeCompare(b.id))){
          if(nextSlots.has(agent.id))continue;
          let slot=[1,2,0,3].find(candidate=>!used.has(candidate));
          if(slot===undefined){slot=4;while(used.has(slot))slot++;}
          used.add(slot);nextSlots.set(agent.id,{tile,slot});
        }
      }
      this.agentSlots=nextSlots;
      this.placeResidents();
      this.resize();
    }
    agentAnchor(agent){
      const record=this.agentSlots.get(agent.id);
      if(record.anchor)return record.anchor;
      const slot=record.slot;
      if(slot<4){
        // A short diagonal row in world space, initially horizontal on screen.
        const dx=(slot-1.5)*12,dy=4;
        return {x:dx/76+dy/38,y:dy/38-dx/76};
      }
      const angle=slot*2.399963229728653,radius=.32;
      return {x:Math.cos(angle)*radius,y:Math.sin(angle)*radius};
    }
    placeResidents(){
      const solid=layout=>layout.filter(p=>!['farm_plot','road','irrigation'].includes(p.structure.type));
      for(const [tile,party] of this.occupied){
        const structures=this.structures.filter(s=>s.position.x+','+s.position.y===tile);
        const obstacles=solid(this.structureLayout(structures));
        if(!obstacles.length)continue;
        const gap=p=>Math.min(...obstacles.map(o=>{
          const radius=(o.structure.type==='storage'?.24:.41)*o.scale;
          return Math.hypot(Math.max(0,Math.abs(p.x-o.dx)-radius),Math.max(0,Math.abs(p.y-o.dy)-radius));
        }));
        const candidates=[];
        for(let y=0;y<=16;y++)for(let x=0;x<=16;x++){
          const p={x:-.44+x*.055,y:-.44+y*.055};
          if(gap(p)>=.065)candidates.push(p);
        }
        // Extremely dense tiles use their clearest corners, never camera-relative offsets.
        if(!candidates.length)for(const x of [-.46,.46])for(const y of [-.46,.46])candidates.push({x,y});
        const placed=[];
        const ordered=party.slice().sort((a,b)=>a.id.localeCompare(b.id));
        for(const agent of ordered){
          const record=this.agentSlots.get(agent.id);
          if(record.anchor&&gap(record.anchor)>=.065)placed.push(record.anchor);
          else delete record.anchor;
        }
        for(const agent of ordered){
          const record=this.agentSlots.get(agent.id);
          if(record.anchor)continue;
          const preferred=this.agentAnchor(agent);
          const score=p=>Math.min(.3,gap(p))+
            (placed.length?Math.min(...placed.map(q=>Math.hypot(p.x-q.x,p.y-q.y)))*2:0)-
            Math.hypot(p.x-preferred.x,p.y-preferred.y)*.08;
          const best=candidates.reduce((a,b)=>score(b)>score(a)?b:a);
          record.anchor={...best};placed.push(record.anchor);
        }
      }
    }
    resize(){
      const box=this.canvas.getBoundingClientRect();if(!box.width||!box.height)return;
      this.w=box.width;this.h=box.height;const dpr=Math.min(devicePixelRatio||1,2);
      this.canvas.width=Math.round(this.w*dpr);this.canvas.height=Math.round(this.h*dpr);this.dpr=dpr;
      if(!this.snapshot)return;
      const {width,height}=this.snapshot.config;
      const total=Math.hypot(width,height)*Math.SQRT2;
      const margin=this.preview?24:Math.min(90,this.w*.055);
      this.scale=Math.min((this.w-margin*2)/(total*38),(this.h-(this.preview?35:115))/(total*19+100));
      this.updateCamera();this.buildBase();this.restart();
    }
    // Orbit the horizontal world plane; vertical heights always stay vertical.
    project(x,y,z=0){
      const c=Math.cos(this.yaw),s=Math.sin(this.yaw),rx=x*c-y*s,ry=x*s+y*c;
      return [(rx-ry)*38,(rx+ry)*19-z];
    }
    unproject(sx,sy){
      const rx=(sx/38+sy/19)/2,ry=(sy/19-sx/38)/2,c=Math.cos(this.yaw),s=Math.sin(this.yaw);
      return [rx*c+ry*s,-rx*s+ry*c];
    }
    updateCamera(){
      const {width,height}=this.snapshot.config,[cx,cy]=this.project(width/2,height/2);
      this.ox=this.w/2-cx*this.scale;this.oy=this.h/2+(41*this.scale)+(this.preview?0:12)-cy*this.scale;
    }
    setYaw(yaw){
      if(this.preview||!this.snapshot||!Number.isFinite(yaw))return;
      this.yaw=((yaw+Math.PI)%(2*Math.PI)+2*Math.PI)%(2*Math.PI)-Math.PI;
      this.onInspect(null);
      const [nx,ny]=this.project(0,-1);
      this.onRotate({yaw:this.yaw,northAngle:Math.atan2(nx,-ny)*180/Math.PI});
      // Coalesce pointer events to one rebuild per display frame.
      if(!this.rotationFrame)this.rotationFrame=requestAnimationFrame(()=>{
        this.rotationFrame=0;this.updateCamera();this.buildBase();this.paint(performance.now()/1000);
      });
    }
    pointerDown(event){
      if(this.preview||!this.snapshot||event.button!==0||!event.isPrimary||this.drag)return;
      this.drag={id:event.pointerId,x:event.clientX,yaw:this.yaw};
      this.canvas.setPointerCapture(event.pointerId);this.canvas.classList.add('rotating');this.canvas.classList.add('pointer-focus');
      this.onInspect(null);
    }
    pointerMove(event){
      if(this.drag){
        if(event.pointerId===this.drag.id)this.setYaw(this.drag.yaw+(event.clientX-this.drag.x)*Math.PI/Math.max(240,this.w*.65));
      }else this.inspect(event);
    }
    pointerUp(event){
      if(!this.drag||event.pointerId!==this.drag.id)return;
      this.drag=null;this.canvas.classList.remove('rotating');
      if(this.canvas.hasPointerCapture(event.pointerId))this.canvas.releasePointerCapture(event.pointerId);
    }
    groundPoint(x,y,z=0){return this.project((x/38+y/19)/2,(y/19-x/38)/2,z);}
    groundPoly(points,fill,stroke){this.poly(points.map(p=>this.groundPoint(...p)),fill,stroke);}
    groundLine(points,color,width=1){this.line(points.map(p=>this.groundPoint(...p)),color,width);}
    mesh(faces){
      const depth=points=>points.reduce((sum,[x,y,z=0])=>sum+this.project(x,y)[1]+z*.25,0)/points.length;
      faces.sort((a,b)=>depth(a.points)-depth(b.points));
      for(const face of faces){
        this.poly(face.points.map(p=>this.project(...p)),face.fill,face.stroke);
        for(const detail of face.details||[])this.poly(detail.points.map(p=>this.project(...p)),detail.fill);
      }
    }
    poly(points,fill,stroke){
      const c=this.c;c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();
      if(fill){c.fillStyle=fill;c.fill();}if(stroke){c.strokeStyle=stroke;c.lineWidth=1;c.stroke();}
    }
    line(points,color,width=1){const c=this.c;c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.strokeStyle=color;c.lineWidth=width;c.lineCap='round';c.lineJoin='round';c.stroke();}
    ellipse(x,y,rx,ry,color){const c=this.c;c.beginPath();c.ellipse(x,y,rx,ry,0,0,Math.PI*2);c.fillStyle=color;c.fill();}
    rect(x,y,w,h,color){this.c.fillStyle=color;this.c.fillRect(x,y,w,h);}
    tile(x,y,color){this.poly([[x,y],[x+1,y],[x+1,y+1],[x,y+1]].map(p=>this.project(...p)),color);}
    at(x,y,fn){const [sx,sy]=this.project(x+.5,y+.5);this.c.save();this.c.translate(sx,sy);fn();this.c.restore();}
    groundPatch(color='#b9b180',r=32){this.groundPoly([[0,-r/2],[r,0],[0,r/2],[-r,0]],color);}
    tree(x,y,variant=0){
      this.ellipse(9,5,21,8,'#385d3824');
      this.poly([[-3,2],[1,4],[4,2],[4,-28],[-3,-28]],'#746548');
      if(variant%3===0){
        this.poly([[0,-70],[-19,-35],[-10,-36],[-25,-17],[0,-6],[24,-17],[11,-35],[18,-34]],'#467356');
        this.poly([[0,-70],[-19,-35],[-9,-36],[-24,-18],[0,-10]],'#618958');
        this.poly([[0,-62],[-9,-42],[0,-38]],'#82a267');
        this.line([[-15,-27],[-3,-22]],'#86a46b',2);
      }else{
        this.poly([[-20,-24],[-27,-40],[-20,-56],[-9,-67],[10,-64],[26,-48],[22,-27],[7,-16]],'#547d51');
        this.poly([[-20,-24],[-27,-40],[-20,-56],[-9,-67],[8,-63],[11,-44],[0,-29]],'#739452');
        this.poly([[-20,-45],[-14,-58],[-3,-63],[3,-53],[-2,-42]],'#91aa62');
        this.poly([[11,-44],[23,-45],[19,-29],[7,-23],[1,-29]],'#60874e');
        this.rect(-12,-49,3,2,'#b2c47a');this.rect(7,-37,3,2,'#8fab63');
      }
    }
    rock(x,y,seed){
      const h=25+seed*30;this.ellipse(5,5,25,9,'#52604d24');
      this.poly([[-26,1],[-16,-h+10],[0,-h],[18,-h+13],[29,0],[11,10]],'#8a9686');
      this.poly([[-26,1],[-16,-h+10],[0,-h],[1,-7],[-10,8]],'#bec1a9');
      this.poly([[0,-h],[18,-h+13],[29,0],[12,-6],[1,-7]],'#a5ad99');
      this.poly([[-16,-h+10],[0,-h],[10,-h+8],[1,-h+5],[-5,-h+12]],'#dce0cc');
      this.line([[-17,-9],[-11,-18],[-8,-18]],'#d0d0b8',2);
    }
    house(type,seed,ground=true){
      const workshop=type==='workshop',shelter=type==='shelter';
      const r=.36,h=shelter?22:30,peak=h+(shelter?18:22);
      if(ground)this.groundPatch('#b7ae82',34);
      if(!shelter)this.ellipse(9,10,32,10,'#59614230');
      const roof=workshop?'#687e81':shelter?'#ac915e':seed>.5?'#b56f52':'#bb7c56';
      const lightRoof=workshop?'#84999a':shelter?'#d2b57a':'#d3956a';
      const window=(axis,side)=>({points:axis==='x'?[[side,-.13,9],[side,.13,9],[side,.13,20],[side,-.13,20]]:[[-.13,side,9],[.13,side,9],[.13,side,20],[-.13,side,20]],fill:'#68898a'});
      const faces=[
        {points:[[-r,-r,0],[r,-r,0],[r,-r,h],[-r,-r,h]],fill:'#ddd0b3',details:[window('y',-r)]},
        {points:[[r,-r,0],[r,r,0],[r,r,h],[r,-r,h]],fill:'#c9bda2',details:[window('x',r)]},
        {points:[[r,r,0],[-r,r,0],[-r,r,h],[r,r,h]],fill:'#eadbc0',
         details:[{points:[[-.12,r,0],[.1,r,0],[.1,r,18],[-.12,r,18]],fill:'#81694f'}]},
        {points:[[-r,r,0],[-r,-r,0],[-r,-r,h],[-r,r,h]],fill:'#e5d8bc',details:[window('x',-r)]},
        {points:[[-r,-r,h],[r,-r,h],[0,-r,peak]],fill:'#ddd0b3'},
        {points:[[-r,r,h],[r,r,h],[0,r,peak]],fill:'#eadbc0'},
        {points:[[-r-.05,-r-.05,h],[-r-.05,r+.05,h],[0,r+.05,peak],[0,-r-.05,peak]],fill:lightRoof},
        {points:[[r+.05,-r-.05,h],[r+.05,r+.05,h],[0,r+.05,peak],[0,-r-.05,peak]],fill:roof}
      ];
      this.mesh(faces);
      this.line([this.project(0,-r-.05,peak),this.project(0,r+.05,peak)],workshop?'#abb6ad':'#e6b78b',2);
      if(workshop){
        const [x,y]=this.project(.2,-.16,h+13);
        this.c.save();this.c.translate(x,y);
        this.mesh([
          {points:[[-.07,-.07,0],[.07,-.07,0],[.07,-.07,21],[-.07,-.07,21]],fill:'#889083'},
          {points:[[.07,-.07,0],[.07,.07,0],[.07,.07,21],[.07,-.07,21]],fill:'#7c867a'},
          {points:[[.07,.07,0],[-.07,.07,0],[-.07,.07,21],[.07,.07,21]],fill:'#a3a794'},
          {points:[[-.07,.07,0],[-.07,-.07,0],[-.07,-.07,21],[-.07,.07,21]],fill:'#aeb09c'},
          {points:[[-.07,-.07,21],[.07,-.07,21],[.07,.07,21],[-.07,.07,21]],fill:'#626f62'}
        ]);this.c.restore();
      }
    }
    storage(seed,ground=true){
      // A low, reinforced timber crate: no roof, door, or house silhouette.
      const r=.24,h=18,wood=seed>.5?'#b99060':'#bd9d6b';
      if(ground)this.groundPatch('#b7ae82',25);
      const side=(axis,edge,fill)=>{
        const point=(u,z)=>axis==='x'?[edge,u,z]:[u,edge,z];
        const panel=(a,b,low,high,color)=>({points:[point(a,low),point(b,low),point(b,high),point(a,high)],fill:color});
        return {points:[point(-r,0),point(r,0),point(r,h),point(-r,h)],fill,
          details:[panel(-.19,.19,3,15,'#99774f'),
            panel(-.18,.18,4,8,wood),panel(-.18,.18,10,14,wood),
            panel(-.21,-.16,0,h,'#68746b'),panel(.16,.21,0,h,'#68746b'),
            panel(-r,r,0,2,'#d1b584'),panel(-r,r,16,18,'#d8bc8c')]};
      };
      const lid={points:[[-r,-r,h],[r,-r,h],[r,r,h],[-r,r,h]],fill:'#dbc293',details:[]};
      for(const y of [-.12,0,.12])lid.details.push({points:[[-r,y,h],[r,y,h],[r,y+.014,h],[-r,y+.014,h]],fill:'#a38b63'});
      for(const x of [-.21,.16])lid.details.push({points:[[x,-r,h],[x+.05,-r,h],[x+.05,r,h],[x,r,h]],fill:'#879186'});
      this.mesh([side('x',-r,'#b08d5e'),side('y',-r,'#b99a68'),
        side('x',r,'#a48257'),side('y',r,'#c5a574'),lid]);
    }
    structureLayout(group){
      if(!group.length)return [];
      const sorted=group.slice().sort((a,b)=>a.type.localeCompare(b.type)||String(a.id).localeCompare(String(b.id)));
      const nominal=s=>s.type==='shelter'?SHELTER_SCALE:s.type==='storage'?STORAGE_SCALE:1;
      if(sorted.length===1)return [{structure:sorted[0],dx:0,dy:0,scale:nominal(sorted[0])}];
      const pair=sorted.length===2&&sorted.some(s=>s.type==='shelter')&&sorted.some(s=>s.type==='storage');
      const {x,y}=sorted[0].position;
      const variant=Math.min(3,Math.floor(hash(x,y,this.snapshot.config.seed||0)*4));
      const turn=([dx,dy])=>variant===0?[dx,dy]:variant===1?[-dy,dx]:variant===2?[-dx,-dy]:[dy,-dx];
      return sorted.map((s,index)=>{
        let point;
        if(pair){
          // Four fixed courtyard arrangements. Keep the hut and crate footprints separate.
          point=s.type==='shelter'?[-.22,-.12]:[.26,.18];
        }else{
          const columns=Math.ceil(Math.sqrt(sorted.length)),rows=Math.ceil(sorted.length/columns),step=.94/columns;
          point=[(index%columns-(columns-1)/2)*step,(Math.floor(index/columns)-(rows-1)/2)*step];
          // Crowding changes placement, never the apparent capacity of a building.
        }
        const [dx,dy]=turn(point);
        return {structure:s,dx,dy,scale:nominal(s)};
      });
    }
    farm(tile,seed,time=0){
      this.groundPatch('#927557',34);
      this.groundPoly([[-33,0],[0,16],[33,0],[33,3],[0,20],[-33,3]],'#786749');
      const food=Math.max(0,tile.resources?.food||0),growth=Math.min(1,food/(this.snapshot.config.farm_food_capacity||24));
      for(let r=0;r<4;r++){
        const [ax,ay]=this.project(r*.19-.3,-.32),[bx,by]=this.project(r*.19-.3,.35);
        this.line([[ax,ay],[bx,by]],'#6e5b45',2);
        for(let k=0;k<4;k++){
          const [x,y]=this.project(r*.19-.3,k*.18-.27);
          const h=3+growth*8, sway=Math.sin(time*.7+seed*8+r)*.8;
          this.line([[x,y],[x+sway,y-h]],growth>.7?'#cbb56c':'#739654',1.8);
          this.line([[x+sway,y-h+4],[x-3+sway,y-h+1]],growth>.7?'#e2c582':'#98b264',2);
          this.line([[x+sway,y-h+2],[x+3+sway,y-h]],growth>.7?'#ecce88':'#a8bd70',2);
        }
      }
      // Only a short edge fence: enough to read as cultivated land.
      this.groundLine([[-31,1,4],[-2,16,4]],'#c2a47a',2);
      for(const [x,y] of [[-31,1],[-17,8],[-2,16]]){const [px,py]=this.groundPoint(x,y);this.rect(px-1,py-6,2,9,'#d4b98c');this.rect(px-1,py-6,2,2,'#eee0b1');}
    }
    well(){
      this.groundPatch('#bbb48b',26);this.ellipse(4,5,19,7,'#52634b25');
      const posts=[[-.19,.19],[.19,-.19]].sort((a,b)=>this.project(...a)[1]-this.project(...b)[1]);
      const post=([x,y])=>{const [px,py]=this.project(x,y);this.rect(px-1.5,py-34,3,35,'#96784e');};
      post(posts[0]);
      this.ellipse(0,0,13,7,'#a2aa95');this.rect(-13,-8,26,9,'#a7af9e');
      this.ellipse(0,-9,13,7,'#d0ceaf');this.ellipse(0,-9,9,4,'#4d8485');
      post(posts[1]);
      this.mesh([
        {points:[[-.26,-.26,32],[-.26,.26,32],[0,.26,44],[0,-.26,44]],fill:'#c1bd87'},
        {points:[[.26,-.26,32],[.26,.26,32],[0,.26,44],[0,-.26,44]],fill:'#a3a575'}
      ]);
      this.line([[0,-31],[0,-10]],'#8c7957',1);this.rect(-3,-14,6,5,'#c5ac7a');
    }
    construction(type,ground=true){
      // Use the finished structure's footprint and materials, with visible missing work.
      const beam=(points,color='#c8a573',width=2)=>this.line(points.map(p=>this.project(...p)),color,width);
      const board=(points,fill='#c5a574')=>this.mesh([{points,fill}]);
      if(type==='well'){
        if(ground)this.groundPatch('#b4a783',26);
        // Excavated shaft and a partly laid stone ring; no house-sized scaffolding.
        this.ellipse(0,0,13,7,'#776a50');this.ellipse(0,-1,9,4,'#474b3b');
        const faces=[],point=(r,a,z)=>[r*Math.cos(a),r*Math.sin(a),z];
        for(let i=0;i<10;i++){
          const a=i*Math.PI/6+.025,b=(i+1)*Math.PI/6-.025,h=i<7?5:2;
          faces.push({points:[point(.24,a,0),point(.24,b,0),point(.24,b,h),point(.24,a,h)],fill:'#a7af9e'},
            {points:[point(.17,b,0),point(.17,a,0),point(.17,a,h),point(.17,b,h)],fill:'#788575'},
            {points:[point(.24,a,h),point(.24,b,h),point(.17,b,h),point(.17,a,h)],fill:'#d0ceaf'});
        }
        this.mesh(faces);
        for(const [x,y] of [[.3,.08],[.29,.2]])board([[x-.045,y-.045,0],[x+.045,y-.045,0],[x+.045,y+.045,2],[x-.045,y+.045,2]],'#b9bea8');
        return;
      }
      if(type==='storage'){
        if(ground)this.groundPatch('#b7ae82',25);
        board([[-.24,-.24,1],[.24,-.24,1],[.24,.24,1],[-.24,.24,1]],'#b99060');
        const faces=[];
        for(const z of [2,7])for(const side of ['x','y']){
          const p=(u,h)=>side==='x'?[-.24,u,h]:[u,-.24,h];
          faces.push({points:[p(-.24,z),p(.24,z),p(.24,z+4),p(-.24,z+4)],fill:side==='x'?'#b08d5e':'#c5a574'});
        }
        this.mesh(faces);
        for(const [x,y] of [[-.21,-.21],[.21,-.21],[-.21,.21],[.21,.21]])beam([[x,y,0],[x,y,18]],'#879186',2);
        beam([[-.16,.04,2],[.18,.04,2]],'#dbc293',3);
        beam([[-.16,.14,2],[.18,.14,2]],'#dbc293',3);
        return;
      }
      if(type==='farm_plot'){
        this.groundPatch('#927557',34);
        for(let row=0;row<4;row++)beam([[row*.19-.3,-.32,0],[row*.19-.3,.35,0]],row<2?'#6e5b45':'#aa8a61',2);
        for(const [x,y] of [[-.32,-.32],[.32,.32]])beam([[x,y,0],[x,y,5]],'#d4b98c',2);
        return;
      }
      if(type==='road'){
        this.groundPatch('#a79878',38);
        this.groundPoly([[-34,0],[0,-17],[5,-8],[-18,6]],'#c8bea0');
        for(const [x,y] of [[-11,-4],[-4,-8],[3,-3],[10,2],[-5,6]])this.groundPoly([[x-2,y],[x,y-1],[x+3,y],[x,y+2]],'#d4c9a6');
        return;
      }
      if(type==='irrigation'){
        this.groundPatch('#bcb68b');
        this.groundLine([[-25,0],[0,12],[25,0]],'#a38c67',9);
        this.groundLine([[-25,0],[0,12],[25,0]],'#6f624b',5);
        this.groundLine([[-25,-3],[-5,7]],'#cbc5a3',2);
        this.groundLine([[-25,3],[-5,13]],'#cbc5a3',2);
        return;
      }
      if(['shelter','house','workshop'].includes(type)){
        const r=.36,h=type==='shelter'?22:30,peak=h+(type==='shelter'?18:22);
        if(ground)this.groundPatch('#b7ae82',34);
        board([[-r,-r,0],[r,-r,0],[r,r,0],[-r,r,0]],'#c4b794');
        // Low wall courses and an open gabled frame at the finished building's dimensions.
        this.mesh([{points:[[-r,-r,0],[r,-r,0],[r,-r,7],[-r,-r,7]],fill:'#ddd0b3'},
          {points:[[-r,-r,0],[-r,r,0],[-r,r,7],[-r,-r,7]],fill:'#e5d8bc'}]);
        for(const [x,y] of [[-r,-r],[r,-r],[r,r],[-r,r]])beam([[x,y,0],[x,y,h]],'#b28d5e',3);
        for(const y of [-r,r])beam([[-r,y,h],[0,y,peak],[r,y,h]],'#d9be89',3);
        for(const x of [-r,r])beam([[x,-r,h],[x,r,h]],'#c8a573',3);
        beam([[0,-r,peak],[0,r,peak]],'#c8a573',3);
        if(type==='workshop'){
          board([[.13,-.23,0],[.27,-.23,0],[.27,-.23,16],[.13,-.23,16]],'#889083');
          board([[.27,-.23,0],[.27,-.09,0],[.27,-.09,16],[.27,-.23,16]],'#a3a794');
        }
        return;
      }
      // Unknown future types get a neutral ground marker, never a misleading building.
      if(ground)this.groundPatch('#b4a783',20);
    }
    structure(s,tile,time=0,shared=false){
      if(s.status&&s.status!=='complete'){this.construction(s.type,!shared);return;}
      if(s.type==='farm_plot'){this.farm(tile,hash(s.position.x,s.position.y),time);return;}
      if(s.type==='well'){this.well();return;}
      if(s.type==='storage'){this.storage(hash(s.position.x,s.position.y),!shared);return;}
      if(['house','shelter','workshop'].includes(s.type)){this.house(s.type,hash(s.position.x,s.position.y),!shared);return;}
      if(s.type==='road'){this.groundPatch('#c8bea0',38);return;}
      if(s.type==='irrigation'){this.groundPatch('#bcb68b');this.groundLine([[-25,0],[0,12],[25,0]],'#6f9d9e',5);return;}
      this.groundPatch();this.poly([[-12,0],[-12,-16],[0,-22],[12,-16],[12,0],[0,6]],'#bdab81');
    }
    agent(a,index,time){
      if(!a.alive){this.ellipse(0,2,7,3,'#6a725c');this.rect(-4,-5,8,7,'#b0b3a0');return;}
      this.ellipse(0,1,7,3,'#344b413c');
      // Feet stay on the ground; only the torso participates in idle breathing.
      this.rect(-4,-5,3,5,'#4c5953');this.rect(1,-5,3,5,'#4c5953');
      const breath=this.reduced.matches?0:Math.sin(time*1.7+index*2)*.45;
      this.c.translate(0,breath);
      this.rect(-5,-13,10,11,colors[index%colors.length]);
      this.rect(-7,-11,2,6,'#dab68d');this.rect(5,-11,2,6,'#dab68d');
      this.rect(-4,-22,8,9,index%3===0?'#bc8d65':'#e5c09a');
      this.rect(-4,-23,8,3,index%3===0?'#655949':'#72533e');this.rect(-5,-21,2,4,'#72533e');
      this.rect(-2,-18,1.4,1.4,'#464c43');this.rect(2,-18,1.4,1.4,'#464c43');
      if(index%3===0){this.rect(-7,-24,14,3,'#d5b981');this.rect(-4,-28,8,4,'#e4ca8c');this.rect(-4,-25,8,1,'#9e8557');}
      if(a.equipped?.length){this.line([[6,-6],[11,-19]],'#927954',2);this.line([[8,-19],[14,-17]],'#a3afae',3);}
    }
    buildBase(){
      this.base=document.createElement('canvas');this.base.width=this.canvas.width;this.base.height=this.canvas.height;
      this.c=this.base.getContext('2d');this.c.scale(this.dpr,this.dpr);this.c.translate(this.ox,this.oy);this.c.scale(this.scale,this.scale);
      const {width,height}=this.snapshot.config;
      const corners=[[0,0],[width,0],[width,height],[0,height]].map(p=>this.project(...p));
      this.c.save();this.c.filter='blur(20px)';this.poly(corners.map(([x,y])=>[x+20,y+30]),'#37584724');this.c.restore();
      for(let i=0;i<4;i++){
        const a=corners[i],b=corners[(i+1)%4];
        if(b[0]>=a[0])continue;
        this.poly([a,b,[b[0],b[1]+22],[a[0],a[1]+22]],i%2?'#7f8f70':'#9a9e75');
        this.poly([[a[0],a[1]+17],[b[0],b[1]+17],[b[0],b[1]+22],[a[0],a[1]+22]],'#7a89714d');
      }
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const tile=this.snapshot.tiles[y][x],terrain=tile.terrain,palette=C[terrain==='plains'?'grass':terrain]||C.grass;
        this.tile(x,y,palette[Math.floor(hash(x,y)*palette.length)]);
        if(terrain==='water'){
          // Shorelines remain attached to their native tile edges at every yaw.
          for(const [dx,dy,a,b] of [[0,-1,[0,0],[1,0]],[1,0,[1,0],[1,1]],[0,1,[1,1],[0,1]],[-1,0,[0,1],[0,0]]]){
            const n=this.snapshot.tiles[y+dy]?.[x+dx];
            if(n&&n.terrain!=='water'){
              this.line([this.project(x+a[0],y+a[1]),this.project(x+b[0],y+b[1])],'#c7c49a',5);
              const mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;
              this.line([this.project(x+.5+(mx-.5)*.85,y+.5+(my-.5)*.85),this.project(x+.5+(b[0]-.5)*.9,y+.5+(b[1]-.5)*.9)],'#b9d4c5',1.5);
            }
          }
        } else if(terrain==='plains'){
          for(let j=0;j<4;j++){const xx=hash(x,y,j+1)*.8+.1,yy=hash(x,y,j+7)*.8+.1,[gx,gy]=this.project(x+xx,y+yy);this.rect(gx,gy,2,1,hash(x,y,j+4)>.5?'#d1d29780':'#829e6480');}
          if(hash(x,y,41)>.91&&!tile.structures?.length)this.at(x,y,()=>{this.rect(10,0,2,3,'#708c59');this.rect(9,-1,4,2,'#ede1a9');});
        }
      }
      this.c=null;
    }
    paint(time=0){
      if(!this.snapshot||!this.base)return;
      const c=this.ctx;c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,this.canvas.width,this.canvas.height);c.drawImage(this.base,0,0);
      this.c=c;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.translate(this.ox,this.oy);c.scale(this.scale,this.scale);
      const {width,height}=this.snapshot.config, objects=[];
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const tile=this.snapshot.tiles[y][x];
        if(tile.terrain==='water'){
          this.at(x,y,()=>{const shift=Math.sin(time*.45+hash(x,y)*8)*3;this.line([[-12+shift,-2],[0+shift,-2]],'#c4e3d367',1.5);if(hash(x,y)>.6)this.line([[5-shift,5],[12-shift,5]],'#e5efd84d',1);});
        }
        if(!tile.structures?.length && (tile.terrain==='forest'||tile.terrain==='mountain'))
          objects.push({x,y,order:0,draw:()=>tile.terrain==='forest'?this.tree(x,y,Math.floor(hash(x,y)*7)):this.rock(x,y,hash(x,y))});
      }
      const grouped=new Map();
      for(const s of this.structures){const key=s.position.x+','+s.position.y;if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(s);}
      for(const group of grouped.values()){
        for(const {structure:s,dx,dy,scale} of this.structureLayout(group)){
          objects.push({x:s.position.x+dx,y:s.position.y+dy,order:1,draw:()=>{
            const tile=this.snapshot.tiles[s.position.y]?.[s.position.x];if(!tile)return;
            this.c.scale(scale,scale);this.structure(s,tile,time,group.length>1);
          }});
        }
      }
      Object.values(this.snapshot.item_piles||{}).forEach(p=>objects.push({...p.position,order:2,draw:()=>{this.rect(-4,3,8,5,'#bba06b');this.line([[-4,5],[4,5]],'#8b7b58',1);}}));
      this.agents.forEach((a,i)=>{
        const anchor=this.agentAnchor(a);
        objects.push({x:a.position.x+anchor.x,y:a.position.y+anchor.y,order:3,draw:()=>this.agent(a,i,time)});
      });
      objects.sort((a,b)=>this.project(a.x,a.y)[1]-this.project(b.x,b.y)[1]||a.order-b.order||a.x-b.x);
      for(const obj of objects)this.at(obj.x,obj.y,obj.draw);
      this.c=null;
    }
    restart(){
      cancelAnimationFrame(this.frame);this.paint(0);
      if(this.reduced.matches||document.hidden||this.preview)return;
      const animate=t=>{if(t-this.lastPaint>65){this.paint(t/1000);this.lastPaint=t;}this.frame=requestAnimationFrame(animate);};
      this.frame=requestAnimationFrame(animate);
    }
    inspect(event){
      if(!this.snapshot)return;
      const box=this.canvas.getBoundingClientRect(),sx=(event.clientX-box.left-this.ox)/this.scale,sy=(event.clientY-box.top-this.oy)/this.scale;
      const [wx,wy]=this.unproject(sx,sy),x=Math.floor(wx),y=Math.floor(wy),tile=this.snapshot.tiles[y]?.[x];
      if(!tile){this.onInspect(null);return;}
      const structures=this.structures.filter(s=>s.position.x===x&&s.position.y===y),agents=this.agents.filter(a=>a.position.x===x&&a.position.y===y);
      this.onInspect({x,y,tile,structures,agents});
    }
    destroy(){cancelAnimationFrame(this.frame);cancelAnimationFrame(this.rotationFrame);this.resizeObserver.disconnect();this.reduced.removeEventListener('change',this.motionListener);document.removeEventListener('visibilitychange',this.visibilityListener);this.canvas.removeEventListener('pointermove',this.pointerListener);this.canvas.removeEventListener('pointerleave',this.leaveListener);
      this.canvas.removeEventListener('pointerdown',this.downListener);this.canvas.removeEventListener('pointerup',this.upListener);
      this.canvas.removeEventListener('pointercancel',this.upListener);this.canvas.removeEventListener('lostpointercapture',this.upListener);
      this.canvas.removeEventListener('keydown',this.keyListener);
      if(this.drag)this.pointerUp({pointerId:this.drag.id});
    }
  }
  global.WorldRenderer=WorldRenderer;
})(window);

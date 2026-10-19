/* Native snapshot -> a quiet isometric diorama. No simulation state is mutated. */
'use strict';
(function (global) {
  const hash = (x,y,n=0) => {let v=Math.imul(x+71,374761393)^Math.imul(y+37,668265263)^Math.imul(n+11,1274126177);v=Math.imul(v^(v>>>13),1274126177);return ((v^(v>>>16))>>>0)/4294967295;};
  const strHash = s => {let v=2166136261;for(const ch of String(s))v=Math.imul(v^ch.charCodeAt(0),16777619);v=Math.imul(v^(v>>>15),2246822507);return ((v^(v>>>13))>>>0)/4294967295;};
  const rgb = h => [1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
  const toHex = v => '#'+v.map(n=>Math.max(0,Math.min(255,Math.round(n))).toString(16).padStart(2,'0')).join('');
  const shades = new Map();
  const shade = (h,f) => {const k=h+f.toFixed(3);let v=shades.get(k);if(!v){if(shades.size>6000)shades.clear();v=toHex(rgb(h).map(n=>n*f));shades.set(k,v);}return v;};
  const withAlpha = (h,a) => h.slice(0,7)+Math.round(Math.max(0,Math.min(1,a))*255).toString(16).padStart(2,'0');
  const SHELTER_SCALE=0.54,STORAGE_SCALE=0.54; // Fixed sizes, including on shared tiles.
  const WATER_DEPTH=5,SLAB=24;
  const GRASS=['#a9c27b','#abc47d','#a7c079','#adc57f'],MEADOW=['#bfd189','#9cb56f','#c8d28e','#a3bb74'];
  const FLOWERS=['#f4f1e1','#f0d36b','#eba4ad','#b9a6d9','#f2b679'];
  const LEAVES=[{dark:'#3f6a45',mid:'#64914f',light:'#9fc36d',trunk:'#7b6047'},{dark:'#4f763f',mid:'#7a9f4f',light:'#b6cf72',trunk:'#806246'},
    {dark:'#38604a',mid:'#58855a',light:'#8db477',trunk:'#735a45'},{dark:'#8d5a35',mid:'#c88a45',light:'#ecc173',trunk:'#7a5a42'}];
  const ROOFS=['#c46f4e','#b8643f','#7c8ea0','#c98157','#8f6a4c'];
  const SKIN=['#f2cfae','#e6b58e','#c98e64','#a2693f','#7a4a2c','#f6dcc2'];
  const HAIR=['#3a2a20','#5b3a24','#8a5a2e','#c99a50','#2b2b2e','#b5aea3','#7a3b22'];
  const colors=['#c9734f','#5f87a3','#b77ba0','#d4a64a','#6f9a68','#b35f5a','#7a7fb0','#4f9a92','#d98f5c','#8aa0c4'];
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
      this.buildMountains();
      this.buildTrails();
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
    buildMountains(){
      const {width,height,seed=0}=this.snapshot.config,tiles=this.snapshot.tiles;
      const key=seed+':'+width+':'+height+':'+tiles.map(row=>row.map(t=>t.terrain==='mountain'?'1':'0').join('')).join('');
      if(key===this.mountainKey)return;
      this.mountainKey=key;this.mountainFaces=[];this.mountainTiles=new Map();this.rockDeposits=new Set();
      const isMountain=(x,y)=>tiles[y]?.[x]?.terrain==='mountain';
      const visited=new Set();
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const id=x+','+y;if(!isMountain(x,y)||visited.has(id))continue;
        const cluster=[[x,y]];visited.add(id);
        for(let i=0;i<cluster.length;i++){
          const [cx,cy]=cluster[i];
          for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){
            const nx=cx+dx,ny=cy+dy,k=nx+','+ny;
            if(isMountain(nx,ny)&&!visited.has(k)){visited.add(k);cluster.push([nx,ny]);}
          }
        }
        // A lone resource tile is an outcrop, not a miniature mountain range.
        if(cluster.length===1){this.rockDeposits.add(id);continue;}
        const minX=Math.min(...cluster.map(p=>p[0])),maxX=Math.max(...cluster.map(p=>p[0]))+1;
        const minY=Math.min(...cluster.map(p=>p[1])),maxY=Math.max(...cluster.map(p=>p[1]))+1;
        const w=maxX-minX,h=maxY-minY,size=Math.min(w,h);
        // Broad connected ranges, with repeatable variation derived from the world seed.
        const amplitude=Math.min(1,size/7),jitter=(hash(minX,minY,seed)-.5)*.12;
        const peaks=[[.375,.286,103,.571],[.75,.286,132,.614],[.625,.714,77,.429]]
          .map(([px,py,z,r])=>[minX+(px+jitter)*w,minY+py*h,z*amplitude,Math.max(1,r*size)]);
        const vertices=new Map();
        const elevation=(px,py)=>{
          const k=px+','+py;if(vertices.has(k))return vertices.get(k);
          if(![[px-1,py-1],[px,py-1],[px-1,py],[px,py]].every(([vx,vy])=>isMountain(vx,vy))){vertices.set(k,0);return 0;}
          let distance=2;
          for(let ny=py-2;ny<=py+1;ny++)for(let nx=px-2;nx<=px+1;nx++){
            if(!isMountain(nx,ny))distance=Math.min(distance,Math.hypot(Math.max(nx-px,0,px-nx-1),Math.max(ny-py,0,py-ny-1)));
          }
          const ridge=Math.max(...peaks.map(([a,b,z,r])=>z*Math.max(0,1-Math.hypot(px-a,py-b)/r)));
          const z=ridge*Math.min(1,distance/1.7);vertices.set(k,z);return z;
        };
        for(const [cx,cy] of cluster){
          const corners=[[cx,cy],[cx+1,cy],[cx+1,cy+1],[cx,cy+1]].map(([vx,vy])=>[vx,vy,elevation(vx,vy)]);
          const middle=[cx+.5,cy+.5,Math.max(10,corners.reduce((sum,p)=>sum+p[2],0)/4)];
          const faces=corners.map((p,i)=>({points:[p,corners[(i+1)%4],middle],tile:{x:cx,y:cy}}));
          for(const face of faces)face.fill=this.mountainColor(face.points);
          this.mountainTiles.set(cx+','+cy,faces);this.mountainFaces.push(...faces);
        }
      }
    }
    mountainColor(points){
      const [a,b,d]=points,u=[(b[0]-a[0])*48,(b[1]-a[1])*48,b[2]-a[2]],v=[(d[0]-a[0])*48,(d[1]-a[1])*48,d[2]-a[2]];
      let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
      if(n[2]<0)n=n.map(value=>-value);
      const norm=Math.hypot(...n),z=points.reduce((sum,p)=>sum+p[2],0)/3;
      // Same camera-fixed sun as the buildings, so orbiting keeps the lit side facing left.
      const cos=Math.cos(this.yaw),sin=Math.sin(this.yaw),rx=n[0]*cos-n[1]*sin,ry=n[0]*sin+n[1]*cos;
      const light=Math.max(0,(rx*-.42+ry*.62+n[2]*.66)/norm),up=n[2]/norm;
      const ramp=(p,q,t)=>p.map((value,i)=>value+(q[i]-value)*t);
      const step=(e0,e1)=>{const t=Math.max(0,Math.min(1,(z-e0)/(e1-e0)));return t*t*(3-2*t);};
      // Meadow foothills, warm rock, pale scree, then snow on the upward-facing summit.
      let color=ramp([136,166,102],[172,163,138],step(6,30));
      color=ramp(color,[196,192,174],step(30,60)).map(value=>value*(.7+.4*light));
      color=ramp(color,[246,247,241].map(value=>value*(.84+.17*light)),step(64,82)*Math.min(1,.35+up));
      return '#'+color.map(value=>Math.round(Math.max(0,Math.min(255,value))).toString(16).padStart(2,'0')).join('');
    }
    triangleWeights(x,y,points){
      const [a,b,c]=points,den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
      if(Math.abs(den)<1e-9)return null;
      const u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den;
      const v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den,w=1-u-v;
      return Math.min(u,v,w)>=-1e-8?[u,v,w]:null;
    }
    terrainHeight(x,y){
      for(const face of this.mountainTiles?.get(Math.floor(x)+','+Math.floor(y))||[]){
        const weights=this.triangleWeights(x,y,face.points);
        if(weights)return weights.reduce((sum,w,i)=>sum+w*face.points[i][2],0);
      }
      return 0;
    }
    terrainHit(sx,sy){
      for(let i=(this.projectedMountains?.length||0)-1;i>=0;i--){
        const face=this.projectedMountains[i];
        if(this.triangleWeights(sx,sy,face.screen))return face.tile;
      }
      const [x,y]=this.unproject(sx,sy);return {x:Math.floor(x),y:Math.floor(y)};
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
    circle(x,y,r,fill){const c=this.c;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle=fill;c.fill();}
    // Gradients degrade to a flat colour on contexts without gradient support.
    radial(x,y,r,stops,fallback,fx=x,fy=y){
      const g=this.c.createRadialGradient?.(fx,fy,0,x,y,r);
      if(!g?.addColorStop)return fallback;
      for(const [offset,color] of stops)g.addColorStop(offset,color);
      return g;
    }
    linear(x0,y0,x1,y1,stops,fallback){
      const g=this.c.createLinearGradient?.(x0,y0,x1,y1);
      if(!g?.addColorStop)return fallback;
      for(const [offset,color] of stops)g.addColorStop(offset,color);
      return g;
    }
    // The sun is fixed to the camera: every orbit angle keeps the same sunlit side.
    lit([nx,ny,nz]){
      const c=Math.cos(this.yaw),s=Math.sin(this.yaw),x=nx*c-ny*s,y=nx*s+ny*c,l=Math.hypot(x,y,nz)||1;
      return (.8+.22*(-.42*x+.62*y+.66*nz)/l)/.936;
    }
    facing(nx,ny){const c=Math.cos(this.yaw),s=Math.sin(this.yaw);return (nx*c-ny*s)+(nx*s+ny*c)>1e-6;}
    face(points,color,n,details=[]){
      const f=this.lit(n);
      return {points,fill:shade(color,f),details:details.map(d=>({points:d.points,fill:d.fill||shade(d.color,f)}))};
    }
    // A ground-plane circle projects to the same 2:1 ellipse at every yaw.
    groundDisc(x,y,r,color,alpha=1,soft=0,z=0){
      const [sx,sy]=this.project(x,y,z),R=r*53.74,c=this.c;
      c.save();c.translate(sx,sy);c.scale(1,.5);c.beginPath();c.arc(0,0,R,0,Math.PI*2);
      c.fillStyle=soft?this.radial(0,0,R,[[0,withAlpha(color,alpha)],[1-soft,withAlpha(color,alpha)],[1,withAlpha(color,0)]],withAlpha(color,alpha*.6)):withAlpha(color,alpha);
      c.fill();c.restore();
    }
    groundPatch(color='#c4b48a',r=32){this.groundDisc(0,0,r/68,color,.8,.5);}
    // Trees are cached sprites; they only sway, so orbiting never redraws them.
    treeSprite(kind,size,tone){
      const k=this.scale*this.dpr,key=kind+size+tone+':'+k.toFixed(3);
      this.sprites??=new Map();
      let sprite=this.sprites.get(key);if(sprite)return sprite;
      const W=100,H=112,ox=44,oy=100,canvas=document.createElement('canvas');
      canvas.width=Math.ceil(W*k);canvas.height=Math.ceil(H*k);
      const saved=this.c;this.c=canvas.getContext('2d');this.c.scale(k,k);this.c.translate(ox,oy);
      const s=[.7,.8,.9,1][size];
      if(kind==='pine')this.pine(s,tone);else if(kind==='bush')this.bush(tone);else this.broadleaf(s,tone);
      this.c=saved;sprite={canvas,W,H,ox,oy};this.sprites.set(key,sprite);
      if(this.sprites.size>240)this.sprites.delete(this.sprites.keys().next().value);
      return sprite;
    }
    drawSprite(kind,size,tone,phase,time){
      const sprite=this.treeSprite(kind,size,tone),c=this.c;
      const sway=this.reduced.matches?0:Math.sin(time*.9+phase*6.283)*(kind==='bush'?.01:.02);
      c.save();c.transform(1,0,sway,1,0,0);c.drawImage(sprite.canvas,-sprite.ox,-sprite.oy,sprite.W,sprite.H);c.restore();
    }
    blob(x,y,r,palette,light){
      this.c.beginPath();this.c.arc(x,y,r,0,Math.PI*2);
      this.c.fillStyle=this.radial(x+r*.15,y+r*.2,r*1.15,[[0,shade(palette.light,light)],[.55,shade(palette.mid,light)],[1,shade(palette.dark,light)]],shade(palette.mid,light),x-r*.45,y-r*.5);
      this.c.fill();
    }
    broadleaf(s,tone){
      const p=LEAVES[tone];
      this.ellipse(10*s,2*s,20*s,6.5*s,'#2c482f2e');
      this.poly([[-2.8*s,1],[-1.6*s,-22*s],[1.6*s,-22*s],[2.8*s,1]],p.trunk);
      this.poly([[.3*s,1],[.2*s,-22*s],[1.6*s,-22*s],[2.8*s,1]],shade(p.trunk,.76));
      this.line([[0,-15*s],[-6*s,-23*s]],p.trunk,1.8*s);
      for(const [x,y,r,l] of [[-8.5,-30,11.5,.8],[9,-29,11,.72],[0,-37,13.5,.93],[-6,-47,10.5,1],[6.5,-45,9.5,.9]])this.blob(x*s,y*s,r*s,p,l);
      for(const [x,y,r] of [[-9,-50,2.6],[-13,-36,2.1],[1,-43,2.3],[-2,-30,1.6]])this.circle(x*s,y*s,r*s,withAlpha(p.light,.5));
    }
    pine(s,tone){
      const t=[1,.95,1.06,1.02][tone];
      this.ellipse(8*s,2*s,15*s,5.5*s,'#2c482f2e');
      this.rect(-1.9*s,-12*s,3.8*s,13*s,'#6e563f');this.rect(.2*s,-12*s,1.7*s,13*s,'#584432');
      for(const [i,w,b,top] of [[0,17,-8,-36],[1,13.5,-25,-52],[2,9.5,-41,-70]]){
        const W=w*s,B=b*s,T=top*s,lift=3*s;
        this.poly([[0,T],[-W,B],[-W*.5,B+lift],[0,B+lift*.55]],shade(['#4f8059','#578a62','#62966c'][i],t));
        this.poly([[0,T],[W,B],[W*.5,B+lift],[0,B+lift*.55]],shade(['#36624a','#3d6b51','#477658'][i],t));
        this.line([[-W*.12,T+(B-T)*.35],[-W*.55,B-1.2*s]],'#a6cc9259',1.3*s);
      }
    }
    bush(tone){
      const p=LEAVES[tone%3];
      this.ellipse(6,2,13,4.5,'#2c482f2a');
      for(const [x,y,r,l] of [[-6,-5,6,.82],[6,-5,5.5,.76],[0,-9,7,1]])this.blob(x,y,r,p,l);
      if(tone>2)for(const [x,y] of [[-6,-8],[3,-12],[7,-6],[-1,-5]])this.circle(x,y,1.3,tone>3?'#f3efe0':'#e59aa2');
    }
    stump(){
      this.ellipse(4,1,8,2.8,'#2c482f26');this.rect(-3.5,-5,7,5.5,'#7a5f45');this.rect(.5,-5,3,5.5,'#634c39');
      this.ellipse(0,-5,3.5,1.6,'#d6b88c');this.ellipse(0,-5,1.6,.7,'#b39066');
    }
    // A forest tile holds up to three trees; harvested wood thins it to stumps.
    forestSlots(x,y,tile){
      const wood=tile.resources?.wood,count=wood===undefined?3:wood>=6?3:wood>=3?2:wood>=1?1:0;
      const turn=hash(x,y,5)*Math.PI*2,slots=[];
      [[-.2,-.22],[.25,-.06],[-.06,.25]].forEach(([dx,dy],i)=>{
        if(i>=count&&hash(x,y,i+50)<.4)return;
        const px=dx*Math.cos(turn)-dy*Math.sin(turn)+(hash(x,y,i+20)-.5)*.12,py=dx*Math.sin(turn)+dy*Math.cos(turn)+(hash(x,y,i+30)-.5)*.12;
        const kind=i>=count?'stump':hash(x,y,i+40)<.42?'pine':'tree',r=hash(x,y,i+60);
        slots.push({dx:px,dy:py,kind,size:Math.min(3,Math.floor(hash(x,y,i+70)*4)),tone:r<.035?3:Math.floor(r*3)%3,phase:hash(x,y,i+80)});
      });
      return slots;
    }
    rockDeposit(){
      const faces=[];
      for(const [cx,cy,r,h] of [[-.12,-.08,.19,16],[.17,.1,.12,10],[-.15,.2,.08,6]]){
        const base=[[-1,-.4],[-.4,-1],[.7,-.8],[1,.3],[.3,1],[-.8,.7]].map(([x,y])=>[cx+x*r,cy+y*r,0]);
        const top=base.map(([x,y],i)=>[cx+(x-cx)*.65,cy+(y-cy)*.65,h*(i%3===0?.8:1)]);
        for(let i=0;i<6;i++){
          const a=base[i],b=base[(i+1)%6];
          faces.push(this.face([a,b,top[(i+1)%6],top[i]],'#b4b8a3',[b[1]-a[1],a[0]-b[0],.35]));
        }
        faces.push(this.face(top,'#d5d7c2',[0,0,1]));
      }
      this.ellipse(2,4,24,8,'#3d4f3c22');this.mesh(faces);
    }
    rock(x,y,seed){this.rockDeposit();}
    chimney(x,y,z0,z1,color){
      const r=.055,p=(u,v,z)=>[x+u*r,y+v*r,z];
      this.mesh([this.face([p(-1,-1,z0),p(1,-1,z0),p(1,-1,z1),p(-1,-1,z1)],color,[0,-1,0]),
        this.face([p(1,-1,z0),p(1,1,z0),p(1,1,z1),p(1,-1,z1)],color,[1,0,0]),
        this.face([p(1,1,z0),p(-1,1,z0),p(-1,1,z1),p(1,1,z1)],color,[0,1,0]),
        this.face([p(-1,1,z0),p(-1,-1,z0),p(-1,-1,z1),p(-1,1,z1)],color,[-1,0,0]),
        this.face([p(-1.3,-1.3,z1),p(1.3,-1.3,z1),p(1.3,1.3,z1),p(-1.3,1.3,z1)],'#5e5650',[0,0,1])]);
    }
    smoke(x,y,z,time,seed){
      if(this.reduced.matches)return;
      const [sx,sy]=this.project(x,y,z);
      for(let i=0;i<4;i++){
        const phase=(time*.28+i/4+seed)%1,fade=Math.min(1,phase*8)*(1-phase);
        this.circle(sx+phase*10+Math.sin(time+i)*1.5,sy-3-phase*30,2.4+phase*5.5,withAlpha('#f6f4ec',fade*.5));
      }
    }
    house(type,seed,ground=true,time=0){
      if(type==='shelter'){this.hut(seed,ground);return;}
      const workshop=type==='workshop',r=.36,o=.06,h=workshop?27:30,peak=h+(workshop?17:22),R=r+o,rise=peak-h+2;
      if(ground)this.groundPatch('#c9b98e',42);
      this.ellipse(10,10,34,11,'#3e533f26');
      const pick=Math.floor(seed*1000);
      const walls=workshop?'#c8a477':['#f1e4ca','#eedcbd','#f3e8d4'][pick%3];
      const roof=workshop?'#6f8189':ROOFS[pick%ROOFS.length],timber=workshop?'#7a5b41':'#9b7656';
      const glass=this.dusk?'#f3c66e':'#6d8b93',frame='#f8f2e2',stone='#b3ad98';
      const wall=(n,P,openings)=>this.face([P(-r,0),P(r,0),P(r,h),P(-r,h)],walls,n,[
        {points:[P(-r,0),P(r,0),P(r,4),P(-r,4)],color:stone},
        ...(workshop?[-.2,-.06,.08,.22].map(u=>({points:[P(u,4),P(u+.012,4),P(u+.012,h),P(u,h)],color:shade(walls,.8)})):
          [{points:[P(-r,4),P(-r+.035,4),P(-r+.035,h),P(-r,h)],color:timber},{points:[P(r-.035,4),P(r,4),P(r,h),P(r-.035,h)],color:timber}]),
        {points:[P(-r,h-2.4),P(r,h-2.4),P(r,h),P(-r,h)],color:timber},...openings(P)]);
      const pane=u=>P=>[{points:[P(u-.1,10),P(u+.1,10),P(u+.1,21),P(u-.1,21)],color:frame},
        {points:[P(u-.075,11.4),P(u+.075,11.4),P(u+.075,19.6),P(u-.075,19.6)],...(this.dusk?{fill:glass}:{color:glass})},
        {points:[P(u-.008,11.4),P(u+.008,11.4),P(u+.008,19.6),P(u-.008,19.6)],color:frame},
        {points:[P(u-.075,15.2),P(u+.075,15.2),P(u+.075,15.8),P(u-.075,15.8)],color:frame},
        {points:[P(u-.11,9),P(u+.11,9),P(u+.11,10.2),P(u-.11,10.2)],color:timber}];
      const door=P=>workshop?[{points:[P(-.22,4),P(.08,4),P(.08,19),P(-.22,19)],color:timber},
          {points:[P(-.2,4),P(.06,4),P(.06,17.5),P(-.2,17.5)],fill:'#4a3a2e'},
          {points:[P(-.16,4),P(.02,4),P(.02,9),P(-.16,9)],fill:'#e39a58'}]:
        [{points:[P(-.2,4),P(-.02,4),P(-.02,20),P(-.2,20)],color:frame},{points:[P(-.185,4),P(-.035,4),P(-.035,18.8),P(-.185,18.8)],color:'#8a6346'},
          {points:[P(-.11,4),P(-.105,4),P(-.105,18.8),P(-.11,18.8)],color:'#6e4e37'}];
      const faces=[
        wall([0,-1,0],(u,z)=>[-u,-r,z],pane(0)),
        wall([1,0,0],(u,z)=>[r,-u,z],P=>[...pane(-.15)(P),...pane(.15)(P)]),
        wall([0,1,0],(u,z)=>[u,r,z],P=>[...door(P),...(workshop?[]:pane(.17)(P))]),
        wall([-1,0,0],(u,z)=>[-r,u,z],P=>[...pane(-.15)(P),...pane(.15)(P)]),
        this.face([[-r,-r,h],[r,-r,h],[0,-r,peak]],walls,[0,-1,0]),
        this.face([[r,r,h],[-r,r,h],[0,r,peak]],walls,[0,1,0])];
      for(const side of [-1,1]){
        const at=(t,y)=>[side*R*(1-t),y,h-2+rise*t];
        faces.push(this.face([at(0,-R),at(0,R),at(1,R),at(1,-R)],roof,[side*rise,0,R*40],
          [.18,.38,.58,.78].map(t=>({points:[at(t,-R),at(t,R),at(t+.04,R),at(t+.04,-R)],color:shade(roof,.84)})).concat(
            [{points:[at(0,-R),at(0,R),at(.05,R),at(.05,-R)],color:shade(roof,.72)}])));
      }
      this.mesh(faces);
      this.line([this.project(0,-R,peak+.6),this.project(0,R,peak+.6)],shade(roof,1.22),2.2);
      if(workshop||seed>.3){
        const cx=workshop?.19:.17,cy=-.15,base=h-2+rise*(1-cx/R);
        this.chimney(cx,cy,base,peak+(workshop?9:5),workshop?'#9c9488':'#b47c62');
        this.smoke(cx,cy,peak+(workshop?11:7),time,seed);
      }
    }
    hut(seed,ground=true){
      if(ground)this.groundPatch('#c9b98e',42);
      this.ellipse(8,8,30,10,'#3e533f26');
      const R=.4,L=.42,ridge=36,thatch=seed>.5?'#cfa960':'#d6b46d';
      const faces=[
        this.face([[-R+.06,-L+.04,1],[R-.06,-L+.04,1],[0,-L+.04,ridge-4]],'#a7895b',[0,-1,0]),
        this.face([[R-.06,L-.04,1],[-R+.06,L-.04,1],[0,L-.04,ridge-4]],'#c09e6b',[0,1,0],[
          {points:[[.15,L-.04,1],[-.15,L-.04,1],[0,L-.04,19]],fill:'#4a3a2b'},
          {points:[[.15,L-.04,1],[.12,L-.04,1],[0,L-.04,19],[-.01,L-.04,17]],color:'#8a6a45'}])];
      for(const side of [-1,1]){
        const at=(t,y)=>[side*R*(1-t),y,1+(ridge-1)*t];
        faces.push(this.face([at(0,-L),at(0,L),at(1,L),at(1,-L)],thatch,[side*(ridge-1),0,R*40],
          [.12,.3,.48,.66,.84].map(t=>({points:[at(t,-L),at(t,L),at(t+.03,L),at(t+.03,-L)],color:shade(thatch,.82)})).concat(
            [{points:[at(0,-L),at(0,L),at(.06,L),at(.06,-L)],color:shade(thatch,.74)}])));
      }
      this.mesh(faces);
      for(const y of [-L,L]){
        const [px,py]=this.project(0,y,ridge);
        this.line([[px-4,py-6],[px+3,py+2]],'#7f6040',1.6);this.line([[px+4,py-6],[px-3,py+2]],'#7f6040',1.6);
      }
      this.line([this.project(0,-L,ridge),this.project(0,L,ridge)],'#e4c47f',2);
    }
    crate(cx,cy,r,h,wood){
      const dark=shade(wood,.72);
      const side=(n,P)=>this.face([P(-1,0),P(1,0),P(1,h),P(-1,h)],wood,n,[
        {points:[P(-1,0),P(-.8,0),P(-.8,h),P(-1,h)],color:dark},{points:[P(.8,0),P(1,0),P(1,h),P(.8,h)],color:dark},
        {points:[P(-1,h*.46),P(1,h*.46),P(1,h*.54),P(-1,h*.54)],color:dark},
        {points:[P(-.8,h*.06),P(-.66,h*.06),P(.8,h*.94),P(.66,h*.94)],color:shade(wood,.86)}]);
      return [side([0,-1,0],(u,z)=>[cx-u*r,cy-r,z]),side([1,0,0],(u,z)=>[cx+r,cy-u*r,z]),
        side([0,1,0],(u,z)=>[cx+u*r,cy+r,z]),side([-1,0,0],(u,z)=>[cx-r,cy+u*r,z]),
        this.face([[cx-r,cy-r,h],[cx+r,cy-r,h],[cx+r,cy+r,h],[cx-r,cy+r,h]],shade(wood,1.1),[0,0,1],
          [-.5,0,.5].map(t=>({points:[[cx-r,cy+t*r,h],[cx+r,cy+t*r,h],[cx+r,cy+t*r+.014,h],[cx-r,cy+t*r+.014,h]],color:shade(wood,.78)})))];
    }
    barrel(x,y,h=13){
      const [sx,sy]=this.project(x,y);
      this.ellipse(sx,sy,6,2.8,'#7d5f40');this.rect(sx-6,sy-h,12,h,'#a77c50');this.rect(sx+1.5,sy-h,4.5,h,'#8b6642');
      for(const z of [.22,.78])this.rect(sx-6,sy-h*z-.7,12,1.4,'#5e5146');
      this.ellipse(sx,sy-h,6,2.8,'#c79c68');this.ellipse(sx,sy-h,4.2,1.8,'#a07a51');
    }
    sack(x,y,color='#d9c59b'){
      const [sx,sy]=this.project(x,y);
      this.ellipse(sx,sy-4,5.5,5,color);this.ellipse(sx+2,sy-3.5,3,4.4,shade(color,.86));
      this.rect(sx-1.5,sy-10,3,2.2,shade(color,.78));
    }
    storage(seed,ground=true){
      // A stocked yard of crates, a barrel and a sack: no roof, door, or house silhouette.
      if(ground)this.groundPatch('#c9b98e',30);
      this.ellipse(5,5,24,8,'#3e533f22');
      const wood=seed>.5?'#c29560':'#b98d5a';
      const items=[{x:-.05,y:-.05,draw:()=>this.mesh(this.crate(-.05,-.05,.14,16,wood))},
        {x:.13,y:.11,draw:()=>this.mesh(this.crate(.13,.11,.085,10,shade(wood,1.06)))},
        {x:-.14,y:.15,draw:()=>this.barrel(-.14,.15)},{x:.15,y:-.14,draw:()=>this.sack(.15,-.14)}];
      items.sort((a,b)=>this.project(a.x,a.y)[1]-this.project(b.x,b.y)[1]).forEach(item=>item.draw());
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
      const S=.42,food=Math.max(0,tile.resources?.food||0),growth=Math.min(1,food/(this.snapshot.config.farm_food_capacity||24));
      const P=(x,y,z=0)=>this.project(x,y,z),sway=this.reduced.matches?0:1;
      this.poly([[-S-.03,-S-.03],[S+.03,-S-.03],[S+.03,S+.03],[-S-.03,S+.03]].map(p=>P(...p)),'#7e6449');
      this.poly([[-S,-S],[S,-S],[S,S],[-S,S]].map(p=>P(...p)),'#8f7152');
      const rows=[-.32,-.16,0,.16,.32];
      for(const y of rows){
        this.poly([[-S+.04,y-.045],[S-.04,y-.045],[S-.04,y+.045],[-S+.04,y+.045]].map(p=>P(...p)),'#a3845e');
        this.line([P(-S+.04,y+.06),P(S-.04,y+.06)],'#76593f',1);
      }
      // A rail fence on the far edges only, so it never hides the crop.
      const edges=[[[-S,-S],[S,-S],0,-1],[[S,-S],[S,S],1,0],[[S,S],[-S,S],0,1],[[-S,S],[-S,-S],-1,0]];
      for(const [a,b,nx,ny] of edges){
        if(this.facing(nx,ny))continue;
        const at=t=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
        for(const z of [3.5,6.5])this.line([P(...at(0),z),P(...at(1),z)],'#c4a477',1.4);
        for(let t=0;t<=1.001;t+=.25){const [x,y]=at(t),[px,py]=P(x,y);this.rect(px-1,py-8,2,8.5,'#a98a62');this.rect(px-1,py-8,2,1.4,'#e6d2a6');}
      }
      const kind=seed<.55?'grain':'greens',plants=[];
      for(const y of rows)for(const x of [-.3,-.15,0,.15,.3])plants.push([x,y]);
      if(seed>.7)plants.push(['scarecrow',0,.02]);
      plants.sort((a,b)=>P(...a.slice(-2))[1]-P(...b.slice(-2))[1]);
      for(const plant of plants){
        if(plant[0]==='scarecrow'){this.scarecrow(...P(plant[1],plant[2]),time);continue;}
        const [x,y]=P(...plant),k=hash(Math.round(plant[0]*20)+40,Math.round(plant[1]*20)+40,Math.floor(seed*97));
        const bend=Math.sin(time*.8+seed*8+plant[0]*6)*.9*sway;
        if(growth<.18){this.line([[x,y],[x-1.6,y-2.4]],'#7fa356',1.3);this.line([[x,y],[x+1.6,y-2.8]],'#93b562',1.3);continue;}
        if(kind==='grain'){
          const h=4+growth*10,ripe=growth>.68,stalk=ripe?'#c9ad5e':'#7a9e52',head=ripe?'#ecc96f':'#a9c466';
          for(const dx of [-1.6,0,1.6]){
            const tip=[x+dx*1.3+bend,y-h-(dx?0:1.5)];
            this.line([[x+dx,y],tip],stalk,1.1);
            this.ellipse(tip[0],tip[1]-1.2,1.2,2.6,head);
          }
        }else{
          const r=1.6+growth*2.8;
          this.ellipse(x+.6,y+.3,r*1.1,r*.45,'#4d613a33');
          this.c.beginPath();this.c.arc(x+bend*.3,y-r*.7,r,0,Math.PI*2);
          this.c.fillStyle=this.radial(x,y-r*.7,r,[[0,'#c5dc8a'],[.6,'#86ad58'],[1,'#5f8a45']],'#86ad58',x-r*.4,y-r*1.1);this.c.fill();
          if(growth>.7&&k>.55){this.ellipse(x+2.4,y-.6,2.6,2,'#e08d3e');this.ellipse(x+3.2,y-.9,1.1,1.6,'#c4732f');}
        }
      }
    }
    scarecrow(x,y,time){
      const lean=this.reduced.matches?0:Math.sin(time*.6)*.6;
      this.ellipse(x+3,y+1,6,2,'#3e533f30');
      this.line([[x,y],[x+lean*.3,y-24]],'#8a6b48',1.6);this.line([[x-8+lean,y-17],[x+8+lean,y-16]],'#8a6b48',1.4);
      this.poly([[x-6+lean,y-18],[x+6+lean,y-17],[x+4+lean,y-9],[x-4+lean,y-9]],'#7d93ad');
      this.circle(x+lean,y-21.5,3.3,'#e6cf96');
      this.ellipse(x+lean,y-24,6,1.6,'#c49a54');this.ellipse(x+lean,y-25.4,3.2,2,'#d6ad62');
    }
    well(time=0){
      this.groundPatch('#c9bc92',30);this.ellipse(5,5,21,7,'#3e533f26');
      const posts=[[-.19,.19],[.19,-.19]].sort((a,b)=>this.project(...a)[1]-this.project(...b)[1]);
      const post=([x,y])=>{const [px,py]=this.project(x,y);this.rect(px-1.6,py-24,3.2,25,'#8f6f48');this.rect(px+.2,py-24,1.4,25,'#735737');};
      post(posts[0]);
      this.wellMasonry(true);
      post(posts[1]);
      const R=.28,roof='#b8714f',faces=[];
      for(const side of [-1,1]){
        const at=(t,y)=>[side*R*(1-t),y,21+8*t];
        faces.push(this.face([at(0,-R),at(0,R),at(1,R),at(1,-R)],roof,[side*8,0,R*40],
          [.3,.62].map(t=>({points:[at(t,-R),at(t,R),at(t+.08,R),at(t+.08,-R)],color:shade(roof,.84)}))));
      }
      this.mesh(faces);
      this.line([[0,-21],[0,-12]],'#6f5f48',.9);
      this.poly([[-3,-13],[3,-13],[2.4,-8.5],[-2.4,-8.5]],'#9a7652');this.rect(-3,-13,6,1.2,'#5e5146');
    }
    wellMasonry(complete=false){
      if(complete){
        // Keep the original low, round basin and open water surface; texture its exterior.
        this.ellipse(0,0,13,7,'#a2aa95');this.rect(-13,-8,26,9,'#a7af9e');
        const edge=(a,z)=>[13*Math.cos(a),7*Math.sin(a)-z];
        for(let course=0;course<2;course++){
          const low=course*4.5,high=low+4.5;
          for(let i=0;i<6;i++){
            const a=Math.max(0,(i-(course?.5:0))*Math.PI/5),b=Math.min(Math.PI,(i+1-(course?.5:0))*Math.PI/5);
            if(a>=b)continue;
            const arc=(z,reverse=false)=>Array.from({length:5},(_,j)=>edge(a+(b-a)*(reverse?4-j:j)/4,z));
            this.poly([...arc(low),...arc(high,true)],i%3===0?'#b5bba8':'#a7af9e');
            this.line([edge(a,low),edge(a,high)],'#8c9787',.65);
          }
        }
        this.line(Array.from({length:17},(_,i)=>edge(i*Math.PI/16,4.5)),'#8c9787',.65);
        this.ellipse(0,-9,13,7,'#d0ceaf');
        for(let i=0;i<12;i++){
          const a=i*Math.PI/6,b=(i+1)*Math.PI/6;
          const point=(r,h,t)=>[r*Math.cos(t),h*Math.sin(t)-9];
          this.poly([point(13,7,a),point(13,7,(a+b)/2),point(13,7,b),point(9,4,b),point(9,4,(a+b)/2),point(9,4,a)],i%3===0?'#dce0cc':'#d0ceaf');
          this.line([point(9,4,a),point(13,7,a)],'#a0a58e',.65);
        }
        this.ellipse(0,-9,9,4,'#4d8485');
        this.line([[-5,-9],[-1,-9]],'#a4c8bd',.7);
        return;
      }
      // The unfinished ring has missing stones and an empty shaft.
      this.ellipse(0,0,13,7,'#776a50');
      this.ellipse(0,-1,9,4,'#474b3b');
      const faces=[],point=(r,a,z)=>[r*Math.cos(a),r*Math.sin(a),z];
      for(let i=0;i<10;i++){
        const a=i*Math.PI/6+.025,b=(i+1)*Math.PI/6-.025;
        const low=0,high=i<7?5:2;
        faces.push({points:[point(.24,a,low),point(.24,b,low),point(.24,b,high),point(.24,a,high)],fill:i%3===0?'#b5bba8':'#a7af9e'},
          {points:[point(.17,b,low),point(.17,a,low),point(.17,a,high),point(.17,b,high)],fill:'#788575'},
          {points:[point(.24,a,high),point(.24,b,high),point(.17,b,high),point(.17,a,high)],fill:i%3===0?'#dce0cc':'#d0ceaf'});
      }
      this.mesh(faces);
    }
    construction(type,ground=true){
      // Use the finished structure's footprint and materials, with visible missing work.
      const beam=(points,color='#c8a573',width=2)=>this.line(points.map(p=>this.project(...p)),color,width);
      const board=(points,fill='#c5a574')=>this.mesh([{points,fill}]);
      if(type==='well'){
        if(ground)this.groundPatch('#b4a783',26);
        // Excavated shaft and a partly laid stone ring; no house-sized scaffolding.
        this.wellMasonry();
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
      if(s.type==='well'){this.well(time);return;}
      if(s.type==='storage'){this.storage(hash(s.position.x,s.position.y),!shared);return;}
      if(['house','shelter','workshop'].includes(s.type)){this.house(s.type,hash(s.position.x,s.position.y),!shared,time);return;}
      if(s.type==='road'){this.groundPatch('#d2c49c',38);return;}
      if(s.type==='irrigation'){this.groundPatch('#bcb68b');this.groundLine([[-25,0],[0,12],[25,0]],'#6f9d9e',5);return;}
      this.groundPatch();this.poly([[-12,0],[-12,-16],[0,-22],[12,-16],[12,0],[0,6]],'#bdab81');
    }
    agent(a,index,time){
      const id=String(a.id),look=k=>strHash(id+':'+k);
      if(!a.alive){
        this.ellipse(2,1,9,3,'#344b4130');
        this.poly([[-5,0],[-5,-9],[-3.5,-12],[0,-13],[3.5,-12],[5,-9],[5,0]],'#b9bcaa');
        this.poly([[.5,0],[.5,-13],[3.5,-12],[5,-9],[5,0]],'#9da291');
        this.line([[-2,-8],[2,-8]],'#8d927f',1);return;
      }
      const cloth=colors[index%colors.length],skin=SKIN[Math.floor(look('skin')*SKIN.length)];
      const hair=HAIR[Math.floor(look('hair')*HAIR.length)],style=Math.floor(look('style')*5),hat=look('hat');
      const carry=a.visible_carry||{},goods=carry.resource_types||[];
      const laden=['some','heavy','full'].includes(carry.load),logs=laden&&goods.includes('wood');
      this.ellipse(1.5,.5,8,3,'#2f463a38');
      // Feet stay on the ground; only the torso participates in idle breathing.
      this.rect(-4,-5,3,5,'#4c5953');this.rect(1,-5,3,5,'#4c5953');
      const breath=this.reduced.matches?0:Math.sin(time*1.7+index*2)*.45;
      this.c.translate(0,breath);
      if(laden&&!logs){this.circle(5.2,-12,4.4,'#d3bd8f');this.circle(6.3,-11.5,3,'#bfa77a');this.rect(3.6,-17,2.4,1.6,'#a48b62');}
      if(logs)for(const dy of [0,2.8]){this.line([[-10,-10.5+dy],[10,-15.5+dy]],'#9a7450',2.8);this.ellipse(10,-15.5+dy,1.3,1.5,'#d8b88a');}
      this.poly([[-5.6,-4.2],[-4.9,-13.4],[-2.6,-15],[2.6,-15],[4.9,-13.4],[5.6,-4.2]],cloth);
      this.poly([[.6,-4.2],[.6,-15],[2.6,-15],[4.9,-13.4],[5.6,-4.2]],shade(cloth,.82));
      this.rect(-5.4,-7.6,10.8,1.5,shade(cloth,.6));
      this.poly([[-4.9,-13.4],[-7.3,-12],[-7.6,-6.8],[-5.5,-6.8]],shade(cloth,.93));this.circle(-6.5,-6,1.45,skin);
      this.poly([[4.9,-13.4],[7.3,-12],[7.6,-6.8],[5.5,-6.8]],shade(cloth,.74));this.circle(6.5,-6,1.45,shade(skin,.88));
      this.rect(-1.2,-16.6,2.4,2.2,shade(skin,.84));
      if(style===1){this.c.beginPath();this.c.moveTo(-5.4,-21);this.c.lineTo(-5.6,-13.5);this.c.quadraticCurveTo(0,-11.5,5.6,-13.5);this.c.lineTo(5.4,-21);this.c.fillStyle=hair;this.c.fill();}
      this.circle(0,-20.6,5.1,skin);
      this.c.beginPath();this.c.arc(0,-20.6,5.1,-Math.PI/2,Math.PI/2);this.c.closePath();this.c.fillStyle=shade(skin,.9);this.c.fill();
      if(style!==4||hat>.3){
        this.c.beginPath();this.c.arc(0,-21.2,5.5,Math.PI*1.02,Math.PI*1.98);this.c.lineTo(5.3,-19.6);this.c.lineTo(3.6,-21.6);
        this.c.lineTo(-1.5,-22.4);this.c.lineTo(-5.3,-19.4);this.c.closePath();this.c.fillStyle=hair;this.c.fill();
      }else{this.c.beginPath();this.c.arc(0,-21,5.2,Math.PI*1.1,Math.PI*1.9);this.c.closePath();this.c.fillStyle=hair;this.c.fill();}
      if(style===2&&hat>.3)this.circle(.5,-26.6,2.5,hair);
      if(style===3&&hat>.3)for(let i=0;i<6;i++){const t=Math.PI*(1.02+i*.19);this.circle(Math.cos(t)*5,-21+Math.sin(t)*4.4,2.1,hair);}
      this.rect(-2.4,-20.6,1.2,1.6,'#37352f');this.rect(1.2,-20.6,1.2,1.6,'#37352f');
      this.circle(-3.1,-18.3,.9,'#e0806b55');this.circle(3.1,-18.3,.9,'#e0806b55');
      if(hat<.2){
        this.ellipse(0,-23.6,8.6,2.5,'#d8b56b');this.ellipse(.8,-23.3,7.6,1.8,'#c9a35a');
        this.ellipse(0,-25.4,4.7,3,'#e6c67e');this.rect(-4.6,-24.8,9.2,1.1,'#b0613f');
      }else if(hat<.3){
        this.c.beginPath();this.c.arc(0,-22,5.4,Math.PI,0);this.c.closePath();this.c.fillStyle=shade(colors[(index+4)%colors.length],.9);this.c.fill();
        this.rect(-5.5,-22.6,11,1.6,shade(colors[(index+4)%colors.length],.75));
      }
      if(a.equipped?.length){this.line([[6.5,-6],[12,-19]],'#8a6b48',1.8);this.poly([[10,-20.5],[15,-19.2],[14.4,-17.4],[10.5,-18.4]],'#aeb7b4');}
    }
    pile(p){
      const item=p.item;
      this.ellipse(1,2,7,2.5,'#3e533f2a');
      if(item==='wood'){for(const [dy,dx] of [[0,0],[-2.6,1.2]]){this.line([[-5+dx,1+dy],[4+dx,-1+dy]],'#9a7450',2.6);this.ellipse(4+dx,-1+dy,1.2,1.4,'#d8b88a');}return;}
      if(item==='stone'){this.ellipse(-2,-1,3.6,2.6,'#b3b3a3');this.ellipse(2.5,0,3,2.2,'#9fa292');this.ellipse(0,-3,2.4,1.8,'#cbccbc');return;}
      this.ellipse(0,-2.5,4.6,3.8,'#d3bd8f');this.ellipse(1.6,-2.2,2.6,3.2,'#bea679');this.rect(-1.2,-7,2.4,1.6,'#a48b62');
    }
    // Presentation only: worn footpaths that join neighbouring buildings.
    buildTrails(){
      const tiles=this.snapshot.tiles,{width,height}=this.snapshot.config;
      const sites=[...new Map(this.structures.filter(s=>!['road','irrigation'].includes(s.type))
        .map(s=>[s.position.x+','+s.position.y,{...s.position,farm:s.type==='farm_plot'}])).values()];
      const open=(x,y)=>{const t=tiles[y]?.[x];return Boolean(t)&&t.terrain!=='water'&&t.terrain!=='mountain';};
      const step=(x,y)=>tiles[y][x].terrain==='forest'?2.6:tiles[y][x].structures?.length?1.7:1;
      const route=(a,b)=>{
        const n=width*height,dist=new Float64Array(n).fill(Infinity),prev=new Int32Array(n).fill(-1),done=new Uint8Array(n);
        const start=a.y*width+a.x,goal=b.y*width+b.x;dist[start]=0;
        for(;;){
          let u=-1;for(let i=0;i<n;i++)if(!done[i]&&dist[i]<Infinity&&(u<0||dist[i]<dist[u]))u=i;
          if(u<0)return null;if(u===goal)break;done[u]=1;
          const ux=u%width,uy=(u-ux)/width;
          for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]){
            const x=ux+dx,y=uy+dy;if(!open(x,y))continue;
            if(dx&&dy&&(!open(ux+dx,uy)||!open(ux,uy+dy)))continue;
            const v=y*width+x,d=dist[u]+step(x,y)*(dx&&dy?Math.SQRT2:1);
            if(d<dist[v]){dist[v]=d;prev[v]=u;}
          }
        }
        const path=[];for(let v=goal;v>=0;v=prev[v])path.unshift([v%width,Math.floor(v/width)]);
        return path;
      };
      const trails=[];
      if(sites.length>1){
        const joined=new Set([0]);
        while(joined.size<sites.length){
          let best=null;
          for(const i of joined)for(let j=0;j<sites.length;j++){
            if(joined.has(j))continue;
            const d=Math.hypot(sites[i].x-sites[j].x,sites[i].y-sites[j].y);
            if(!best||d<best.d)best={i,j,d};
          }
          joined.add(best.j);
          const a=sites[best.i],b=sites[best.j];
          if(best.d<=6.5&&!(a.farm&&b.farm)&&open(a.x,a.y)&&open(b.x,b.y)){const path=route(a,b);if(path)trails.push(path);}
        }
      }
      this.trails=trails.map((path,k)=>path.map(([x,y],i)=>i===0||i===path.length-1?[x+.5,y+.5]:
        [x+.5+(hash(x,y,60+k)-.5)*.3,y+.5+(hash(x,y,70+k)-.5)*.3]));
    }
    drawTrails(){
      const c=this.c;c.lineCap='round';c.lineJoin='round';
      for(const trail of this.trails||[]){
        const pts=trail.map(([x,y])=>this.project(x,y));
        const path=()=>{
          c.beginPath();c.moveTo(...pts[0]);
          for(let i=1;i<pts.length-1;i++)c.quadraticCurveTo(pts[i][0],pts[i][1],(pts[i][0]+pts[i+1][0])/2,(pts[i][1]+pts[i+1][1])/2);
          c.lineTo(...pts[pts.length-1]);
        };
        path();c.strokeStyle='#b4a4723d';c.lineWidth=14;c.stroke();
        path();c.strokeStyle='#d9cba0b8';c.lineWidth=7;c.stroke();
      }
    }
    buildBase(){
      this.base=document.createElement('canvas');this.base.width=this.canvas.width;this.base.height=this.canvas.height;
      const c=this.c=this.base.getContext('2d');c.scale(this.dpr,this.dpr);c.translate(this.ox,this.oy);c.scale(this.scale,this.scale);
      const {width,height}=this.snapshot.config,tiles=this.snapshot.tiles,W=WATER_DEPTH;
      const terrain=(x,y)=>tiles[y]?.[x]?.terrain,isWater=(x,y)=>terrain(x,y)==='water';
      const isLand=(x,y)=>terrain(x,y)!==undefined&&!isWater(x,y);
      const quad=(x,y,z=0)=>[[x,y],[x+1,y],[x+1,y+1],[x,y+1]].map(p=>this.project(p[0],p[1],z));
      const sides=[[0,-1,[0,0],[1,0]],[1,0,[1,0],[1,1]],[0,1,[1,1],[0,1]],[-1,0,[0,1],[0,0]]];
      const corners=[[0,0],[width,0],[width,height],[0,height]].map(p=>this.project(...p));
      c.save();c.filter='blur(22px)';this.poly(corners.map(([x,y])=>[x+22,y+40]),'#37584726');c.restore();
      // Water sits below the meadow; shallows fade toward open water.
      const depth=new Map(),queue=[];
      for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(isWater(x,y)&&sides.some(([dx,dy])=>isLand(x+dx,y+dy))){depth.set(x+','+y,1);queue.push([x,y]);}
      for(let i=0;i<queue.length;i++){
        const [x,y]=queue[i],d=depth.get(x+','+y);
        for(const [dx,dy] of sides){const k=(x+dx)+','+(y+dy);if(isWater(x+dx,y+dy)&&!depth.has(k)){depth.set(k,d+1);queue.push([x+dx,y+dy]);}}
      }
      c.save();c.beginPath();
      for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(isWater(x,y)){const q=quad(x,y,-W);c.moveTo(...q[0]);q.slice(1).forEach(p=>c.lineTo(...p));c.closePath();}
      c.fillStyle='#5d9dad';c.fill();c.strokeStyle='#5d9dad';c.lineWidth=1;c.stroke();c.clip();
      for(const [shallow,color,r] of [[2,'#6aabb5',.9],[1,'#7dbdbc',.82]])
        for(const [k,d] of depth)if(d===shallow){const [x,y]=k.split(',').map(Number);this.groundDisc(x+.5,y+.5,r,color,.9,.55,-W);}
      for(const [k,d] of depth){
        const [x,y]=k.split(',').map(Number);
        if(d!==1||hash(x,y,80)<.62)continue;
        for(const i of [0,1]){
          const [px,py]=this.project(x+.3+hash(x,y,81+i)*.4,y+.3+hash(x,y,83+i)*.4,-W);
          this.ellipse(px,py,4.4,2.1,'#7fae66');this.poly([[px,py],[px+4.4,py-.8],[px+4.4,py+.8]],'#7dbdbc');
          if(i===0&&hash(x,y,85)>.5){this.circle(px-1,py-1,1.4,'#f2b6c0');this.circle(px-1,py-1.3,.6,'#fff3c9');}
        }
      }
      c.restore();
      // Earthen banks and a line of foam where land meets water.
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        if(!isWater(x,y))continue;
        for(const [dx,dy,a,b] of sides){
          if(!isLand(x+dx,y+dy))continue;
          const A=[x+a[0],y+a[1]],B=[x+b[0],y+b[1]];
          if(this.facing(-dx,-dy))this.poly([this.project(...A,0),this.project(...B,0),this.project(...B,-W),this.project(...A,-W)],shade('#a08e63',this.lit([-dx,-dy,0])));
          this.line([this.project(A[0]-dx*.05,A[1]-dy*.05,-W),this.project(B[0]-dx*.05,B[1]-dy*.05,-W)],'#f1f6eaa0',2);
        }
      }
      for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(isLand(x,y)){const g=GRASS[Math.floor(hash(x,y)*GRASS.length)];this.poly(quad(x,y),g,g);}
      // Soft meadow variation and forest floor, clipped to the land.
      c.save();c.beginPath();
      for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(isLand(x,y)){const q=quad(x,y);c.moveTo(...q[0]);q.slice(1).forEach(p=>c.lineTo(...p));c.closePath();}
      c.clip();
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        if(!isLand(x,y))continue;
        this.groundDisc(x+.2+hash(x,y,90)*.6,y+.2+hash(x,y,91)*.6,.6+hash(x,y,92)*.5,MEADOW[Math.floor(hash(x,y,93)*MEADOW.length)],.32,.9);
      }
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        if(terrain(x,y)!=='forest'||tiles[y][x].structures?.length)continue;
        this.groundDisc(x+.5,y+.5,.76,'#86a062',1,.3);
        this.groundDisc(x+.35+hash(x,y,94)*.3,y+.35+hash(x,y,95)*.3,.45,'#738f55',.55,.7);
      }
      c.restore();
      // Sandy margins along every shore.
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        if(!isLand(x,y))continue;
        for(const [dx,dy,a,b] of sides){
          if(!isWater(x+dx,y+dy))continue;
          const A=[x+a[0],y+a[1]],B=[x+b[0],y+b[1]];
          for(const [w,color,alpha] of [[.2,'#e2d4a0',.4],[.11,'#e8dcac',.95]]){
            this.poly([this.project(...A),this.project(...B),this.project(B[0]-dx*w,B[1]-dy*w),this.project(A[0]-dx*w,A[1]-dy*w)],withAlpha(color,alpha));
          }
        }
      }
      // Grass tufts, wildflowers, pebbles and reeds.
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const tile=tiles[y][x],t=terrain(x,y);
        if(!isLand(x,y)||tile.structures?.length||this.rockDeposits.has(x+','+y)||this.mountainTiles.has(x+','+y))continue;
        const tuft=t==='forest'?'#5f804ab0':'#7c9a58b0';
        for(let j=0;j<5;j++){
          const [gx,gy]=this.project(x+.1+hash(x,y,j+1)*.8,y+.1+hash(x,y,j+7)*.8);
          this.line([[gx-1.4,gy],[gx-2.4,gy-3]],tuft,1);this.line([[gx,gy],[gx+.6,gy-3.6]],tuft,1);this.line([[gx+1.2,gy],[gx+2.4,gy-2.6]],tuft,1);
        }
        if(t==='plains'&&hash(x,y,50)<.22){
          const color=FLOWERS[Math.floor(hash(x,y,51)*FLOWERS.length)],cx=x+.25+hash(x,y,52)*.5,cy=y+.25+hash(x,y,53)*.5;
          for(let j=0;j<6;j++){
            const [fx,fy]=this.project(cx+(hash(x,y,j+54)-.5)*.32,cy+(hash(x,y,j+60)-.5)*.32);
            this.line([[fx,fy+1.5],[fx,fy]],'#6f8f50',.8);this.circle(fx,fy-.3,1.4,color);this.circle(fx,fy-.3,.5,'#fff6d6');
          }
        }
        if(hash(x,y,66)<.09){const [px,py]=this.project(x+.3+hash(x,y,67)*.4,y+.3+hash(x,y,68)*.4);this.ellipse(px,py,3,1.6,'#a9aa98');this.ellipse(px-.5,py-.5,2.2,1.1,'#c9cabb');}
        for(const [dx,dy,a,b] of sides){
          if(!isWater(x+dx,y+dy)||hash(x,y,dx*3+dy+100)<.5)continue;
          for(let j=0;j<4;j++){
            const t2=.15+j*.22+hash(x,y,j+110)*.08,ex=x+a[0]+(b[0]-a[0])*t2-dx*.1,ey=y+a[1]+(b[1]-a[1])*t2-dy*.1;
            const [rx,ry]=this.project(ex,ey),h=6+hash(x,y,j+120)*5,lean=(hash(x,y,j+130)-.5)*3;
            this.line([[rx,ry],[rx+lean,ry-h]],'#6f8c4e',1.1);
            if(j%2===0)this.rect(rx+lean-.9,ry-h-1,1.8,3.6,'#8a6a48');
          }
        }
      }
      this.drawTrails();
      // A gentle sunlit wash across the meadow, before the mountains rise above it.
      c.save();c.beginPath();corners.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();c.clip();
      const top=Math.min(...corners.map(p=>p[1])),bottom=Math.max(...corners.map(p=>p[1]));
      const left=Math.min(...corners.map(p=>p[0])),right=Math.max(...corners.map(p=>p[0]));
      c.fillStyle=this.linear(left,top,right*.4,bottom,[[0,'#fff4d222'],[.55,'#ffffff00'],[1,'#1f3d2c18']],'#ffffff00');
      c.fillRect(left,top,right-left,bottom-top);c.restore();
      // The diorama slab: a turf lip over layered soil, with water cut away at its edge.
      const edges=[];
      for(let x=0;x<width;x++)edges.push([x,0,x+1,0,0,-1,x,0],[x+1,height,x,height,0,1,x,height-1]);
      for(let y=0;y<height;y++)edges.push([0,y+1,0,y,-1,0,0,y],[width,y,width,y+1,1,0,width-1,y]);
      for(const [ax,ay,bx,by,nx,ny,tx,ty] of edges){
        if(!this.facing(nx,ny))continue;
        const f=this.lit([nx,ny,0]),wet=isWater(tx,ty);
        const band=(z0,z1,color)=>{const fill=shade(color,f);this.poly([this.project(ax,ay,z0),this.project(bx,by,z0),this.project(bx,by,z1),this.project(ax,ay,z1)],fill,fill);};
        if(wet){band(-W,-13,'#79b2b8');band(-13,-SLAB,'#8d7c5d');}
        else{band(0,-3.5,'#93ad68');band(-3.5,-13,'#ab9168');band(-13,-SLAB,'#8f7d5e');}
        band(-SLAB+2.5,-SLAB,'#76694f');
      }
      this.projectedMountains=(this.mountainFaces||[]).map(face=>({...face,fill:this.mountainColor(face.points),screen:face.points.map(p=>this.project(...p)),
        depth:face.points.reduce((sum,p)=>sum+this.project(p[0],p[1])[1],0)/3})).sort((a,b)=>a.depth-b.depth);
      for(const face of this.projectedMountains)this.poly(face.screen,face.fill,face.fill);
      this.c=null;
    }
    waterGlint(x,y,time){
      const h=hash(x,y),shift=this.reduced.matches?0:Math.sin(time*.5+h*8)*3;
      this.line([[-13+shift,-3],[-4+shift,-3]],'#e3f1e870',1.3);
      if(h>.55)this.line([[4-shift,5],[11-shift,5]],'#eef6ea5c',1.1);
      if(this.reduced.matches)return;
      const phase=(time*.2+h*3)%1;
      if(phase<.1){
        const a=Math.sin(phase/.1*Math.PI),sx=(hash(x,y,3)-.5)*26,sy=(hash(x,y,4)-.5)*10;
        this.line([[sx-2.6,sy],[sx+2.6,sy]],withAlpha('#ffffff',a*.9),1);this.line([[sx,sy-1.6],[sx,sy+1.6]],withAlpha('#ffffff',a*.9),1);
      }
    }
    paint(time=0){
      if(!this.snapshot||!this.base)return;
      const c=this.ctx;c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,this.canvas.width,this.canvas.height);c.drawImage(this.base,0,0);
      this.c=c;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.translate(this.ox,this.oy);c.scale(this.scale,this.scale);
      const {width,height}=this.snapshot.config,tiles=this.snapshot.tiles,objects=[];
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const tile=tiles[y][x];
        if(tile.terrain==='water')this.at(x,y,()=>{this.c.translate(0,WATER_DEPTH);this.waterGlint(x,y,time);});
        if(tile.structures?.length)continue;
        if(this.rockDeposits.has(x+','+y))objects.push({x,y,order:0,draw:()=>this.rockDeposit()});
        if(tile.terrain==='forest')for(const t of this.forestSlots(x,y,tile))
          objects.push({x:x+t.dx,y:y+t.dy,order:0,draw:()=>t.kind==='stump'?this.stump():this.drawSprite(t.kind,t.size,t.tone,t.phase,time)});
        if(tile.terrain==='plains'&&hash(x,y,140)>.9&&[[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>tiles[y+dy]?.[x+dx]?.terrain==='forest'))
          objects.push({x:x+(hash(x,y,141)-.5)*.5,y:y+(hash(x,y,142)-.5)*.5,order:0,draw:()=>this.drawSprite('bush',0,Math.floor(hash(x,y,143)*5),hash(x,y,144),time)});
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
      Object.values(this.snapshot.item_piles||{}).forEach(p=>objects.push({...p.position,order:2,draw:()=>this.pile(p)}));
      this.agents.forEach((a,i)=>{
        const anchor=this.agentAnchor(a);
        objects.push({x:a.position.x+anchor.x,y:a.position.y+anchor.y,order:3,draw:()=>this.agent(a,i,time)});
      });
      objects.sort((a,b)=>this.project(a.x,a.y)[1]-this.project(b.x,b.y)[1]||a.order-b.order||a.x-b.x);
      // Terrain is a separate layer. Residents remain legible at every camera angle;
      // their feet follow the exact displayed surface without camera-relative movement.
      for(const obj of objects)this.at(obj.x,obj.y,()=>{
        this.c.translate(0,-this.terrainHeight(obj.x+.5,obj.y+.5));obj.draw();
      });
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
      // Pick visible raised residents before the terrain behind them.
      const resident=this.agents.slice().reverse().find(a=>{
        const anchor=this.agentAnchor(a),wx=a.position.x+.5+anchor.x,wy=a.position.y+.5+anchor.y;
        const [px,py]=this.project(wx,wy,this.terrainHeight(wx,wy));
        return Math.abs(sx-px)<=8&&sy>=py-29&&sy<=py+3;
      });
      const {x,y}=resident?resident.position:this.terrainHit(sx,sy),tile=this.snapshot.tiles[y]?.[x];
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

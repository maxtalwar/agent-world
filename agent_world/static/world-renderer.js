/* Native snapshot -> a quiet isometric diorama. No simulation state is mutated. */
'use strict';
(function (global) {
  const C = {grass:['#a8bd79','#aec37e','#a6bc77','#b3c682'], forest:['#829e65','#8ba66b','#91ac70'], mountain:['#a4ac8c','#abb295','#b2b79b'], water:['#79b7ba','#7dbbbd','#80bdbf']};
  const hash = (x,y,n=0) => {let v=Math.imul(x+71,374761393)^Math.imul(y+37,668265263)^Math.imul(n+11,1274126177);v=Math.imul(v^(v>>>13),1274126177);return ((v^(v>>>16))>>>0)/4294967295;};
  const colors=['#c97b55','#69879a','#b8849f','#c8a653','#7d9671','#b76b64','#7e80a4','#5c9690','#d19b6b','#8e9dba'];
  class WorldRenderer {
    constructor(canvas,{preview=false,onInspect=()=>{}}={}) {
      this.canvas=canvas;this.ctx=canvas.getContext('2d');this.preview=preview;this.onInspect=onInspect;
      this.reduced=matchMedia('(prefers-reduced-motion: reduce)');this.snapshot=null;this.frame=0;this.lastPaint=0;
      this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(canvas);
      this.motionListener=()=>this.restart();this.reduced.addEventListener('change',this.motionListener);
      this.visibilityListener=()=>this.restart();document.addEventListener('visibilitychange',this.visibilityListener);
      this.pointerListener=e=>this.inspect(e);this.leaveListener=()=>this.onInspect(null);
      if(!preview){canvas.addEventListener('pointermove',this.pointerListener);canvas.addEventListener('pointerleave',this.leaveListener);}
    }
    setSnapshot(snapshot) {
      this.snapshot=snapshot;this.structures=Object.values(snapshot.structures||{});
      this.agents=Object.values(snapshot.agents||{});this.occupied=new Map();
      for(const a of this.agents){const k=a.position.x+','+a.position.y;if(!this.occupied.has(k))this.occupied.set(k,[]);this.occupied.get(k).push(a);}
      this.resize();
    }
    resize(){
      const box=this.canvas.getBoundingClientRect();if(!box.width||!box.height)return;
      this.w=box.width;this.h=box.height;const dpr=Math.min(devicePixelRatio||1,2);
      this.canvas.width=Math.round(this.w*dpr);this.canvas.height=Math.round(this.h*dpr);this.dpr=dpr;
      if(!this.snapshot)return;
      const {width,height}=this.snapshot.config;
      const total=width+height;
      const margin=this.preview?24:Math.min(90,this.w*.055);
      this.scale=Math.min((this.w-margin*2)/(total*38),(this.h-(this.preview?35:115))/(total*19+100));
      this.ox=this.w/2-(width-height)*19*this.scale;
      this.oy=(this.h-(total*19+46)*this.scale)/2+64*this.scale+(this.preview?0:12);
      this.buildBase();this.restart();
    }
    project(x,y){return [(x-y)*38,(x+y)*19];}
    poly(points,fill,stroke){
      const c=this.c;c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();
      if(fill){c.fillStyle=fill;c.fill();}if(stroke){c.strokeStyle=stroke;c.lineWidth=1;c.stroke();}
    }
    line(points,color,width=1){const c=this.c;c.beginPath();points.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.strokeStyle=color;c.lineWidth=width;c.lineCap='round';c.lineJoin='round';c.stroke();}
    ellipse(x,y,rx,ry,color){const c=this.c;c.beginPath();c.ellipse(x,y,rx,ry,0,0,Math.PI*2);c.fillStyle=color;c.fill();}
    rect(x,y,w,h,color){this.c.fillStyle=color;this.c.fillRect(x,y,w,h);}
    tile(x,y,color){this.poly([[x,y],[x+38,y+19],[x,y+38],[x-38,y+19]],color);}
    at(x,y,fn){const [sx,sy]=this.project(x,y);this.c.save();this.c.translate(sx,sy+19);fn();this.c.restore();}
    groundPatch(color='#b9b180',r=32){this.poly([[0,-r/2],[r,0],[0,r/2],[-r,0]],color);}
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
    house(type,seed){
      const storage=type==='storage', workshop=type==='workshop', shelter=type==='shelter';
      const w=storage?22:shelter?23:27, d=storage?12:15, h=storage?21:shelter?20:31;
      this.groundPatch('#b7ae82',34);this.ellipse(9,10,32,10,'#59614230');
      if(shelter){
        this.poly([[-27,1],[-4,-35],[26,-9],[6,17]],'#a48151');
        this.poly([[-27,1],[-4,-35],[6,17]],'#d8bd80');
        this.poly([[-15,6],[-4,-22],[0,13]],'#655b42');
        this.line([[-4,-35],[26,-9]],'#e4ca91',2);return;
      }
      this.poly([[-w,-d],[-w,h*.15],[0,d+7],[0,-h+d]],'#ecdec0');
      this.poly([[0,-h+d],[w,-d],[w,6],[0,d+7]],'#c0b399');
      this.poly([[-w,-h],[-w,-d],[0,1],[0,-h+d]],'#eadbc0');
      this.poly([[0,-h+d],[w,-h],[w,-d],[0,1]],'#c9bda2');
      // A pitched roof, with subdued tile courses and a narrow sunlit ridge.
      const roof=workshop?'#687e81':storage?'#909867':seed>.5?'#b56f52':'#bb7c56';
      this.poly([[-w-4,-h+2],[-4,-h-25],[w+4,-h-11],[4,-h+17]],roof);
      this.poly([[-w-4,-h+2],[-4,-h-25],[4,-h+17]],workshop?'#84999a':storage?'#a8ae77':'#d3956a');
      this.line([[-w-4,-h+2],[-4,-h-25],[w+4,-h-11]],workshop?'#abb6ad':'#e6b78b',2);
      for(let i=1;i<4;i++)this.line([[-4+i*7,-h-25+i*3.5],[-4+i*7-20,-h-25+i*3.5+23]],'#684f3e22',1);
      this.poly([[-18,1],[-18,-14],[-8,-9],[-8,6]],'#81694f');
      this.line([[-17,-13],[-9,-9]],'#f0dcad',1);
      this.poly([[8,-6],[8,-17],[17,-21],[17,-10]],'#648487');
      this.line([[12,-18],[12,-8]],'#e1d8b9',1);this.line([[8,-12],[17,-16]],'#e1d8b9',1);
      if(workshop){
        this.poly([[13,-h-9],[13,-h-32],[20,-h-35],[25,-h-32],[25,-h-5]],'#889083');
        this.poly([[13,-h-32],[20,-h-35],[25,-h-32],[18,-h-29]],'#d1cbb8');
        this.poly([[17,-h-32],[20,-h-33],[23,-h-32],[19,-h-31]],'#59645e');
        this.rect(-28,3,10,6,'#a18056');this.rect(-30,1,14,3,'#d3b77c');
      }
      if(storage){this.rect(5,6,8,7,'#a38a5c');this.rect(15,1,7,8,'#bc9b67');}
    }
    farm(tile,seed,time=0){
      this.groundPatch('#927557',34);
      this.poly([[-33,0],[0,16],[33,0],[33,3],[0,20],[-33,3]],'#786749');
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
      this.line([[-31,1],[-2,16]],'#c2a47a',2);
      for(const [x,y] of [[-31,1],[-17,8],[-2,16]]){this.rect(x-1,y-6,2,9,'#d4b98c');this.rect(x-1,y-6,2,2,'#eee0b1');}
    }
    well(){
      this.groundPatch('#bbb48b',26);this.ellipse(4,5,19,7,'#52634b25');
      this.ellipse(0,0,13,7,'#a2aa95');this.rect(-13,-8,26,9,'#a7af9e');
      this.ellipse(0,-9,13,7,'#d0ceaf');this.ellipse(0,-9,9,4,'#4d8485');
      this.rect(-15,-34,3,29,'#96784e');this.rect(12,-34,3,29,'#806b4b');
      this.poly([[-21,-33],[0,-46],[21,-33],[0,-23]],'#a3a575');
      this.poly([[-21,-33],[0,-46],[0,-23]],'#c1bd87');
      this.line([[0,-31],[0,-10]],'#8c7957',1);this.rect(-3,-14,6,5,'#c5ac7a');
    }
    construction(){
      this.groundPatch('#b4a783',32);
      this.poly([[-24,0],[0,12],[24,0],[0,-12]],'#c4b794','#8f8b71');
      for(const [x,y] of [[-24,0],[0,12],[24,0],[0,-12]]){this.rect(x-1.5,y-29,3,30,'#b28d5e');this.rect(x-1.5,y-29,3,3,'#d9be89');}
      this.line([[-24,-29],[0,-17],[24,-29],[0,-41],[-24,-29]],'#c8a573',3);
      this.line([[-20,0],[-4,8]],'#d4b785',3);this.line([[-20,-4],[-4,4]],'#d4b785',3);
    }
    structure(s,tile,time=0){
      if(s.status&&s.status!=='complete'){this.construction();return;}
      if(s.type==='farm_plot'){this.farm(tile,hash(s.position.x,s.position.y),time);return;}
      if(s.type==='well'){this.well();return;}
      if(['house','shelter','storage','workshop'].includes(s.type)){this.house(s.type,hash(s.position.x,s.position.y));return;}
      if(s.type==='road'){this.groundPatch('#c8bea0',38);return;}
      if(s.type==='irrigation'){this.groundPatch('#bcb68b');this.line([[-25,0],[0,12],[25,0]],'#6f9d9e',5);return;}
      this.groundPatch();this.poly([[-12,0],[-12,-16],[0,-22],[12,-16],[12,0],[0,6]],'#bdab81');
    }
    agent(a,index,time){
      if(!a.alive){this.ellipse(0,2,7,3,'#6a725c');this.rect(-4,-5,8,7,'#b0b3a0');return;}
      const party=this.occupied.get(a.position.x+','+a.position.y),slot=party.indexOf(a);
      const dx=party.length>1?(slot-(party.length-1)/2)*12:10,dy=party.length>1?10:11;
      this.c.translate(dx,dy);
      this.ellipse(1,2,7,3,'#344b413c');
      const breath=this.reduced.matches?0:Math.sin(time*1.7+index*2)*.45;
      this.c.translate(0,breath);
      this.rect(-4,-3,3,5,'#4c5953');this.rect(1,-3,3,5,'#4c5953');
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
      const top=this.project(0,0),right=this.project(width,0),bottom=this.project(width,height),left=this.project(0,height);
      this.c.save();this.c.filter='blur(20px)';this.poly([[left[0]+20,left[1]+30],[bottom[0]+25,bottom[1]+40],[right[0]+25,right[1]+30],[0,30]],'#37584724');this.c.restore();
      this.poly([left,bottom,[bottom[0],bottom[1]+22],[left[0],left[1]+22]],'#9a9e75');
      this.poly([right,bottom,[bottom[0],bottom[1]+22],[right[0],right[1]+22]],'#7f8f70');
      this.poly([[left[0],left[1]+17],[bottom[0],bottom[1]+17],[right[0],right[1]+17],[right[0],right[1]+22],[bottom[0],bottom[1]+22],[left[0],left[1]+22]],'#7a89714d');
      for(let y=0;y<height;y++)for(let x=0;x<width;x++){
        const tile=this.snapshot.tiles[y][x],terrain=tile.terrain,palette=C[terrain==='plains'?'grass':terrain]||C.grass,[sx,sy]=this.project(x,y);
        this.tile(sx,sy,palette[Math.floor(hash(x,y)*palette.length)]);
        if(terrain==='water'){
          // Shorelines follow the actual grid, including the landlocked lake.
          for(const [dx,dy,a,b] of [[0,-1,[0,0],[38,19]],[1,0,[38,19],[0,38]],[0,1,[0,38],[-38,19]],[-1,0,[-38,19],[0,0]]]){
            const n=this.snapshot.tiles[y+dy]?.[x+dx];
            if(n&&n.terrain!=='water'){
              this.line([[sx+a[0],sy+a[1]],[sx+b[0],sy+b[1]]],'#c7c49a',5);
              const mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;
              this.line([[sx+mx*.85,sy+19+(my-19)*.85],[sx+b[0]*.9,sy+19+(b[1]-19)*.9]],'#b9d4c5',1.5);
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
      for(const group of grouped.values())group.forEach((s,i)=>objects.push({...s.position,order:1,draw:()=>{
        const tile=this.snapshot.tiles[s.position.y]?.[s.position.x];if(!tile)return;
        if(group.length>1){this.c.translate((i-(group.length-1)/2)*18,0);this.c.scale(Math.max(.45,1/group.length+.2),Math.max(.45,1/group.length+.2));}
        this.structure(s,tile,time);
      }}));
      Object.values(this.snapshot.item_piles||{}).forEach(p=>objects.push({...p.position,order:2,draw:()=>{this.rect(-4,3,8,5,'#bba06b');this.line([[-4,5],[4,5]],'#8b7b58',1);}}));
      this.agents.forEach((a,i)=>objects.push({...a.position,order:3,draw:()=>this.agent(a,i,time)}));
      objects.sort((a,b)=>(a.x+a.y)-(b.x+b.y)||a.order-b.order||a.x-b.x);
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
      const x=Math.floor((sx/38+sy/19)/2),y=Math.floor((sy/19-sx/38)/2),tile=this.snapshot.tiles[y]?.[x];
      if(!tile){this.onInspect(null);return;}
      const structures=this.structures.filter(s=>s.position.x===x&&s.position.y===y),agents=this.agents.filter(a=>a.position.x===x&&a.position.y===y);
      this.onInspect({x,y,tile,structures,agents});
    }
    destroy(){cancelAnimationFrame(this.frame);this.resizeObserver.disconnect();this.reduced.removeEventListener('change',this.motionListener);document.removeEventListener('visibilitychange',this.visibilityListener);this.canvas.removeEventListener('pointermove',this.pointerListener);this.canvas.removeEventListener('pointerleave',this.leaveListener);}
  }
  global.WorldRenderer=WorldRenderer;
})(window);

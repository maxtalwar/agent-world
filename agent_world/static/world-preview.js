'use strict';
(() => {
  const canvas=document.getElementById('world-preview');
  if(!canvas||document.getElementById('laboratory-panel').hidden)return;
  const renderer=new WorldRenderer(canvas,{preview:true});
  fetch('/api/world?run=demo',{signal:AbortSignal.timeout(15000)})
    .then(response=>{if(!response.ok)throw new Error('Preview unavailable');return response.json();})
    .then(data=>renderer.setSnapshot(data.snapshot))
    .catch(()=>{canvas.hidden=true;});
  window.addEventListener('pagehide',()=>renderer.destroy());
})();

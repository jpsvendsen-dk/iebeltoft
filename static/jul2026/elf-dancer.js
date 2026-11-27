import {poseAt, PlayerClock} from './elf-motion.js?v=1';
import {ElfRenderer} from './elf-renderer.js?v=1';

const ROOT='/static/jul2026/';
export async function createDancer(stage, {getPlayer, isVisible, isCurrent=()=>true, preview=false}) {
  const [map, atlasInfo] = await Promise.all([
    fetch(ROOT+'elf-feliz-navidad-v1.json?v=1').then(r=>{if(!r.ok)throw Error('Timing');return r.json();}),
    fetch(ROOT+'elf-atlas-v1.json?v=1').then(r=>{if(!r.ok)throw Error('Atlas');return r.json();}),
  ]);
  if(!isCurrent())return null;
  const image=new Image();
  await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;image.src=ROOT+'elf-atlas-v1.webp?v=1';});
  if(!isCurrent())return null;
  const canvas=stage.querySelector('canvas'),toggle=stage.querySelector('.elf-toggle');
  const renderer=new ElfRenderer(canvas,image,atlasInfo.parts),clock=new PlayerClock();
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let stopped=false,manualPause=false,state=-1,frame=0,lastSample=-Infinity,shown=false,lastTime=0;
  const note=stage.querySelector('.elf-caption');
  note.textContent=preview?'Danseprøve · Rytmen afventer øretest':'Nissepigens danseprøve';
  function stopFrame(){cancelAnimationFrame(frame);frame=0;}
  function button(){toggle.textContent=manualPause?'Start nissen':'Pause nissen';toggle.setAttribute('aria-pressed',String(manualPause));toggle.disabled=reduced.matches;if(reduced.matches)toggle.textContent='Rolig visning';}
  function hide(){stopFrame();stage.hidden=true;stage.closest('#surprise').classList.remove('elf-playing');shown=false;}
  function show(){stage.hidden=false;stage.closest('#surprise').classList.add('elf-playing');shown=true;button();}
  function sample(now){
    try {const player=getPlayer();clock.sample(player.getCurrentTime(),now,player.getPlaybackRate());}
    catch(_){clock.valid=false;}
    lastSample=now;
  }
  function render(now){
    frame=0;
    if(stopped||state!==1||document.hidden||!isVisible())return;
    if(now-lastSample>=150)sample(now);
    const time=clock.current(now);
    if(time!==null&&!clock.stalled(now))lastTime=time;
    renderer.draw(poseAt(lastTime,map));
    if(!manualPause&&!reduced.matches)frame=requestAnimationFrame(render);
  }
  function resume(){
    stopFrame();
    if(stopped||state!==1||document.hidden||!isVisible())return;
    show();clock.playing=true;sample(performance.now());
    const time=clock.current(performance.now());if(time!==null)lastTime=time;
    renderer.draw(poseAt(lastTime,map));
    if(!manualPause&&!reduced.matches)frame=requestAnimationFrame(render);
  }
  function playerState(value){
    if(stopped)return;
    state=value;clock.playing=value===1;
    if(value===1)resume();
    else {stopFrame();if(value===0||value===-1||value===5)hide();}
  }
  const onToggle=()=>{manualPause=!manualPause;button();if(manualPause)stopFrame();else resume();};
  const onVisibility=()=>{if(document.hidden)stopFrame();else resume();};
  const onMotion=()=>{button();resume();};
  toggle.addEventListener('click',onToggle);
  document.addEventListener('visibilitychange',onVisibility);
  reduced.addEventListener('change',onMotion);
  let calibration=null;
  if(preview){
    calibration=document.createElement('details');calibration.className='elf-calibration';
    calibration.innerHTML='<summary>Justér rytmen i prøven</summary><p>Foreløbig rytmeplan. Ændringer her gælder kun denne prøvevisning og udgives ikke automatisk.</p><label>Tempo (BPM)<input class="elf-bpm" type="number" min="30" max="260" step="0.05"></label><label>Første taktslag (sekunder)<input class="elf-offset" type="number" min="0" max="30" step="0.01"></label><button class="elf-tap" type="button">Markér et taktslag nu</button><p class="elf-timing-status" role="status"></p>';
    stage.append(calibration);
    const bpm=calibration.querySelector('.elf-bpm'),offset=calibration.querySelector('.elf-offset'),status=calibration.querySelector('.elf-timing-status');
    bpm.value=map.bpm;offset.value=map.anchors[0].time;
    const update=()=>{
      const tempo=Number(bpm.value),start=Number(offset.value);
      if(!Number.isFinite(tempo)||tempo<30||tempo>260||!Number.isFinite(start)||start<0||start>30)return;
      map.bpm=tempo;map.anchors=[{time:start,beat:0},{time:map.end,beat:(map.end-start)*tempo/60}];
      status.textContent=`Prøve: ${tempo} BPM · Første slag ${start.toFixed(2)} s.`;resume();
    };
    bpm.addEventListener('change',update);offset.addEventListener('change',update);
    let tapped=[];
    calibration.querySelector('.elf-tap').addEventListener('click',()=>{
      try{
        const t=getPlayer().getCurrentTime();
        if(tapped.length&&t-tapped.at(-1)>2)tapped=[];
        if(!tapped.length||t-tapped.at(-1)>.15)tapped.push(t);
        if(tapped.length>12)tapped.shift();
        if(tapped.length>=4){
          const intervals=tapped.slice(1).map((t,i)=>t-tapped[i]).sort((a,b)=>a-b);
          const period=intervals[Math.floor(intervals.length/2)],tempo=60/period;
          bpm.value=(Math.round(tempo*20)/20).toFixed(2);offset.value=(tapped[0]%period).toFixed(2);update();
        }else status.textContent=`Markér mindst fire på hinanden følgende taktslag (${tapped.length}/4).`;
      }catch(_){status.textContent='Start videoen først.';}
    });
  }
  renderer.draw(poseAt(-1,map));
  try{playerState(getPlayer()?.getPlayerState()??-1);}catch(_){}
  return {
    playerState,
    refresh:resume,
    hide,
    dispose(){stopped=true;hide();toggle.removeEventListener('click',onToggle);document.removeEventListener('visibilitychange',onVisibility);reduced.removeEventListener('change',onMotion);calibration?.remove();},
  };
}

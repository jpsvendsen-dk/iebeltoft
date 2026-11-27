import {MatteVideo} from './matte-video.js';
import {SongClock,DanceSynchronizer} from './playback-sync.js';
import {sampleDance,validateRhythm} from './beat-dance.js';

export async function createDancer(stage,{videoId,getPlayer,isVisible,isCurrent=()=>true}){
    const json=async path=>{const response=await fetch(new URL(path,import.meta.url));if(!response.ok)throw Error('Dancer asset');return response.json();};
  const songs=await json('assets/dance-songs.json?v=2');
  const song=songs[videoId];
  if(!song||!isCurrent())return null;
  const [info,map]=await Promise.all([json(song.video||'assets/dance-video.json'),json(song.rhythm)]);
  validateRhythm(map);
  if(map.videoId!==videoId||Math.abs(info.duration-map.clip.duration)>.05)throw Error('Dance media mismatch');
  if(!isCurrent())return null;
  const canvas=stage.querySelector('canvas'),note=stage.querySelector('.elf-caption');
  const video=document.createElement('video');video.hidden=true;video.muted=true;video.playsInline=true;video.preload='auto';
  stage.append(video);canvas.setAttribute('aria-label',`En voksen nissekvinde danser til ${song.title}`);
  const renderer=new MatteVideo(video,canvas,{...info,src:new URL(info.src,import.meta.url).href});
  const clock=new SongClock();
  const sync=new DanceSynchronizer(video,()=>{note.textContent='Sæt sangen på pause og start den igen for at genstarte dansen.';});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let stopped=false,state=-1,lastSample=-Infinity;
  note.textContent=`Nissen danser til ${song.title}`;
  function hide(){sync.pause();stage.hidden=true;stage.closest('#surprise')?.classList.remove('elf-playing');}
  function tick(){
    if(stopped)return;
    if(!isCurrent()){dispose();return;}
    if(!isVisible()){hide();return;}
    if(document.hidden){sync.pause();return;}
    const now=performance.now();
    try{
      const player=getPlayer();
      if(!player)return;
      const next=player.getPlayerState();
      if(next!==state){if(next===1)sync.requestAlignment();state=next;}
      if(state===-1||state===0||state===5){hide();return;}
      if(state===1){stage.hidden=false;stage.closest('#surprise')?.classList.add('elf-playing');}
      if(now-lastSample>=140){clock.observe(player.getCurrentTime(),now,player.getPlaybackRate()||1,state===1);lastSample=now;}
      if(reduced.matches){sync.pause();return;}
      sync.update(sampleDance(clock.sample(now,state===1),map),{playing:state===1,masterRate:clock.rate,now});
    }catch(_){sync.pause();}
  }
  function playerState(value){if(stopped)return;if(value===1&&state!==1)sync.requestAlignment();state=value;lastSample=-Infinity;tick();}
  const onVisibility=()=>{if(document.hidden)sync.pause();else{sync.requestAlignment();tick();}};
  const onMotion=()=>{tick();};
  document.addEventListener('visibilitychange',onVisibility);
  reduced.addEventListener('change',onMotion);
  const timer=setInterval(tick,50);
  function dispose(){
    if(stopped)return;stopped=true;clearInterval(timer);hide();renderer.dispose();
    document.removeEventListener('visibilitychange',onVisibility);reduced.removeEventListener('change',onMotion);video.remove();
  }
  tick();
  return {playerState,refresh:()=>{sync.requestAlignment();tick();},hide,dispose};
}

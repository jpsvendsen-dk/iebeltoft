import {SnakeGame} from './snake-core.js?v=1';
import {SnakeRenderer} from './snake-renderer.js?v=2';

(() => {
  const $ = id => document.getElementById(id), dialog = $('snake-dialog'), canvas = $('snake-board');
  const renderer = new SnakeRenderer(canvas), preview = new SnakeGame(2026), api = '/Jul2026/api/snake';
  let game = null, round = null, turns = [], nextDirection = null, timer;
  let phase = 'idle', profile = null, loaded = false, loading = false, saving = false, pending = false, failedSave = false;
  let loadGeneration = 0, guestBest = 0;
  try { guestBest = Math.max(0,Math.min(3970,Number(localStorage.getItem('jul2026-snake-guest-best'))||0)); } catch (_) {}
  const message = text => { $('snake-status').textContent = text; };
  const identity = value => value?.account_id ?? null;
  async function request(path, body) {
    const response = await fetch(api+path, body === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json','X-Calendar-Request':'1'},body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Forbindelsen driller. Prøv igen.');
    return data;
  }
  function controls() {
    $('snake-score').textContent = game?.score || 0;
    $('snake-best').textContent = profile ? profile.best_score : guestBest;
    $('snake-start').hidden = !['idle','over'].includes(phase);
    $('snake-start').disabled = !loaded || loading || saving || pending;
    $('snake-start').textContent = game ? 'Spil igen' : 'Start spil';
    $('snake-pause').hidden = !['running','paused'].includes(phase);
    $('snake-pause').disabled = loading;
    $('snake-pause').textContent = phase === 'paused' ? 'Fortsæt' : 'Pause';
    $('snake-retry').hidden = !failedSave;
    $('snake-retry').disabled = saving;
    $('snake-reload').hidden = loaded || loading;
    $('snake-settings').hidden = !profile;
    $('snake-login').hidden = Boolean(profile);
    $('snake-profile-note').textContent = profile ? 'Din rekord gemmes på kalenderprofilen på tværs af enheder.' : 'Gæstespil · Rekorden gemmes kun i denne browser. Log ind for at gemme på din profil.';
  }
  function draw() { renderer.update(game || preview, phase); }
  async function leaderboard() {
    const list=$('snake-toplist');
    try {
      const data=await request('/leaderboard');list.replaceChildren();
      for(const player of data.players){const row=document.createElement('li'),name=document.createElement('span'),score=document.createElement('strong');name.textContent=`${player.rank}. ${player.name}`;score.textContent=`${player.score} point`;row.append(name,score);list.append(row);}
      if(!data.players.length){const row=document.createElement('li');row.textContent='Her er plads til julens første rekord.';list.append(row);}
    } catch (_) {list.textContent='Toplisten kunne ikke hentes. Åbn spillet igen for at prøve på ny.';}
  }
  async function loadProfile() {
    const generation=++loadGeneration;loading=true;controls();
    try {
      const data=await request('/profile');if(generation!==loadGeneration)return;
      if(identity(profile)!==identity(data.profile) && game){
        clearTimeout(timer);game=null;round=null;turns=[];phase='idle';pending=failedSave=false;
        message('Dit login er ændret. Start et nyt spil på den aktuelle profil.');
      }
      profile=data.profile;loaded=true;
      $('snake-name').value=profile?.display_name||'';$('snake-public').checked=Boolean(profile?.is_public);
      if(!game)message('Saml gaver, og undgå kanten og din egen hale. 10 point pr. gave.');
    } catch(error){loaded=false;message(error.message||'Din profil kunne ikke hentes. Prøv igen.');}
    finally{if(generation===loadGeneration){loading=false;controls();draw();}}
  }
  function pause() {if(phase==='running'){clearTimeout(timer);phase='paused';message('Spillet er på pause. Tryk Fortsæt, når du er klar.');controls();draw();}}
  async function saveResult() {
    if(!pending || saving || !round)return;
    saving=true;failedSave=false;message('Gemmer resultatet på din profil …');controls();
    const submission=round;
    try {
      const data=await request(`/rounds/${submission.round_id}/finish`,{account_id:submission.account_id,ticks:game.tick,turns});
      if(round!==submission)return;
      profile=data.profile;pending=false;message(`Gemt på profilen · Din rekord er ${profile.best_score} point.`);void leaderboard();
    } catch(error){if(round===submission){failedSave=true;message(`${error.message||'Resultatet kunne ikke gemmes.'} Behold siden åben, og prøv at gemme igen.`);}}
    finally{saving=false;controls();}
  }
  function finish() {
    phase='over';
    if(round){pending=true;void saveResult();}
    else {guestBest=Math.max(guestBest,game.score);try{localStorage.setItem('jul2026-snake-guest-best',String(guestBest));}catch(_){}message(`Spillet er slut · ${game.score} point. Din lokale rekord er ${guestBest} point.`);}
    controls();draw();
  }
  function schedule() {
    clearTimeout(timer);
    timer=setTimeout(()=>{
      if(phase!=='running')return;
      if(nextDirection!==null){turns.push({tick:game.tick+1,direction:nextDirection});}
      game.step(nextDirection);nextDirection=null;controls();draw();
      if(game.over)finish();else schedule();
    },game.interval);
  }
  async function start() {
    if(!loaded || loading || saving || pending || ['running','paused'].includes(phase))return;
    loading=true;controls();
    try {
      const data=await request('/profile');
      profile=data.profile;
      let seed;
      if(profile){const started=await request('/rounds',{account_id:profile.account_id});round={...started,account_id:profile.account_id};seed=started.seed;}
      else{round=null;const random=new Uint32Array(1);crypto.getRandomValues(random);seed=random[0]||1;}
      game=new SnakeGame(seed);turns=[];nextDirection=null;phase=dialog.open&&!document.hidden?'running':'paused';
      failedSave=false;message(phase==='running'?'God gavejagt!':'Spillet er på pause. Tryk Fortsæt.');
      if(phase==='running')schedule();
      if(phase==='running')canvas.focus({preventScroll:true});
    } catch(error){message(error.message||'Spillet kunne ikke starte. Prøv igen.');}
    finally{loading=false;controls();draw();}
  }
  function turn(direction) {
    if(phase!=='running' || nextDirection!==null || direction===(game.direction+2)%4 || direction===game.direction)return;
    nextDirection=direction;
  }
  $('snake-open').addEventListener('click',()=>{
    if(!document.dispatchEvent(new Event('jul2026:snake-open',{cancelable:true})))return;
    dialog.showModal();pause();void loadProfile();void leaderboard();
  });
  $('snake-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{pause();});dialog.addEventListener('cancel',pause);
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
  window.addEventListener('orientationchange',pause);
  $('snake-start').addEventListener('click',start);
  $('snake-retry').addEventListener('click',saveResult);
  $('snake-reload').addEventListener('click',loadProfile);
  $('snake-pause').addEventListener('click',()=>{if(loading)return;if(phase==='running')pause();else if(phase==='paused'){phase='running';message('God gavejagt!');controls();draw();schedule();canvas.focus({preventScroll:true});}});
  $('snake-login').addEventListener('click',()=>{dialog.close();$('account-open').click();});
  const keyMap={ArrowRight:0,d:0,D:0,ArrowDown:1,s:1,S:1,ArrowLeft:2,a:2,A:2,ArrowUp:3,w:3,W:3};
  document.addEventListener('keydown',event=>{
    if(!dialog.open)return;
    if(['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName))return;
    if(keyMap[event.key]!==undefined){event.preventDefault();turn(keyMap[event.key]);}
    else if(event.code==='Space'&&event.target===canvas){event.preventDefault();$('snake-pause').click();}
  });
  for(const button of dialog.querySelectorAll('[data-snake-direction]')){
    button.addEventListener('pointerdown',event=>{event.preventDefault();turn(Number(button.dataset.snakeDirection));});
    button.addEventListener('click',event=>{if(event.detail===0)turn(Number(button.dataset.snakeDirection));});
  }
  let pointer=null;
  canvas.addEventListener('pointerdown',event=>{pointer=[event.clientX,event.clientY];canvas.setPointerCapture(event.pointerId);});
  canvas.addEventListener('pointermove',event=>{if(!pointer)return;const dx=event.clientX-pointer[0],dy=event.clientY-pointer[1];if(Math.max(Math.abs(dx),Math.abs(dy))<14)return;turn(Math.abs(dx)>Math.abs(dy)?dx>0?0:2:dy>0?1:3);pointer=[event.clientX,event.clientY];});
  for(const name of ['pointerup','pointercancel'])canvas.addEventListener(name,()=>{pointer=null;});
  $('snake-preferences').addEventListener('submit',async event=>{
    event.preventDefault();if(!profile || loading || saving)return;pause();loading=true;controls();$('snake-settings-save').disabled=true;
    try{const data=await request('/profile',{account_id:profile.account_id,display_name:$('snake-name').value,is_public:$('snake-public').checked});profile=data.profile;$('snake-name').value=profile.display_name;message(profile.is_public?'Du deltager nu på toplisten med dit spillernavn.':'Din rekord er privat. Du vises ikke på toplisten.');void leaderboard();}
    catch(error){message(error.message||'Indstillingen kunne ikke gemmes.');}
    finally{loading=false;$('snake-settings-save').disabled=false;controls();}
  });
  controls();draw();
})();

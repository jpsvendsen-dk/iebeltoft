import {SnakeGame} from './snake-core.js?v=3';
import {SnakeRenderer} from './snake-renderer.js?v=6';
import {SnakeAudio} from './snake-audio.js?v=2';

(() => {
  const $ = id => document.getElementById(id), dialog = $('snake-dialog'), canvas = $('snake-board');
  const renderer = new SnakeRenderer(canvas), preview = new SnakeGame(2026,3), api = '/Jul2026/api/snake';
  const sounds = new SnakeAudio();
  let game = null, round = null, turns = [], directionQueue = [], timer;
  let phase = 'idle', profile = null, loaded = false, loading = false, saving = false, pending = false, failedSave = false;
  let loadGeneration = 0, guestBest = 0;
  let newRecord = false;
  let preferencesDirty=false, preferencesTimer, preferencesPromise=null, leaderboardGeneration=0;
  try { guestBest = Math.max(0,Math.min(200000,Number(localStorage.getItem('jul2026-snake-guest-best'))||0)); } catch (_) {}
  const message = text => { $('snake-status').textContent = text; };
  const identity = value => value?.account_id ?? null;
  async function logClick(action) {
    const body={event_id:crypto.randomUUID(),action};
    try{await request('/events',body);}catch(_){try{await request('/events',body);}catch(_){/* Logging must not block the game. */}}
  }
  async function request(path, body) {
    const response = await fetch(api+path, body === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json','X-Calendar-Request':'1'},body:JSON.stringify(body),keepalive:path==='/profile'});
    const data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Forbindelsen driller. Prøv igen.');
    return data;
  }
  function controls() {
    const soundEnabled=$('sound').getAttribute('aria-pressed')!=='false';
    sounds.setEnabled(soundEnabled);
    $('snake-sound').textContent=soundEnabled?'♫ Lyd til':'♫ Lyd fra';
    $('snake-sound').setAttribute('aria-pressed',String(soundEnabled));
    $('snake-score').textContent = game?.score || 0;
    $('snake-best').textContent = profile ? profile.best_score : guestBest;
    $('snake-lives').textContent=game?.lives??2;
    $('snake-start').hidden = !['idle','over'].includes(phase);
    $('snake-start').disabled = !loaded || loading || saving || pending;
    $('snake-start').textContent = game ? 'Spil igen' : 'Start spil';
    $('snake-pause').hidden = !['running','paused','life'].includes(phase);
    $('snake-pause').disabled = loading;
    $('snake-pause').textContent = phase === 'life' ? 'Brug næste liv' : phase === 'paused' ? 'Fortsæt' : 'Pause';
    $('snake-retry').hidden = !failedSave;
    $('snake-retry').disabled = saving;
    $('snake-reload').hidden = loaded || loading;
    $('snake-settings').hidden = !profile;
    $('snake-login').hidden = Boolean(profile);
    if(profile||phase!=='over')$('snake-invitation').hidden=true;
    $('snake-profile-note').textContent = profile ? 'Din rekord gemmes på kalenderprofilen på tværs af enheder.' : 'Gæstespil · Rekorden gemmes kun i denne browser. Log ind for at gemme på din profil.';
    $('snake-player-note').textContent=profile?.display_name?`Du spiller som ${profile.display_name}`:profile?'Du er logget ind · Vælg dit spillernavn under “Julens top 10”.':'Du spiller som gæst';
    $('snake-public').checked=true;
    $('snake-membership').textContent=!profile?'Log ind for at gemme dit spillernavn og deltage.':!profile.display_name?'Gem dit spillernavn nedenfor. Din rekord kommer automatisk med på toplisten.':profile.best_score===0?`Du spiller som ${profile.display_name}. Afslut et spil med point for at komme med på listen.`:`Du deltager som ${profile.display_name} · Din rekord er ${profile.best_score} point.`;
  }
  function draw() { renderer.update(game || preview, phase); }
  async function inviteGuestToTopTen(finishedGame) {
    const score=guestBest;
    if(profile||score<=0)return;
    try{
      const data=await request('/leaderboard');
      if(profile||game!==finishedGame||phase!=='over'||!dialog.open)return;
      const players=data.players;
      if(!Array.isArray(players))return;
      // Existing players win tied scores, matching the server's ordering.
      const rank=1+players.filter(player=>player.score>=score).length;
      if(rank>10)return;
      $('snake-invitation-text').textContent=`Din gæsterekord på ${score} point ville lige nu give en ${rank}. plads på Julens top 10! Opret en profil og vælg et spillernavn for at spille med på toplisten.`;
      $('snake-invitation').hidden=false;
    }catch(_){/* An unavailable leaderboard must not interrupt the game. */}
  }
  async function leaderboard() {
    const list=$('snake-toplist'),generation=++leaderboardGeneration;
    try {
      const data=await request('/leaderboard');if(generation!==leaderboardGeneration)return;list.replaceChildren();
      for(const player of data.players){const row=document.createElement('li'),name=document.createElement('span'),score=document.createElement('strong');name.textContent=`${player.rank}. ${player.name}`;score.textContent=`${player.score} point`;row.append(name,score);list.append(row);}
      if(!data.players.length){const row=document.createElement('li');row.textContent='Ingen rekorder endnu. Gem dit spillernavn og afslut et spil med point.';list.append(row);}
    } catch (_) {if(generation===leaderboardGeneration)list.textContent='Toplisten kunne ikke hentes. Tryk “Opdatér topliste” for at prøve igen.';}
  }
  async function loadProfile() {
    const generation=++loadGeneration;loading=true;controls();
    try {
      const data=await request('/profile');if(generation!==loadGeneration)return;
      if(identity(profile)!==identity(data.profile) && game){
        clearTimeout(timer);game=null;round=null;turns=[];directionQueue=[];phase='idle';pending=failedSave=false;
        message('Dit login er ændret. Start et nyt spil på den aktuelle profil.');
      }
      const changed=identity(profile)!==identity(data.profile);
      profile=data.profile;loaded=true;
      if(changed){preferencesDirty=false;clearTimeout(preferencesTimer);}
      if(!preferencesDirty){$('snake-name').value=profile?.display_name||'';$('snake-public').checked=true;$('snake-preferences-status').textContent=profile?.display_name?'Spillernavnet er gemt på din profil.':'';$('snake-preferences-status').removeAttribute('data-error');}
      if(!game)message('Du har 2 liv. Saml gaver, og få ét ekstra liv, når du kommer over 500 point.');
    } catch(error){loaded=false;message(error.message||'Din profil kunne ikke hentes. Prøv igen.');}
    finally{if(generation===loadGeneration){loading=false;controls();draw();}}
  }
  function pause() {sounds.stop();if(phase==='running'){clearTimeout(timer);directionQueue=[];phase='paused';message('Spillet er på pause. Tryk Fortsæt, når du er klar.');controls();draw();}}
  async function saveResult() {
    if(!pending || saving || !round)return;
    saving=true;failedSave=false;message('Gemmer resultatet på din profil …');controls();
    const submission=round;
    try {
      const data=await request(`/rounds/${submission.round_id}/finish`,{account_id:submission.account_id,ticks:game.tick,turns});
      if(round!==submission)return;
      profile={...profile,best_score:Math.max(profile?.best_score||0,data.profile.best_score)};pending=false;message(`${newRecord?'Tillykke med din nye rekord! ':''}Gemt på profilen · Din rekord er ${profile.best_score} point.`);void leaderboard();
    } catch(error){if(round===submission){failedSave=true;message(`${error.message||'Resultatet kunne ikke gemmes.'} Behold siden åben, og prøv at gemme igen.`);}}
    finally{saving=false;controls();}
  }
  function finish() {
    phase='over';
    newRecord=game.score>(profile?profile.best_score:guestBest);
    sounds.play(game.won?'start':'over');
    if(round){pending=true;void saveResult();}
    else {guestBest=Math.max(guestBest,game.score);try{localStorage.setItem('jul2026-snake-guest-best',String(guestBest));}catch(_){}message(`${newRecord?'Tillykke med din nye rekord! ':''}Spillet er slut · ${game.score} point. Din lokale rekord er ${guestBest} point.`);}
    controls();draw();
    if(newRecord)renderer.celebrate();
    if(!round)void inviteGuestToTopTen(game);
  }
  function schedule() {
    clearTimeout(timer);
    timer=setTimeout(()=>{
      if(phase!=='running')return;
      const direction=directionQueue.shift()??null;
      if(direction!==null){turns.push({tick:game.tick+1,direction});}
      const before=game.score;
      const hadBonus=game.bonusLife;
      game.step(direction);controls();draw();
      if(game.score>before&&!game.over)sounds.play('gift');
      if(!hadBonus&&game.bonusLife)message('Ekstra liv! Du er kommet over 500 point.');
      if(game.over)finish();
      else if(game.lifeLost){directionQueue=[];phase='life';sounds.play('life');message(`Du mistede et liv. ${game.lives} tilbage — dine ${game.score} point og slangens længde er bevaret.`);controls();draw();}
      else schedule();
    },game.interval);
  }
  async function start() {
    if(!loaded || loading || saving || pending || ['running','paused','life'].includes(phase))return;
    if(game)void logClick('replay');
    sounds.stop();void sounds.unlock();
    loading=true;controls();
    try {
      if(!await savePreferences())throw Error('Spillernavnet kunne ikke gemmes. Se beskeden under “Julens top 10”.');
      const data=await request('/profile');
      profile=data.profile;
      if(!preferencesDirty){$('snake-name').value=profile?.display_name||'';$('snake-public').checked=true;}
      let seed;
      if(profile){const started=await request('/rounds',{account_id:profile.account_id,rules_version:3});round={...started,account_id:profile.account_id};seed=started.seed;}
      else{round=null;const random=new Uint32Array(1);crypto.getRandomValues(random);seed=random[0]||1;}
      game=new SnakeGame(seed,round?.rules_version??3);newRecord=false;turns=[];directionQueue=[];phase=dialog.open&&!document.hidden?'running':'paused';
      failedSave=false;message(phase==='running'?'God gavejagt!':'Spillet er på pause. Tryk Fortsæt.');
      if(phase==='running'){sounds.play('start');schedule();}
      if(phase==='running')canvas.focus({preventScroll:true});
    } catch(error){message(error.message||'Spillet kunne ikke starte. Prøv igen.');}
    finally{loading=false;controls();draw();}
  }
  function turn(direction) {
    if(phase!=='running' || directionQueue.length>=2)return;
    // Validate against the previous queued turn, so a quick up/left corner is
    // kept even while travelling right. Never queue a reverse or duplicate.
    const planned=directionQueue.at(-1)??game.direction;
    if(direction===(planned+2)%4 || direction===planned)return;
    directionQueue.push(direction);
  }
  $('snake-open').addEventListener('click',()=>{
    if(!document.dispatchEvent(new Event('jul2026:snake-open',{cancelable:true})))return;
    void logClick('open');
    dialog.showModal();showView('play',false);pause();void loadProfile();void leaderboard();
  });
  $('snake-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{pause();renderer.stop();void savePreferences();});dialog.addEventListener('cancel',pause);
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){pause();renderer.stop();}});
  window.addEventListener('orientationchange',pause);
  $('snake-start').addEventListener('click',start);
  $('snake-retry').addEventListener('click',saveResult);
  $('snake-reload').addEventListener('click',loadProfile);
  $('snake-pause').addEventListener('click',()=>{if(loading)return;if(phase==='running')pause();else if(phase==='paused'||phase==='life'){void sounds.unlock();if(phase==='life'){game.respawn();directionQueue=[];}phase='running';message('God gavejagt!');controls();draw();schedule();canvas.focus({preventScroll:true});}});
  $('snake-sound').addEventListener('click',()=>{$('sound').click();controls();if(sounds.enabled)void sounds.unlock();});
  $('snake-login').addEventListener('click',()=>{dialog.close();$('account-open').click();});
  $('snake-join-top').addEventListener('click',()=>{dialog.close();$('account-open').click();});
  const keyMap={ArrowRight:0,d:0,D:0,ArrowDown:1,s:1,S:1,ArrowLeft:2,a:2,A:2,ArrowUp:3,w:3,W:3};
  document.addEventListener('keydown',event=>{
    if(!dialog.open)return;
    if(['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName))return;
    if(keyMap[event.key]!==undefined){event.preventDefault();if(!event.repeat)turn(keyMap[event.key]);}
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
  async function savePreferences() {
    clearTimeout(preferencesTimer);
    if(!profile||!preferencesDirty)return true;
    if(preferencesPromise){const success=await preferencesPromise;return success&&preferencesDirty?savePreferences():success;}
    const accountId=profile.account_id,name=$('snake-name').value,isPublic=true,status=$('snake-preferences-status');
    status.textContent='Gemmer på din profil …';status.removeAttribute('data-error');$('snake-settings-save').disabled=true;
    preferencesPromise=(async()=>{
      try{
        const data=await request('/profile',{account_id:accountId,display_name:name,is_public:isPublic});
        if(identity(profile)!==accountId)return false;
        profile={...data.profile,best_score:Math.max(profile.best_score,data.profile.best_score)};
        if($('snake-name').value===name&&$('snake-public').checked===isPublic){preferencesDirty=false;$('snake-name').value=profile.display_name;status.textContent='Gemt på din profil. Navnet huskes næste gang.';}
        void leaderboard();return true;
      }catch(error){if(identity(profile)===accountId){status.textContent=error.message||'Kunne ikke gemme. Prøv Gem indstillinger igen.';status.setAttribute('data-error','');}return false;}
      finally{preferencesPromise=null;$('snake-settings-save').disabled=false;controls();}
    })();
    return preferencesPromise;
  }
  $('snake-name').addEventListener('input',()=>{preferencesDirty=true;$('snake-preferences-status').textContent='Ikke gemt endnu …';clearTimeout(preferencesTimer);preferencesTimer=setTimeout(()=>void savePreferences(),600);});
  $('snake-name').addEventListener('change',()=>{preferencesDirty=true;void savePreferences();});
  $('snake-public').addEventListener('change',()=>{$('snake-public').checked=true;});
  $('snake-preferences').addEventListener('submit',event=>{event.preventDefault();preferencesDirty=true;pause();void savePreferences();});
  function showView(view,save=true){
    if(view==='top'){pause();void leaderboard();}else if(save)void savePreferences();
    $('snake-layout').dataset.view=view;$('snake-view-play').setAttribute('aria-pressed',String(view==='play'));$('snake-view-top').setAttribute('aria-pressed',String(view==='top'));dialog.scrollTop=0;
  }
  $('snake-view-play').addEventListener('click',()=>showView('play'));
  $('snake-view-top').addEventListener('click',()=>showView('top'));
  $('snake-top-refresh').addEventListener('click',leaderboard);
  controls();draw();
})();

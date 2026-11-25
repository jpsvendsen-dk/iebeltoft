import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {fakeAudio} from './snake-audio.mjs';
import {setImmediate as nextTurn} from 'node:timers/promises';
import {randomUUID} from 'node:crypto';

export async function runSnakeTests() {
  const core=await readFile(new URL('../static/jul2026/snake-core.js',import.meta.url),'utf8');
  const ui=await readFile(new URL('../static/jul2026/snake.js',import.meta.url),'utf8');
  const rendererSource=(await readFile(new URL('../static/jul2026/snake-renderer.js',import.meta.url),'utf8')).replace(/export /g,'');
  const audioSource=(await readFile(new URL('../static/jul2026/snake-audio.js',import.meta.url),'utf8')).replace(/export /g,'');
  const engineSource=core.replace(/export /g,'');
  const engineContext=vm.createContext({});
  vm.runInContext(engineSource+';globalThis.Game=SnakeGame;',engineContext);
  const {Game}=engineContext;
  const g=new Game(1);
  assert.deepEqual(Array.from(g.food),[12,0]);
  for(let t=1;t<=13;t++)g.step(t===3?3:null);
  assert.equal(g.score,10);assert.equal(g.tick,13);assert(g.over);assert.equal(g.elapsedMs,2080);
  assert.throws(()=>g.step());
  const speed=new Game(1);speed.score=50;assert.equal(speed.interval,150);speed.score=500;assert.equal(speed.interval,80);
  const bonus=new Game(1,2);bonus.score=490;bonus.food=[11,10];bonus.step();assert.equal(bonus.lives,2);
  bonus.food=[12,10];bonus.step();assert.equal(bonus.score,510);assert.equal(bonus.lives,3);
  bonus.food=[13,10];bonus.step();assert.equal(bonus.lives,3);
  const kept=new Game(1,3);
  for(let tick=1;tick<=13;tick++)kept.step(tick===3?3:null);
  assert.equal(kept.body.length,4);kept.respawn();
  assert.deepEqual(Array.from(kept.body,p=>Array.from(p)),[[10,10],[9,10],[8,10],[7,10]]);
  assert.equal(kept.score,10);assert.equal(kept.lives,1);
  for(let length=3;length<400;length++){
    const model=new Game(1,3);model.body=Array.from({length},(_,i)=>[i%20,Math.floor(i/20)]);model.food=[10,10];model.respawn();
    assert.equal(model.body.length,length);assert.equal(new Set(model.body.map(p=>p.join(','))).size,length);
    assert(!model.body.some(([x,y])=>x===11&&y===10));
    assert(!model.body.some(([x,y])=>x===model.food[0]&&y===model.food[1]));
    for(let i=1;i<length;i++)assert.equal(Math.abs(model.body[i][0]-model.body[i-1][0])+Math.abs(model.body[i][1]-model.body[i-1][1]),1);
  }

  function harness(initialProfile=null) {
    const nodes=new Map(),storage=new Map(),calls=[],docEvents={},winEvents={},timers=new Map(),frames=new Map(),headings=[];
    let clock=0;const audio=fakeAudio();
    let profile=initialProfile?{...initialProfile}:null, seq=0, failSave=false, profileFails=false, preferencesFail=false;
    const context2d=new Proxy({rotate:angle=>headings.push(angle)}, {get:(target,key)=>target[key]??(key.startsWith('create')?()=>({addColorStop(){}}):()=>{}),set:(target,key,value)=>(target[key]=value,true)});
    class Element {
      constructor(){this.listeners={};this.children=[];this.open=false;this.width=440;this.height=440;this.value='';this.checked=false;this.tagName='DIV';this.dataset={};this.attrs={};}
      getAttribute(name){return this.attrs[name]??null;}
      setAttribute(name,value){this.attrs[name]=value;}
      removeAttribute(name){delete this.attrs[name];}
      addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
      emit(name,event={}){event.target??=this;event.preventDefault??=()=>{};for(const fn of this.listeners[name]||[])fn(event);}
      click(){this.emit('click',{detail:0});}
      showModal(){this.open=true;}
      close(){this.open=false;this.emit('close');}
      focus(){this.focused=true;}
      setPointerCapture(){}
      getContext(){return context2d;}
      getBoundingClientRect(){return {width:220};}
      querySelectorAll(){return dpad;}
      append(...children){this.children.push(...children);}
      replaceChildren(){this.children=[];}
    }
    const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
    const dpad=[0,1,2,3].map(direction=>{const node=new Element();node.dataset.snakeDirection=String(direction);return node;});
    get('snake-board').tagName='CANVAS';
    get('sound').setAttribute('aria-pressed','true');
    get('sound').addEventListener('click',()=>get('sound').setAttribute('aria-pressed',get('sound').getAttribute('aria-pressed')==='true'?'false':'true'));
    const document={hidden:false,getElementById:get,createElement:()=>new Element(),addEventListener:(name,fn)=>{(docEvents[name]??=[]).push(fn);},dispatchEvent:()=>true};
    const ctx=vm.createContext({document,navigator:{audioSession:{}},window:{AudioContext:audio.AudioContext,devicePixelRatio:2,addEventListener:(name,fn)=>{winEvents[name]=fn;}},performance:{now:()=>clock},requestAnimationFrame:fn=>{frames.set(++seq,fn);return seq;},cancelAnimationFrame:id=>frames.delete(id),Event:class{},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},crypto:{randomUUID,getRandomValues(array){array[0]=1;}},setTimeout:fn=>{timers.set(++seq,fn);return seq;},clearTimeout:id=>timers.delete(id),
      fetch:(url,options={})=>{
        audio.order.push('fetch');
        calls.push({url,options});let data,status=200;
        if(url.endsWith('/events'))data={ok:true};
        else if(url.endsWith('/profile') && !options.method){if(profileFails)throw Error('Offline');data={profile:profile?{...profile}:null};}
        else if(url.endsWith('/profile')){if(preferencesFail)throw Error('Navnet kunne ikke gemmes');const body=JSON.parse(options.body);assert.equal(body.account_id,profile.account_id);profile={...profile,...body};data={profile:{...profile}};}
        else if(url.endsWith('/leaderboard'))data={players:profile?.is_public?[{rank:1,name:profile.display_name,score:profile.best_score}]:[]};
        else if(url.endsWith('/rounds')){assert.equal(JSON.parse(options.body).account_id,profile.account_id);assert.equal(JSON.parse(options.body).rules_version,3);data={seed:1,round_id:'test-round',max_ticks:20000,rules_version:3};}
        else if(url.endsWith('/finish')){
          const body=JSON.parse(options.body);assert.equal(body.account_id,profile.account_id);assert.equal(body.score,undefined);
          if(failSave){status=503;data={detail:'Offline'};}
          else{const verified=new Game(1,3),changes=new Map(body.turns.map(t=>[t.tick,t.direction]));for(let t=1;t<=body.ticks;t++)verified.step(changes.get(t)??null);assert(verified.over);profile.best_score=Math.max(profile.best_score,verified.score);data={score:verified.score,profile:{...profile}};}
        } else throw Error(url);
        return {ok:status===200,status,json:()=>data};
      },
    },{microtaskMode:'afterEvaluate'});
    vm.runInContext(engineSource+'\n'+rendererSource+'\n'+audioSource+'\n'+ui.replace(/^import .*;\s*/gm,''),ctx);
    const drain=()=>{for(let i=0;i<30;i++)vm.runInContext('',ctx);};
    const emit=(map,name,event={})=>{event.preventDefault??=()=>{};for(const fn of map[name]||[])fn(event);drain();};
    return {get,calls,storage,dpad,audio,open(){get('snake-open').click();drain();},start(){get('snake-start').click();drain();},drain,
      async settle(){for(let i=0;i<3;i++){await nextTurn();drain();}},
      tick(){const next=timers.entries().next().value;if(!next)return false;clock+=160;timers.delete(next[0]);next[1]();drain();return true;},
      frame(ms=16){clock+=ms;const next=frames.entries().next().value;if(!next)return false;frames.delete(next[0]);next[1](clock);drain();return true;},
      renderProbe:()=>JSON.parse(vm.runInContext(`JSON.stringify((()=>{
        const r=new SnakeRenderer(document.getElementById('probe')),model=new SnakeGame(1),now=performance.now();
        r.update(model,'running');model.step();r.update(model,'running');
        const x=[0,80,160].map(ms=>r.positions(now+ms)[0][0]);
        r.update(model,'paused');const paused=[0,80,160].map(ms=>r.positions(now+ms)[0][0]);
        r.motion={matches:true};r.update(model,'running');const reduced=r.positions(now)[0][0];r.stop();
        return {x,paused,reduced};
      })())`,ctx)),
      heading:()=>headings.at(-1),
      key(key,target=get('snake-board'),options={}){emit(docEvents,'keydown',{key,target,...options});},
      hidden(){document.hidden=true;emit(docEvents,'visibilitychange');},orient(){winEvents.orientationchange();drain();},
      setProfile:p=>{profile=p;},failSave:value=>{failSave=value;},profileFails:value=>{profileFails=value;},preferencesFail:value=>{preferencesFail=value;},profile:()=>profile};
  }
  const guest=harness();guest.open();guest.audio.order.length=0;guest.start();
  assert.deepEqual(guest.audio.order.slice(0,3),['resume','warmup','fetch']);
  await guest.settle();
  assert.equal(guest.audio.tones.length,10);
  assert.equal(guest.get('snake-board').width,440); // CSS width 220 at device pixel ratio 2.
  assert(guest.frame()); // Rendering runs between simulation ticks.
  guest.key('ArrowLeft'); // Opposite direction must be ignored.
  guest.tick();guest.tick();guest.key('w');
  for(let i=0;i<11;i++)guest.tick();
  assert.equal(guest.get('snake-score').textContent,10);
  assert.equal(guest.get('snake-lives').textContent,1);
  assert.equal(guest.get('snake-pause').textContent,'Brug næste liv');
  assert.equal(guest.storage.get('jul2026-snake-guest-best'),undefined);
  guest.get('snake-pause').click();guest.drain();for(let i=0;i<10;i++)guest.tick();
  assert.equal(guest.get('snake-lives').textContent,0);
  assert.equal(guest.storage.get('jul2026-snake-guest-best'),'10');
  assert.equal(guest.audio.tones.length,20); // Start 10 + gift 4 + lost life 2 + final death 4.
  assert(!guest.calls.some(c=>c.url.endsWith('/rounds')||c.url.endsWith('/finish')));
  assert.deepEqual(guest.renderProbe(),{x:[231,242,253],paused:[231,231,231],reduced:253});
  guest.start();guest.hidden();assert.equal(guest.tick(),false);assert.equal(guest.frame(),false);assert.equal(guest.get('snake-pause').textContent,'Fortsæt');
  assert(guest.audio.stops.length>=20); // Pausing also stops any scheduled sounds.
  assert.deepEqual(guest.calls.filter(c=>c.url.endsWith('/events')).map(c=>JSON.parse(c.options.body).action),['open','replay']);

  const quiet=harness();quiet.open();quiet.get('snake-sound').click();quiet.start();
  assert.equal(quiet.audio.contexts.length,0);assert.equal(quiet.get('sound').getAttribute('aria-pressed'),'false');
  for(let i=0;i<10;i++)quiet.tick();quiet.get('snake-pause').click();quiet.drain();for(let i=0;i<10;i++)quiet.tick();
  assert.equal(quiet.audio.tones.length,0);assert(!quiet.get('snake-start').hidden);

  const fast=harness({account_id:21,best_score:0,display_name:'',is_public:false});fast.open();fast.start();
  fast.key('ArrowUp');fast.key('ArrowLeft'); // Two quick corners before the next simulation step.
  fast.tick();assert.equal(fast.heading(),3*Math.PI/2); // Facing changes at the start, not end, of the tween.
  fast.key('ArrowUp',undefined,{repeat:true}); // Holding the old key must not add an unwanted turn.
  fast.tick();assert.equal(fast.heading(),Math.PI);
  fast.tick();assert.equal(fast.heading(),Math.PI);
  for(let i=0;i<12;i++)fast.tick();
  fast.get('snake-pause').click();fast.drain();for(let i=0;i<10;i++)fast.tick();
  const fastResult=JSON.parse(fast.calls.find(c=>c.url.endsWith('/finish')).options.body);
  assert.deepEqual(fastResult.turns,[{tick:1,direction:3},{tick:2,direction:2}]);

  const pausedInput=harness();pausedInput.open();pausedInput.start();pausedInput.key('ArrowUp');
  pausedInput.get('snake-pause').click();pausedInput.get('snake-pause').click();pausedInput.drain();
  pausedInput.tick();assert.equal(pausedInput.heading(),0); // No old queued input after a pause.

  const user=harness({account_id:5,best_score:0,display_name:'',is_public:false});user.open();user.start();
  user.tick();user.tick();
  user.dpad[3].emit('pointerdown');user.drain();
  user.failSave(true);for(let i=0;i<11;i++)user.tick();
  assert.equal(user.calls.filter(c=>c.url.endsWith('/finish')).length,0);
  user.get('snake-pause').click();user.drain();for(let i=0;i<10;i++)user.tick();
  assert.equal(user.get('snake-retry').hidden,false);assert(user.get('snake-start').disabled);
  user.failSave(false);user.get('snake-retry').click();user.drain();assert.equal(user.profile().best_score,10);
  assert.equal(user.get('snake-retry').hidden,true);assert(!user.get('snake-start').disabled);
  const finishes=user.calls.filter(c=>c.url.endsWith('/finish'));assert.equal(finishes.length,2);assert.equal(finishes[0].options.body,finishes[1].options.body);
  user.get('snake-name').value='Nisse';user.get('snake-public').checked=true;user.get('snake-preferences').emit('submit');user.drain();assert(user.profile().is_public);
  assert.equal(user.get('snake-toplist').children[0].children[0].textContent,'1. Nisse');
  user.get('snake-dialog').close();user.open();assert.equal(user.get('snake-name').value,'Nisse');
  assert(user.get('snake-player-note').textContent.includes('Nisse'));
  user.start();user.get('snake-board').emit('pointerdown',{clientX:50,clientY:50,pointerId:1});
  user.get('snake-board').emit('pointermove',{clientX:50,clientY:20});user.tick();
  user.orient();assert.equal(user.tick(),false);
  user.get('snake-dialog').close();user.open();assert.equal(user.get('snake-pause').textContent,'Fortsæt');
  user.setProfile({account_id:6,best_score:20,display_name:'Anden',is_public:false});user.get('snake-dialog').close();user.open();
  assert.equal(user.get('snake-score').textContent,0);assert.equal(user.get('snake-best').textContent,20);assert(!user.get('snake-start').hidden);
  user.profileFails(true);user.get('snake-dialog').close();user.open();assert(user.get('snake-start').disabled);assert.equal(user.get('snake-reload').hidden,false);

  const nameSave=harness({account_id:31,best_score:0,display_name:'',is_public:false});nameSave.open();nameSave.get('snake-view-top').click();nameSave.drain();
  assert.equal(nameSave.get('snake-layout').dataset.view,'top');
  nameSave.get('snake-name').value='Juleven';nameSave.get('snake-name').emit('input');nameSave.tick();
  assert.equal(nameSave.profile().display_name,'Juleven');assert.equal(nameSave.profile().is_public,true);assert.equal(nameSave.get('snake-public').checked,true);
  assert(nameSave.get('snake-preferences-status').textContent.includes('Gemt'));
  nameSave.get('snake-dialog').close();nameSave.open();assert.equal(nameSave.get('snake-name').value,'Juleven');
  assert.equal(nameSave.get('snake-layout').dataset.view,'play');
  nameSave.get('snake-view-top').click();nameSave.get('snake-public').checked=false;nameSave.get('snake-public').emit('change');nameSave.drain();
  assert.equal(nameSave.profile().is_public,true);assert.equal(nameSave.get('snake-public').checked,true);
  assert(nameSave.get('snake-membership').textContent.includes('Afslut et spil med point'));
  nameSave.get('snake-name').value='Ny Nisse';nameSave.get('snake-name').emit('input');nameSave.get('snake-view-play').click();nameSave.drain();
  assert.equal(nameSave.profile().display_name,'Ny Nisse');
  nameSave.preferencesFail(true);nameSave.get('snake-name').value='Nyt navn';nameSave.get('snake-name').emit('change');nameSave.drain();
  assert.equal(nameSave.profile().display_name,'Ny Nisse');assert.equal(nameSave.get('snake-preferences-status').getAttribute('data-error'),'');
  nameSave.preferencesFail(false);nameSave.get('snake-preferences').emit('submit');nameSave.drain();assert.equal(nameSave.profile().display_name,'Nyt navn');
  const savedRequests=nameSave.calls.filter(c=>c.url.endsWith('/profile')&&c.options.method==='POST');assert(savedRequests.every(c=>c.options.keepalive===true));
  return 'OK: deterministic replay, gift collection, direction controls/swipe, pause/visibility/orientation, guest storage, server-only profile records, automatic named leaderboard, retry and account switching.';
}

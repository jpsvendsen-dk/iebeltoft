import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';

export async function runSnakeTests() {
  const core=await readFile(new URL('../static/jul2026/snake-core.js',import.meta.url),'utf8');
  const ui=await readFile(new URL('../static/jul2026/snake.js',import.meta.url),'utf8');
  const rendererSource=(await readFile(new URL('../static/jul2026/snake-renderer.js',import.meta.url),'utf8')).replace(/export /g,'');
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

  function harness(initialProfile=null) {
    const nodes=new Map(),storage=new Map(),calls=[],docEvents={},winEvents={},timers=new Map(),frames=new Map();
    let clock=0;
    let profile=initialProfile?{...initialProfile}:null, seq=0, failSave=false, profileFails=false;
    const context2d=new Proxy({}, {get:(target,key)=>target[key]??(key.startsWith('create')?()=>({addColorStop(){}}):()=>{}),set:(target,key,value)=>(target[key]=value,true)});
    class Element {
      constructor(){this.listeners={};this.children=[];this.open=false;this.width=440;this.height=440;this.value='';this.checked=false;this.tagName='DIV';this.dataset={};}
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
    const document={hidden:false,getElementById:get,createElement:()=>new Element(),addEventListener:(name,fn)=>{(docEvents[name]??=[]).push(fn);},dispatchEvent:()=>true};
    const ctx=vm.createContext({document,window:{devicePixelRatio:2,addEventListener:(name,fn)=>{winEvents[name]=fn;}},performance:{now:()=>clock},requestAnimationFrame:fn=>{frames.set(++seq,fn);return seq;},cancelAnimationFrame:id=>frames.delete(id),Event:class{},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},crypto:{getRandomValues(array){array[0]=1;}},setTimeout:fn=>{timers.set(++seq,fn);return seq;},clearTimeout:id=>timers.delete(id),
      fetch:(url,options={})=>{
        calls.push({url,options});let data,status=200;
        if(url.endsWith('/profile') && !options.method){if(profileFails)throw Error('Offline');data={profile:profile?{...profile}:null};}
        else if(url.endsWith('/profile')){const body=JSON.parse(options.body);assert.equal(body.account_id,profile.account_id);profile={...profile,...body};data={profile:{...profile}};}
        else if(url.endsWith('/leaderboard'))data={players:profile?.is_public?[{rank:1,name:profile.display_name,score:profile.best_score}]:[]};
        else if(url.endsWith('/rounds')){assert.equal(JSON.parse(options.body).account_id,profile.account_id);data={seed:1,round_id:'test-round',max_ticks:20000};}
        else if(url.endsWith('/finish')){
          const body=JSON.parse(options.body);assert.equal(body.account_id,profile.account_id);assert.equal(body.score,undefined);
          if(failSave){status=503;data={detail:'Offline'};}
          else{const verified=new Game(1),changes=new Map(body.turns.map(t=>[t.tick,t.direction]));for(let t=1;t<=body.ticks;t++)verified.step(changes.get(t)??null);assert(verified.over);profile.best_score=Math.max(profile.best_score,verified.score);data={score:verified.score,profile:{...profile}};}
        } else throw Error(url);
        return {ok:status===200,status,json:()=>data};
      },
    },{microtaskMode:'afterEvaluate'});
    vm.runInContext(engineSource+'\n'+rendererSource+'\n'+ui.replace(/^import .*;\s*/gm,''),ctx);
    const drain=()=>{for(let i=0;i<30;i++)vm.runInContext('',ctx);};
    const emit=(map,name,event={})=>{event.preventDefault??=()=>{};for(const fn of map[name]||[])fn(event);drain();};
    return {get,calls,storage,dpad,open(){get('snake-open').click();drain();},start(){get('snake-start').click();drain();},drain,
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
      key(key,target=get('snake-board')){emit(docEvents,'keydown',{key,target});},
      hidden(){document.hidden=true;emit(docEvents,'visibilitychange');},orient(){winEvents.orientationchange();drain();},
      setProfile:p=>{profile=p;},failSave:value=>{failSave=value;},profileFails:value=>{profileFails=value;},profile:()=>profile};
  }
  const guest=harness();guest.open();guest.start();
  assert.equal(guest.get('snake-board').width,440); // CSS width 220 at device pixel ratio 2.
  assert(guest.frame()); // Rendering runs between simulation ticks.
  guest.key('ArrowLeft'); // Opposite direction must be ignored.
  guest.tick();guest.tick();guest.key('w');
  for(let i=0;i<11;i++)guest.tick();
  assert.equal(guest.get('snake-score').textContent,10);
  assert.equal(guest.storage.get('jul2026-snake-guest-best'),'10');
  assert(!guest.calls.some(c=>c.url.endsWith('/rounds')||c.url.endsWith('/finish')));
  assert.deepEqual(guest.renderProbe(),{x:[231,242,253],paused:[231,231,231],reduced:253});
  guest.start();guest.hidden();assert.equal(guest.tick(),false);assert.equal(guest.frame(),false);assert.equal(guest.get('snake-pause').textContent,'Fortsæt');

  const user=harness({account_id:5,best_score:0,display_name:'',is_public:false});user.open();user.start();
  user.tick();user.tick();
  user.dpad[3].emit('pointerdown');user.drain();
  user.failSave(true);for(let i=0;i<11;i++)user.tick();
  assert.equal(user.get('snake-retry').hidden,false);assert(user.get('snake-start').disabled);
  user.failSave(false);user.get('snake-retry').click();user.drain();assert.equal(user.profile().best_score,10);
  assert.equal(user.get('snake-retry').hidden,true);assert(!user.get('snake-start').disabled);
  const finishes=user.calls.filter(c=>c.url.endsWith('/finish'));assert.equal(finishes.length,2);assert.equal(finishes[0].options.body,finishes[1].options.body);
  user.get('snake-name').value='Nisse';user.get('snake-public').checked=true;user.get('snake-preferences').emit('submit');user.drain();assert(user.profile().is_public);
  assert.equal(user.get('snake-toplist').children[0].children[0].textContent,'1. Nisse');
  user.start();user.get('snake-board').emit('pointerdown',{clientX:50,clientY:50,pointerId:1});
  user.get('snake-board').emit('pointermove',{clientX:50,clientY:20});user.tick();
  user.orient();assert.equal(user.tick(),false);
  user.get('snake-dialog').close();user.open();assert.equal(user.get('snake-pause').textContent,'Fortsæt');
  user.setProfile({account_id:6,best_score:20,display_name:'Anden',is_public:false});user.get('snake-dialog').close();user.open();
  assert.equal(user.get('snake-score').textContent,0);assert.equal(user.get('snake-best').textContent,20);assert(!user.get('snake-start').hidden);
  user.profileFails(true);user.get('snake-dialog').close();user.open();assert(user.get('snake-start').disabled);assert.equal(user.get('snake-reload').hidden,false);
  return 'OK: deterministic replay, gift collection, direction controls/swipe, pause/visibility/orientation, guest storage, server-only profile records, opt-in leaderboard, retry and account switching.';
}

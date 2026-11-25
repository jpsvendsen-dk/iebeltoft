// Run with Node, or import runTests() from the connected Node runtime.
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { setImmediate as nextTurn } from 'node:timers/promises';

export async function runTests() {
  const source = await readFile(new URL('../static/jul2026/calendar.js', import.meta.url), 'utf8');
  new vm.Script(source);
  new vm.Script(await readFile(new URL('../static/jul2026/login.js', import.meta.url), 'utf8'));

  function harness({path='/Jul2026', stored={}, merge=false, account=null, offlineInitial=false, audioState=null, audioBlocked=false, apiAvailable=true}={}) {
    const nodes=new Map(), storage=new Map(Object.entries(stored)), session=new Map(merge ? [['jul2026-merge-guest','yes']] : []);
    const calls=[], audioCalls=[], sources=[], audioSession={}, players=[];
    let current=account, offline=offlineInitial, refresh, dropNextOpen=false;
    class Element {
      constructor() { this.style={setProperty(k,v){this[k]=v;}}; this.dataset={}; this.children=[]; this.classes=new Set(); this.attrs={}; this.listeners={}; this.classList={add:n=>this.classes.add(n),remove:n=>this.classes.delete(n),contains:n=>this.classes.has(n)}; }
      set className(value) { this.classes=new Set(value.split(' ')); }
      setAttribute(k,v) { this.attrs[k]=v; }
      toggleAttribute(k,v) { if(v)this.attrs[k]='';else delete this.attrs[k]; }
      addEventListener(k,f) { this.listeners[k]=f; }
      replaceChildren() { this.children=[]; }
      append(el) { this.children.push(el); }
      querySelector() { return this.back??=new Element(); }
      getBoundingClientRect() { return {width:68,height:86,left:0,top:0,right:68,bottom:86}; }
      showModal() { this.open=true; }
      close() { this.open=false; this.listeners.close?.(); }
    }
    const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
    const storageApi=map=>({getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)});
    class SafariAudio {
      constructor(){this.state=audioState;this.sampleRate=8000;this.destination={};}
      resume(){audioCalls.push('resume');if(!audioBlocked)this.state='running';return{then:resolve=>resolve()};}
      createBuffer(_,length,rate){const samples=new Float32Array(length);return{duration:length/rate,getChannelData:()=>samples};}
      createBufferSource(){const source={connect(){},disconnect(){},start(){audioCalls.push(this.buffer.duration<.01?'warmup':'creak');},stop(){this.stopped=true;this.onended?.();}};sources.push(source);return source;}
      createBiquadFilter(){return{frequency:{},connect(){},disconnect(){}};}
    }
    class YouTubePlayer {
      constructor(frame,options){this.frame=frame;this.events=options.events;this.plays=0;this.pauses=0;players.push(this);}
      unMute(){this.unmuted=true;}
      playVideo(){this.plays++;}
      pauseVideo(){this.pauses++;}
      destroy(){this.destroyed=true;}
    }
    const ctx=vm.createContext({
      document:{getElementById:get,documentElement:new Element(),head:get('document-head'),createElement:()=>new Element(),addEventListener(){}},
      location:{pathname:path,origin:'https://www.iebeltoft.dk',assign(){}},localStorage:storageApi(storage),sessionStorage:storageApi(session),
      crypto:{randomUUID},URL,
      navigator:{audioSession},window:{YT:apiAvailable?{Player:YouTubePlayer}:undefined,AudioContext:audioState?SafariAudio:undefined,matchMedia:()=>({matches:true})},setTimeout:(f,ms)=>{if(ms===0)f();return 1;},clearTimeout(){},setInterval:f=>{refresh=f;},
      fetch:(url,options={})=>{
        audioCalls.push('fetch');
        calls.push({url,options});
        let result, ok=true, status=200;
        if(url.endsWith('/state'))result={available:path.startsWith('/admin/')||current?.early_access?24:8,early_access:Boolean(current?.early_access),preview:path.startsWith('/admin/'),today:'2026-12-08'};
        else if(url.endsWith('/account/opened')){
          const body=JSON.parse(options.body);
          if(offline){ok=false;result={};}
          else{assert.equal(body.account_id,current.id);assert.equal(body.progress_version,current.progress_version||0);current.opened=[...new Set([...current.opened,...body.days])].sort((a,b)=>a-b);result={opened:[...current.opened]};}
        }
        else if(url.endsWith('/account'))result={account:current?{...current,opened:[...current.opened]}:null};
        else if(url.includes('/doors/')){
          assert.equal(options.method,'POST');
          assert(url.endsWith('/open'));
          const body=JSON.parse(options.body),day=Number(url.split('/').at(-2));
          assert.match(body.event_id,/^[0-9a-f-]{36}$/);
          assert.equal(body.progress_version,current?.progress_version||0);
          const allowed=path.startsWith('/admin/')||current?.early_access||day<=8;
          if(!allowed){ok=false;status=403;result={detail:'Lågen er låst.'};}
          else{
            if(current)current.opened=[...new Set([...current.opened,day])].sort((a,b)=>a-b);
            result={title:'Song',artist:'Artist',youtube:'https://www.youtube.com/watch?v=testVideo'+String(day).padStart(2,'0'),animal:'Fox',reflection:`Reflection for day ${day}`};
            if(dropNextOpen){dropNextOpen=false;throw Error('Response lost');}
          }
        }
        else throw Error(`Unexpected request: ${url}`);
        return {ok,status:ok?200:status===403?403:503,json:()=>result};
      },
    },{microtaskMode:'afterEvaluate'});
    new vm.Script(source).runInContext(ctx);
    const drain=()=>{for(let i=0;i<20;i++)vm.runInContext('',ctx);};
    drain();
    return {get,storage,calls,drain,players,readyVideo:()=>{const p=players.at(-1);p.events.onReady({target:p});drain();},settle:async()=>{for(let i=0;i<4;i++){await nextTurn();drain();}},audioCalls,sources,audioSession,refresh:()=>{refresh();drain();},setAccount:a=>{current=a;},offline:v=>{offline=v;},loseResponse:()=>{dropNextOpen=true;},days:()=>current?.opened,door:day=>get('calendar').children.find(e=>e.dataset.day===day)};
  }

  const a=harness({stored:{'jul2026-opened':'[1,2]'},merge:true,account:{id:1,email:'a@example.com',opened:[3]}});
  assert.deepEqual(a.days(),[1,2,3]);
  assert.equal(a.storage.has('jul2026-opened'),false);
  for(const day of [1,2,3])assert(a.door(day).classList.contains('opened'));
  a.door(7).listeners.click();a.drain();
  assert(a.door(7).classList.contains('opened'));
  assert(JSON.parse(a.storage.get('jul2026-account-1')).includes(7));
  const pending=harness({stored:{'jul2026-account-9':'[7]'},account:{id:9,email:'pending@example.com',opened:[]},offlineInitial:true});
  assert(pending.get('account-status').textContent.includes('venter'));
  pending.offline(false);pending.refresh();assert(pending.days().includes(7));
  a.setAccount({id:1,email:'a@example.com',opened:[1,2,3,7,8]});a.refresh();assert(a.door(8).classList.contains('opened'));
  a.setAccount({id:2,email:'b@example.com',opened:[4]});a.refresh();
  assert(a.door(4).classList.contains('opened'));assert(!a.door(1).classList.contains('opened'));assert(!a.door(7).classList.contains('opened'));
  a.setAccount(null);a.refresh();assert(!a.door(4).classList.contains('opened'));assert.equal(a.get('account-open').textContent,'Gem min kalender');

  const reset=harness({stored:{'jul2026-account-11':'[2,3]'},account:{id:11,email:'reset@example.com',opened:[2,3]}});
  reset.door(4).listeners.click();reset.drain();assert(reset.get('surprise').open);
  reset.setAccount({id:11,email:'reset@example.com',progress_version:1,opened:[]});reset.refresh();
  for(const day of [2,3,4])assert(!reset.door(day).classList.contains('opened'));
  assert.equal(reset.get('surprise').open,false);assert.deepEqual(reset.days(),[]);
  reset.door(5).listeners.click();reset.drain();assert.deepEqual(reset.days(),[5]);
  assert.deepEqual(JSON.parse(reset.storage.get('jul2026-account-11-v1')),[5]);
  const resetLogin=harness({merge:true,stored:{'jul2026-account-11':'[2,3]','jul2026-opened':'[1,4]'},account:{id:11,email:'reset@example.com',progress_version:2,opened:[]}});
  assert.deepEqual(resetLogin.days(),[]);assert.equal(resetLogin.storage.has('jul2026-opened'),false);

  const clicks=harness({account:{id:7,email:'click@example.com',opened:[]}});
  clicks.door(24).listeners.click();clicks.drain();
  assert(clicks.calls.some(c=>c.url.endsWith('/doors/24/open')));assert(!clicks.door(24).classList.contains('opened'));
  clicks.setAccount({id:7,email:'click@example.com',opened:[],early_access:true});clicks.refresh();
  clicks.door(24).listeners.click();clicks.drain();assert(clicks.door(24).classList.contains('opened'));
  clicks.setAccount({id:7,email:'click@example.com',opened:[24],early_access:false});clicks.refresh();
  assert(clicks.door(24).classList.contains('opened'));assert.equal(clicks.door(24).attrs['aria-disabled'],'true');assert(JSON.parse(clicks.storage.get('jul2026-account-7')).includes(24));
  clicks.loseResponse();clicks.door(2).listeners.click();clicks.drain();
  const retries=clicks.calls.filter(c=>c.url.endsWith('/doors/2/open'));
  assert.equal(retries.length,2);assert.equal(retries[0].options.body,retries[1].options.body);
  clicks.door(2).listeners.click();clicks.drain();
  const repeat=clicks.calls.filter(c=>c.url.endsWith('/doors/2/open'));
  assert.notEqual(JSON.parse(repeat[1].options.body).event_id,JSON.parse(repeat[2].options.body).event_id);

  const guest=harness();
  for(let day=1;day<=24;day++)assert(guest.door(day).innerHTML.includes('<span class="door-back"></span>')); // No rear star can bleed through Safari's 3D layers.
  guest.door(2).listeners.click();guest.drain();assert.deepEqual(JSON.parse(guest.storage.get('jul2026-opened')),[2]);assert(!guest.calls.some(c=>c.url.endsWith('/account/opened')));
  const preview=harness({path:'/admin/jul2026'});preview.door(24).listeners.click();preview.drain();assert.deepEqual(JSON.parse(preview.storage.get('jul2026-preview-opened')),[24]);assert(!preview.calls.some(c=>c.url.includes('/account')));assert(preview.get('account-open').hidden);

  const media=harness();media.door(2).listeners.click();media.drain();
  assert.equal(media.get('door-reflection').textContent,'Reflection for day 2');
  assert.equal(media.get('animal-art').hidden,false);
  assert.equal(media.get('play-inline').disabled,true); // Wait for a ready player, not an autoplay iframe.
  const frame=media.get('video-container').children[0];
  assert.equal(frame.src,'https://www.youtube-nocookie.com/embed/testVideo02?enablejsapi=1&autoplay=0&playsinline=1&rel=0&hl=da&origin=https%3A%2F%2Fwww.iebeltoft.dk');
  assert.equal(frame.referrerPolicy,'strict-origin-when-cross-origin');
  assert(frame.allow.includes('autoplay') && frame.allowFullscreen);
  assert.equal(media.players[0].plays,0);
  media.readyVideo();assert.equal(media.get('play-inline').disabled,false);
  media.get('play-inline').listeners.click();
  assert.equal(media.players[0].plays,1); // Synchronous: no await/network between tap and playVideo.
  assert.equal(media.get('door-reflection').textContent,'Reflection for day 2');
  assert.equal(media.get('video-container').children[0],frame);
  assert.equal(media.get('animal-art').hidden,true);
  assert.equal(media.get('play-inline').attrs['aria-pressed'],'true');
  media.get('play-inline').listeners.click();
  assert.equal(media.get('video-container').children.length,1);
  assert.equal(media.players[0].pauses,1);
  assert.equal(media.get('animal-art').hidden,false);
  media.get('play-inline').listeners.click();media.get('surprise-close').onclick();
  assert.equal(media.get('video-container').children.length,0);assert.equal(media.get('surprise').open,false);
  assert(media.players[0].destroyed);
  media.players[0].events.onReady({target:media.players[0]}); // A late callback must not revive a closed popup.
  media.door(3).listeners.click();media.drain();
  assert.equal(media.get('door-reflection').textContent,'Reflection for day 3');
  assert.equal(media.get('animal-art').hidden,false);assert.equal(media.players[1].plays,0);
  media.readyVideo();
  media.get('play-inline').listeners.click();assert(media.get('video-container').children[0].src.includes('/testVideo03?'));
  media.players[1].events.onAutoplayBlocked();assert(media.get('video-help').textContent.includes('browser'));
  media.get('surprise').listeners.cancel();media.get('surprise').close();
  assert.equal(media.get('video-container').children.length,0);
  media.door(2).listeners.click();media.drain();media.readyVideo();media.get('play-inline').listeners.click();media.get('youtube').listeners.click();
  assert.equal(media.get('video-container').children.length,0);assert.equal(media.get('surprise').open,false);
  assert.equal(media.get('youtube').href,'https://www.youtube.com/watch?v=testVideo02');
  assert(media.door(2).classList.contains('opened'));
  assert.equal(media.get('surprise-media').style['--photo-aspect'],'68 / 86');
  assert.equal(media.get('animal-art').innerHTML,media.door(2).back.innerHTML);
  assert(media.get('animal-art').innerHTML.includes('viewBox="256 0 256 256" preserveAspectRatio="xMidYMid slice"'));
  const apiFailure=harness({apiAvailable:false});apiFailure.door(1).listeners.click();apiFailure.drain();
  apiFailure.get('document-head').children[0].onerror();apiFailure.drain();await apiFailure.settle();
  assert(apiFailure.get('play-inline').disabled);assert.equal(apiFailure.get('animal-art').hidden,false);
  assert(apiFailure.get('video-help').textContent.includes('YouTube'));

  for(const state of ['suspended','interrupted']){
    const iphone=harness({audioState:state});
    iphone.audioCalls.length=0;
    iphone.door(2).listeners.click();
    assert.deepEqual(iphone.audioCalls.slice(0,3),['resume','warmup','fetch']);
    iphone.drain(); await iphone.settle();
    assert.equal(iphone.audioSession.type,'playback');
    assert(iphone.audioCalls.includes('creak'), JSON.stringify({state,calls:iphone.audioCalls,notice:iphone.get('toast').textContent,buffers:iphone.sources.map(s=>s.buffer?.duration)})); // Reduced motion must not mute audio.
    const recording=iphone.sources.find(s=>s.buffer.duration>1);
    assert.equal(recording.buffer.duration,4.8);
    const samples=recording.buffer.getChannelData(0);
    assert(samples.every(Number.isFinite));assert(Math.max(...samples)<1);assert(Math.max(...samples)>.2);
    iphone.door(2).listeners.click();iphone.drain();await iphone.settle();
    assert.equal(iphone.sources.filter(s=>s.buffer.duration>1).length,2); // Reopened doors also creak.
    assert(recording.stopped);
    iphone.get('sound').listeners.click();
    const plays=iphone.audioCalls.filter(s=>s==='creak').length;
    iphone.door(3).listeners.click();iphone.drain();await iphone.settle();
    assert.equal(iphone.audioCalls.filter(s=>s==='creak').length,plays);
    iphone.get('sound-test').listeners.click();iphone.drain();await iphone.settle();
    assert.equal(iphone.audioCalls.filter(s=>s==='creak').length,plays+1);
    assert.equal(iphone.storage.get('jul2026-sound'),'on');
    for(let day=1;day<=24;day++)assert(iphone.door(day).innerHTML.includes(`<span class="flap"><span class="door-decoration">✧</span><span class="door-number">${day}</span>`));
  }
  const blocked=harness({audioState:'interrupted',audioBlocked:true});blocked.door(1).listeners.click();blocked.drain();await blocked.settle();
  assert(blocked.door(1).classList.contains('opened')); // Failed sound cannot block the door.
  assert.equal(blocked.sources.filter(s=>s.buffer.duration>1).length,0);
  assert(blocked.get('toast').textContent.includes('lågelyden'));

  const loginSource=await readFile(new URL('../static/jul2026/login.js', import.meta.url),'utf8');
  const loginButton={addEventListener(_,fn){this.click=fn;}}, loginStatus={}, loginCalls=[];
  let cleaned=false, destination;
  const loginStorage=new Map();
  const ctx=vm.createContext({
    URLSearchParams,location:{hash:'#token='+'a'.repeat(43),replace:url=>{destination=url;}},
    history:{replaceState(){cleaned=true;}},document:{getElementById:id=>id==='confirm-login'?loginButton:loginStatus},
    sessionStorage:{setItem:(k,v)=>loginStorage.set(k,v)},
    fetch:(url,options={})=>{assert(cleaned);loginCalls.push({url,options});return{ok:true,json:()=>url.endsWith('/account')?{account:{id:1}}:{ok:true}};},
  },{microtaskMode:'afterEvaluate'});
  new vm.Script(loginSource).runInContext(ctx);
  assert(cleaned);assert.equal(loginCalls.length,0); // Mail scanners cannot consume a link with GET.
  loginButton.click();vm.runInContext('',ctx);
  assert.equal(loginCalls[0].url,'/Jul2026/api/login/consume');
  assert.equal(JSON.parse(loginCalls[0].options.body).token,'a'.repeat(43));
  assert.equal(loginStorage.get('jul2026-merge-guest'),'yes');assert.equal(destination,'/Jul2026');
  return 'OK: ready-before-tap YouTube playback, synchronous play command, no autoplay on open, pause/destroy and stale callbacks, blocked-player fallback, identical proportional photo crop, mobile audio and account/history flows.';
}

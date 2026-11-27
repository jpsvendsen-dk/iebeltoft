import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';

export async function runElfTests(){
  const base=new URL('../static/jul2026/',import.meta.url);
  const map=JSON.parse(await readFile(new URL('elf-feliz-navidad-v1.json',base),'utf8'));
  const parts=JSON.parse(await readFile(new URL('elf-atlas-v1.json',base),'utf8'));
  const sources=await Promise.all(['elf-motion.js','elf-renderer.js','elf-dancer.js'].map(name=>readFile(new URL(name,base),'utf8')));
  class Element{
    constructor(){this.listeners={};this.hidden=true;this.attrs={};this.classes=new Set();this.classList={add:n=>this.classes.add(n),remove:n=>this.classes.delete(n)};}
    addEventListener(name,callback){this.listeners[name]=callback;}
    removeEventListener(name){delete this.listeners[name];}
    setAttribute(name,value){this.attrs[name]=value;}
  }
  let wall=0,time=0,rate=1,visible=true,playerState=5,draws=0,id=0;
  const frames=new Map(),stage=new Element(),toggle=new Element(),note=new Element(),popup=new Element(),doc=new Element(),reduced=new Element();
  reduced.matches=false;doc.hidden=false;
  const context=new Proxy({},{get:(_,name)=>name==='drawImage'?()=>draws++:()=>{},set:()=>true});
  const canvas={getContext:()=>context};
  stage.querySelector=selector=>selector==='canvas'?canvas:selector==='.elf-toggle'?toggle:note;stage.closest=()=>popup;
  const player={getCurrentTime:()=>time,getPlaybackRate:()=>rate,getPlayerState:()=>playerState};
  const sandbox=vm.createContext({Math,Number,Promise,Image:class{set src(value){this.url=value;queueMicrotask(()=>this.onload());}},fetch:async url=>({ok:true,json:async()=>url.includes('atlas')?parts:map}),document:doc,matchMedia:()=>reduced,performance:{now:()=>wall},requestAnimationFrame:callback=>{frames.set(++id,callback);return id;},cancelAnimationFrame:key=>frames.delete(key),stage,player,isVisible:()=>visible});
  for(const source of sources)vm.runInContext(source.replace(/^import .*;\n/gm,'').replace(/\bexport /g,''),sandbox);
  const dancer=await vm.runInContext('createDancer(stage,{getPlayer:()=>player,isVisible})',sandbox);
  const tick=()=>{wall+=16.667;time+=.016667*rate;const batch=[...frames.values()];frames.clear();batch.forEach(callback=>callback(wall));};
  assert.equal(stage.hidden,true);assert.equal(frames.size,0);
  playerState=1;dancer.playerState(1);assert.equal(stage.hidden,false);assert.equal(frames.size,1);
  for(let i=0;i<100;i++)tick();assert(draws>100);
  dancer.playerState(2);assert.equal(frames.size,0);const paused=draws;wall+=5000;assert.equal(draws,paused);
  time=60;dancer.playerState(1);tick();assert.equal(frames.size,1);
  rate=1.5;dancer.refresh();tick();
  dancer.playerState(3);assert.equal(frames.size,0);
  dancer.playerState(1);toggle.listeners.click();assert.equal(frames.size,0);assert.equal(toggle.attrs['aria-pressed'],'true');
  toggle.listeners.click();assert.equal(frames.size,1);
  doc.hidden=true;doc.listeners.visibilitychange();assert.equal(frames.size,0);
  doc.hidden=false;doc.listeners.visibilitychange();assert.equal(frames.size,1);
  reduced.matches=true;reduced.listeners.change();assert.equal(frames.size,0);assert.equal(toggle.disabled,true);
  reduced.matches=false;reduced.listeners.change();assert.equal(frames.size,1);
  dancer.playerState(0);assert.equal(stage.hidden,true);assert.equal(frames.size,0);
  dancer.dispose();dancer.playerState(1);assert.equal(stage.hidden,true);assert.equal(frames.size,0);
  assert.equal(Object.keys(doc.listeners).length,0);
  sandbox.map=map;
  const before=vm.runInContext('poseAt(10,map)',sandbox),after=vm.runInContext('poseAt(10,map)',sandbox);
  assert.deepEqual(before,after);
  for(let t=0;t<183;t+=.13){const pose=vm.runInContext(`poseAt(${t},map)`,sandbox);for(const value of Object.values(pose))if(typeof value==='number')assert(Number.isFinite(value));}
  const clock=vm.runInContext('new PlayerClock()',sandbox);clock.sample(50,1000,2);clock.playing=true;assert.equal(clock.current(1100),50.2);clock.sample(10,1200,1);assert.equal(clock.current(1200),10);clock.sample(NaN,1300);assert.equal(clock.current(1300),null);
  assert.equal(vm.runInContext('beatAt(-1,map)',sandbox),null);
  assert.equal(vm.runInContext('beatAt(183,map)',sandbox),null);
  sandbox.restMap={...map,rests:[{start:2,end:3}]};assert.equal(vm.runInContext('beatAt(2.5,restMap)',sandbox),null);
  assert.equal(parts.parts.length,16);
  return 'OK: deterministic poses, video clock/seek/rate, play/pause/buffering/end, manual stop, reduced motion, visibility, disposal and finite joint positions throughout the song.';
}

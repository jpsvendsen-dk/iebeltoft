import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {setImmediate as nextTurn} from 'node:timers/promises';

export function fakeAudio({blocked=false}={}) {
  const order=[],tones=[],stops=[],contexts=[];
  const param=()=>({value:0,setValueAtTime(value){this.value=value;},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}});
  class AudioContext {
    constructor(){this.state='suspended';this.currentTime=0;this.sampleRate=44100;this.destination={};contexts.push(this);}
    resume(){order.push('resume');if(!blocked)this.state='running';return{then:resolve=>resolve()};}
    createGain(){return{gain:param(),connect(){},disconnect(){}};}
    createBuffer(){return{};}
    createBufferSource(){return{connect(){},disconnect(){},start(){order.push('warmup');}};}
    createOscillator(){return{frequency:param(),connect(){},disconnect(){},start(at){tones.push({frequency:this.frequency.value,type:this.type,at});},stop(at){if(at===undefined){stops.push(this);this.onended?.();}}};}
  }
  return {AudioContext,order,tones,stops,contexts};
}

export async function runSnakeAudioTests() {
  const source=(await readFile(new URL('../static/jul2026/snake-audio.js',import.meta.url),'utf8')).replace(/export /g,'');
  function harness(options={}) {
    const audio=fakeAudio(options),navigator={audioSession:{}};
    const ctx=vm.createContext({window:{webkitAudioContext:audio.AudioContext},navigator},{microtaskMode:'afterEvaluate'});
    vm.runInContext(source+';globalThis.audio=new SnakeAudio();',ctx);
    const run=async code=>{vm.runInContext(code,ctx);for(let pass=0;pass<3;pass++){await nextTurn();for(let i=0;i<20;i++)vm.runInContext('',ctx);}};
    return{...audio,navigator,run};
  }
  const bell=harness();await bell.run('audio.unlock();audio.play("start");');
  assert.deepEqual(bell.order,['resume','warmup']);assert.equal(bell.navigator.audioSession.type,'playback');
  assert.equal(bell.tones.length,10);assert(bell.tones.every(t=>t.type==='sine'&&Number.isFinite(t.frequency)&&t.frequency>0));
  await bell.run('audio.play("gift");');assert.equal(bell.tones.length,14);
  await bell.run('audio.play("over");');assert.equal(bell.tones.length,18);
  assert(bell.tones.slice(-4).every(t=>t.type==='square'));
  assert.deepEqual(bell.tones.slice(-4).map(t=>t.frequency),[329.63,261.63,196,130.81]);
  assert.equal(bell.stops.length,14); // Death cancels the fanfare and gift tails.
  await bell.run('audio.setEnabled(false);audio.play("gift");');assert.equal(bell.tones.length,18);
  assert.equal(bell.stops.length,18);
  await bell.run('audio.setEnabled(true);audio.unlock();audio.play("gift");');assert.equal(bell.contexts.length,1);assert.equal(bell.tones.length,22);
  const late=harness();await late.run('audio.unlock();audio.play("start");audio.stop();');assert.equal(late.tones.length,0);
  const blocked=harness({blocked:true});await blocked.run('audio.unlock();audio.play("start");audio.play("gift");audio.play("over");');assert.equal(blocked.tones.length,0);
  const muted=harness();await muted.run('audio.setEnabled(false);audio.unlock();audio.play("start");');assert.equal(muted.contexts.length,0);
  return 'OK: Safari gesture warm-up, bell fanfare, gift ping, descending arcade ending, mute/cancellation, blocked-audio fallback and context reuse.';
}

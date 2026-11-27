import test from 'node:test';
import assert from 'node:assert/strict';
import {SongClock,DanceSynchronizer,phaseError} from '../static/jul2026/dance-v2/playback-sync.js';

export function checkClock(){
  const clock=new SongClock();
  let previous=0;
  // Stale and slightly backward reports must not repeatedly rewind the dancer.
  for(let now=0;now<2500;now+=25){
    if(now%150===0){const report=Math.max(0,Math.floor(now/200)*.2-(now%300===0?.04:0));clock.observe(report,now,1,true);}
    const time=clock.sample(now,true);
    assert.ok(time>=previous,`clock rewound at ${now}`);previous=time;
  }
  const stalled=new SongClock();stalled.observe(0,0,1,true);
  stalled.observe(0,140,1,true);
  assert.equal(stalled.sample(200,true),.2);
  assert.equal(stalled.sample(2000,true),.25);
  // An explicit restart must ignore the old YouTube position until acknowledged.
  clock.seek(0,3000);clock.observe(15,3020,1,true);
  assert.equal(clock.sample(3040,true),0);
  clock.observe(0,3100,1,true);assert.equal(clock.sample(3150,true),.05);
  clock.observe(8,3200,1,false);assert.equal(clock.sample(5000,false),8);
  clock.observe(2,5100,1,true);assert.equal(clock.sample(5100,true),2);
}
function fakeVideo(){
  return {_time:0,seeks:0,plays:0,pauses:0,paused:true,seeking:false,readyState:4,duration:8.125,playbackRate:1,
    get currentTime(){return this._time;},set currentTime(value){this._time=value;this.seeking=true;this.seeks++;},
    play(){this.paused=false;this.plays++;return Promise.resolve();},pause(){this.paused=true;this.pauses++;}};
}
export function checkDecoderStartup(){
  const video=fakeVideo(),sync=new DanceSynchronizer(video);
  const intro={time:3.4,rate:1,active:false};
  sync.update(intro,{playing:true,now:0});assert.equal(video.seeks,1);
  for(let now=50;now<1000;now+=50)sync.update(intro,{playing:true,now});
  assert.equal(video.seeks,1,'do not restart an unfinished decoder seek');
  assert.equal(video.plays,0,'intro stays still');
  video.seeking=false;
  sync.update(intro,{playing:true,now:1000});assert.equal(video.seeks,1);
  sync.update({time:3.42,rate:1,active:true},{playing:true,now:1050});
  assert.equal(video.seeks,1);assert.equal(video.plays,1);
  sync.pause();assert.equal(video.paused,true);
}
export function checkGentleCorrection(){
  const video=fakeVideo(),sync=new DanceSynchronizer(video);
  sync.align=false;video._time=1;
  for(let now=0;now<3000;now+=50){
    const target=(1.2+now/1000)%video.duration;
    sync.update({time:target,rate:1,active:true},{playing:true,now});
    video._time=(video._time+.05*video.playbackRate)%video.duration;
  }
  assert.equal(video.seeks,0,'small clock drift must not cause visible jumps');
  assert.ok(video.playbackRate>.94&&video.playbackRate<1.07);
  video._time=8.11;
  assert.ok(Math.abs(phaseError(.02,video.currentTime,video.duration))<.04);
  sync.update({time:.02,rate:1,active:true},{playing:true,now:3100});
  assert.equal(video.seeks,0,'normal loop boundary is not a large drift');
  sync.requestAlignment();
  sync.update({time:4,rate:1,active:true},{playing:true,now:3200});
  assert.equal(video.seeks,1,'intentional seeking still works');
  sync.update({time:4.05,rate:1,active:true},{playing:true,now:3250});
  assert.equal(video.seeks,1);
}
test('YouTube clock remains steady during stale startup reports',checkClock);
test('decoder aligns once and waits for the first seek',checkDecoderStartup);
test('small drift and loop boundaries use smooth speed correction',checkGentleCorrection);

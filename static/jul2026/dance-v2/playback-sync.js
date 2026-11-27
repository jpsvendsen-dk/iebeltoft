// YouTube may repeat or slightly revise its time while starting/buffering.
// Never turn those stale measurements into backward motion during normal play.
export class SongClock {
  constructor(){this.time=0;this.wall=0;this.rate=1;this.report=null;this.output=0;this.pending=null;}
  seek(time,now){this.time=time;this.wall=now;this.output=time;this.report=null;this.pending={time,until:now+1800};}
  observe(time,now,rate,playing){
    if(!Number.isFinite(time)||time<0)return;
    this.rate=Number.isFinite(rate)&&rate>0?rate:1;
    if(this.pending){
      if(Math.abs(time-this.pending.time)>.35&&now<this.pending.until)return;
      this.pending=null;this.output=time;this.report=null;
    }
    const backwardSeek=this.report!==null&&time<this.report-.5;
    if(!playing||backwardSeek){this.time=time;this.wall=now;this.output=time;this.report=time;return;}
    if(this.report===null||Math.abs(time-this.report)>.005){
      this.time=time;this.wall=now;this.report=time;
    }
  }
  sample(now,playing){
    if(this.pending)return this.pending.time;
    if(!playing)return this.time;
    const elapsed=Math.max(0,now-this.wall)/1000;
    const predicted=this.time+Math.min(elapsed,.25)*this.rate;
    this.output=Math.max(this.output,predicted);
    return this.output;
  }
}

export function phaseError(target,actual,duration){
  const error=target-actual;
  return Number.isFinite(duration)&&duration>0?((error+duration/2)%duration+duration)%duration-duration/2:error;
}

// Let the decoder play continuously; use gentle speed correction for small
// drift. Seeking on every timer tick is especially disruptive at video startup.
export class DanceSynchronizer {
  constructor(video,onBlocked=()=>{}){
    this.video=video;this.onBlocked=onBlocked;this.align=true;
    this.lastSeek=-Infinity;this.waitingForSeek=false;this.pendingPlay=false;this.blocked=false;this.shouldPlay=false;
  }
  requestAlignment(){this.align=true;this.blocked=false;}
  pause(){this.shouldPlay=false;if(!this.video.paused)this.video.pause();}
  update(clip,{playing,masterRate=1,now}){
    const video=this.video;
    this.shouldPlay=Boolean(playing&&clip.active);
    if(!this.shouldPlay)this.pause();
    // Allow an outstanding decoder seek to finish before another correction.
    if(video.seeking){this.waitingForSeek=true;return;}
    if(video.readyState<2)return;
    if(this.waitingForSeek){this.waitingForSeek=false;this.lastSeek=now;}
    const error=phaseError(clip.time,video.currentTime,video.duration);
    if(!this.shouldPlay){
      if(Math.abs(error)>.025&&now-this.lastSeek>250){video.currentTime=clip.time;this.lastSeek=now;this.waitingForSeek=true;}
      return;
    }
    const base=Math.max(.0625,Math.min(4,clip.rate*masterRate));
    const force=this.align;
    this.align=false;
    if((force&&Math.abs(error)>.035)||(Math.abs(error)>.45&&now-this.lastSeek>750)){
      video.currentTime=clip.time;video.playbackRate=base;this.lastSeek=now;this.waitingForSeek=true;return;
    }
    const correction=Math.max(-.06,Math.min(.06,error*.18));
    const wanted=Math.max(.0625,Math.min(4,base*(1+correction)));
    const rate=force?base:video.playbackRate+(wanted-video.playbackRate)*.2;
    if(Math.abs(rate-video.playbackRate)>.004)video.playbackRate=rate;
    if(video.paused&&!this.pendingPlay&&!this.blocked){
      this.pendingPlay=true;
      Promise.resolve(video.play()).catch(()=>{this.blocked=true;this.onBlocked();}).finally(()=>{
        this.pendingPlay=false;if(!this.shouldPlay)this.pause();
      });
    }
  }
}

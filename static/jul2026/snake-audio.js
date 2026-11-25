// Short original cues. No downloads, music loops or blocking game timers.
export class SnakeAudio {
  constructor() {
    this.enabled=true;this.context=null;this.ready=Promise.resolve(false);
    this.voices=new Set();this.generation=0;
  }
  setEnabled(enabled) {if(this.enabled===enabled)return;this.enabled=enabled;if(!enabled)this.stop();}
  unlock() {
    if(!this.enabled)return Promise.resolve(false);
    try {
      const Audio=window.AudioContext||window.webkitAudioContext;
      if(!Audio)return Promise.resolve(false);
      try{if(navigator.audioSession)navigator.audioSession.type='playback';}catch(_){}
      if(!this.context||this.context.state==='closed'){
        this.context=new Audio();this.master=this.context.createGain();
        this.master.gain.value=.32;this.master.connect(this.context.destination);
      }
      const c=this.context;
      // Both operations happen inside the original Start/Resume tap, before fetch.
      const resumed=c.state==='running'?Promise.resolve():c.resume();
      const warmup=c.createBufferSource();warmup.buffer=c.createBuffer(1,1,c.sampleRate);
      warmup.connect(c.destination);warmup.onended=()=>warmup.disconnect();warmup.start(0);
      this.ready=Promise.resolve(resumed).then(()=>c.state==='running',()=>false);
    }catch(_){this.ready=Promise.resolve(false);}
    return this.ready;
  }
  stop() {
    this.generation++;
    for(const voice of this.voices){
      try{voice.oscillator.stop();}catch(_){}
      voice.oscillator.disconnect();voice.gain.disconnect();
    }
    this.voices.clear();
  }
  note(frequency,offset,duration,type,volume,slide=null) {
    const c=this.context,at=c.currentTime+.008+offset,oscillator=c.createOscillator(),gain=c.createGain();
    oscillator.type=type;oscillator.frequency.setValueAtTime(frequency,at);
    if(slide)oscillator.frequency.exponentialRampToValueAtTime(slide,at+duration);
    gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(volume,at+.008);
    gain.gain.exponentialRampToValueAtTime(.0001,at+duration);
    oscillator.connect(gain);gain.connect(this.master);
    const voice={oscillator,gain};this.voices.add(voice);
    oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();this.voices.delete(voice);};
    oscillator.start(at);oscillator.stop(at+duration+.02);
  }
  play(kind) {
    if(!this.enabled)return;
    if(kind==='start'||kind==='over'||kind==='life')this.stop();
    const generation=this.generation;
    void this.ready.then(ready=>{
      if(!ready||!this.enabled||generation!==this.generation||this.context?.state!=='running')return;
      try{
        const bell=(frequency,offset,duration=.24)=>{
          this.note(frequency,offset,duration,'sine',.3);
          this.note(frequency*2.01,offset,duration*.55,'sine',.065);
        };
        if(kind==='start'){
          // A small major-key holiday flourish, under one second long.
          for(const [frequency,offset,duration] of [[784,0,.2],[1046.5,.12,.2],[1318.5,.24,.2],[1568,.36,.32],[1046.5,.6,.28]])bell(frequency,offset,duration);
        }else if(kind==='gift'){
          bell(1318.5,0,.13);bell(1760,.065,.16);
        }else if(kind==='life'){
          this.note(392,0,.13,'triangle',.16);this.note(293.66,.12,.2,'triangle',.16);
        }else if(kind==='over'){
          // Soft square-wave arcade cadence with a downward final pitch bend.
          for(const [frequency,offset,duration] of [[329.63,0,.15],[261.63,.16,.15],[196,.32,.15],[130.81,.48,.36]])this.note(frequency,offset,duration,'square',.11,offset===.48?65.41:null);
        }
      }catch(_){/* Sound must never interrupt play or score saving. */}
    });
  }
}

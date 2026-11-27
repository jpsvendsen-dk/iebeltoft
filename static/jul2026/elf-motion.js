// Pure, time-addressable choreography. No wall-clock accumulation or random steps.
export const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
export function beatAt(time, map) {
  if (!Number.isFinite(time)) return null;
  const anchors = map.anchors;
  if (time < anchors[0].time || time >= map.end || map.rests.some(r => time >= r.start && time < r.end)) return null;
  let i = 0;
  while (i < anchors.length - 2 && time >= anchors[i + 1].time) i++;
  const a = anchors[i], b = anchors[i + 1];
  return a.beat + (time - a.time) * (b.beat - a.beat) / (b.time - a.time);
}
export function poseAt(time, map) {
  const beat = beatAt(time, map);
  if (beat === null) return {move:'idle', x:0, lift:0, lean:0, leftArm:.15, rightArm:-.15, leftElbow:.08, rightElbow:-.08, leftFoot:[-12,0], rightFoot:[12,0], turn:1, hair:0, blink:1};
  const moves = ['step','sway','wave','clap','hop','twirl'];
  const move = moves[Math.floor(beat / 16) % moves.length];
  const cycle = Math.sin(beat * Math.PI), pulse = Math.sin(beat * Math.PI * 2), bounce = Math.pow(Math.max(0, Math.sin(beat * Math.PI * 2)), 2);
  const p = {move, x:cycle*5, lift:bounce*1.6, lean:cycle*.035, leftArm:.18+cycle*.16, rightArm:-.18+cycle*.16, leftElbow:.12, rightElbow:-.12, leftFoot:[-12,0], rightFoot:[12,0], turn:1, hair:Math.sin(beat*Math.PI-.4)*.06, blink:(beat%11)>10.8?.12:1};
  if (move==='step') {p.leftFoot=[-12+cycle*7, Math.max(0,cycle)*7];p.rightFoot=[12+cycle*7,Math.max(0,-cycle)*7];p.x=cycle*8;}
  if (move==='sway') {p.x=cycle*10;p.lean=cycle*.09;p.leftArm=.35+cycle*.12;p.rightArm=-.35+cycle*.12;}
  if (move==='wave') {p.leftArm=-2.0+cycle*.3;p.leftElbow=-.4+pulse*.4;p.rightArm=-.5;}
  if (move==='clap') {const close=(1+Math.cos(beat*Math.PI*2))*.5;p.leftArm=-.55-close*.22;p.rightArm=.55+close*.22;p.leftElbow=-1.2-close*.65;p.rightElbow=1.2+close*.65;p.lean=cycle*.03;}
  if (move==='hop') {p.lift=bounce*13;p.leftArm=-.6-bounce*.6;p.rightArm=.6+bounce*.6;p.leftFoot=[-15,0];p.rightFoot=[15,0];}
  if (move==='twirl') {const angle=(beat%4)/4*Math.PI*2;p.turn=Math.cos(angle);p.leftArm=-1.05;p.rightArm=1.05;p.x=Math.sin(angle)*6;p.lift=bounce*3;}
  return p;
}

// Re-anchor to the real player frequently; extrapolation only smooths API sampling.
export class PlayerClock {
  constructor() {this.reset();}
  reset() {this.time=0;this.wall=0;this.changedAt=0;this.last=null;this.rate=1;this.playing=false;this.valid=false;}
  sample(time, wall, rate=1) {
    if (!Number.isFinite(time) || time<0 || !Number.isFinite(rate) || rate<=0) {this.valid=false;return;}
    if (this.last===null || Math.abs(time-this.last)>.005) this.changedAt=wall;
    this.time=time;this.wall=wall;this.rate=rate;this.last=time;this.valid=true;
  }
  current(wall) {
    if (!this.valid) return null;
    const delta=this.playing?Math.min(Math.max(0,wall-this.wall)/1000,.3)*this.rate:0;
    return this.time+delta;
  }
  stalled(wall) {return !this.valid || wall-this.changedAt>600;}
}

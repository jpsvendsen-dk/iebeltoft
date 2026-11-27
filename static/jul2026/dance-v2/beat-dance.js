// Song time is authoritative. Every frame is mapped to the analyzed beat grid,
// then to the matching phase of a complete, even-beat dance phrase.
function interval(points,value,getValue){
  let low=0,high=points.length-2;
  while(low<high){const middle=Math.ceil((low+high)/2);if(getValue(points[middle])<=value)low=middle;else high=middle-1;}
  return low;
}
export function validateRhythm(rhythm){
  if(!rhythm||!Array.isArray(rhythm.beats)||rhythm.beats.length<2||!Number.isFinite(rhythm.duration)||rhythm.duration<=0)throw Error('Invalid song rhythm');
  if(!rhythm.beats.every((beat,i)=>Number.isFinite(beat)&&beat>=0&&(i===0||beat>rhythm.beats[i-1])))throw Error('Song beats must increase');
  const clip=rhythm.clip;
  if(!clip||!Number.isFinite(clip.anchorSongBeat)||!Number.isFinite(clip.beats)||clip.beats<=0||!Number.isFinite(clip.duration)||clip.duration<=0)throw Error('Invalid dance phrase');
  if(!Array.isArray(clip.markers)||clip.markers.length<2||clip.markers[0].beat!==0||clip.markers[0].time!==0)throw Error('Invalid clip markers');
  if(!clip.markers.every((point,i)=>Number.isFinite(point.beat)&&Number.isFinite(point.time)&&(i===0||(point.beat>clip.markers[i-1].beat&&point.time>clip.markers[i-1].time))))throw Error('Clip markers must increase');
  const end=clip.markers.at(-1);
  if(end.beat!==clip.beats||Math.abs(end.time-clip.duration)>1e-6)throw Error('Incomplete clip phrase');
  return rhythm;
}
export function sampleDance(songTime,rhythm){
  if(!Number.isFinite(songTime))return {time:0,rate:1,active:false,beat:0,cycle:0};
  const {beats,clip}=rhythm;
  const position=Math.max(beats[0],Math.min(songTime,rhythm.duration));
  const index=interval(beats,position,n=>n);
  const secondsPerBeat=beats[index+1]-beats[index];
  const beat=index+(position-beats[index])/secondsPerBeat;
  const relative=beat-clip.anchorSongBeat;
  let phase=((relative%clip.beats)+clip.beats)%clip.beats;
  if(phase<1e-7||clip.beats-phase<1e-7)phase=0;
  const marker=interval(clip.markers,phase,p=>p.beat);
  const a=clip.markers[marker],b=clip.markers[marker+1];
  const videoSecondsPerBeat=(b.time-a.time)/(b.beat-a.beat);
  return {time:a.time+(phase-a.beat)*videoSecondsPerBeat,
          rate:videoSecondsPerBeat/secondsPerBeat,
          active:songTime>=beats[0]&&songTime<rhythm.duration,
          beat,cycle:Math.floor(relative/clip.beats)};
}

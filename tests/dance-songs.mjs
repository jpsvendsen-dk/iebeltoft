import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {sampleDance,validateRhythm} from '../static/jul2026/dance-v2/beat-dance.js';
const load=path=>JSON.parse(readFileSync(new URL(`../static/jul2026/dance-v2/${path}`,import.meta.url)));

export function checkRegisteredSongs(){
  const songs=load('assets/dance-songs.json');
  assert.deepEqual(Object.values(songs).map(s=>s.door).sort((a,b)=>a-b),[1,2,3,4,23]);
  const files=new Set(),report=[];
  for(const [id,song] of Object.entries(songs)){
    const media=load(song.video||'assets/dance-video.json');
    assert.ok(!files.has(song.rhythm),'each song gets its own beat analysis');files.add(song.rhythm);
    const map=validateRhythm(load(song.rhythm));
    assert.equal(map.videoId,id);
    assert.equal(map.clip.duration,media.duration);
    assert.ok(map.beats.length>=200);
    let minRate=Infinity,maxRate=0;
    for(let t=map.beats[0];t<map.duration;t+=.035){
      const pose=sampleDance(t,map);
      assert.ok(pose.time>=0&&pose.time<media.duration);
      assert.ok(Number.isFinite(pose.rate)&&pose.rate>=.0625&&pose.rate<=4);
      minRate=Math.min(minRate,pose.rate);maxRate=Math.max(maxRate,pose.rate);
    }
    if(song.door===23){
      assert.equal(map.clip.anchorSongTime,29);
      assert.equal(map.sourceVideoId,id);
      assert.ok(Math.abs(sampleDance(29,map).time)<1e-6,'original dance starts at 0:29');
      for(let i=0;i<map.clip.markers.length-1;i++){
        const marker=map.clip.markers[i],beat=map.clip.anchorSongBeat+marker.beat;
        const j=Math.floor(beat),time=map.beats[j]+(beat-j)*(map.beats[j+1]-map.beats[j]);
        assert.ok(Math.abs(sampleDance(time,map).time-marker.time)<1e-5);
      }
    }else if(song.door!==1){
      const first=map.clip.markers[1];
      assert.ok(Math.abs(sampleDance(map.beats[0],map).time-first.time)<1e-6);
      for(let i=0;i<map.beats.length;i++){
        const phase=i%map.clip.beats+first.beat,markers=map.clip.markers;
        let j=0;while(j<markers.length-2&&markers[j+1].beat<=phase)j++;
        const a=markers[j],b=markers[j+1];
        const expected=a.time+(phase-a.beat)/(b.beat-a.beat)*(b.time-a.time);
        assert.ok(Math.abs(sampleDance(map.beats[i],map).time-expected)<1e-5,`door ${song.door}, beat ${i}`);
      }
    }else assert.ok(Math.abs(sampleDance(13,map).time)<1e-6);
    report.push({door:song.door,beats:map.beats.length,minRate,maxRate});
  }
  return report;
}
test('registered doors use distinct rhythm maps, matching media and original dance anchors',checkRegisteredSongs);

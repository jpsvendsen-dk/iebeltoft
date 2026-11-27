// Presentation only: animation never advances the verified game simulation.
const VIEW = 440, CELL = VIEW / 20;
const clamp = value => Math.max(0, Math.min(1, value));
export class SnakeRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.background = document.createElement('canvas');
    this.background.width = this.background.height = VIEW;
    this.paintBackground();
    this.frame = null; this.scene = null; this.phase = 'idle'; this.progress = 1;
    this.effects = []; this.source = null;
    this.motion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    this.motion?.addEventListener?.('change', () => { this.stop(); this.draw(performance.now()); this.animate(); });
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => this.resize()).observe(canvas);
    else window.addEventListener('resize', () => this.resize());
    this.resize();
  }
  paintBackground() {
    const c = this.background.getContext('2d');
    const sky = c.createLinearGradient(0,0,VIEW,VIEW);
    sky.addColorStop(0,'#122f3c'); sky.addColorStop(.5,'#143d3c'); sky.addColorStop(1,'#092b30');
    c.fillStyle=sky;c.fillRect(0,0,VIEW,VIEW);
    const light=c.createRadialGradient(180,160,10,220,220,320);
    light.addColorStop(0,'#6cbd9d18');light.addColorStop(1,'#00171c55');
    c.fillStyle=light;c.fillRect(0,0,VIEW,VIEW);
    c.strokeStyle='#bdddd00b';c.lineWidth=1;
    for(let i=1;i<20;i++){c.beginPath();c.moveTo(i*CELL,0);c.lineTo(i*CELL,VIEW);c.moveTo(0,i*CELL);c.lineTo(VIEW,i*CELL);c.stroke();}
    for(let i=0;i<65;i++){
      const x=(i*137+17)%VIEW,y=(i*73+29)%VIEW;
      c.fillStyle=i%3?'#e0f8ed22':'#fff4dc44';c.beginPath();c.arc(x,y,i%3===0?1.5:.7,0,Math.PI*2);c.fill();
    }
    // Quiet fir silhouettes at the edge, kept behind the play field.
    c.fillStyle='#71a79410';
    for(const [x,h] of [[8,68],[31,42],[410,48],[434,86]]){
      for(let level=0;level<3;level++){const top=VIEW-h+level*h*.22;c.beginPath();c.moveTo(x,top);c.lineTo(x-h*(.16+level*.06),top+h*.5);c.lineTo(x+h*(.16+level*.06),top+h*.5);c.closePath();c.fill();}
    }
    c.strokeStyle='#d3c18d33';c.lineWidth=2;c.strokeRect(1,1,VIEW-2,VIEW-2);
  }
  resize() {
    const ratio=Math.min(window.devicePixelRatio||1,3);
    const width=this.canvas.getBoundingClientRect().width||VIEW;
    const pixels=Math.max(1,Math.round(width*ratio));
    if(this.canvas.width!==pixels || this.canvas.height!==pixels)this.canvas.width=this.canvas.height=pixels;
    this.draw(performance.now());
  }
  stop() {if(this.frame!==null)cancelAnimationFrame(this.frame);this.frame=null;}
  fraction(now) {
    if(this.motion?.matches)return 1;
    return this.phase==='running'?clamp((now-this.started)/this.duration):this.progress;
  }
  update(game, phase) {
    const now=performance.now(), fresh=this.source!==game || this.lifeLost&&!game.lifeLost;
    if(fresh || this.tick!==game.tick){
      const old=this.scene;
      this.previous=fresh?game.body.map(p=>[...p]):old.body;
      this.duration=game.interval;
      if(!fresh && game.score>old.score && old.food && !this.motion?.matches){
        this.effects.push({x:(old.food[0]+.5)*CELL,y:(old.food[1]+.5)*CELL,time:now});
      }
      if(fresh){this.effects=[];this.recordAt=null;}
      this.scene={body:game.body.map(p=>[...p]),food:game.food?[...game.food]:null,direction:game.direction,interval:game.interval,score:game.score,lives:game.lives,won:game.won};
      this.source=game;this.tick=game.tick;this.started=now;
      this.lifeLost=game.lifeLost;
      this.progress=fresh||game.over?1:0;
      if(this.progress===1)this.started=now-this.duration;
    }
    if(phase!==this.phase){
      if(this.phase==='running')this.progress=this.fraction(now);
      if(phase==='running')this.started=now-this.progress*this.duration;
      this.phase=phase;
    }
    this.stop();this.draw(now);this.animate();
  }
  animate() {
    const celebrating=this.recordAt!=null&&performance.now()-this.recordAt<2600;
    if(this.frame!==null || (this.phase!=='running'&&!celebrating) || this.motion?.matches||document.hidden)return;
    this.frame=requestAnimationFrame(now=>{this.frame=null;this.draw(now);this.animate();});
  }
  celebrate() {
    this.recordAt=performance.now();
    this.draw(this.recordAt);this.animate();
  }
  fireworks(now) {
    if(this.recordAt==null||this.motion?.matches)return;
    const elapsed=now-this.recordAt,c=this.ctx;
    for(const [index,x,y,color] of [[0,100,115,'#ffd785'],[1,335,120,'#ff9b9b'],[2,220,80,'#a1e6d1']]){
      const t=(elapsed-index*430)/1500;
      if(t<0||t>1)continue;
      c.save();c.globalAlpha=(1-t)*(1-t);c.strokeStyle=color;c.fillStyle=color;
      c.lineWidth=2;c.shadowColor=color;c.shadowBlur=7;
      for(let i=0;i<22;i++){
        const angle=i*Math.PI*2/22,radius=(45+(i%3)*16)*Math.sin(t*Math.PI/2);
        const px=x+Math.cos(angle)*radius,py=y+Math.sin(angle)*radius+36*t*t;
        c.beginPath();c.moveTo(px-Math.cos(angle)*7*(1-t),py-Math.sin(angle)*7*(1-t));c.lineTo(px,py);c.stroke();
        c.beginPath();c.arc(px,py,1.5,0,Math.PI*2);c.fill();
      }
      c.restore();
    }
  }
  positions(now) {
    const t=this.fraction(now);
    return this.scene.body.map((point,i)=>{
      const from=this.previous[Math.min(i,this.previous.length-1)];
      return [(from[0]+(point[0]-from[0])*t+.5)*CELL,(from[1]+(point[1]-from[1])*t+.5)*CELL];
    });
  }
  roundedBox(c,x,y,w,h,r) {c.beginPath();c.roundRect(x,y,w,h,r);}
  gift(now) {
    if(!this.scene.food)return;
    const c=this.ctx,[x,y]=this.scene.food,animated=this.phase==='running'&&!this.motion?.matches;
    const bob=animated?Math.sin(now/320)*1.3:0, pulse=animated ? .5+.5*Math.sin(now/420) : .5;
    c.save();c.translate((x+.5)*CELL,(y+.5)*CELL+bob);
    const glow=c.createRadialGradient(0,0,2,0,0,CELL*1.25);
    glow.addColorStop(0,`rgba(255,217,130,${.17+pulse*.08})`);glow.addColorStop(1,'rgba(255,217,130,0)');
    c.fillStyle=glow;c.fillRect(-CELL*1.25,-CELL*1.25,CELL*2.5,CELL*2.5);
    c.shadowColor='#0009';c.shadowBlur=5;c.shadowOffsetY=3;
    const red=c.createLinearGradient(-8,-9,9,9);red.addColorStop(0,'#f29384');red.addColorStop(.45,'#d94f54');red.addColorStop(1,'#8f233e');
    c.fillStyle=red;this.roundedBox(c,-9,-7,18,16,3);c.fill();c.shadowBlur=0;c.shadowOffsetY=0;
    c.fillStyle='#f3cf83';c.fillRect(-1.6,-9,3.2,18);c.fillRect(-10,-6,20,3);
    c.strokeStyle='#ffdf9e';c.lineWidth=1.8;c.beginPath();c.ellipse(-3,-10,3.5,2.5,.5,0,Math.PI*2);c.ellipse(3,-10,3.5,2.5,-.5,0,Math.PI*2);c.stroke();
    c.fillStyle='#ffffff55';this.roundedBox(c,-8,-6,5,10,2);c.fill();c.restore();
  }
  snake(now) {
    const c=this.ctx,points=this.positions(now),path=()=>{
      c.beginPath();const tail=points.at(-1);c.moveTo(...tail);
      for(let i=points.length-2;i>=0;i--){
        if(i===0)c.lineTo(...points[i]);
        else{const p=points[i],next=points[i-1];c.quadraticCurveTo(p[0],p[1],(p[0]+next[0])/2,(p[1]+next[1])/2);}
      }
    };
    c.save();c.lineCap=c.lineJoin='round';
    c.shadowColor='#0008';c.shadowBlur=8;c.shadowOffsetY=3;c.strokeStyle='#163f32';c.lineWidth=CELL*.88;path();c.stroke();
    c.shadowBlur=0;c.shadowOffsetY=0;
    const green=c.createLinearGradient(0,0,VIEW,VIEW);green.addColorStop(0,'#c1e796');green.addColorStop(.5,'#76b480');green.addColorStop(1,'#39866f');
    c.strokeStyle=green;c.lineWidth=CELL*.7;path();c.stroke();
    c.strokeStyle='#e4ffbf38';c.lineWidth=CELL*.2;path();c.stroke();
    // Position stays fluid, but facing follows the accepted turn immediately.
    // Tweening facing over a full tick made a correct turn look unresponsive.
    const [hx,hy]=points[0];
    c.translate(hx,hy);c.rotate(this.scene.direction*Math.PI/2);
    const head=c.createLinearGradient(-10,-10,9,10);head.addColorStop(0,'#e0f6ba');head.addColorStop(1,'#91ca88');
    c.fillStyle=head;c.beginPath();c.ellipse(0,0,11,9,0,0,Math.PI*2);c.fill();
    for(const y of [-4,4]){c.fillStyle='#fffced';c.beginPath();c.ellipse(4,y,3.8,3.3,0,0,Math.PI*2);c.fill();c.fillStyle='#153a35';c.beginPath();c.arc(5,y,1.7,0,Math.PI*2);c.fill();c.fillStyle='#fff';c.beginPath();c.arc(5.5,y-.6,.6,0,Math.PI*2);c.fill();}
    c.strokeStyle='#4d805e';c.lineWidth=1;c.beginPath();c.arc(5,0,3,-.6,.6);c.stroke();
    const hat=c.createLinearGradient(-17,-8,-5,5);hat.addColorStop(0,'#f0897d');hat.addColorStop(1,'#b62d47');c.fillStyle=hat;
    c.beginPath();c.moveTo(-5,-8);c.quadraticCurveTo(-16,-14,-18,2);c.quadraticCurveTo(-13,-3,-5,8);c.closePath();c.fill();
    c.strokeStyle='#fff5de';c.lineWidth=5;c.lineCap='round';c.beginPath();c.moveTo(-5,-7);c.lineTo(-5,7);c.stroke();
    c.fillStyle='#fff5de';c.beginPath();c.arc(-18,2,3.7,0,Math.PI*2);c.fill();c.restore();
  }
  sparkles(now) {
    if(this.motion?.matches)return;
    const c=this.ctx;
    this.effects=this.effects.filter(effect=>now-effect.time<480);
    for(const effect of this.effects){const t=clamp((now-effect.time)/480);c.save();c.globalAlpha=1-t;c.fillStyle='#ffe6a6';
      for(let i=0;i<10;i++){const angle=i*Math.PI/5,range=5+t*27;c.beginPath();c.arc(effect.x+Math.cos(angle)*range,effect.y+Math.sin(angle)*range,2*(1-t)+.5,0,Math.PI*2);c.fill();}c.restore();}
  }
  draw(now) {
    const c=this.ctx;c.setTransform(this.canvas.width/VIEW,0,0,this.canvas.height/VIEW,0,0);
    c.clearRect(0,0,VIEW,VIEW);c.drawImage(this.background,0,0,VIEW,VIEW);
    if(!this.scene)return;
    this.gift(now);this.snake(now);this.sparkles(now);
    if(this.phase==='paused'||this.phase==='over'||this.phase==='life'){
      c.fillStyle='#082c31a8';c.fillRect(0,0,VIEW,VIEW);
      c.fillStyle='#112e35ed';this.roundedBox(c,48,164,344,112,20);c.fill();c.strokeStyle='#e6c58c66';c.lineWidth=1;c.stroke();
      const record=this.phase==='over'&&this.recordAt!=null;
      c.fillStyle=record?'#ffdf94':'#fff0d3';c.textAlign='center';c.font='600 26px system-ui';c.fillText(this.phase==='life'?(this.scene.lives===1?'Ét liv tilbage':`${this.scene.lives} liv tilbage`):this.phase==='paused'?'En lille julepause':record?'Tillykke!':this.scene.won?'Alle gaver samlet!':'Tak for spillet!',VIEW/2,211);
      c.font='17px system-ui';c.fillStyle='#e7d4b4';c.fillText(this.phase==='life'?'Tryk “Brug næste liv”':this.phase==='over'?`${record?'Ny rekord · ':''}${this.scene.score} point`:'Tag dig god tid',VIEW/2,244);
    }
    this.fireworks(now);
  }
}

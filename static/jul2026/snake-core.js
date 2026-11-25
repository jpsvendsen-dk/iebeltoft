// These deterministic rules are mirrored by app/services/christmas_snake.py.
export const SIZE = 20, MAX_TICKS = 20000;
const vectors = [[1,0],[0,1],[-1,0],[0,-1]];
// Same closed respawn route as the server; every body length fits safely.
const respawnPath=[[0,0]];
for(let y=0;y<SIZE;y++)for(let i=1;i<SIZE;i++)respawnPath.push([y%2===0?i:SIZE-i,y]);
for(let y=SIZE-1;y>0;y--)respawnPath.push([0,y]);
const respawnHead=respawnPath.findIndex(([x,y])=>x===10&&y===10);
export class SnakeGame {
  constructor(seed, version = 1) {
    this.version = version; this.lives = version >= 2 ? 2 : 1;
    this.bonusLife = false; this.lifeLost = false;
    this.seed = seed >>> 0; this.body = [[10,10],[9,10],[8,10]];
    this.direction = 0; this.score = 0; this.tick = 0; this.elapsedMs = 0;
    this.over = false; this.won = false; this.food = this.spawn();
  }
  spawn() {
    const occupied = new Set(this.body.map(([x,y]) => y * SIZE + x));
    const free = [];
    for (let y=0;y<SIZE;y++) for (let x=0;x<SIZE;x++) if (!occupied.has(y*SIZE+x)) free.push([x,y]);
    if (!free.length) return null;
    let value = this.seed;
    value ^= value << 13; value ^= value >>> 17; value ^= value << 5;
    this.seed = value >>> 0;
    return free[this.seed % free.length];
  }
  get interval() { return Math.max(80,160-Math.floor(this.score/50)*10); }
  step(direction = null) {
    if (this.over) throw Error('Spillet er allerede afsluttet.');
    if (this.lifeLost) this.respawn();
    if (direction !== null) {
      if (direction === (this.direction+2)%4) throw Error('Slangen kan ikke vende direkte tilbage.');
      this.direction = direction;
    }
    this.elapsedMs += this.interval; this.tick++;
    const [dx,dy] = vectors[this.direction], head = [this.body[0][0]+dx,this.body[0][1]+dy];
    const grows = this.food && head[0] === this.food[0] && head[1] === this.food[1];
    const obstacles = grows ? this.body : this.body.slice(0,-1);
    if (head[0]<0 || head[0]>=SIZE || head[1]<0 || head[1]>=SIZE || obstacles.some(p=>p[0]===head[0] && p[1]===head[1])) {
      this.lives--;this.over=this.lives===0 || this.tick===MAX_TICKS;this.lifeLost=!this.over;return;
    }
    this.body.unshift(head);
    if (grows) {
      this.score += 10;
      if (this.version >= 2 && this.score > 500 && !this.bonusLife) { this.lives++; this.bonusLife=true; }
      this.food = this.spawn();
      if (!this.food) this.over = this.won = true;
    } else this.body.pop();
    if (this.tick === MAX_TICKS) this.over = true;
  }
  respawn() {
    this.body=this.version>=3?Array.from({length:this.body.length},(_,i)=>[...respawnPath[(respawnHead-i+respawnPath.length)%respawnPath.length]]):[[10,10],[9,10],[8,10]];
    this.direction=0;this.lifeLost=false;
    if (this.food && this.body.some(p=>p[0]===this.food[0] && p[1]===this.food[1])) this.food=this.spawn();
  }
}

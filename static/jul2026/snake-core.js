// These deterministic rules are mirrored by app/services/christmas_snake.py.
export const SIZE = 20, MAX_TICKS = 20000;
const vectors = [[1,0],[0,1],[-1,0],[0,-1]];
export class SnakeGame {
  constructor(seed) {
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
    if (direction !== null) {
      if (direction === (this.direction+2)%4) throw Error('Slangen kan ikke vende direkte tilbage.');
      this.direction = direction;
    }
    this.elapsedMs += this.interval; this.tick++;
    const [dx,dy] = vectors[this.direction], head = [this.body[0][0]+dx,this.body[0][1]+dy];
    const grows = this.food && head[0] === this.food[0] && head[1] === this.food[1];
    const obstacles = grows ? this.body : this.body.slice(0,-1);
    if (head[0]<0 || head[0]>=SIZE || head[1]<0 || head[1]>=SIZE || obstacles.some(p=>p[0]===head[0] && p[1]===head[1])) { this.over=true; return; }
    this.body.unshift(head);
    if (grows) {
      this.score += 10; this.food = this.spawn();
      if (!this.food) this.over = this.won = true;
    } else this.body.pop();
    if (this.tick === MAX_TICKS) this.over = true;
  }
}

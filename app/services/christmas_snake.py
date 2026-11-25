"""Deterministic Snake rules, mirrored by snake-core.js for replay validation."""
SIZE = 20
MAX_TICKS = 20000
VECTORS = ((1, 0), (0, 1), (-1, 0), (0, -1))


class Game:
    def __init__(self, seed):
        self.seed = seed
        self.body = [(10, 10), (9, 10), (8, 10)]
        self.direction = 0
        self.score = 0
        self.tick = 0
        self.elapsed_ms = 0
        self.over = False
        self.won = False
        self.food = self.spawn()

    def spawn(self):
        occupied = set(self.body)
        free = [(x, y) for y in range(SIZE) for x in range(SIZE) if (x, y) not in occupied]
        if not free:
            return None
        value = self.seed
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= value >> 17
        value ^= (value << 5) & 0xFFFFFFFF
        self.seed = value & 0xFFFFFFFF
        return free[self.seed % len(free)]

    @property
    def interval(self):
        return max(80, 160 - (self.score // 50) * 10)

    def step(self, direction=None):
        if self.over:
            raise ValueError("Spillet er allerede afsluttet.")
        if direction is not None:
            if direction == (self.direction + 2) % 4:
                raise ValueError("Slangen kan ikke vende direkte tilbage.")
            self.direction = direction
        self.elapsed_ms += self.interval
        self.tick += 1
        dx, dy = VECTORS[self.direction]
        head = (self.body[0][0] + dx, self.body[0][1] + dy)
        grows = head == self.food
        if not (0 <= head[0] < SIZE and 0 <= head[1] < SIZE) or head in (self.body if grows else self.body[:-1]):
            self.over = True
            return
        self.body.insert(0, head)
        if grows:
            self.score += 10
            self.food = self.spawn()
            if self.food is None:
                self.over = self.won = True
        else:
            self.body.pop()
        if self.tick == MAX_TICKS:
            self.over = True


def replay(seed, ticks, turns):
    game = Game(seed)
    previous = 0
    changes = {}
    for turn in turns:
        if turn.tick <= previous or turn.tick > ticks:
            raise ValueError("Retningsskiftene er ugyldige.")
        previous = turn.tick
        changes[turn.tick] = turn.direction
    for tick in range(1, ticks + 1):
        game.step(changes.get(tick))
    if not game.over:
        raise ValueError("Spillet er ikke afsluttet endnu.")
    return game

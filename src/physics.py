"""Deterministic 2D physics for ring-escape and grow battles.

The simulation runs once headless, records per-frame ball states and sound
events, and the renderer replays the recording. Units: pixels, seconds.
"""
import math
import random

FPS = 60
SUBSTEPS = 6
TAU = math.tau


def wrap(a):
    return (a + math.pi) % TAU - math.pi


class Ball:
    __slots__ = ("x", "y", "vx", "vy", "r", "team", "alive", "done_t", "grow_n")

    def __init__(self, x, y, vx, vy, r, team):
        self.x, self.y, self.vx, self.vy, self.r, self.team = x, y, vx, vy, r, team
        self.alive = True
        self.done_t = None
        self.grow_n = 0


class Ring:
    __slots__ = ("R", "thick", "gap", "ang", "w")

    def __init__(self, R, thick, gap, ang, w):
        self.R, self.thick, self.gap, self.ang, self.w = R, thick, gap, ang, w


class World:
    """mode 'escape': first ball to leave every ring wins.
    mode 'grow': each wall bounce grows the ball; first to target radius wins."""

    def __init__(self, mode, teams, seed, cx, cy, arena_r, p):
        self.mode, self.teams, self.cx, self.cy = mode, teams, cx, cy
        self.rng = random.Random(seed)
        self.g = p.get("gravity", 1300.0)
        self.vmax = p.get("vmax", 2300.0)
        self.boost = p.get("boost", 1.0)
        self.t = 0.0
        self.events = []  # (t, kind, team, extra, x, y)
        self.winner = None
        self.win_t = None
        rng = self.rng
        self.rings = []
        if mode == "escape":
            n = p["rings"]
            for i in range(n):
                R = arena_r * (0.36 + 0.64 * i / max(1, n - 1))
                w = rng.choice((-1, 1)) * rng.uniform(*p["spin"])
                self.rings.append(Ring(R, 10.0, math.radians(p["gap_deg"]), rng.uniform(-math.pi, math.pi), w))
        else:
            self.rings.append(Ring(arena_r, 12.0, 0.0, 0.0, 0.0))
        self.target_r = p.get("target_r", 120.0)
        self.grow_step = p.get("grow_step", 3.0)
        r0 = p.get("ball_r", 34.0)
        inner = self.rings[0].R - r0 - 12
        self.balls = []
        k = len(teams)
        for i in range(k):
            a = TAU * i / k + rng.uniform(-0.2, 0.2)
            d = inner * (0.45 if mode == "escape" else 0.55)
            sp = rng.uniform(700, 1000)
            va = rng.uniform(0, TAU)
            self.balls.append(Ball(cx + d * math.cos(a), cy + d * math.sin(a),
                                   sp * math.cos(va), sp * math.sin(va), r0, i))

    def _ev(self, kind, b, extra):
        self.events.append((self.t, kind, b.team, extra, b.x, b.y))

    def layer(self, b):
        d = math.hypot(b.x - self.cx, b.y - self.cy)
        return sum(1 for rg in self.rings if rg.R > d)

    def _ring_collide(self, b, rg, ri):
        dx, dy = b.x - self.cx, b.y - self.cy
        d = math.hypot(dx, dy) or 1e-6
        half = rg.thick / 2
        if abs(d - rg.R) >= b.r + half:
            return
        if rg.gap > 0:
            rel = wrap(math.atan2(dy, dx) - rg.ang)
            if abs(rel) < rg.gap / 2 - (b.r / rg.R) * 0.6:
                return  # inside the gap: free passage
        nx, ny = dx / d, dy / d
        vn = b.vx * nx + b.vy * ny
        if d < rg.R:
            b.x, b.y = self.cx + nx * (rg.R - half - b.r), self.cy + ny * (rg.R - half - b.r)
            if vn > 0:
                self._reflect(b, nx, ny, vn, ri)
        else:
            b.x, b.y = self.cx + nx * (rg.R + half + b.r), self.cy + ny * (rg.R + half + b.r)
            if vn < 0:
                self._reflect(b, nx, ny, vn, ri)

    def _reflect(self, b, nx, ny, vn, ri):
        b.vx -= 2 * vn * nx
        b.vy -= 2 * vn * ny
        b.vx *= self.boost
        b.vy *= self.boost
        self._ev("bounce", b, ri)
        if self.mode == "grow" and b.alive:
            b.r = min(self.target_r, b.r + self.grow_step)
            b.grow_n += 1
            if b.r >= self.target_r and self.winner is None:
                self.winner, self.win_t = b.team, self.t
                self._ev("win", b, 0)

    def _ball_collide(self, a, b):
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        m = a.r + b.r
        if d >= m or d == 0:
            return
        nx, ny = dx / d, dy / d
        ma, mb = a.r * a.r, b.r * b.r
        over = m - d
        a.x -= nx * over * mb / (ma + mb)
        a.y -= ny * over * mb / (ma + mb)
        b.x += nx * over * ma / (ma + mb)
        b.y += ny * over * ma / (ma + mb)
        rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
        if rv < 0:
            j = 2 * rv / (ma + mb)
            a.vx += j * mb * nx
            a.vy += j * mb * ny
            b.vx -= j * ma * nx
            b.vy -= j * ma * ny
            self._ev("clack", a, 0)

    def step(self):
        dt = 1.0 / FPS / SUBSTEPS
        for _ in range(SUBSTEPS):
            self.t += dt
            for rg in self.rings:
                rg.ang = wrap(rg.ang + rg.w * dt)
            live = [b for b in self.balls if b.alive]
            for b in live:
                b.vy += self.g * dt
                s = math.hypot(b.vx, b.vy)
                if s > self.vmax:
                    b.vx, b.vy = b.vx * self.vmax / s, b.vy * self.vmax / s
                before = self.layer(b) if self.mode == "escape" else 0
                b.x += b.vx * dt
                b.y += b.vy * dt
                for ri, rg in enumerate(self.rings):
                    self._ring_collide(b, rg, ri)
                if self.mode == "escape":
                    after = self.layer(b)
                    if after < before:
                        self._ev("pass", b, after)
                        if after == 0:
                            b.alive = False
                            b.done_t = self.t
                            if self.winner is None:
                                self.winner, self.win_t = b.team, self.t
                                self._ev("win", b, 0)
                    elif after > before:
                        self._ev("fall", b, after)
            for i in range(len(live)):
                for j in range(i + 1, len(live)):
                    self._ball_collide(live[i], live[j])

    def snapshot(self):
        return {
            "rings": [(rg.R, rg.thick, rg.gap, rg.ang) for rg in self.rings],
            "balls": [(b.x, b.y, b.r, b.team, b.alive) for b in self.balls],
            "layers": [self.layer(b) if b.alive else 0 for b in self.balls] if self.mode == "escape" else None,
        }


def simulate(mode, teams, seed, cx, cy, arena_r, p, max_s=55.0, tail_s=3.5):
    """Runs to the winner + tail. Returns (frames, events, winner, win_t) or None if no winner."""
    w = World(mode, teams, seed, cx, cy, arena_r, p)
    frames = []
    while w.t < max_s:
        w.step()
        frames.append(w.snapshot())
        if w.win_t is not None and w.t > w.win_t + tail_s:
            return frames, w.events, w.winner, w.win_t
    return None


def race_stats(mode, teams, seed, cx, cy, arena_r, p, max_s=55.0):
    """Cheap headless run used for seed search: winner time and closeness."""
    w = World(mode, teams, seed, cx, cy, arena_r, p)
    while w.t < max_s and w.win_t is None:
        w.step()
    if w.win_t is None:
        return None
    if mode == "escape":
        layers = sorted(w.layer(b) for b in w.balls if b.alive)
        runner_up = layers[0] if layers else 0
        lead_changes = len({e[2] for e in w.events if e[1] == "pass"})
        return {"t": w.win_t, "runner_up_gap": runner_up, "movers": lead_changes}
    rs = sorted((b.r for b in w.balls), reverse=True)
    return {"t": w.win_t, "runner_up_gap": (rs[0] - rs[1]) / w.grow_step if len(rs) > 1 else 9, "movers": len(teams)}

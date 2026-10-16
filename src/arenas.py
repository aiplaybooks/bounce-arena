"""Extra arena modes: maze, golf, plinko, race, storm, territory, sumo, tower, chain, flip, pinball, hole.

Every mode is a deterministic headless sim (same contract as physics.World): it records per-frame
snapshots that render.py replays. Snapshots carry generic drawing primitives ("shapes") so the
renderer needs no per-mode code. Shape tuples (colors are RGB tuples, an int team index, or
("t", team, f) = team color blended f of the way from the dark background):
  ("line", x1, y1, x2, y2, width, color)   ("circle", x, y, r, color)   ("ring", x, y, r, width, color)
  ("rect", x, y, w, h, color)              ("poly", [(x, y), ...], color)
  ("text", str, x, y, size, color)         ("capsule", x, y1, y2, r, color)  (vertical capsule)
"""
import math
import random

FPS = 60
TAU = math.tau
BX0, BX1, BY0, BY1 = 115, 965, 490, 1340
CX, CY = 540, 915
WHITE = (240, 240, 250)
WALL = (120, 130, 255)


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def finale_gap(times):
    """Elimination modes: how frantic was the finish = time between the last two eliminations (1.5 s ~ 1.0)."""
    ts = sorted(times)
    return (ts[-1] - ts[-2]) / 1.5 if len(ts) > 1 else 9.0


class Ball:
    __slots__ = ("x", "y", "vx", "vy", "r", "team", "vis", "dead", "score", "t0", "k", "px", "py", "st", "aux")

    def __init__(self, x, y, r, team, vx=0.0, vy=0.0):
        self.x, self.y, self.r, self.team, self.vx, self.vy = x, y, r, team, vx, vy
        self.vis, self.dead, self.score, self.t0, self.k = True, False, 0, 0.0, 0
        self.px, self.py, self.st, self.aux = x, y, 0, 0.0


def seg_hit(b, ax, ay, bx, by, half, rest=0.8, fric=0.0, svx=0.0, svy=0.0):
    """Ball vs thick segment (capsule). Returns None if no overlap, else the impact speed (0 if separating)."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 > 0:
        t = ((b.x - ax) * dx + (b.y - ay) * dy) / l2
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    else:
        t = 0.0
    ox, oy = b.x - (ax + dx * t), b.y - (ay + dy * t)
    m = b.r + half
    d2 = ox * ox + oy * oy
    if d2 >= m * m:
        return None
    d = math.sqrt(d2)
    if d < 1e-9:
        l = math.sqrt(l2)
        nx, ny = (-dy / l, dx / l) if l > 0 else (0.0, -1.0)
    else:
        nx, ny = ox / d, oy / d
    b.x += nx * (m - d)
    b.y += ny * (m - d)
    vn = (b.vx - svx) * nx + (b.vy - svy) * ny
    if vn >= 0:
        return 0.0
    e = rest if -vn > 60 else 0.0
    b.vx -= (1 + e) * vn * nx
    b.vy -= (1 + e) * vn * ny
    if fric:
        tx, ty = -ny, nx
        vt = (b.vx - svx) * tx + (b.vy - svy) * ty
        b.vx -= vt * fric * tx
        b.vy -= vt * fric * ty
    return -vn


def ball_hit(a, b, rest=1.0):
    """Ball vs ball (mass ~ r^2). Returns impact speed or 0."""
    dx, dy = b.x - a.x, b.y - a.y
    m = a.r + b.r
    d2 = dx * dx + dy * dy
    if d2 >= m * m or d2 == 0:
        return 0.0
    d = math.sqrt(d2)
    nx, ny = dx / d, dy / d
    ma, mb = a.r * a.r, b.r * b.r
    over = m - d
    a.x -= nx * over * mb / (ma + mb)
    a.y -= ny * over * mb / (ma + mb)
    b.x += nx * over * ma / (ma + mb)
    b.y += ny * over * ma / (ma + mb)
    rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
    if rv < 0:
        j = (1 + rest) * rv / (ma + mb)
        a.vx += j * mb * nx
        a.vy += j * mb * ny
        b.vx -= j * ma * nx
        b.vy -= j * ma * ny
        return -rv
    return 0.0


class Arena:
    SUB = 8
    G = 0.0

    def __init__(self, teams, seed, p):
        self.teams, self.n, self.p = teams, len(teams), p
        self.rng = random.Random(seed)
        self.t = 0.0
        self.events = []
        self.winner = None
        self.win_t = None
        self.failed = False
        self.balls = []
        self.static = []
        self.lead = None
        self.lead_changes = 0
        self._lastev = {}
        self.after = 0  # frames since the win; the world is frozen from then on
        self.setup()

    # -- helpers -------------------------------------------------------------------------------
    def ev(self, kind, b, extra=0, x=None, y=None, gap=0.0):
        key = (kind, b.team)
        if gap and self.t - self._lastev.get(key, -9) < gap:
            return
        self._lastev[key] = self.t
        self.events.append((self.t, kind, b.team, extra, b.x if x is None else x, b.y if y is None else y))

    def win(self, team, b=None):
        if self.winner is None:
            self.winner, self.win_t = team, self.t
            b = b or self.balls[0]
            self.events.append((self.t, "win", team, 0, b.x, b.y))

    def step(self):
        if self.win_t is not None:
            self.after += 1
            return
        dt = 1.0 / FPS / self.SUB
        for _ in range(self.SUB):
            self.t += dt
            self.tick(dt)
        lead = self.leader()
        if lead is not None:
            if self.lead is not None and lead != self.lead:
                self.lead_changes += 1
            self.lead = lead

    def snapshot(self, first=False):
        fr = {"rings": [], "layers": None, "shapes": self.dyn(), "standings": self.standings(),
              "balls": [(b.x, b.y, b.r, b.team, b.vis) for b in self.balls]}
        if first:
            fr["static"] = self.static
        g = self.grid()
        if g:
            fr["grid"] = g
        return fr

    # -- overridables --------------------------------------------------------------------------
    def setup(self):
        raise NotImplementedError

    def tick(self, dt):
        raise NotImplementedError

    def dyn(self):
        return []

    def grid(self):
        return None

    def leader(self):
        return None

    def standings(self):
        return [(b.team, "") for b in self.balls]

    def gap(self):
        return 9.0

    def collide_balls(self, rest=1.0, only=None):
        live = only if only is not None else [b for b in self.balls if b.vis and not b.dead]
        for i in range(len(live)):
            a = live[i]
            for j in range(i + 1, len(live)):
                s = ball_hit(a, live[j], rest)
                if s > 220:
                    self.ev("clack", a, gap=0.08)


# ====================================================================================================
class Maze(Arena):
    """Balls race through a random maze; at each junction they follow the right way with some probability."""
    SUB = 2

    def setup(self):
        p, rng = self.p, self.rng
        C = R = p.get("size", 12)
        cs = 840 / C
        self.C, self.R, self.cs = C, R, cs
        self.ox, self.oy = CX - C * cs / 2, BY0 + 8
        adj = {(c, r): [] for c in range(C) for r in range(R)}
        seen, stack = {(0, 0)}, [(0, 0)]
        while stack:
            c, r = stack[-1]
            nb = [(c + dc, r + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if 0 <= c + dc < C and 0 <= r + dr < R and (c + dc, r + dr) not in seen]
            if nb:
                n = rng.choice(nb)
                adj[(c, r)].append(n)
                adj[n].append((c, r))
                seen.add(n)
                stack.append(n)
            else:
                stack.pop()
        for _ in range(p.get("loops", 7)):  # knock out extra walls so there are alternative routes
            c, r = rng.randrange(C), rng.randrange(R)
            dc, dr = rng.choice(((1, 0), (0, 1)))
            n = (c + dc, r + dr)
            if n in adj and n not in adj[(c, r)]:
                adj[(c, r)].append(n)
                adj[n].append((c, r))
        self.adj = adj
        self.exit = (C - 1, R - 1)
        dist = {self.exit: 0}
        q = [self.exit]
        for cur in q:
            for n in adj[cur]:
                if n not in dist:
                    dist[n] = dist[cur] + 1
                    q.append(n)
        self.dist = dist
        ox, oy = self.ox, self.oy
        st = self.static
        st.append(("rect", ox, oy, C * cs, R * cs, (18, 20, 46)))
        wc = WALL
        for c in range(C):
            for r in range(R):
                x, y = ox + c * cs, oy + r * cs
                if (c + 1, r) not in adj[(c, r)]:
                    st.append(("line", x + cs, y, x + cs, y + cs, 9, wc))
                if (c, r + 1) not in adj[(c, r)]:
                    st.append(("line", x, y + cs, x + cs, y + cs, 9, wc))
        st += [("line", ox, oy, ox + C * cs, oy, 9, wc), ("line", ox, oy, ox, oy + R * cs, 9, wc),
               ("line", ox + C * cs, oy, ox + C * cs, oy + R * cs, 9, wc), ("line", ox, oy + R * cs, ox + C * cs, oy + R * cs, 9, wc)]
        ex, ey = self.center(self.exit)
        sx, sy = self.center((0, 0))
        st += [("circle", ex, ey, 31, (30, 120, 60)), ("text", "EXIT", ex, ey, 26, WHITE),
               ("circle", sx, sy, 31, (60, 60, 90)), ("text", "START", sx, sy, 19, WHITE)]
        qlo, qhi = p.get("q", (0.3, 0.5))
        for i in range(self.n):
            a = TAU * i / self.n
            b = Ball(sx, sy, 18, i)
            b.aux = (9 * math.cos(a), 9 * math.sin(a))
            b.k = (0, 0)  # current cell
            b.px = None  # previous cell
            b.st = None  # next cell
            b.vx = rng.uniform(qlo, qhi)  # junction accuracy
            b.vy = rng.uniform(230, 280)  # speed px/s
            b.score = 0.0  # progress 0..1 between cells
            self.balls.append(b)
            self.pick(b)

    def center(self, cell):
        return self.ox + (cell[0] + 0.5) * self.cs, self.oy + (cell[1] + 0.5) * self.cs

    def pick(self, b):
        nb = self.adj[b.k]
        if len(nb) == 1:
            b.st = nb[0]
            return
        opts = [n for n in nb if n != b.px] or nb
        if self.rng.random() < b.vx:
            b.st = min(nb, key=lambda n: (self.dist[n], self.rng.random()))
        else:
            b.st = self.rng.choice(opts)

    def tick(self, dt):
        for b in self.balls:
            if b.k == self.exit:
                continue
            b.score += b.vy * dt / self.cs
            while b.score >= 1.0 and b.k != self.exit:
                b.score -= 1.0
                b.px, b.k = b.k, b.st
                self.ev("bounce", b, gap=0.1)
                if b.k == self.exit:
                    b.score = 0.0
                    self.win(b.team, b)
                    break
                self.pick(b)
            ax, ay = self.center(b.k)
            if b.k != self.exit:
                nx, ny = self.center(b.st)
                ax, ay = ax + (nx - ax) * b.score, ay + (ny - ay) * b.score
            b.x, b.y = ax + b.aux[0], ay + b.aux[1]

    def leader(self):
        return min(self.balls, key=lambda b: (self.dist[b.k], -b.score)).team

    def standings(self):
        rows = sorted(((self.dist[b.k], -b.score, b.team) for b in self.balls))
        return [(t, "ESCAPED!" if d == 0 else f"{d} STEPS LEFT") for d, _, t in rows]

    def gap(self):
        ds = sorted(self.dist[b.k] for b in self.balls)
        return float(ds[1]) if len(ds) > 1 else 9.0


# ====================================================================================================
class Golf(Arena):
    """Balls roll down zig-zag ramps to a green; first to sink in the hole wins."""
    SUB = 8
    G = 1300.0

    def setup(self):
        rng = self.rng
        self.hx, self.hy = CX, 1300
        self.r0 = 26
        st = self.static
        self.segs = []  # (ax, ay, bx, by, half, rest, fric)
        gap = 140
        ys = [545 + 135 * k for k in range(5)]
        self.ramps = []
        for k, y0 in enumerate(ys):
            if k % 2 == 0:
                self.ramps.append((BX0, y0, BX1 - gap, y0 + 78))
            else:
                self.ramps.append((BX1, y0, BX0 + gap, y0 + 78))
        for a in self.ramps:
            self.segs.append((*a, 8, 0.45, 0.0006))
        self.segs.append((BX0, 1245, self.hx, self.hy, 8, 0.4, 0.0006))
        self.segs.append((BX1, 1245, self.hx, self.hy, 8, 0.4, 0.0006))
        self.segs.append((BX0, BY0, BX0, BY1, 6, 0.6, 0.0))
        self.segs.append((BX1, BY0, BX1, BY1, 6, 0.6, 0.0))
        self.pegs = []
        for k in (1, 2, 3):  # floating bumpers above the ramps scatter the pack
            self.pegs.append((CX + rng.uniform(-150, 150), ys[k] - 62, 20))
        for a in self.segs:
            st.append(("line", a[0], a[1], a[2], a[3], a[4] * 2, (70, 200, 120) if a[4] == 8 else WALL))
        for x, y, r in self.pegs:
            st.append(("circle", x, y, r, (255, 190, 70)))
        st += [("circle", self.hx, self.hy + 4, 34, (0, 0, 0)), ("ring", self.hx, self.hy + 4, 34, 4, WHITE),
               ("line", self.hx + 26, self.hy - 6, self.hx + 26, self.hy - 150, 6, WHITE),
               ("poly", [(self.hx + 26, self.hy - 150), (self.hx + 26, self.hy - 112), (self.hx + 92, self.hy - 131)], (255, 60, 90)),
               ("text", "TEE", BX0 + 40, ys[0] - 40, 30, WHITE)]
        for i in range(self.n):
            x = BX0 + 50 + i * 62
            y = self.ramp_y(0, x) - self.r0 - 10
            b = Ball(x, y, self.r0, i, rng.uniform(100, 420), 0)
            b.t0 = rng.uniform(1.0, 2.5)
            b.k = rng.uniform(0.0003, 0.0011)  # rolling friction differs per ball
            self.balls.append(b)

    def ramp_y(self, k, x):
        ax, ay, bx, by = self.ramps[k]
        return ay + (by - ay) * (x - ax) / (bx - ax)

    def tick(self, dt):
        G = self.G
        live = [b for b in self.balls if b.vis]
        for b in live:
            b.vy += G * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            if self.t > b.t0:  # wind gust
                b.t0 = self.t + self.rng.uniform(1.2, 2.6)
                b.vx += self.rng.uniform(-260, 260)
                b.vy -= self.rng.uniform(0, 140)
            for ax, ay, bx, by, half, rest, fric in self.segs:
                s = seg_hit(b, ax, ay, bx, by, half, rest, fric * b.k / 0.0006 if fric else 0.0)
                if s and s > 250:
                    self.ev("bounce", b, gap=0.07)
            for x, y, r in self.pegs:
                s = seg_hit(b, x, y, x, y, r, 0.9)
                if s is not None and s > 60:
                    sp0 = math.hypot(b.vx, b.vy)
                    if sp0 < 380:  # bumper kick keeps balls from perching on top
                        dx, dy = b.x - x, b.y - y
                        d = math.hypot(dx, dy) or 1.0
                        b.vx, b.vy = dx / d * 380, dy / d * 380
                    if s > 250:
                        self.ev("bounce", b, gap=0.07)
            sp = math.hypot(b.vx, b.vy)
            if sp > 1800:
                b.vx, b.vy = b.vx * 1800 / sp, b.vy * 1800 / sp
            if sp < 30 and b.y < self.hy - 60:  # stuck on a peg/ramp lip: shake it loose
                b.aux += dt
                if b.aux > 0.35:
                    b.aux = 0.0
                    b.vx += self.rng.choice((-1, 1)) * self.rng.uniform(120, 260)
                    b.vy -= 160
            else:
                b.aux = 0.0
            if abs(b.x - self.hx) < 30 and b.y > self.hy - self.r0 - 36 and sp < 430:
                b.vis = False
                self.ev("pass", b, x=self.hx, y=self.hy)
                self.win(b.team, b)
        self.collide_balls(0.6, live)

    def yards(self, b):
        return int((abs(b.x - self.hx) * 0.5 + max(0, self.hy - b.y)) / 5)

    def leader(self):
        live = [b for b in self.balls if b.vis]
        return min(live, key=self.yards).team if live else None

    def standings(self):
        rows = sorted((0 if not b.vis else self.yards(b), b.team, b.vis) for b in self.balls)
        return [(t, "IN THE HOLE!" if not vis else f"{y} YD") for y, t, vis in rows]

    def gap(self):
        ds = [math.hypot(b.x - self.hx, b.y - self.hy) for b in self.balls if b.vis]
        return min(ds) / 100 if ds else 9.0


# ====================================================================================================
class Plinko(Arena):
    """Balls drop through a peg board into scoring slots; most points wins."""
    SUB = 4
    G = 1400.0

    def setup(self):
        p, rng = self.p, self.rng
        per = p.get("per_team", 4)
        iv = p.get("interval", 0.85)
        self.sw = (BX1 - BX0) / 9
        self.pegs = []
        for row in range(8):
            y = 585 + row * 80
            if row % 2 == 0:
                xs = [BX0 + self.sw * j for j in range(10)]
            else:
                xs = [BX0 + self.sw * (j + 0.5) for j in range(1, 8)]
            for x in xs:
                self.pegs.append((x, y))
        self.rows = {}
        for x, y in self.pegs:
            self.rows.setdefault(y, []).append((x, y))
        self.row_ys = sorted(self.rows)
        self.vals = rng.sample([5, 10, 10, 20, 25, 50, 50, 100, 250], 9)
        self.floor = BY1
        st = self.static
        st.append(("rect", BX0, BY0, BX1 - BX0, BY1 - BY0, (14, 16, 38)))
        for x, y in self.pegs:
            st.append(("circle", x, y, 11, (170, 180, 255)))
        for j in range(10):
            x = BX0 + self.sw * j
            st.append(("line", x, 1205, x, BY1, 8, WALL))
        st += [("line", BX0, BY0, BX0, BY1, 8, WALL), ("line", BX1, BY0, BX1, BY1, 8, WALL), ("line", BX0, BY1, BX1, BY1, 8, WALL)]
        for j, v in enumerate(self.vals):
            col = (255, 210, 60) if v >= 100 else (255, 150, 60) if v >= 50 else (200, 210, 255)
            st.append(("text", str(v), BX0 + self.sw * (j + 0.5), 1170, 38 if v < 100 else 44, col))
        order = [t for t in range(self.n) for _ in range(per)]
        rng.shuffle(order)
        for i, t in enumerate(order):
            b = Ball(rng.uniform(BX0 + 90, BX1 - 90), BY0 + 25, 22, t, rng.uniform(-140, 140), 80)
            b.t0, b.vis, b.st = i * iv, False, 0
            self.balls.append(b)
        self.stack = [0] * 9
        self.totals = [0] * self.n

    def tick(self, dt):
        G = self.G
        for b in self.balls:
            if b.st == 2:
                continue
            if b.st == 0:
                if self.t < b.t0:
                    continue
                b.st, b.vis = 1, True
            b.vy += G * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x < BX0 + b.r:
                b.x, b.vx = BX0 + b.r, abs(b.vx) * 0.5
            elif b.x > BX1 - b.r:
                b.x, b.vx = BX1 - b.r, -abs(b.vx) * 0.5
            if b.vx * b.vx + b.vy * b.vy < 900 and b.y < 1225:  # perched on a peg: shake it loose
                b.aux += dt
                if b.aux > 0.25:
                    b.aux = 0.0
                    b.vx += self.rng.choice((-1, 1)) * self.rng.uniform(80, 180)
            else:
                b.aux = 0.0
            if b.y < 1225:
                for ry in self.row_ys:
                    if abs(b.y - ry) < 44:
                        for x, y in self.rows[ry]:
                            s = seg_hit(b, x, y, x, y, 11, 0.55)
                            if s and s > 250:
                                self.ev("bounce", b, gap=0.05)
            else:  # inside the slots: dividers
                for j in range(10):
                    xd = BX0 + self.sw * j
                    if abs(b.x - xd) < b.r + 5:
                        seg_hit(b, xd, 1205, xd, BY1, 4, 0.4)
            if b.y > 1262:
                j = min(8, max(0, int((b.x - BX0) / self.sw)))
                self.totals[b.team] += self.vals[j]
                b.st = 2
                b.vx = b.vy = 0.0
                b.x = BX0 + self.sw * (j + 0.5)
                b.y = BY1 - 6 - b.r - self.stack[j] * b.r * 1.7
                self.stack[j] += 1
                self.ev("pass", b, gap=0.04)
        self.collide_balls(0.5, [b for b in self.balls if b.st == 1])
        if self.winner is None and all(b.st == 2 for b in self.balls):
            top = sorted(self.totals, reverse=True)
            if top[0] == top[1]:
                self.failed = True
            else:
                self.win(self.totals.index(top[0]), self.balls[0])

    def leader(self):
        m = max(self.totals)
        return self.totals.index(m) if self.totals.count(m) == 1 else None

    def standings(self):
        return [(t, f"{s} PTS") for s, t in sorted(((s, t) for t, s in enumerate(self.totals)), reverse=True)]

    def gap(self):
        s = sorted(self.totals, reverse=True)
        return (s[0] - s[1]) / 25


# ====================================================================================================
class Race(Arena):
    """Balls drive laps around a stadium track with boost/mud pads and bumping."""
    SUB = 4

    def setup(self):
        p, rng = self.p, self.rng
        self.laps = p.get("laps", 3)
        self.ya, self.yb, self.ri, self.ro = CY - 150, CY + 150, 70, 300
        self.base = p.get("speed", 300.0)
        self.pads = []
        kinds = [1, 1, -1, -1]
        rng.shuffle(kinds)
        for i, kd in enumerate(kinds):
            self.pads.append((wrap(1.0 + i * math.pi / 2 + rng.uniform(-0.25, 0.25)), 0.17, 1.6 if kd > 0 else 0.55, kd))
        st = self.static
        st += [("capsule", CX, self.ya, self.yb, self.ro + 10, WHITE), ("capsule", CX, self.ya, self.yb, self.ro, (52, 54, 78)),
               ("capsule", CX, self.ya, self.yb, self.ri + 10, WHITE), ("capsule", CX, self.ya, self.yb, self.ri, (14, 52, 38))]
        for (am, hw, mult, kd) in self.pads:
            pts = self.sector(am - hw, am + hw)
            st.append(("poly", pts, (40, 200, 90) if kd > 0 else (150, 70, 40)))
        for j in range(10):  # checkered finish line on the right straight
            for k in range(2):
                st.append(("rect", CX + self.ri + j * 20, CY - 10 + k * 10, 20, 10, (255, 255, 255) if (j + k) % 2 == 0 else (0, 0, 0)))
        st.append(("text", "START / FINISH", CX + 200, CY - 38, 26, WHITE))
        for i in range(self.n):
            x = CX + self.ri + 21 + i * (self.ro - self.ri - 42) / max(1, self.n - 1)
            y = CY + 45  # everyone starts on the same line, side by side
            b = Ball(x, y, 21, i, 0.0, -150.0)
            b.aux = (self.base * (1 + rng.uniform(-0.04, 0.04)), rng.uniform(0, TAU), rng.uniform(0, TAU), rng.uniform(0.9, 1.7), rng.uniform(2.0, 3.4))
            b.px = math.atan2(y - CY, x - CX)
            b.score = 0.0  # cumulative angle
            self.balls.append(b)

    def core(self, x, y):
        qy = min(self.yb, max(self.ya, y))
        dx, dy = x - CX, y - qy
        d = math.hypot(dx, dy) or 1e-6
        return d, dx / d, dy / d

    def sector(self, a0, a1):
        def edge(R, ang):
            lo, hi = 0.0, 700.0
            c, s = math.cos(ang), math.sin(ang)
            for _ in range(30):
                mid = (lo + hi) / 2
                if self.core(CX + mid * c, CY + mid * s)[0] < R:
                    lo = mid
                else:
                    hi = mid
            return CX + lo * c, CY + lo * s
        steps = 8
        angs = [a0 + (a1 - a0) * i / steps for i in range(steps + 1)]
        return [edge(self.ri + 2, a) for a in angs] + [edge(self.ro - 2, a) for a in reversed(angs)]

    def prog(self, b):
        return -b.score / TAU

    def tick(self, dt):
        t = self.t
        for b in self.balls:
            d, nx, ny = self.core(b.x, b.y)
            tx, ty = ny, -nx
            vt = b.vx * tx + b.vy * ty
            vn = b.vx * nx + b.vy * ny
            base, ph1, ph2, w1, w2 = b.aux
            tgt = base * (1 + 0.10 * math.sin(w1 * t + ph1) + 0.06 * math.sin(w2 * t + ph2))
            ang = math.atan2(b.y - CY, b.x - CX)
            for am, hw, mult, kd in self.pads:
                if abs(wrap(ang - am)) < hw:
                    tgt *= mult
                    break
            if self.ya < b.y < self.yb:
                pass
            else:
                tgt *= d / ((self.ri + self.ro) / 2)  # same centre-line speed in every lane through the bends
            vt += (tgt - vt) / 0.30 * dt
            vn *= max(0.0, 1 - 4 * dt)
            b.vx, b.vy = vt * tx + vn * nx, vt * ty + vn * ny
            b.x += b.vx * dt
            b.y += b.vy * dt
            d, nx, ny = self.core(b.x, b.y)
            if d > self.ro - b.r or d < self.ri + b.r:
                tgt_d = self.ro - b.r if d > self.ro - b.r else self.ri + b.r
                qy = b.y - ny * d
                b.x, b.y = CX + nx * tgt_d, qy + ny * tgt_d
                vn = b.vx * nx + b.vy * ny
                if (d > self.ro - b.r and vn > 0) or (d < self.ri + b.r and vn < 0):
                    b.vx -= 1.4 * vn * nx
                    b.vy -= 1.4 * vn * ny
                    if abs(vn) > 120:
                        self.ev("bounce", b, gap=0.1)
            a2 = math.atan2(b.y - CY, b.x - CX)
            old = int(self.prog(b))
            b.score += wrap(a2 - b.px)
            b.px = a2
            if int(self.prog(b)) > old and self.prog(b) < self.laps:
                self.ev("pass", b)
            if self.prog(b) >= self.laps:
                self.win(b.team, b)
        self.collide_balls(0.9)

    def leader(self):
        return max(self.balls, key=self.prog).team

    def standings(self):
        rows = sorted(((-self.prog(b), b.team) for b in self.balls))
        return [(t, "FINISH!" if -pr >= self.laps else f"LAP {int(-pr) + 1}/{self.laps}") for pr, t in rows]

    def gap(self):
        ps = sorted((self.prog(b) for b in self.balls), reverse=True)
        return (self.laps - ps[1]) / 0.03 if len(ps) > 1 else 9.0


# ====================================================================================================
class Storm(Arena):
    """Rectangle arena; a storm closes in from the walls and drains the HP of anything it touches."""
    SUB = 4

    def setup(self):
        p, rng = self.p, self.rng
        self.W = BX1 - BX0
        self.rate = p.get("rate", rng.uniform(9.0, 12.0))
        self.tx, self.ty = CX + rng.uniform(-230, 230), CY + rng.uniform(-230, 230)
        self.r0 = 34
        for i in range(self.n):
            a = TAU * i / self.n + rng.uniform(-0.2, 0.2)
            sp = rng.uniform(380, 560)
            va = rng.uniform(0, TAU)
            b = Ball(CX + 230 * math.cos(a), CY + 230 * math.sin(a), self.r0, i, sp * math.cos(va), sp * math.sin(va))
            b.aux = rng.uniform(5.0, 10.0)  # seek strength
            b.score = 1.0  # hp
            b.t0 = rng.uniform(1.0, 2.0)  # next kick
            self.balls.append(b)
        self.deaths = []
        self.static.append(("rect", BX0, BY0, self.W, self.W, (16, 18, 40)))
        self.last_reseek = 0.0

    def edges(self):
        """Safe zone: shrinks and drifts toward a random corner-ish target, so balls have to run to stay inside."""
        t = min(self.t, self.win_t if self.win_t is not None else self.t)
        half = max(95.0, 425.0 - self.rate * t * (1 + t / 45))
        f = min(1.0, t / 24.0)
        zx = min(BX1 - half, max(BX0 + half, CX + (self.tx - CX) * f))
        zy = min(BY1 - half, max(BY0 + half, CY + (self.ty - CY) * f))
        return zx - half, zx + half, zy - half, zy + half

    def tick(self, dt):
        L, R, T, B = self.edges()
        rng = self.rng
        dmg = 0.0 if self.winner is not None else 0.30 + 0.012 * self.t
        reseek = self.t - self.last_reseek > 3.0
        if reseek:
            self.last_reseek = self.t
        live = [b for b in self.balls if not b.dead]
        for b in live:
            if reseek:
                b.aux = rng.uniform(5.0, 10.0)
            b.vx += b.aux * ((L + R) / 2 - b.x) * dt
            b.vy += b.aux * ((T + B) / 2 - b.y) * dt
            if self.t > b.t0:
                b.t0 = self.t + rng.uniform(1.0, 2.2)
                a = rng.uniform(0, TAU)
                b.vx += 380 * math.cos(a)
                b.vy += 380 * math.sin(a)
            sp = math.hypot(b.vx, b.vy)
            if sp > 1100:
                b.vx, b.vy = b.vx * 1100 / sp, b.vy * 1100 / sp
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x < BX0 + b.r:
                b.x, b.vx = BX0 + b.r, abs(b.vx)
                self.ev("bounce", b, gap=0.1)
            elif b.x > BX1 - b.r:
                b.x, b.vx = BX1 - b.r, -abs(b.vx)
                self.ev("bounce", b, gap=0.1)
            if b.y < BY0 + b.r:
                b.y, b.vy = BY0 + b.r, abs(b.vy)
                self.ev("bounce", b, gap=0.1)
            elif b.y > BY1 - b.r:
                b.y, b.vy = BY1 - b.r, -abs(b.vy)
                self.ev("bounce", b, gap=0.1)
            if b.x < L or b.x > R or b.y < T or b.y > B:
                b.score -= dmg * dt
                if b.score <= 0:
                    b.dead, b.vis, b.score = True, False, 0.0
                    self.deaths.append((self.t, b.team))
                    self.ev("pass", b)
        self.collide_balls(1.0, [b for b in live if not b.dead])
        alive = [b for b in self.balls if not b.dead]
        if self.winner is None:
            if len(alive) == 1:
                self.win(alive[0].team, alive[0])
            elif not alive:
                self.failed = True
    def dyn(self):
        L, R, T, B = self.edges()
        red = (84, 12, 30)
        sh = []
        if T > BY0:
            sh.append(("rect", BX0, BY0, self.W, T - BY0, red))
        if B < BY1:
            sh.append(("rect", BX0, B, self.W, BY1 - B, red))
        if L > BX0:
            sh.append(("rect", BX0, T, L - BX0, B - T, red))
        if R < BX1:
            sh.append(("rect", R, T, BX1 - R, B - T, red))
        sh += [("line", L, T, R, T, 6, (255, 255, 255)), ("line", L, B, R, B, 6, (255, 255, 255)),
               ("line", L, T, L, B, 6, (255, 255, 255)), ("line", R, T, R, B, 6, (255, 255, 255))]
        for b in self.balls:  # HP bar over each ball; red ring while it stands in the storm
            if b.dead:
                continue
            if b.x < L or b.x > R or b.y < T or b.y > B:
                sh.append(("ring", b.x, b.y, b.r + 8, 5, (255, 60, 70)))
            hp = max(0.0, b.score)
            col = (70, 230, 110) if hp > 0.5 else (255, 200, 60) if hp > 0.25 else (255, 70, 70)
            sh += [("rect", b.x - 32, b.y - b.r - 24, 64, 11, (20, 20, 30)), ("rect", b.x - 30, b.y - b.r - 22, 60 * hp, 7, col)]
        return sh

    def leader(self):
        alive = [b for b in self.balls if not b.dead]
        return max(alive, key=lambda b: b.score).team if alive else None

    def standings(self):
        rows = sorted(((-b.score, b.team, b.dead) for b in self.balls))
        return [(t, "OUT" if d else f"{int(-s * 100)}% HP") for s, t, d in rows]

    def gap(self):
        w = next((b for b in self.balls if not b.dead), None)
        return w.score / 0.25 if w else 9.0


# ====================================================================================================
class Territory(Arena):
    """Balls paint the grid with their color for a fixed time; most cells wins."""
    SUB = 4
    N = 17

    def setup(self):
        p, rng = self.p, self.rng
        self.T = p.get("duration", 22.0)
        self.cs = (BX1 - BX0) / self.N
        self.owner = [-1] * (self.N * self.N)
        self.counts = [0] * self.n
        speed = p.get("speed", 640.0)
        for i in range(self.n):
            a = TAU * i / self.n + rng.uniform(-0.3, 0.3)
            va = rng.uniform(0, TAU)
            b = Ball(CX + 250 * math.cos(a), CY + 250 * math.sin(a), 36, i, speed * math.cos(va), speed * math.sin(va))
            b.aux = speed * rng.uniform(0.92, 1.08)
            self.balls.append(b)

    def tick(self, dt):
        for b in self.balls:
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x < BX0 + b.r:
                b.x, b.vx = BX0 + b.r, abs(b.vx)
                self.ev("bounce", b, gap=0.1)
            elif b.x > BX1 - b.r:
                b.x, b.vx = BX1 - b.r, -abs(b.vx)
                self.ev("bounce", b, gap=0.1)
            if b.y < BY0 + b.r:
                b.y, b.vy = BY0 + b.r, abs(b.vy)
                self.ev("bounce", b, gap=0.1)
            elif b.y > BY1 - b.r:
                b.y, b.vy = BY1 - b.r, -abs(b.vy)
                self.ev("bounce", b, gap=0.1)
        self.collide_balls(1.0)
        N, cs = self.N, self.cs
        for b in self.balls:
            sp = math.hypot(b.vx, b.vy) or 1.0
            b.vx, b.vy = b.vx * b.aux / sp, b.vy * b.aux / sp
            c0, c1 = int((b.x - b.r - BX0) / cs), int((b.x + b.r - BX0) / cs)
            r0, r1 = int((b.y - b.r - BY0) / cs), int((b.y + b.r - BY0) / cs)
            for r in range(max(0, r0), min(N - 1, r1) + 1):
                for c in range(max(0, c0), min(N - 1, c1) + 1):
                    cx_, cy_ = BX0 + (c + 0.5) * cs - b.x, BY0 + (r + 0.5) * cs - b.y
                    if cx_ * cx_ + cy_ * cy_ < (b.r * 0.9) ** 2:
                        k = r * N + c
                        old = self.owner[k]
                        if old != b.team:
                            if old >= 0:
                                self.counts[old] -= 1
                            self.counts[b.team] += 1
                            self.owner[k] = b.team
        if self.winner is None and self.t >= self.T:
            top = sorted(self.counts, reverse=True)
            if top[0] == top[1]:
                self.failed = True
            else:
                self.win(self.counts.index(top[0]), self.balls[0])

    def grid(self):
        return (BX0, BY0, self.cs, self.N, tuple(self.owner))

    def dyn(self):
        w = (BX1 - BX0) * max(0.0, 1 - self.t / self.T)
        return [("rect", BX0, BY1 + 8, w, 8, WHITE)]

    def leader(self):
        m = max(self.counts)
        return self.counts.index(m) if self.counts.count(m) == 1 else None

    def standings(self):
        tot = self.N * self.N
        return [(t, f"{int(c / tot * 100)}%") for c, t in sorted(((c, t) for t, c in enumerate(self.counts)), reverse=True)]

    def gap(self):
        s = sorted(self.counts, reverse=True)
        return (s[0] - s[1]) / 6


# ====================================================================================================
class Sumo(Arena):
    """Top-down sumo: balls dash at each other on a shrinking platform; last one standing wins."""
    SUB = 4

    def setup(self):
        p, rng = self.p, self.rng
        self.R0, self.Rmin, self.rate = 410.0, 150.0, p.get("shrink", 11.0)
        self.fric = p.get("friction", 3.0)
        for i in range(self.n):
            a = TAU * i / self.n + rng.uniform(-0.2, 0.2)
            b = Ball(CX + 230 * math.cos(a), CY + 230 * math.sin(a), 40, i)
            b.t0 = rng.uniform(0.6, 1.6)
            self.balls.append(b)
        self.falls = []

    def radius(self):
        return max(self.Rmin, self.R0 - self.rate * self.t)

    def tick(self, dt):
        R = self.radius()
        rng = self.rng
        live = [b for b in self.balls if not b.dead]
        for b in self.balls:
            if b.st == 1:  # falling
                b.x += b.vx * dt
                b.y += b.vy * dt
                b.r = max(0.0, 40 * (1 - (self.t - b.aux) / 0.7))
                if b.r <= 1:
                    b.vis, b.dead = False, True
        for b in live:
            if b.st == 1:
                continue
            if self.t > b.t0:
                b.t0 = self.t + rng.uniform(0.9, 1.9)
                others = [o for o in live if o is not b and o.st == 0]
                if others:
                    others.sort(key=lambda o: (o.x - b.x) ** 2 + (o.y - b.y) ** 2)
                    tgt = others[0] if rng.random() < 0.65 or len(others) == 1 else rng.choice(others)
                    ang = math.atan2(tgt.y - b.y, tgt.x - b.x) + rng.uniform(-0.25, 0.25)
                    f = rng.uniform(*self.p.get("dash", (480, 800)))
                    b.vx += f * math.cos(ang)
                    b.vy += f * math.sin(ang)
                    self.ev("bounce", b, gap=0.05)
            k = math.exp(-self.fric * dt)
            b.vx *= k
            b.vy *= k
            sp = math.hypot(b.vx, b.vy)
            if sp > 1600:
                b.vx, b.vy = b.vx * 1600 / sp, b.vy * 1600 / sp
            b.x += b.vx * dt
            b.y += b.vy * dt
        self.collide_balls(0.95, [b for b in live if b.st == 0])
        for b in live:
            if b.st == 0 and math.hypot(b.x - CX, b.y - CY) > R + b.r * 0.25:
                b.st, b.aux = 1, self.t
                self.falls.append((self.t, b.team))
                self.ev("pass", b)
        left = [b for b in self.balls if b.st == 0]
        if self.winner is None:
            if len(left) == 1:
                self.win(left[0].team, left[0])
            elif not left:
                self.failed = True

    def dyn(self):
        R = self.radius()
        return [("circle", CX, CY, R + 16, (90, 100, 190)), ("circle", CX, CY, R, (30, 34, 74)),
                ("ring", CX, CY, R * 0.62, 3, (52, 60, 112)), ("ring", CX, CY, R * 0.28, 3, (52, 60, 112))]

    def leader(self):
        left = [b for b in self.balls if b.st == 0]
        if not left:
            return None
        return min(left, key=lambda b: math.hypot(b.x - CX, b.y - CY)).team

    def standings(self):
        rows = sorted(((b.st, math.hypot(b.x - CX, b.y - CY), b.team) for b in self.balls))
        return [(t, "FELL OFF" if st else "ON THE RING") for st, _, t in rows]

    def gap(self):
        return finale_gap([f[0] for f in self.falls])


# ====================================================================================================
class Tower(Arena):
    """Doodle-jump style: balls auto-jump from moving platforms; first onto the top platform wins."""
    SUB = 6
    G = 1500.0

    def setup(self):
        p, rng = self.p, self.rng
        self.floors = p.get("floors", 8)
        self.hmin, self.hmax = p.get("jump", (180.0, 300.0))
        self.gy = BY1 - 5
        self.plats = []  # (y, w, mid, amp, omega, phase)
        spacing = (self.gy - (BY0 + 60)) / self.floors
        for k in range(1, self.floors + 1):
            w = 255 - 7 * k
            amp = (BX1 - BX0) / 2 - w / 2 - 6
            self.plats.append((self.gy - k * spacing, w, CX, amp, rng.choice((-1, 1)) * rng.uniform(0.7, 1.5), rng.uniform(0, TAU)))
        st = self.static
        st.append(("rect", BX0, BY0, BX1 - BX0, BY1 - BY0, (14, 16, 38)))
        st += [("line", BX0, BY0, BX0, BY1, 8, WALL), ("line", BX1, BY0, BX1, BY1, 8, WALL),
               ("line", BX0, self.gy + 5, BX1, self.gy + 5, 10, (70, 200, 120))]
        st.append(("text", "CROWN", CX, BY0 + 22, 30, (255, 210, 60)))
        for i in range(self.n):
            b = Ball(BX0 + 80 + i * (BX1 - BX0 - 160) / max(1, self.n - 1), self.gy - 40, 28, i, rng.uniform(-100, 100), -rng.uniform(500, 800))
            b.px, b.py = b.x, b.y
            b.k = 0  # best floor reached
            self.balls.append(b)

    def px_mid(self, k):
        y, w, mid, amp, om, ph = self.plats[k]
        return mid + amp * math.sin(om * self.t + ph)

    def tick(self, dt):
        rng = self.rng
        G = self.G
        live = [b for b in self.balls if not b.dead]
        for b in live:
            b.py = b.y
            b.vy += G * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x < BX0 + b.r:
                b.x, b.vx = BX0 + b.r, abs(b.vx)
            elif b.x > BX1 - b.r:
                b.x, b.vx = BX1 - b.r, -abs(b.vx)
            if b.y < BY0 + b.r:
                b.y, b.vy = BY0 + b.r, abs(b.vy) * 0.5
            if b.vy > 0:
                landed = None
                if b.y + b.r >= self.gy and b.py + b.r <= self.gy + 4:
                    landed = (-1, self.gy)
                else:
                    for k, (y, w, mid, amp, om, ph) in enumerate(self.plats):
                        top = y - 7
                        if b.py + b.r <= top + 3 and b.y + b.r >= top and abs(b.x - self.px_mid(k)) <= w / 2 + 6:
                            landed = (k, top)
                            break
                if landed:
                    k, top = landed
                    b.y = top - b.r
                    h = rng.uniform(self.hmin, self.hmax)
                    b.vy = -math.sqrt(2 * G * h)
                    b.vx = rng.uniform(-330, 330)
                    self.ev("bounce", b, gap=0.06)
                    if k + 1 > b.k:
                        b.k = k + 1
                        self.ev("pass", b, gap=0.1)
                    if k + 1 >= self.floors:
                        self.win(b.team, b)
        self.collide_balls(0.9, live)

    def dyn(self):
        sh = []
        for k, (y, w, mid, amp, om, ph) in enumerate(self.plats):
            x = self.px_mid(k)
            top = k + 1 == self.floors
            sh.append(("line", x - w / 2, y, x + w / 2, y, 14, (255, 210, 60) if top else (90, 220, 150)))
        return sh

    def leader(self):
        return max(self.balls, key=lambda b: b.k).team

    def standings(self):
        rows = sorted(((-b.k, b.team) for b in self.balls))
        return [(t, "AT THE TOP!" if -k >= self.floors else f"FLOOR {-k}/{self.floors}") for k, t in rows]

    def gap(self):
        ks = sorted((b.k for b in self.balls), reverse=True)
        return float(self.floors - ks[1]) if len(ks) > 1 else 9.0


# ====================================================================================================
class Chain(Arena):
    """Balls ricochet through a lattice of bombs; every hit sets off a chain reaction credited to the ball."""
    SUB = 6
    G = 900.0

    def setup(self):
        p, rng = self.p, self.rng
        self.T = p.get("duration", 24.0)
        self.pc = p.get("chain", 0.22)
        self.targets = []  # [x, y, state(0 idle,1 armed,2 gone), fire_t, team]
        for j in range(7):
            for i in range(9):
                x = BX0 + 66 + i * 84 + (42 if j % 2 else 0)
                self.targets.append([x, 640 + j * 72, 0, 0.0, -1])
        self.fx = []  # (t0, x, y, team)
        self.score = [0] * self.n
        for i in range(self.n):
            b = Ball(BX0 + 90 + i * (BX1 - BX0 - 180) / max(1, self.n - 1), BY0 + 40, 24, i, rng.uniform(-220, 220), 100)
            self.balls.append(b)
        self.static.append(("rect", BX0, BY0, BX1 - BX0, BY1 - BY0, (14, 16, 38)))
        self.static += [("line", BX0, BY0, BX0, BY1, 8, WALL), ("line", BX1, BY0, BX1, BY1, 8, WALL),
                        ("line", BX0, BY0, BX1, BY0, 8, WALL), ("line", BX0, BY1, BX1, BY1, 8, WALL)]

    def arm(self, tg, team, delay):
        if tg[2] == 0:
            tg[2], tg[3], tg[4] = 1, self.t + delay, team

    def tick(self, dt):
        rng = self.rng
        G = self.G
        for b in self.balls:
            b.vy += G * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            sp = math.hypot(b.vx, b.vy)
            if sp > 1500:
                b.vx, b.vy = b.vx * 1500 / sp, b.vy * 1500 / sp
            if b.x < BX0 + b.r:
                b.x, b.vx = BX0 + b.r, abs(b.vx) * 0.95
            elif b.x > BX1 - b.r:
                b.x, b.vx = BX1 - b.r, -abs(b.vx) * 0.95
            if b.y < BY0 + b.r:
                b.y, b.vy = BY0 + b.r, abs(b.vy) * 0.95
            elif b.y > BY1 - b.r:
                b.y, b.vy = BY1 - b.r, -min(abs(b.vy) * 0.97, 1400) - 250
                if b.vy > -700:
                    b.vy = -700
            for tg in self.targets:
                if tg[2] == 0 and abs(tg[0] - b.x) < 44 and abs(tg[1] - b.y) < 44:
                    s = seg_hit(b, tg[0], tg[1], tg[0], tg[1], 16, 0.9)
                    if s is not None:
                        self.arm(tg, b.team, 0.0)
                        self.ev("bounce", b, gap=0.05)
        self.collide_balls(0.95)
        for tg in self.targets:
            if tg[2] == 2 and self.t >= tg[3] and not any((b.x - tg[0]) ** 2 + (b.y - tg[1]) ** 2 < 70 ** 2 for b in self.balls):
                tg[2] = 0  # bombs regrow so the show lasts the whole round
            if tg[2] == 1 and self.t >= tg[3]:
                tg[2] = 2
                tg[3] = self.t + rng.uniform(3.0, 6.0)
                team = tg[4]
                self.score[team] += 1
                self.fx.append((self.t, tg[0], tg[1], team))
                self.events.append((self.t, "boom", team, 0, tg[0], tg[1]))
                for o in self.targets:
                    if o[2] == 0 and (o[0] - tg[0]) ** 2 + (o[1] - tg[1]) ** 2 < 105 ** 2 and rng.random() < self.pc:
                        self.arm(o, team, rng.uniform(0.08, 0.16))
                for b in self.balls:
                    dx, dy = b.x - tg[0], b.y - tg[1]
                    d = math.hypot(dx, dy)
                    if 0 < d < 130:
                        b.vx += dx / d * 220
                        b.vy += dy / d * 220
        if self.winner is None:
            if self.t >= self.T:
                top = sorted(self.score, reverse=True)
                if top[0] == top[1]:
                    self.failed = True
                else:
                    self.win(self.score.index(top[0]), self.balls[0])

    def dyn(self):
        sh = []
        for tg in self.targets:
            if tg[2] == 0:
                sh.append(("circle", tg[0], tg[1], 16, (200, 206, 235)))
            elif tg[2] == 1:
                sh.append(("circle", tg[0], tg[1], 19, ("t", tg[4], 1.0)))
        keep = []
        for fx in self.fx:
            age = self.t - fx[0]
            if age < 0.4:
                keep.append(fx)
                sh.append(("ring", fx[1], fx[2], 20 + 100 * age / 0.4, 6, ("t", fx[3], 1 - age / 0.4)))
        self.fx = keep
        return sh

    def leader(self):
        m = max(self.score)
        return self.score.index(m) if self.score.count(m) == 1 else None

    def standings(self):
        return [(t, f"{s} BOOMS") for s, t in sorted(((s, t) for t, s in enumerate(self.score)), reverse=True)]

    def gap(self):
        s = sorted(self.score, reverse=True)
        return (s[0] - s[1]) / 4


# ====================================================================================================
class Flip(Arena):
    """Gravity keeps changing direction; the walls have spike patches. Last ball alive wins."""
    SUB = 6

    def setup(self):
        p, rng = self.p, self.rng
        self.g = p.get("gravity", 1500.0)
        self.period = p.get("period", 3.1)
        sw = p.get("spike_w", 85.0)
        self.zones = {}  # side -> [(a, b)] along-wall coordinate ranges
        for side in ("t", "b", "l", "r"):
            lo, hi = (BX0, BX1) if side in "tb" else (BY0, BY1)
            zs = []
            for _ in range(2):
                for _try in range(20):
                    a = rng.uniform(lo + 20, hi - 20 - sw)
                    if all(a > z[1] + 40 or a + sw < z[0] - 40 for z in zs):
                        zs.append((a, a + sw))
                        break
            self.zones[side] = zs
        st = self.static
        st.append(("rect", BX0, BY0, BX1 - BX0, BY1 - BY0, (14, 16, 38)))
        for side, zs in self.zones.items():
            for a, b in zs:
                n = 4
                for k in range(n):
                    x0, x1 = a + (b - a) * k / n, a + (b - a) * (k + 1) / n
                    xm = (x0 + x1) / 2
                    if side == "t":
                        pts = [(x0, BY0), (x1, BY0), (xm, BY0 + 40)]
                    elif side == "b":
                        pts = [(x0, BY1), (x1, BY1), (xm, BY1 - 40)]
                    elif side == "l":
                        pts = [(BX0, x0), (BX0, x1), (BX0 + 40, xm)]
                    else:
                        pts = [(BX1, x0), (BX1, x1), (BX1 - 40, xm)]
                    st.append(("poly", pts, (255, 60, 80)))
        st += [("line", BX0, BY0, BX1, BY0, 6, WALL), ("line", BX0, BY1, BX1, BY1, 6, WALL),
               ("line", BX0, BY0, BX0, BY1, 6, WALL), ("line", BX1, BY0, BX1, BY1, 6, WALL)]
        self.dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        self.gi = 0
        self.next_flip = self.period
        self.nxt = 1
        for i in range(self.n):
            fb = Ball(BX0 + 120 + i * (BX1 - BX0 - 240) / max(1, self.n - 1), CY + rng.uniform(-80, 80), 30, i, rng.uniform(-300, 300), rng.uniform(-300, 300))
            self.balls.append(fb)
        self.deaths = []

    def tick(self, dt):
        rng = self.rng
        if self.t >= self.next_flip:
            self.gi = self.nxt
            self.nxt = rng.choice([k for k in range(4) if k != self.gi])
            self.next_flip += self.period
            for b in self.balls:
                if not b.dead:
                    b.st = 1
                    a = rng.uniform(0, TAU)
                    s = rng.uniform(150, 420)
                    b.vx += s * math.cos(a)
                    b.vy += s * math.sin(a)
        gx, gy = self.dirs[self.gi]
        live = [b for b in self.balls if not b.dead]
        for b in live:
            b.vx += gx * self.g * dt
            b.vy += gy * self.g * dt
            sp = math.hypot(b.vx, b.vy)
            if sp > 1900:
                b.vx, b.vy = b.vx * 1900 / sp, b.vy * 1900 / sp
            b.x += b.vx * dt
            b.y += b.vy * dt
            hit = None
            hs = math.hypot(b.vx, b.vy)
            if b.x < BX0 + b.r:
                b.x, hit = BX0 + b.r, "l"
                b.vx = abs(b.vx) * 0.82
            elif b.x > BX1 - b.r:
                b.x, hit = BX1 - b.r, "r"
                b.vx = -abs(b.vx) * 0.82
            if b.y < BY0 + b.r:
                b.y, hit = BY0 + b.r, "t"
                b.vy = abs(b.vy) * 0.82
            elif b.y > BY1 - b.r:
                b.y, hit = BY1 - b.r, "b"
                b.vy = -abs(b.vy) * 0.82
            if hit:
                along = b.x if hit in "tb" else b.y
                armed, b.st = b.st == 1, 0  # spikes only get you on the first touch after a flip
                if armed and self.winner is None and any(a - 8 <= along <= bb + 8 for a, bb in self.zones[hit]):
                    b.dead, b.vis = True, False
                    self.deaths.append(self.t)
                    self.ev("pass", b)
                elif abs(b.vx) + abs(b.vy) > 200:
                    self.ev("bounce", b, gap=0.08)
        self.collide_balls(0.9, [b for b in live if not b.dead])
        alive = [b for b in self.balls if not b.dead]
        if self.winner is None:
            if len(alive) == 1:
                self.win(alive[0].team, alive[0])
            elif not alive:
                self.failed = True

    def dyn(self):
        def arrow(dirn, col, s):
            dx, dy = dirn
            px, py = -dy, dx
            tip = (CX + dx * 90 * s, CY + dy * 90 * s)
            b1 = (CX - dx * 20 * s + px * 70 * s, CY - dy * 20 * s + py * 70 * s)
            b2 = (CX - dx * 20 * s - px * 70 * s, CY - dy * 20 * s - py * 70 * s)
            return ("poly", [tip, b1, b2], col)
        sh = [arrow(self.dirs[self.gi], (34, 38, 78), 1.6)]
        if self.next_flip - self.t < 0.9:
            sh.append(arrow(self.dirs[self.nxt], (255, 210, 60), 1.0))
        return sh

    def leader(self):
        alive = [b for b in self.balls if not b.dead]
        return alive[0].team if len(alive) == 1 else None

    def standings(self):
        rows = sorted(((b.dead, b.team) for b in self.balls))
        return [(t, "DEAD" if d else "ALIVE") for d, t in rows]

    def gap(self):
        return finale_gap(self.deaths)


# ====================================================================================================
class Pinball(Arena):
    """Pinball table with bumpers and auto flippers; each ball has one life, highest score wins."""
    SUB = 8
    G = 1250.0

    def setup(self):
        p, rng = self.p, self.rng
        self.T = p.get("duration", 26.0)
        self.walls = [(BX0, 600, BX0 + 110, BY0), (BX1, 600, BX1 - 110, BY0), (BX0 + 110, BY0, BX1 - 110, BY0),
                      (BX0, 600, BX0, 1140), (BX1, 600, BX1, 1140), (BX0, 1140, 335, 1245), (BX1, 1140, 745, 1245)]
        self.bumpers = [(330, 710, 44, 100), (750, 710, 44, 100), (540, 830, 48, 100), (300, 960, 38, 100), (780, 960, 38, 100), (540, 1040, 34, 100)]
        self.posts = [(210, 830), (870, 830), (430, 960), (650, 960), (540, 640), (440, 740), (640, 740)]
        # flippers: pivot, length, rest angle, up angle
        self.fl = [{"px": 335.0, "py": 1250.0, "L": 150.0, "rest": 0.52, "up": -0.52, "a": 0.52, "hold": 0.0, "w": 0.0},
                   {"px": 745.0, "py": 1250.0, "L": 150.0, "rest": math.pi - 0.52, "up": math.pi + 0.52, "a": math.pi - 0.52, "hold": 0.0, "w": 0.0}]
        st = self.static
        st.append(("rect", BX0, BY0, BX1 - BX0, BY1 - BY0, (14, 16, 38)))
        for a in self.walls:
            st.append(("line", *a, 12, WALL))
        for x, y, r, pts in self.bumpers:
            st += [("circle", x, y, r + 8, (255, 90, 160)), ("circle", x, y, r, (255, 210, 80)), ("text", "100", x, y, 30, (80, 30, 50))]
        for x, y in self.posts:
            st.append(("circle", x, y, 12, (170, 180, 255)))
        for i in range(self.n):
            b = Ball(rng.uniform(BX0 + 160, BX1 - 160), BY0 + 40, 22, i, rng.uniform(-200, 200), 150)
            b.t0, b.vis, b.st = i * 0.75, False, 0
            self.balls.append(b)

    def tip(self, f):
        return f["px"] + f["L"] * math.cos(f["a"]), f["py"] + f["L"] * math.sin(f["a"])

    def tick(self, dt):
        G = self.G
        live = [b for b in self.balls if b.vis and not b.dead]
        for f in self.fl:  # auto flipper
            trig = False
            tx, ty = self.tip(f)
            for b in live:
                if b.y > 1130 and b.vy > -150 and math.hypot(b.x - (f["px"] + tx) / 2, b.y - (f["py"] + ty) / 2) < 105:
                    trig = True
            if trig:
                f["hold"] = self.t + 0.26
            target = f["up"] if self.t < f["hold"] else f["rest"]
            diff = target - f["a"]
            step = 18.0 * dt
            if abs(diff) <= step:
                f["w"] = 0.0
                f["a"] = target
            else:
                f["w"] = 18.0 * (1 if diff > 0 else -1)
                f["a"] += f["w"] * dt
        for b in self.balls:
            if b.st == 0 and self.t >= b.t0:
                b.st, b.vis = 1, True
        live = [b for b in self.balls if b.vis and not b.dead]
        for b in live:
            b.vy += G * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            sp = math.hypot(b.vx, b.vy)
            if sp > 1900:
                b.vx, b.vy = b.vx * 1900 / sp, b.vy * 1900 / sp
            for a in self.walls:
                s = seg_hit(b, *a, 6, 0.55)
                if s and s > 250:
                    self.ev("bounce", b, gap=0.08)
            for x, y in self.posts:
                s = seg_hit(b, x, y, x, y, 12, 0.7)
                if s and s > 200:
                    b.score += 10
                    self.ev("bounce", b, gap=0.06)
            for x, y, r, pts in self.bumpers:
                s = seg_hit(b, x, y, x, y, r, 1.0)
                if s is not None and s > 80:
                    dx, dy = b.x - x, b.y - y
                    d = math.hypot(dx, dy) or 1.0
                    sp = math.hypot(b.vx, b.vy)
                    if sp < 820:
                        b.vx, b.vy = dx / d * 820, dy / d * 820
                    b.score += pts
                    self.ev("pass", b, gap=0.05)
            for f in self.fl:
                tx, ty = self.tip(f)
                # contact point velocity from angular speed (approx at ball projection)
                rx, ry = b.x - f["px"], b.y - f["py"]
                svx, svy = -f["w"] * ry, f["w"] * rx
                s = seg_hit(b, f["px"], f["py"], tx, ty, 11, 0.5, 0.0, svx, svy)
                if s and s > 120:
                    self.ev("bounce", b, gap=0.08)
            if b.y > BY1 + 40:
                b.dead, b.vis = True, False
                self.ev("pass", b, x=b.x, y=BY1 - 20)
        self.collide_balls(0.8, [b for b in live if not b.dead])
        if self.winner is None:
            pending = any((b.st == 0) or (b.vis and not b.dead) for b in self.balls)
            if self.t >= self.T or not pending:
                tot = [0] * self.n
                for b in self.balls:
                    tot[b.team] += b.score
                top = sorted(tot, reverse=True)
                if top[0] == top[1]:
                    self.failed = True
                else:
                    self.win(tot.index(top[0]), self.balls[0])

    def dyn(self):
        sh = []
        for f in self.fl:
            tx, ty = self.tip(f)
            sh.append(("line", f["px"], f["py"], tx, ty, 22, (255, 255, 255)))
            sh.append(("circle", f["px"], f["py"], 14, (255, 90, 160)))
        return sh

    def leader(self):
        m = max(b.score for b in self.balls)
        w = [b.team for b in self.balls if b.score == m]
        return w[0] if len(w) == 1 else None

    def standings(self):
        return [(b.team, f"{b.score} PTS") for b in sorted(self.balls, key=lambda b: -b.score)]

    def gap(self):
        s = sorted((b.score for b in self.balls), reverse=True)
        return (s[0] - s[1]) / 150


# ====================================================================================================
class Hole(Arena):
    """A black hole in the middle of a round arena swallows the balls; last survivor wins."""
    SUB = 6

    def setup(self):
        p, rng = self.p, self.rng
        self.mu0 = p.get("pull", 8.0e6)
        self.AR = 410
        self.drag = p.get("drag", 0.12)
        for i in range(self.n):
            a = TAU * i / self.n + rng.uniform(-0.25, 0.25)
            d = rng.uniform(260, 340)
            sp = rng.uniform(430, 620)
            dirn = rng.choice((-1, 1))
            b = Ball(CX + d * math.cos(a), CY + d * math.sin(a), 34, i, -dirn * sp * math.sin(a), dirn * sp * math.cos(a))
            b.t0 = rng.uniform(0.8, 2.0)
            self.balls.append(b)
        rs = random.Random(5)
        self.static.append(("rect", 0, BY0 - 20, 1080, BY1 - BY0 + 40, (8, 8, 22)))
        for _ in range(70):
            self.static.append(("circle", rs.uniform(30, 1050), rs.uniform(BY0, BY1), rs.choice((1, 2, 2, 3)), (120, 120, 170)))
        self.static.append(("ring", CX, CY, self.AR + 8, 8, (90, 70, 160)))
        self.eaten = []

    def te(self):
        return self.t if self.win_t is None else self.win_t

    def hr(self):
        return 52 + 2.0 * self.te()

    def tick(self, dt):
        rng = self.rng
        mu = self.mu0 * (1 + 0.035 * self.t) if self.winner is None else 0.0
        hr = self.hr()
        live = [b for b in self.balls if not b.dead]
        for b in self.balls:
            if b.st == 1:
                b.r = max(0.0, 34 * (1 - (self.t - b.aux) / 0.6))
                if b.r <= 1:
                    b.vis, b.dead = False, True
        for b in live:
            dx, dy = CX - b.x, CY - b.y
            d = math.hypot(dx, dy) or 1.0
            a = mu / (d * d + 3000)
            b.vx += dx / d * a * dt
            b.vy += dy / d * a * dt
            if b.st == 0:
                k = math.exp(-self.drag * dt)
                b.vx *= k
                b.vy *= k
                if self.t > b.t0:
                    b.t0 = self.t + rng.uniform(1.1, 2.4)
                    ang = rng.uniform(0, TAU)
                    s = rng.uniform(300, 650)
                    b.vx += s * math.cos(ang)
                    b.vy += s * math.sin(ang)
            sp = math.hypot(b.vx, b.vy)
            if sp > 2200:
                b.vx, b.vy = b.vx * 2200 / sp, b.vy * 2200 / sp
            b.x += b.vx * dt
            b.y += b.vy * dt
            d = math.hypot(b.x - CX, b.y - CY)
            if d > self.AR - b.r and b.st == 0:
                nx, ny = (b.x - CX) / d, (b.y - CY) / d
                b.x, b.y = CX + nx * (self.AR - b.r), CY + ny * (self.AR - b.r)
                vn = b.vx * nx + b.vy * ny
                if vn > 0:
                    b.vx -= 1.9 * vn * nx
                    b.vy -= 1.9 * vn * ny
                    self.ev("bounce", b, gap=0.1)
            if b.st == 0 and d < hr + b.r * 0.2:
                b.st, b.aux = 1, self.t
                self.eaten.append(self.t)
                self.ev("pass", b)
        self.collide_balls(0.95, [b for b in live if b.st == 0])
        alive = [b for b in self.balls if b.st == 0]
        if self.winner is None:
            if len(alive) == 1:
                self.win(alive[0].team, alive[0])
            elif not alive:
                self.failed = True

    def dyn(self):
        hr = self.hr()
        sh = [("circle", CX, CY, hr + 46, (22, 12, 52)), ("circle", CX, CY, hr + 24, (48, 18, 96)),
              ("circle", CX, CY, hr + 8, (110, 50, 190)), ("circle", CX, CY, hr, (0, 0, 0))]
        for arm in range(3):
            base = self.t * 2.4 + arm * TAU / 3
            prev = None
            for k in range(18):
                rr = hr + 10 + k * 15
                ang = base - k * 0.22
                pt = (CX + rr * math.cos(ang), CY + rr * math.sin(ang))
                if prev:
                    sh.append(("line", prev[0], prev[1], pt[0], pt[1], max(2, 9 - k // 2), (150, 100, 240)))
                prev = pt
        return sh

    def leader(self):
        alive = [b for b in self.balls if b.st == 0]
        if not alive:
            return None
        return max(alive, key=lambda b: math.hypot(b.x - CX, b.y - CY)).team

    def standings(self):
        rows = sorted(((b.st, -math.hypot(b.x - CX, b.y - CY), b.team) for b in self.balls))
        return [(t, "SWALLOWED" if st else "ALIVE") for st, _, t in rows]

    def gap(self):
        return finale_gap(self.eaten)


MODES = {"maze": Maze, "golf": Golf, "plinko": Plinko, "race": Race, "storm": Storm, "territory": Territory,
         "sumo": Sumo, "tower": Tower, "chain": Chain, "flip": Flip, "pinball": Pinball, "hole": Hole}
TRIES = {"maze": 80, "golf": 50, "plinko": 50, "race": 50, "storm": 50, "territory": 60, "sumo": 60, "tower": 50,
         "chain": 50, "flip": 60, "pinball": 40, "hole": 60}


def simulate(mode, teams, seed, p, max_s=60.0, tail_s=3.5):
    w = MODES[mode](teams, seed, p)
    frames = []
    while w.t < max_s:
        w.step()
        frames.append(w.snapshot(first=not frames))
        if w.failed:
            return None
        if w.win_t is not None and w.after >= tail_s * FPS:
            return frames, w.events, w.winner, w.win_t
    return None


def stats(mode, teams, seed, p, max_s=60.0):
    w = MODES[mode](teams, seed, p)
    while w.t < max_s and w.win_t is None and not w.failed:
        w.step()
    if w.win_t is None:
        return None
    return {"t": w.win_t, "runner_up_gap": w.gap(), "movers": w.lead_changes}

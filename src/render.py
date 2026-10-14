"""Replays a recorded simulation into a 1080x1920 60fps MP4 (pygame -> ffmpeg pipe)."""
import math
import os
import random
import subprocess
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
import pygame.gfxdraw as gfx  # noqa: E402

from physics import FPS  # noqa: E402

W, H = 1080, 1920
CX, CY, ARENA_R = 540, 900, 420
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "assets", "fonts", "Anton-Regular.ttf")
PALETTE = ["#FF3B5C", "#3C8CFF", "#3DFF8C", "#FFD23F", "#B45CFF", "#FF8A2B", "#2BE7FF", "#FF5CD1"]
BG_TOP, BG_BOT = (12, 10, 30), (4, 4, 12)


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Painter:
    def __init__(self, teams, colors, hook, mode, cta):
        pygame.font.init()
        self.teams, self.mode, self.cta = teams, mode, cta
        self.colors = [hexc(c) for c in colors]
        self.bg = pygame.Surface((W, H))
        for y in range(H):
            pygame.draw.line(self.bg, mix(BG_TOP, BG_BOT, y / H), (0, y), (W, y))
        self.fonts = {}
        self.label_cache = {}
        self.glow = {}
        self.trails = [deque(maxlen=9) for _ in teams]
        self.particles = []
        self.rng = random.Random(1)
        self.hook_surfs = self._wrap(hook.upper(), 92, W - 120, (255, 255, 255))

    def font(self, size):
        size = max(10, int(size))
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(FONT, size)
        return self.fonts[size]

    def _wrap(self, text, size, maxw, color):
        f = self.font(size)
        lines, cur = [], ""
        for word in text.split():
            trial = (cur + " " + word).strip()
            if f.size(trial)[0] <= maxw:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        if len(lines) > 2:
            return self._wrap(text, size - 8, maxw, color)
        return [self._outlined(l, f, color) for l in lines]

    def _outlined(self, text, f, color, ow=5):
        base = f.render(text, True, color)
        out = pygame.Surface((base.get_width() + ow * 2, base.get_height() + ow * 2), pygame.SRCALPHA)
        edge = f.render(text, True, (0, 0, 0))
        for dx in range(-ow, ow + 1, 2):
            for dy in range(-ow, ow + 1, 2):
                if dx * dx + dy * dy <= ow * ow:
                    out.blit(edge, (dx + ow, dy + ow))
        out.blit(base, (ow, ow))
        return out

    def glow_sprite(self, team, r):
        key = (team, int(r))
        if key not in self.glow:
            gr = int(r * 2.2)
            s = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            c = self.colors[team % len(self.colors)]
            for i in range(gr, int(r * 0.9), -3):
                a = int(70 * (1 - (i - r) / (gr - r)) ** 2)
                gfx.filled_circle(s, gr, gr, i, (*c, max(0, min(255, a // 3))))
            self.glow[key] = s
        return self.glow[key]

    def label(self, team, r):
        key = (team, int(r))
        if key not in self.label_cache:
            name = self.teams[team].upper()
            size = r * 0.78
            f = self.font(size)
            while f.size(name)[0] > r * 1.75 and size > 12:
                size -= 2
                f = self.font(size)
            self.label_cache[key] = self._outlined(name, f, (255, 255, 255), 2)
        return self.label_cache[key]

    def ring(self, surf, R, thick, gap, ang, color):
        half = thick / 2
        if gap <= 0:
            for k in range(int(thick)):
                gfx.aacircle(surf, CX, CY, int(R - half + k), color)
            return
        a0, a1 = ang + gap / 2, ang + math.tau - gap / 2
        n = 140
        pts_o = [(CX + (R + half) * math.cos(a0 + (a1 - a0) * i / n), CY + (R + half) * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        pts_i = [(CX + (R - half) * math.cos(a0 + (a1 - a0) * i / n), CY + (R - half) * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n, -1, -1)]
        poly = pts_o + pts_i
        gfx.aapolygon(surf, poly, color)
        gfx.filled_polygon(surf, poly, color)

    def spawn_burst(self, x, y, team, n):
        c = self.colors[team % len(self.colors)]
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            s = self.rng.uniform(150, 900)
            self.particles.append([x, y, s * math.cos(a), s * math.sin(a), self.rng.uniform(0.4, 1.1), c])

    def draw(self, surf, fr, idx, win_frame, winner, standings):
        surf.blit(self.bg, (0, 0))
        y = 210
        for s in self.hook_surfs:
            surf.blit(s, ((W - s.get_width()) // 2, y))
            y += s.get_height() - 18
        nr = len(fr["rings"])
        for i, (R, thick, gap, ang) in enumerate(fr["rings"]):
            hue = (190 + 120 * i / max(1, nr - 1)) % 360
            c = pygame.Color(0)
            c.hsva = (hue, 75, 100, 100)
            self.ring(surf, R, thick, gap, ang, (c.r, c.g, c.b))
        for x, y2, r, team, alive in fr["balls"]:
            if not alive:
                continue
            col = self.colors[team % len(self.colors)]
            tr = self.trails[team]
            for k, (tx, ty) in enumerate(tr):
                f = (k + 1) / (len(tr) + 1)
                gfx.filled_circle(surf, int(tx), int(ty), max(2, int(r * f * 0.8)), mix(BG_BOT, col, f * 0.55))
            tr.append((x, y2))
            g = self.glow_sprite(team, r)
            surf.blit(g, (int(x - g.get_width() / 2), int(y2 - g.get_height() / 2)))
            gfx.filled_circle(surf, int(x), int(y2), int(r), col)
            gfx.aacircle(surf, int(x), int(y2), int(r), mix(col, (255, 255, 255), 0.5))
            gfx.filled_circle(surf, int(x - r * 0.35), int(y2 - r * 0.4), max(2, int(r * 0.22)), mix(col, (255, 255, 255), 0.6))
            lab = self.label(team, r)
            surf.blit(lab, (int(x - lab.get_width() / 2), int(y2 - lab.get_height() / 2)))
        dt = 1 / FPS
        alive = []
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 900 * dt
            p[4] -= dt
            if p[4] > 0:
                gfx.filled_circle(surf, int(p[0]), int(p[1]), max(2, int(13 * p[4])), p[5])
                alive.append(p)
        self.particles = alive
        self.scoreboard(surf, standings)
        if win_frame is not None and idx >= win_frame:
            self.banner(surf, winner, (idx - win_frame) / FPS)

    def scoreboard(self, surf, standings):
        f = self.font(40)
        rows = standings[:8]
        cols = 2 if len(rows) > 4 else 1
        per = math.ceil(len(rows) / cols)
        for i, (team, text) in enumerate(rows):
            col, row = divmod(i, per)
            x = 90 + col * 470 if cols == 2 else 260
            y = 1360 + row * 52
            gfx.filled_circle(surf, x, y + 26, 14, self.colors[team % len(self.colors)])
            s = f.render(f"{self.teams[team].upper()}  {text}", True, (235, 235, 245))
            surf.blit(s, (x + 28, y + 2))

    def banner(self, surf, winner, t):
        k = min(1.0, t / 0.35)
        size = int(70 + 70 * k)
        col = self.colors[winner % len(self.colors)]
        title = self._outlined(f"{self.teams[winner].upper()} WINS!", self.font(size), col, 6)
        box = pygame.Surface((W, 330), pygame.SRCALPHA)
        box.fill((0, 0, 0, int(170 * k)))
        surf.blit(box, (0, CY - 170))
        surf.blit(title, ((W - title.get_width()) // 2, CY - 150))
        if t > 0.6:
            sub = self._outlined(self.cta.upper(), self.font(50), (255, 255, 255), 4)
            surf.blit(sub, ((W - sub.get_width()) // 2, CY + 50))


def standings_for(mode, fr, teams, target_r):
    if mode == "escape":
        rows = []
        for (x, y, r, team, alive), layer in zip(fr["balls"], fr["layers"]):
            rows.append((layer, team, "ESCAPED!" if not alive else f"{layer} RING{'S' if layer != 1 else ''} LEFT"))
        rows.sort()
        return [(t, txt) for _, t, txt in rows]
    rows = sorted(((-r, team) for x, y, r, team, alive in fr["balls"]))
    return [(team, f"{min(100, int(-nr / target_r * 100))}%") for nr, team in rows]


def render(sim, job, out_mp4, audio_wav, preview_dir=None):
    frames, events, winner, win_t = sim
    painter = Painter(job["teams"], job["colors"], job["hook"], job["mode"], job["cta"])
    win_frame = int(win_t * FPS)
    ev_by_frame = {}
    for e in events:
        if e[1] in ("pass", "win"):
            ev_by_frame.setdefault(int(e[0] * FPS), []).append(e)
    surf = pygame.Surface((W, H))
    target_r = job["params"].get("target_r", 120)
    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        picks = {30, len(frames) // 2, min(len(frames) - 1, win_frame + 50)}
        for i, fr in enumerate(frames):
            for e in ev_by_frame.get(i, ()):
                painter.spawn_burst(e[4], e[5], e[2], 60 if e[1] == "win" else 18)
            painter.draw(surf, fr, i, win_frame, winner, standings_for(job["mode"], fr, job["teams"], target_r))
            if i in picks:
                pygame.image.save(surf, os.path.join(preview_dir, f"frame_{i:05d}.png"))
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", audio_wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i, fr in enumerate(frames):
        for e in ev_by_frame.get(i, ()):
            painter.spawn_burst(e[4], e[5], e[2], 60 if e[1] == "win" else 18)
        painter.draw(surf, fr, i, win_frame, winner, standings_for(job["mode"], fr, job["teams"], target_r))
        proc.stdin.write(pygame.image.tobytes(surf, "RGB"))
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")

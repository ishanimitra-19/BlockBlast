#!/usr/bin/env python3
"""
Block Blast viewer — draws the game streamed from the ESP32 over USB serial.

    pip3 install pygame pyserial numpy
    python3 viewer.py            # auto-detects the port
    python3 viewer.py /dev/cu.usbserial-XXXX   # or pass it explicitly

Close the Arduino Serial Monitor first — only one program can own the port.
Press M to mute/unmute music.
"""
import sys, time, os, json, math
import pygame
import serial
from serial.tools import list_ports

try:
    import numpy as np
except ImportError:
    np = None

BAUD = 115200
CELL = 60
GRID = 8
PAD  = 30
PANEL_W = 300
W = PAD * 2 + CELL * GRID + PANEL_W
H = PAD * 2 + CELL * GRID
HISCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.json")

COLORS = {
    0: (36, 40, 56),
    1: (255, 99, 132), 2: (54, 162, 235), 3: (255, 206, 86),
    4: (75, 192, 120), 5: (153, 102, 255), 6: (255, 159, 64), 7: (0, 200, 200),
}
BG, GRIDLINE, TEXT, DIM, GOLD = (24, 26, 36), (60, 64, 84), (240, 240, 240), (120, 125, 150), (255, 220, 90)


# ---------------------------------------------------------------- audio
class Audio:
    """Tiny synth: a looping chiptune bassline + blips. Needs numpy; silent otherwise."""
    def __init__(self):
        self.ok = False
        self.muted = False
        self.sfx_place = self.sfx_clear = self.sfx_pick = self.sfx_over = self.sfx_hi = None
        if np is None:
            return
        try:
            pygame.mixer.pre_init(22050, -16, 1, 512)
            pygame.mixer.init()
            self.rate = 22050
            self.music = self._make_music()
            self.sfx_place = self._tone([(660, 0.06), (880, 0.08)], 0.35)
            self.sfx_clear = self._tone([(523, 0.07), (659, 0.07), (784, 0.07), (1047, 0.14)], 0.45)
            self.sfx_pick  = self._tone([(440, 0.05)], 0.25)
            self.sfx_over  = self._tone([(392, 0.15), (330, 0.15), (262, 0.3)], 0.4)
            self.sfx_hi    = self._tone([(784, 0.08), (988, 0.08), (1175, 0.08), (1568, 0.25)], 0.5)
            self.ok = True
            self.music.play(loops=-1)
        except Exception:
            self.ok = False

    def _wave(self, freq, dur, vol, kind="square"):
        n = int(self.rate * dur)
        t = np.arange(n) / self.rate
        if kind == "square":
            w = np.sign(np.sin(2 * math.pi * freq * t))
        elif kind == "tri":
            w = 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
        else:
            w = np.sin(2 * math.pi * freq * t)
        env = np.minimum(1, np.minimum(t / 0.005, (dur - t) / 0.03))   # click-free edges
        return w * env * vol

    def _sound(self, buf):
        pcm = (np.clip(buf, -1, 1) * 32767).astype(np.int16)
        ch = pygame.mixer.get_init()[2]
        if ch > 1:
            pcm = np.repeat(pcm[:, None], ch, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))

    def _tone(self, notes, vol):
        return self._sound(np.concatenate([self._wave(f, d, vol) for f, d in notes]))

    def _make_music(self):
        # "Korobeiniki" (Russian folk song, 1860s, public domain) - A section, A minor, 150 BPM
        bpm = 150; q = 60 / bpm; e = q / 2
        N = {"E5":659.3,"B4":493.9,"C5":523.3,"D5":587.3,"A4":440.0,"F5":698.5,"G5":784.0,"E4":329.6,
             "A2":110.0,"E3":164.8,"G2":98.0,"D3":146.8,"C3":130.8,"G3":196.0,"F2":87.3,"A3":220.0,"B2":123.5}
        lead = [("E5",q),("B4",e),("C5",e),("D5",q),("C5",e),("B4",e),
                ("A4",q),("A4",e),("C5",e),("E5",q),("D5",e),("C5",e),
                ("B4",q+e),("C5",e),("D5",q),("E5",q),
                ("C5",q),("A4",q),("A4",q),("A4",e),("B4",e),("C5",e),
                ("D5",q+e),("F5",e),("G5",q),("A4",e),("G5",e),
                ("F5",e),("E5",q+e),("C5",e),("E5",q),("D5",e),("C5",e),
                ("B4",q),("B4",e),("C5",e),("D5",q),("E5",q),
                ("C5",q),("A4",q),("A4",q),(None,q)]
        bass = [("A2",e),("E3",e)]*4 + [("G2",e),("D3",e)]*2 + [("C3",e),("G3",e)]*2 + \
               [("A2",e),("E3",e)]*4 + [("D3",e),("A3",e)]*2 + [("F2",e),("C3",e)]*2 + \
               [("C3",e),("G3",e)]*2 + [("G2",e),("D3",e)]*2 + [("A2",e),("E3",e)]*4
        def seq(notes, vol, kind):
            return np.concatenate([self._wave(N[n], d, vol, kind) if n else np.zeros(int(self.rate*d)) for n, d in notes])
        l = seq(lead, 0.09, "square")
        b = seq(bass, 0.16, "tri")
        n = min(len(l), len(b))
        return self._sound(l[:n] + b[:n])

    def play(self, s):
        if self.ok and not self.muted and s is not None:
            s.play()

    def toggle_mute(self):
        if not self.ok:
            return
        self.muted = not self.muted
        self.music.set_volume(0 if self.muted else 1)


# ---------------------------------------------------------------- state
def find_port():
    for p in list_ports.comports():
        d = (p.device + " " + (p.description or "")).lower()
        if any(k in d for k in ("usbserial", "wchusb", "slab", "cp210", "ch340", "ttyusb", "ttyacm", "usbmodem")):
            return p.device
    ports = list_ports.comports()
    return ports[0].device if ports else None


def load_hiscore():
    try:
        with open(HISCORE_FILE) as f:
            return int(json.load(f).get("high", 0))
    except Exception:
        return 0


def save_hiscore(v):
    try:
        with open(HISCORE_FILE, "w") as f:
            json.dump({"high": v}, f)
    except Exception:
        pass


class State:
    def __init__(self):
        self.score = 0; self.mode = 0; self.sel = 0; self.cx = 0; self.cy = 0
        self.over = 0; self.grid = [[0] * GRID for _ in range(GRID)]
        self.pieces = [None, None, None]
        self.high = load_hiscore()
        self.new_high = False
        self.flash_until = 0

    def parse(self, line, audio):
        parts = line.strip().split(";")
        if len(parts) != 11 or parts[0] != "F":
            return False
        prev_score, prev_mode, prev_over = self.score, self.mode, self.over
        prev_filled = sum(v != 0 for row in self.grid for v in row)

        self.score = int(parts[1]); self.mode = int(parts[2]); self.sel = int(parts[3])
        self.cx = int(parts[4]); self.cy = int(parts[5]); self.over = int(parts[6])
        g = parts[7]
        if len(g) == GRID * GRID:
            self.grid = [[int(g[y * GRID + x]) for x in range(GRID)] for y in range(GRID)]
        for i in range(3):
            p = parts[8 + i]
            if p == "-":
                self.pieces[i] = None
            else:
                w, h, cells, col = p.split(",")
                self.pieces[i] = (int(w), int(h), cells, int(col))

        # ---- events -> sound / high score
        now_filled = sum(v != 0 for row in self.grid for v in row)
        if self.score > prev_score:
            if now_filled < prev_filled:            # cells vanished => line clear
                audio.play(audio.sfx_clear)
                self.flash_until = time.time() + 0.25
            else:
                audio.play(audio.sfx_place)
        elif self.mode == 1 and prev_mode == 0:
            audio.play(audio.sfx_pick)

        if self.score > self.high:
            if not self.new_high:
                self.new_high = True
                audio.play(audio.sfx_hi)
            self.high = self.score
            save_hiscore(self.high)

        if self.over and not prev_over:
            audio.play(audio.sfx_over)
        if not self.over and prev_over:             # new game started
            self.new_high = False
        return True

    def fits(self, piece, x, y):
        w, h, cells, _ = piece
        if x < 0 or y < 0 or x + w > GRID or y + h > GRID:
            return False
        for r in range(h):
            for c in range(w):
                if cells[r * w + c] == "#" and self.grid[y + r][x + c]:
                    return False
        return True


# ---------------------------------------------------------------- drawing
def draw_cell(surf, x, y, size, color, alpha=255):
    r = pygame.Rect(x + 3, y + 3, size - 6, size - 6)
    if alpha < 255:
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        s.fill((*color, alpha))
        surf.blit(s, r.topleft)
    else:
        pygame.draw.rect(surf, color, r, border_radius=8)
        hl = tuple(min(255, c + 50) for c in color)
        pygame.draw.rect(surf, hl, pygame.Rect(r.x, r.y, r.w, 6), border_top_left_radius=8, border_top_right_radius=8)


def draw(screen, st, font, small, big, status, audio):
    screen.fill(BG)
    ox, oy = PAD, PAD

    flash = time.time() < st.flash_until
    for y in range(GRID):
        for x in range(GRID):
            col = COLORS[st.grid[y][x]]
            if flash and st.grid[y][x] == 0:
                col = (60, 66, 90)
            draw_cell(screen, ox + x * CELL, oy + y * CELL, CELL, col)
    pygame.draw.rect(screen, GRIDLINE, pygame.Rect(ox, oy, CELL * GRID, CELL * GRID), 2, border_radius=6)

    if st.mode == 1 and st.pieces[st.sel]:
        w, h, cells, col = st.pieces[st.sel]
        ok = st.fits(st.pieces[st.sel], st.cx, st.cy)
        ghost = (80, 230, 120) if ok else (240, 80, 80)
        for r in range(h):
            for c in range(w):
                if cells[r * w + c] == "#":
                    draw_cell(screen, ox + (st.cx + c) * CELL, oy + (st.cy + r) * CELL, CELL, ghost, alpha=170)

    # ---- side panel
    px = ox + CELL * GRID + PAD
    screen.blit(big.render("BLOCK BLAST", True, TEXT), (px, oy))
    screen.blit(font.render(f"Score  {st.score}", True, TEXT), (px, oy + 50))
    hi_col = GOLD if st.new_high else DIM
    hi_txt = f"Best   {st.high}" + ("  NEW!" if st.new_high else "")
    screen.blit(font.render(hi_txt, True, hi_col), (px, oy + 74))

    if st.over:
        mode_txt, mc = "GAME OVER - press button", (255, 120, 120)
    elif st.mode:
        mode_txt, mc = "Joystick to move, press to drop", DIM
    else:
        mode_txt, mc = "Pot to choose, button to pick", DIM
    screen.blit(small.render(mode_txt, True, mc), (px, oy + 102))

    mini = 24
    for i in range(3):
        slot_y = oy + 132 + i * 110
        slot = pygame.Rect(px, slot_y, PANEL_W - PAD, 100)
        pygame.draw.rect(screen, (34, 38, 52), slot, border_radius=10)
        if i == st.sel:
            pygame.draw.rect(screen, GOLD if st.mode == 0 else (80, 230, 120), slot, 3, border_radius=10)
        p = st.pieces[i]
        if p:
            w, h, cells, col = p
            sx = slot.centerx - w * mini // 2
            sy = slot.centery - h * mini // 2
            for r in range(h):
                for c in range(w):
                    if cells[r * w + c] == "#":
                        draw_cell(screen, sx + c * mini, sy + r * mini, mini, COLORS[col])

    # ---- New Game button
    btn = pygame.Rect(px, oy + 132 + 3 * 110 + 4, PANEL_W - PAD, 38)
    hover = btn.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(screen, (70, 76, 110) if hover else (50, 55, 80), btn, border_radius=10)
    t = font.render("New Game  [N]", True, TEXT)
    screen.blit(t, t.get_rect(center=btn.center))

    # ---- bottom status line (under the board, out of the way)
    mute = "  [M] music off" if audio.muted else "  [M] music on" if audio.ok else ""
    screen.blit(small.render(status + mute, True, DIM), (ox, H - PAD + 6))
    pygame.display.flip()
    return btn


# ---------------------------------------------------------------- main
def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    pygame.init()
    audio = Audio()
    screen = pygame.display.set_mode((W, H + 20))
    pygame.display.set_caption("Block Blast")
    font  = pygame.font.SysFont("menlo,consolas,monospace", 18)
    small = pygame.font.SysFont("menlo,consolas,monospace", 14)
    big   = pygame.font.SysFont("menlo,consolas,monospace", 30, bold=True)
    st = State()
    ser = None
    buf = b""
    status = "connecting..." if port else "no serial port found"
    clock = pygame.time.Clock()
    btn = pygame.Rect(0, 0, 0, 0)

    def new_game():
        if ser:
            try:
                ser.write(b"N")
            except Exception:
                pass

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                audio.toggle_mute()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_n:
                new_game()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and btn.collidepoint(e.pos):
                new_game()

        if ser is None and port:
            try:
                ser = serial.Serial(port, BAUD, timeout=0)
                status = "connected"
            except Exception:
                status = "waiting for board..."
                time.sleep(0.5)

        if ser:
            try:
                if ser.in_waiting:
                    buf += ser.read(ser.in_waiting)
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        st.parse(line.decode(errors="ignore"), audio)
            except Exception:
                ser = None; status = "lost connection, retrying..."

        btn = draw(screen, st, font, small, big, status, audio)
        clock.tick(60)


if __name__ == "__main__":
    main()

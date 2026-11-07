"""Frame pacing: one game frame per vertical blank, as on the console.

ALUN_CD.EXE runs one game frame per VSync (main loop 0x8002C570: GameFrame, VSync 0x80043324,
draw 0x8002BEAC).  An NTSC PlayStation in 240-line mode has 263 lines of 3413 GPU clocks at
53.693175 MHz: 59.826 frames a second.  The camera is the game's (0x8002D080, checked against the
recompiled game: every camera value of a 670-frame walk is identical), so smooth scrolling
depends on each of those frames reaching the screen once and evenly.

pygame's Clock.tick(60) waits whole milliseconds (16 ms: 62.5 frames a second), so on a 60 Hz
monitor without vsync a frame was dropped about every half second and the picture tore - the
camera seemed to skip.  Now:
  * with vsync (the default; Options > VSync) the window flips on the monitor's refresh.  On a
    monitor at 59-61 Hz every refresh is shown (lockstep), and the game frames still run at 59.826 a
    second: on a 60 Hz monitor about one refresh in 350 shows the last picture again rather than
    the game running 0.3% fast (user, 2026-10-24: the game must not run faster);
  * otherwise (vsync off or not available, or another refresh rate) game frames are timed at
    59.826 a second with a fine clock, and a frame is drawn only when a new one was made."""
import time
from collections import deque

CONSOLE_HZ = 53_693_175 / (3413 * 263)          # 59.826
DT = 1.0 / CONSOLE_HZ
MAX_CATCH_UP = 4                                # after a stall, at most this many frames at once


class Pacer:
    PROBE = 20                                   # frames timed (unthrottled) to see whether flips wait

    def __init__(self, vsync=False):
        self.reset(vsync)

    def reset(self, vsync=None):
        if vsync is not None: self.vsync = vsync
        self.last = None; self.acc = 0.0
        self.gaps = deque(maxlen=30)
        self.lockstep = False
        self.probing = bool(self.vsync)          # with vsync: first find out what a flip waits for

    def due(self):
        """How many game frames to run now."""
        now = time.perf_counter()
        if self.last is None:
            self.last = now; return 1
        gap = now - self.last; self.last = now
        if self.probing:
            self.gaps.append(gap)
            if gap < 0.012:                      # flips do not wait for a ~60 Hz refresh
                self.probing = False; self.gaps.clear(); self.acc = 0.0
            elif len(self.gaps) >= self.PROBE:
                self.probing = False
                self.lockstep = 1 / 61.5 <= _median(self.gaps) <= 1 / 58.5
                if not self.lockstep: self.gaps.clear(); self.acc = 0.0
            if self.probing or self.lockstep: return 1
        elif self.lockstep:
            self.gaps.append(gap)
            if _median(self.gaps) < 1 / 61.5:    # the flips stopped waiting: time the frames ourselves
                self.lockstep = False; self.gaps.clear(); self.acc = 0.0
            else:                                # each refresh is shown, but game frames keep the console's
                self.acc += gap                  # 59.826 a second: on a 60 Hz monitor about one refresh in
                n = int(self.acc / DT)           # 350 runs none and shows the last picture again
                if n > MAX_CATCH_UP: n = MAX_CATCH_UP; self.acc = 0.0
                else: self.acc -= n * DT
                return n
        self.acc += gap
        n = int(self.acc / DT)
        if n > MAX_CATCH_UP: n = MAX_CATCH_UP; self.acc = 0.0      # a long stall: do not race to catch up
        else: self.acc -= n * DT
        return n

    def wait(self):
        """Without lockstep: sleep until the next game frame is due (the last ~2 ms spun, since
        sleep() can overshoot by a millisecond or more on Windows)."""
        if self.lockstep or self.probing or self.last is None: return
        until = self.last + (DT - self.acc)
        while True:
            left = until - time.perf_counter()
            if left <= 0: return
            if left > 0.002: time.sleep(left - 0.002)


def _median(xs):
    v = sorted(xs)
    return v[len(v) // 2]

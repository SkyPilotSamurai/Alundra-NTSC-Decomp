"""The game's own random number generator (US ALUN_CD.EXE, inlined in StartFlying 0x800827D0
and many AI routines; seed word at 0x8009AF70):
    seed = seed * 0x7D2B89DD + 0xE06A02E7   (32 bit)
    random(n) = (seed * n) >> 32
The oracle copies the seed in, so AI decisions follow the real game exactly."""
SEED_ADDR = 0x8009AF70
state = [0x12345678]


def seed(v): state[0] = v & 0xFFFFFFFF


def rnd(n):
    s = (state[0] * 0x7D2B89DD + 0xE06A02E7) & 0xFFFFFFFF
    state[0] = s
    return (s * (n & 0xFFFFFFFF)) >> 32


def tick():
    """End of every game frame (0x8002BE58): the seed advances once even when nothing
    asked for a number, so the next frame's numbers depend on how many frames passed."""
    state[0] = (state[0] * 0x7D2B89DD + 0xE06A02E7) & 0xFFFFFFFF

/* sndvm: plays Alundra's music with the game's own sound code.
   ALUN_CD.EXE is loaded into an R3000 interpreter; the game's sound start-up (0x8004946C) and its
   music load/play (0x8004C380, script command A7) run as they do on the console, with the disc
   reads served from SOUND.BIN, and the libsnd vsync tick (0x80090C40) is called once per frame.
   The SPU is the PSXRecomp runtime's (spu.c), driven in lockstep, so the voice manager sees the
   envelope levels it reads back exactly as on hardware.
   usage: sndvm ALUN_CD.EXE SOUND.BIN music_id|sN[@bank] frames out.raw trace.bin [log.bin|-] [ntsc=1]
   out.raw: s16 stereo 44.1 kHz.  trace.bin per frame: u32 read_ptr, flags(+0x90), voices_on, samples.
   log.bin: every SPU register write (u64 sample, u32 addr, u32 value). */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "spu.c"

void psx_irq_raise(uint32_t bit, uint32_t detail) { (void)bit; (void)detail; }
uint64_t s_frame_count = 0;
uint32_t crc32_update(uint32_t c, const uint8_t *p, size_t n) { (void)p; (void)n; return c; }
void audio_trace_pcm(int tap, const int16_t *s, int n) { (void)tap; (void)s; (void)n; }
void audio_trace_event(uint16_t k, uint32_t a, uint32_t b) { (void)k; (void)a; (void)b; }
bool spu_shadow_enabled(void) { return 0; }
void spu_shadow_process(int16_t *s, int n) { (void)s; (void)n; }
void spu_shadow_reset(void) {}
uint64_t psx_get_cycle_count(void) { return 0; }

static uint8_t ram[0x200000], scr[0x400];
static uint32_t R[32], HI, LO, PC, NPC, xfer_addr;
static uint64_t g_sample;
static FILE *g_log;
static uint8_t *g_sound; static size_t g_sound_n;
#define MAGIC 0x80FFFFF0u

static uint32_t rdm(uint32_t a, int sz) {
    uint32_t p = a & 0x1FFFFFFF;
    uint8_t *b = 0;
    if (p < 0x800000) b = ram + (p & 0x1FFFFF);
    else if (p >= 0x1F800000 && p < 0x1F800400) b = scr + (p - 0x1F800000);
    else if (p >= 0x1F801C00 && p < 0x1F802000) {
        if (sz == 4) return spu_read(p) | spu_read(p + 2) << 16;
        uint32_t v = spu_read(p & ~1u);
        return sz == 1 ? (v >> ((p & 1) * 8)) & 0xFF : v;
    } else return 0;
    if (sz == 1) return b[0];
    if (sz == 2) return b[0] | b[1] << 8;
    return b[0] | b[1] << 8 | b[2] << 16 | (uint32_t)b[3] << 24;
}
static void spuw(uint32_t p, uint32_t v) {
    if (g_log) { uint32_t r[4] = {(uint32_t)g_sample, (uint32_t)(g_sample >> 32), p, v & 0xFFFF}; fwrite(r, 4, 4, g_log); }
    spu_write(p, v & 0xFFFF);
}
static void wrm(uint32_t a, uint32_t v, int sz) {
    uint32_t p = a & 0x1FFFFFFF;
    uint8_t *b = 0;
    if (p < 0x800000) b = ram + (p & 0x1FFFFF);
    else if (p >= 0x1F800000 && p < 0x1F800400) b = scr + (p - 0x1F800000);
    else if (p >= 0x1F801C00 && p < 0x1F802000) {
        if (sz == 4) { spuw(p, v); spuw(p + 2, v >> 16); }
        else spuw(p & ~1u, v);
        return;
    } else return;
    b[0] = v; if (sz > 1) b[1] = v >> 8; if (sz > 2) { b[2] = v >> 16; b[3] = v >> 24; }
}

static int hook(void) {
    switch (PC) {
    case 0x8009A830: xfer_addr = R[4]; R[2] = R[4]; break;                 /* SpuSetTransferStartAddr */
    case 0x8009A8A0:                                                         /* SpuWrite */
        for (uint32_t i = 0; i < R[5]; i++) spu_ram[(xfer_addr + i) & (SPU_RAM_SIZE - 1)] = ram[(R[4] + i) & 0x1FFFFF];
        xfer_addr += R[5]; R[2] = R[5]; break;
    case 0x8009A86C: case 0x8009A9D4: R[2] = 0; break;                       /* transfer mode / callback */
    case 0x8009A92C: R[2] = 1; break;                                        /* SpuIsTransferCompleted */
    case 0x80083F04: {                                                       /* load_file(path, dest, offset, size) */
        char path[64]; int i;
        for (i = 0; i < 63; i++) { path[i] = rdm(R[4] + i, 1); if (!path[i]) break; }
        path[i] = 0;
        if (strcmp(path, "data\\sound.bin")) { fprintf(stderr, "load_file %s not served\n", path); exit(7); }
        if (getenv("SNDVM_TRACE")) fprintf(stderr, "load_file sound.bin %u +%u -> %08x\n", R[6], R[7], R[5]);
        for (uint32_t k = 0; k < R[7]; k++) ram[(R[5] + k) & 0x1FFFFF] = R[6] + k < g_sound_n ? g_sound[R[6] + k] : 0;
        R[2] = R[7]; break; }
    case 0x80083EE4: R[2] = 0; break;                                        /* debug print */
    case 0xA0: case 0xB0: case 0xC0: R[2] = 0; break;                       /* BIOS */
    default: return 0;
    }
    PC = R[31]; NPC = PC + 4;
    return 1;
}

static void step(void) {
    uint32_t cur = PC, op = rdm(PC, 4);
    PC = NPC; NPC = PC + 4;
    uint32_t rs = op >> 21 & 31, rt = op >> 16 & 31, rd = op >> 11 & 31, sa = op >> 6 & 31;
    int32_t imm = (int16_t)op; uint32_t uimm = op & 0xFFFF;
    uint32_t bt = PC + (imm << 2), a = R[rs] + imm;
    switch (op >> 26) {
    case 0:
        switch (op & 63) {
        case 0: R[rd] = R[rt] << sa; break;
        case 2: R[rd] = R[rt] >> sa; break;
        case 3: R[rd] = (int32_t)R[rt] >> sa; break;
        case 4: R[rd] = R[rt] << (R[rs] & 31); break;
        case 6: R[rd] = R[rt] >> (R[rs] & 31); break;
        case 7: R[rd] = (int32_t)R[rt] >> (R[rs] & 31); break;
        case 8: NPC = R[rs]; break;
        case 9: { uint32_t t = R[rs]; R[rd] = cur + 8; NPC = t; break; }
        case 12: break;
        case 13: fprintf(stderr, "break at %08x\n", cur); exit(3);
        case 16: R[rd] = HI; break;
        case 17: HI = R[rs]; break;
        case 18: R[rd] = LO; break;
        case 19: LO = R[rs]; break;
        case 24: { int64_t m = (int64_t)(int32_t)R[rs] * (int32_t)R[rt]; LO = m; HI = m >> 32; break; }
        case 25: { uint64_t m = (uint64_t)R[rs] * R[rt]; LO = m; HI = m >> 32; break; }
        case 26: {
            int32_t n = R[rs], d = R[rt];
            if (d == 0) { LO = n >= 0 ? 0xFFFFFFFF : 1; HI = n; }
            else if ((uint32_t)n == 0x80000000u && d == -1) { LO = 0x80000000u; HI = 0; }
            else { LO = n / d; HI = n % d; }
            break; }
        case 27: if (R[rt] == 0) { LO = 0xFFFFFFFF; HI = R[rs]; } else { LO = R[rs] / R[rt]; HI = R[rs] % R[rt]; } break;
        case 32: case 33: R[rd] = R[rs] + R[rt]; break;
        case 34: case 35: R[rd] = R[rs] - R[rt]; break;
        case 36: R[rd] = R[rs] & R[rt]; break;
        case 37: R[rd] = R[rs] | R[rt]; break;
        case 38: R[rd] = R[rs] ^ R[rt]; break;
        case 39: R[rd] = ~(R[rs] | R[rt]); break;
        case 42: R[rd] = (int32_t)R[rs] < (int32_t)R[rt]; break;
        case 43: R[rd] = R[rs] < R[rt]; break;
        default: fprintf(stderr, "bad special %08x at %08x\n", op, cur); exit(3);
        }
        break;
    case 1: {
        int take = (rt & 1) ? (int32_t)R[rs] >= 0 : (int32_t)R[rs] < 0;
        if (rt & 0x10) R[31] = cur + 8;
        if (take) NPC = bt;
        break; }
    case 2: NPC = (PC & 0xF0000000) | (op & 0x3FFFFFF) << 2; break;
    case 3: R[31] = cur + 8; NPC = (PC & 0xF0000000) | (op & 0x3FFFFFF) << 2; break;
    case 4: if (R[rs] == R[rt]) NPC = bt; break;
    case 5: if (R[rs] != R[rt]) NPC = bt; break;
    case 6: if ((int32_t)R[rs] <= 0) NPC = bt; break;
    case 7: if ((int32_t)R[rs] > 0) NPC = bt; break;
    case 8: case 9: R[rt] = R[rs] + imm; break;
    case 10: R[rt] = (int32_t)R[rs] < imm; break;
    case 11: R[rt] = R[rs] < (uint32_t)imm; break;
    case 12: R[rt] = R[rs] & uimm; break;
    case 13: R[rt] = R[rs] | uimm; break;
    case 14: R[rt] = R[rs] ^ uimm; break;
    case 15: R[rt] = uimm << 16; break;
    case 16: if (rs == 0) R[rt] = 0; break;              /* mfc0 / mtc0 / rfe */
    case 18: case 50: case 58: break;                    /* GTE: unused by the sound code */
    case 32: R[rt] = (int8_t)rdm(a, 1); break;
    case 33: R[rt] = (int16_t)rdm(a, 2); break;
    case 34: { uint32_t w = rdm(a & ~3u, 4), r = R[rt];
        switch (a & 3) { case 0: r = (r & 0x00FFFFFF) | w << 24; break; case 1: r = (r & 0xFFFF) | w << 16; break;
                         case 2: r = (r & 0xFF) | w << 8; break; default: r = w; }
        R[rt] = r; break; }
    case 35: R[rt] = rdm(a, 4); break;
    case 36: R[rt] = rdm(a, 1); break;
    case 37: R[rt] = rdm(a, 2); break;
    case 38: { uint32_t w = rdm(a & ~3u, 4), r = R[rt];
        switch (a & 3) { case 0: r = w; break; case 1: r = (r & 0xFF000000) | w >> 8; break;
                         case 2: r = (r & 0xFFFF0000) | w >> 16; break; default: r = (r & 0xFFFFFF00) | w >> 24; }
        R[rt] = r; break; }
    case 40: wrm(a, R[rt], 1); break;
    case 41: wrm(a, R[rt], 2); break;
    case 42: { uint32_t m = rdm(a & ~3u, 4), r = R[rt];
        switch (a & 3) { case 0: m = (m & 0xFFFFFF00) | r >> 24; break; case 1: m = (m & 0xFFFF0000) | r >> 16; break;
                         case 2: m = (m & 0xFF000000) | r >> 8; break; default: m = r; }
        wrm(a & ~3u, m, 4); break; }
    case 43: wrm(a, R[rt], 4); break;
    case 46: { uint32_t m = rdm(a & ~3u, 4), r = R[rt];
        switch (a & 3) { case 0: m = r; break; case 1: m = (m & 0xFF) | r << 8; break;
                         case 2: m = (m & 0xFFFF) | r << 16; break; default: m = (m & 0xFFFFFF) | r << 24; }
        wrm(a & ~3u, m, 4); break; }
    default: fprintf(stderr, "bad op %08x at %08x\n", op, cur); exit(3);
    }
    R[0] = 0;
}

static uint32_t call(uint32_t fn, uint32_t a0, uint32_t a1, uint32_t a2, uint32_t a3, uint32_t v0) {
    R[2] = v0; R[4] = a0; R[5] = a1; R[6] = a2; R[7] = a3; R[31] = MAGIC; R[29] = 0x801FFF00;
    PC = fn; NPC = fn + 4;
    for (long n = 0; PC != MAGIC; n++) {
        if (n > 200000000L) { fprintf(stderr, "runaway in %08x at %08x\n", fn, PC); exit(4); }
        if (!hook()) step();
    }
    return R[2];
}
static uint32_t r32(uint32_t a) { return rdm(a, 4); }
static int16_t r16(uint32_t a) { return (int16_t)rdm(a, 2); }
static uint8_t *slurp(const char *p, size_t *n) {
    FILE *f = fopen(p, "rb"); if (!f) { perror(p); exit(1); }
    fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *b = malloc(*n + 1); if (fread(b, 1, *n, f) != *n) exit(1); fclose(f); return b;
}

int main(int argc, char **argv) {
    if (argc < 7) { fprintf(stderr, "usage: sndvm ALUN_CD.EXE SOUND.BIN music_id|sN[@bank] frames out.raw trace.bin [log.bin|-] [ntsc]\n"); return 1; }
    size_t n;
    uint8_t *exe = slurp(argv[1], &n);
    uint32_t pc0, gp0, t_addr, t_size;
    memcpy(&pc0, exe + 0x10, 4); memcpy(&gp0, exe + 0x14, 4); memcpy(&t_addr, exe + 0x18, 4); memcpy(&t_size, exe + 0x1C, 4);
    memcpy(ram + (t_addr & 0x1FFFFF), exe + 0x800, t_size < n - 0x800 ? t_size : n - 0x800);
    g_sound = slurp(argv[2], &g_sound_n);
    int id = atoi(argv[3]); long frames = atol(argv[4]);
    FILE *out = fopen(argv[5], "wb"), *trace = fopen(argv[6], "wb");
    g_log = (argc > 7 && strcmp(argv[7], "-")) ? fopen(argv[7], "wb") : 0;
    int ntsc = argc > 8 ? atoi(argv[8]) : 1;
    /* 240-line NTSC: 53.693182 MHz / (3413 * 263) = 59.826 Hz vsync, the libsnd tick (SS_TICK60 -> vsync) */
    double spf = ntsc ? 44100.0 * 3413.0 * 263.0 / 53693181.818 : 735.0, acc = 0;

    spu_init();
    R[28] = 0x800CBF4C;                                   /* crt0's gp */
    call(0x8009089C, 0, 0, 0, 0, 0);                      /* SsInit (main 0x8002C178) */
    call(0x8004946C, 0, 0, 0, 0, 0);                      /* sound start-up 0x80049464 (CD init skipped) */
    int sound = argv[3][0] == 's', bank = -1;
    if (sound) {                                          /* "sN" or "sN@bank": PlaySound(N) */
        id = atoi(argv[3] + 1);
        const char *at = strchr(argv[3], '@');
        if (at) bank = atoi(at + 1);
        if (bank >= 0) { wrm(0x801D7DC4, bank, 4); call(0x80049820, bank, 0, 0, 0, 0); }   /* the map's bank */
        call(0x8004A128, id, 0, 0, 0, 0);
        const char *vol = getenv("SNDVM_VOL");            /* "l,r": then the volume command 0x8004A928 (script BF / AB) */
        if (vol) { int l = 127, r = 127; sscanf(vol, "%d,%d", &l, &r); call(0x8004A928, id, l, r, 0, 0); }
    } else
        call(0x8004C380, id, 1, 0, 0, 0);                 /* A7: load music id, play now */
    int16_t s = r16(0x8013A050);
    uint32_t sq = r32(0x801F30D0 + s * 4);
    int16_t buf[2 * 2048];
    for (long f = 0; f < frames; f++) {
        call(0x80090C40, 0, 0, 0, 0, 0);                  /* the vsync tick */
        if (sound) call(0x80049CD4, 0, 0, 0, 0, 0);       /* the sound manager's voice / sequence upkeep */
        uint32_t von = 0;
        for (int i = 0; i < 24; i++) if (spu_read(0x1F801C0C + i * 16)) von |= 1u << i;
        acc += spf; int cnt = (int)acc; acc -= cnt;
        uint32_t t[4] = {r32(sq + 4), r32(sq + 0x90), von, (uint32_t)cnt};
        fwrite(t, 4, 4, trace);
        spu_render(buf, cnt);
        fwrite(buf, 4, cnt, out);
        g_sample += cnt;
    }
    fclose(out); fclose(trace); if (g_log) fclose(g_log);
    return 0;
}

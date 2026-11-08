/* spurender: plays a list of SPU register writes through the PSXRecomp runtime's SPU (spu.c),
   the offline renderer tools/audio/spu_replay.py drives (sfx_dry.py, sfx_release.py, sfx_render.py).
   usage: spurender spu_ram.bin events.bin samples out.raw [voices.vs]
     spu_ram.bin  up to 512 KB copied to SPU RAM at 0
     events.bin   records (u64 sample, u32 address, u32 value), sorted by sample: each write is
                  applied before that output sample is rendered
     out.raw      s16 stereo, 44.1 kHz, `samples` frames
   voices.vs (resuming captured voice states) is not supported here; the sound tools never pass it.
   Build: see build_windows.cmd (same SPU source and stubs as sndvm.c). */
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

#pragma pack(push, 1)
typedef struct { uint64_t t; uint32_t addr, value; } Ev;
#pragma pack(pop)

int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage: spurender ram.bin events.bin samples out.raw\n"); return 2; }
    if (argc > 5) { fprintf(stderr, "spurender: voice-state resume is not supported\n"); return 2; }
    spu_init();
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    size_t got = fread(spu_ram, 1, SPU_RAM_SIZE, f); (void)got; fclose(f);

    f = fopen(argv[2], "rb");
    if (!f) { perror(argv[2]); return 1; }
    fseek(f, 0, SEEK_END); long nb = ftell(f); fseek(f, 0, SEEK_SET);
    size_t nev = (size_t)nb / sizeof(Ev);
    Ev *ev = (Ev *)malloc(nev ? nev * sizeof(Ev) : 1);
    if (nev && fread(ev, sizeof(Ev), nev, f) != nev) { fprintf(stderr, "short events file\n"); return 1; }
    fclose(f);

    uint64_t total = strtoull(argv[3], NULL, 10);
    FILE *o = fopen(argv[4], "wb");
    if (!o) { perror(argv[4]); return 1; }
    enum { CHUNK = 1024 };
    static int16_t buf[CHUNK * 2];
    uint64_t pos = 0; size_t i = 0;
    while (pos < total) {
        while (i < nev && ev[i].t <= pos) { spu_write(ev[i].addr, ev[i].value & 0xFFFF); i++; }
        uint64_t next = total;
        if (i < nev && ev[i].t < next) next = ev[i].t;
        uint64_t n = next - pos; if (n > CHUNK) n = CHUNK;
        if (n == 0) n = 1;
        spu_render(buf, (int)n);
        fwrite(buf, sizeof(int16_t) * 2, (size_t)n, o);
        pos += n;
    }
    fclose(o); free(ev);
    return 0;
}

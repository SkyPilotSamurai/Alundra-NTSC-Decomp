#!/bin/sh
# Builds sndvm against the PSXRecomp runtime's SPU (spu.c is compiled in).
D="$(cd "$(dirname "$0")" && pwd)"
RT="$D/../../../Alundra EU Recomp/psxrecomp/runtime"
gcc -O2 -w -I "$RT/src" -I "$RT/include" -o "$D/sndvm" "$D/sndvm.c" -lm

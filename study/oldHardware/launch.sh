#!/bin/bash
for bs in 8 12 16 20 24 32
do
    for gs in $(seq 0 0.10 1)
    do
        export PYSWEEP_SHARE=$gs
        export PYSWEEP_BLOCK=$bs
        sbatch -J "old"$PYSWEEP_EQN$bs$gs old.sh
    done
done
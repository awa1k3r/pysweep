#!/bin/bash

#SBATCH --get-user-env                      #Use user env

#SBATCH -A niemeyek						# name of my sponsored account, e.g. class or research group

#SBATCH -p preempt

#SBATCH --gres=gpu:1

#SBATCH -F ./old-nodes

#SBATCH -N 2

#SBATCH --ntasks-per-node=1

#SBATCH --cpus-per-task=16

#SBATCH --time=2-00:00:00

#SBATCH -o gtxSweepOne.out					# name of output file for this submission script

#SBATCH -e gtxSweepOne.err					# name of error file for this submission script

#SBATCH --mail-type=BEGIN,END,FAIL				# send email when job begins, ends or aborts

#SBATCH --mail-user=walkanth@oregonstate.edu		# send email to this address

# load any software environment module required for app

# run my jobs

echo $SLURM_JOB_ID

export RANKS_PER_NODE=1

for nx in 160 320 480 640 800 960 1120
do
        mpiexec -n 32 --hostfile ./old-nodes pysweep -f $PYSWEEP_EQN -nx $nx -nt 500 -b $PYSWEEP_BLOCK -s $PYSWEEP_SHARE  --swept --verbose --ignore --clean

        mpiexec -n 32 --hostfile ./old-nodes pysweep -f $PYSWEEP_EQN -nx $nx -nt 500 -b $PYSWEEP_BLOCK -s $PYSWEEP_SHARE  --verbose --ignore --clean
done


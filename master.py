#Programmer: Anthony Walker
#This is the main file for running and testing the swept solver
from src.sweep import *
from src.analytical import *
from src.equations import *
from src.decomp import *
import multiprocessing as mp
#Calling analytical solution
def analytical():
    """Use this funciton to solve the analytical euler vortex."""
    # create_vortex_data(cvics,X,Y,npx,npy,times=(0,0.1))
    pass

def create_block_sizes():
    """Use this function to create arguements for the two codes."""
    #Block_sizes
    bss = list()
    for i in range(3,6,1):
        cbs = (int(2**i),int(2**i),1)
        bss.append(cbs)
    return bss

if __name__ == "__main__":

    comm = MPI.COMM_WORLD
    master_rank = 0 #master rank
    rank = comm.Get_rank()  #current rank

    #Properties
    gamma = 1.4

    #Analytical properties
    cvics = vics()
    cvics.Shu(gamma)
    initial_args = cvics.get_args()
    X = cvics.L
    Y = cvics.L
    #Dimensions and steps
    npx = 512
    npy = 16
    dx = X/npx
    dy = Y/npy
    #Time testing arguments
    t0 = 0
    t_b = 1
    dt = 0.1
    targs = (t0,t_b,dt)
    # Creating initial vortex from analytical code
    initial_vortex = vortex(cvics,X,Y,npx,npy,times=(0,))
    initial_vortex = np.swapaxes(initial_vortex,0,2)
    initial_vortex = np.swapaxes(initial_vortex,1,3)[0]

    #GPU Arguments
    kernel = "/home/walkanth/pysweep/src/equations/euler.h"
    cpu_source = "/home/walkanth/pysweep/src/equations/euler.py"
    ops = 2 #number of atomic operations
    #File args
    swept_name = "./results/swept"
    decomp_name = "./results/decomp"
    #Changing arguments
    affinities = np.linspace(1/2,1,mp.cpu_count()/2)
    block_sizes = create_block_sizes()
    if rank == master_rank:
        f =  open("./results/time_data.txt",'w')
    #Swept results
    for i,bs in enumerate(block_sizes[:1]):
        for j,aff in enumerate(affinities[:2]):
            fname = swept_name+"_"+str(i)+"_"+str(j)
            ct = sweep(initial_vortex,targs,dx,dy,ops,bs,kernel,cpu_source,affinity=aff,filename=fname)
            if rank == master_rank:
                f.write("Swept: "+str((ct,bs,aff))+"\n")
            comm.Barrier()

    for i,bs in enumerate(block_sizes[:1]):
        for j,aff in enumerate(affinities[:2]):
            fname = decomp_name+"_"+str(i)+"_"+str(j)
            ct = decomp(initial_vortex,targs,dx,dy,ops,bs,kernel,cpu_source,affinity=aff,filename=fname)
            if rank == master_rank:
                f.write("Decom: "+str((ct,bs,aff))+"\n")
            comm.Barrier()

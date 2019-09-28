
#Programmer: Anthony Walker
#PySweep is a package used to implement the swept rule for solving PDEs

#System imports
import sys
import os
cwd = os.getcwd()
sys.path.insert(1,cwd+"/src/sweep")
#Writing imports
import h5py

#DataStructure and Math imports
import math
import numpy as np
import ctypes
from collections import deque
from itertools import cycle

#CUDA Imports
# import pycuda.driver as cuda
# import pycuda.autoinit  #Cor debugging only
# from pycuda.compiler import SourceModule
# import pycuda.gpuarray as gpuarray

#MPI imports
from mpi4py import MPI

#Multiprocessing Imports
import multiprocessing as mp
import ctypes

#GPU Utility Imports
import GPUtil

#Swept imports
# from .pysweep_lambda import sweep_lambda
# from .pysweep_functions import *
# from .pysweep_decomposition import *
from pysweep_block import *
# from .pysweep_regions import *
# from .pysweep_source import *
import importlib.util
#Testing and Debugging
import warnings
import time as timer
warnings.simplefilter("ignore") #THIS IGNORES WARNINGS


def pm(arr,i):
    for item in arr[i,0,:,:]:
        sys.stdout.write("[ ")
        for si in item:
            sys.stdout.write("%1.1f"%si+", ")
        sys.stdout.write("]\n")

def node_split(nodes,node,master_node,num_block_rows,AF,total_num_cores,num_cores,total_num_gpus,num_gpus):
    """Use this function to split data amongst nodes."""
    #Assert that the total number of blocks is an integer
    gpu_rows = np.ceil(num_block_rows*AF)
    rows_per_gpu = gpu_rows/total_num_gpus if total_num_gpus > 0 else 0
    cpu_rows = num_block_rows-gpu_rows
    rows_per_core = np.ceil(cpu_rows/total_num_cores) if num_cores > 0 else 0
    #Over estimate number of rows
    node_rows = rows_per_gpu*num_gpus+rows_per_core*num_cores
    #Number of row correction
    tnr = nodes.gather(node_rows)
    cores = nodes.gather(num_cores)
    if node == master_node:
        total_rows = np.sum(tnr)
        cis = cycle(tuple(np.zeros(nodes.Get_size()-1))+(1,))
        ncyc = cycle(range(0,nodes.Get_size(),1))
        min_cores = min(cores)
        while total_rows > num_block_rows:
            curr = next(ncyc)
            if min_cores >= cores[curr]:
                tnr[curr]-=1
                total_rows-=1
            min_cores += next(cis)
    nodes.Barrier()
    node_rows = nodes.scatter(tnr,root=master_node)
    return node_rows

# def create_shared_arrays():
#     """Use this function to create shared memory arrays for node communication."""
#     #----------------------------Creating shared arrays-------------------------#
#     global cpu_array
#     cpu_array_base = mp.Array(ctypes.c_double, shm_dim)
#     cpu_array = np.ctypeslib.as_array(cpu_array_base.get_obj())
#     cpu_array = cpu_array.reshape(block_size)
#
#     global gpu_array
#     gpu_array_base = mp.Array(ctypes.c_double, shm_dim)
#     gpu_array = np.ctypeslib.as_array(gpu_array_base.get_obj())
#     gpu_array = gpu_array.reshape(block_size)


def dsweep(arr0,gargs,swargs,filename ="results",exid=[]):
    """Use this function to perform swept rule
    args:
    arr0 -  3D numpy array of initial conditions (v (variables), x,y)
    gargs:   (global args)
        The first three variables must be time arguments (t0,tf,dt).
        Subsequent variables can be anything passed to the source code in the
        "set_globals" function
    swargs: (Swept args)
        TSO - order of the time scheme
        OPS - operating points to remove from each side for a function step
            (e.g. a 5 point stencil would result in OPS=2).
        BS - an integer which represents the x and y dimensions of the gpu block size
        AF -  the GPU affinity (GPU work/CPU work)/TotalWork
        GS - GPU source code file
        CS - CPU source code file
    dType: data type for the run (e.g. np.dtype("float32")).
    filename: Name of the output file excluding hdf5
    exid: GPU ids to exclude from the calculation.
    """
    #Unpacking arguments
    t0,tf,dt = gargs[:3]
    TSO,OPS,BS,AF,GS,CS = swargs
    BS = (BS,BS,1)
    start = timer.time()
    #Local Constants
    ZERO = 0
    QUARTER = 0.25
    HALF = 0.5
    ONE = 1
    TWO = 2
    TOPS = TWO*OPS
    #Getting GPU info
    #-------------MPI Set up----------------------------#
    nodes = MPI.COMM_WORLD
    processor = MPI.Get_processor_name()
    master_node = ZERO #master rank
    total_num_cpus = nodes.Get_size() #number of ranks
    node = nodes.Get_rank()  #current rank
    num_cores = pool_size = mp.cpu_count()
    total_num_cores = num_cores*total_num_cpus #Assumes all nodes have the same number of cores in CPU

    #Getting GPUs if affinity is greater than 1
    if AF>0:
        gpu_node = GPUtil.getAvailable(order = 'load',maxLoad=1,maxMemory=1,excludeID=exid,limit=1e8) #getting devices by load
        gpu_node = [(True,id) for id in gpu_node]
        num_gpus = len(gpu_node)
    else:
        gpu_node = []
        num_gpus = 0
    num_cores -= num_gpus
    #Get total number of GPUs
    total_num_gpus = np.sum(nodes.allgather(num_gpus))
    #Get total number of blocks
    NB = np.prod(arr0.shape[1:])/np.prod(BS)
    assert (NB).is_integer()
    num_block_rows = arr0.shape[1]/BS[0]
    #This function splits the rows among the nodes by affinity
    node_rows = int(node_split(nodes,node,master_node,num_block_rows,AF,total_num_cores,num_cores,total_num_gpus,num_gpus))
    #Gathering a list of all nodes
    node_list = cycle(nodes.allgather((node,node_rows)))
    #Creating forward and backward nodes
    fnode = bnode = None
    prev = next(node_list)
    nxt = next(node_list)
    while fnode is None:
        curr = nxt
        nxt = next(node_list)
        if curr[0] == node:
            fnode = nxt
            bnode = prev
        prev = curr
    #---------------------SWEPT VARIABLE SETUP----------------------$
    #Splits for shared array
    SPLITX = int(BS[ZERO]/TWO)   #Split computation shift - add OPS
    SPLITY = int(BS[ONE]/TWO)   #Split computation shift
    up_sets = create_up_sets(BS,OPS)
    down_sets = create_down_sets(BS,OPS)[:-1]
    oct_sets = down_sets+up_sets[1:]
    MPSS = len(up_sets)
    MOSS = len(oct_sets)
    bridge_sets, bridge_slices = create_bridge_sets(BS,OPS,MPSS)
    IEP = 1 if MPSS%2==0 else 0 #This accounts for even or odd MPSS

    #----------------Data Input setup -------------------------#
    time_steps = int((tf-t0)/dt)  #Number of time steps
    #Global swept step
    MGST = int(TSO*(time_steps)/(MOSS)-1)    #THIS ASSUMES THAT time_steps > MOSS
    time_steps = int((MGST*(MOSS)/TSO)+MPSS) #Updating time steps

    #-----------------------SHARED ARRAY CREATION----------------------#
    #Create shared process array for data transfer  - TWO is added to shared shaped for IC and First Step
    shared_shape = (MOSS+TSO+ONE,time_steps,arr0.shape[0],int(node_rows*BS[1]),arr0.shape[2])
    sarr_base = mp.Array(ctypes.c_float, int(np.prod(shared_shape)))
    sarr = np.ctypeslib.as_array(sarr_base.get_obj())
    sarr = sarr.reshape(shared_shape)

    



    # #Fill shared array and communicate initial boundaries
    # if rank == master_rank:
    #     np.copyto(sarr[TSO-ONE,:,OPS:arr0.shape[ONE]+OPS,OPS:arr0.shape[TWO]+OPS],arr0[:,:,:])
    #     boundary_update(sarr,OPS,SPLITX,SPLITY)   #communicate boundaries
    # #------------------------------DECOMPOSITION BY REGION CREATION--------------#
    # GRB = gpu_rank[ZERO]
    # #Splits regions up amongst architecture
    # if GRB:#Total number of GPUS

    #     gri = gpu_comm.Get_rank()
    #     cri = None
    #     WR = create_write_region(gpu_comm,gri,gpu_master,num_gpus,BS,arr0.shape,gpu_slices,shared_shape[0],OPS)
    # else:
    #     cri = cpu_comm.Get_rank()
    #     gri = None
    #     WR = create_write_region(cpu_comm,cri,cpu_master,num_cpus,BS,arr0.shape,cpu_slices,shared_shape[0],OPS)
    # #---------------------_REMOVING UNWANTED RANKS---------------------------#
    # #Checking if rank is useful
    # if WR[3].start == WR[3].stop or WR[2].start == WR[2].stop:
    #     include_ranks = None
    # else:
    #     include_ranks = rank
    # #Gathering results
    # include_ranks = comm.gather(include_ranks,root=master_rank)
    # if rank == master_rank:
    #     include_ranks = list(filter(lambda a: a is not None, include_ranks))
    # #Distributing new results
    # include_ranks = comm.bcast(include_ranks,root=master_rank)
    # #Creating new comm group
    # comm_group = comm.group.Incl(include_ranks)
    #Killing unwanted processes
    # if rank not in include_ranks:
    #     MPI.Finalize()
    #     exit(0)
    # #Updating comm
    # comm = comm.Create_group(comm_group)
    # #Sync all processes - Ensures boundaries are updated
    # comm.Barrier()
    # #--------------------------CREATING OTHER REGIONS--------------------------#
    # RR = create_read_region(WR,OPS)   #Create read region
    # SRR,SWR,XR,YR = create_shift_regions(RR,SPLITX,SPLITY,shared_shape,OPS)  #Create shifted read region
    # BDR = create_boundaries(WR,SPLITX,SPLITY,OPS,shared_shape)
    # SBDR = create_shifted_boundaries(SWR,SPLITX,SPLITY,OPS,shared_shape)
    # wxt = create_standard_bridges(XR,OPS,bridge_slices[0],shared_shape,BS,rank)
    # wyt = create_standard_bridges(YR,OPS,bridge_slices[1],shared_shape,BS,rank)
    # wxts = create_shifted_bridges(YR,OPS,bridge_slices[0],shared_shape,BS,rank)
    # wyts = create_shifted_bridges(XR,OPS,bridge_slices[1],shared_shape,BS,rank)
    # #--------------------------------CREATING LOCAL ARRAYS-----------------------------------------#
    # larr = np.copy(sarr[RR])
    #---------------Generating Source Modules----------------------------------#
    # if GRB:
    #     # Creating cuda device and Context
    #     cuda.init()
    #     cuda_device = cuda.Device(gpu_rank[ONE])
    #     cuda_context = cuda_device.make_context()
    #     #Creating local GPU array with split
    #     GRD = (int((larr.shape[TWO]-TOPS)/BS[ZERO]),int((larr.shape[3]-TOPS)/BS[ONE]))   #Grid size
    #     #Creating constants
    #     NV = larr.shape[ONE]
    #     SGIDS = (BS[ZERO]+TWO*OPS)*(BS[ONE]+TWO*OPS)
    #     STS = SGIDS*NV #Shared time shift
    #     VARS =  larr.shape[TWO]*larr.shape[3]
    #     TIMES = VARS*NV
    #     const_dict = ({"NV":NV,"SGIDS":SGIDS,"VARS":VARS,"TIMES":TIMES,"SPLITX":SPLITX,"SPLITY":SPLITY,"MPSS":MPSS,"MOSS":MOSS,"OPS":OPS,"TSO":TSO,"STS":STS})
    #     #Building CUDA source code
    #     SM = build_gpu_source(GS)
    #     swept_constant_copy(SM,const_dict)
    #     cpu_SM = build_cpu_source(CS)   #Building cpu source for set_globals
    #     cpu_SM.set_globals(GRB,SM,*gargs)
    #     del cpu_SM
    #     CRS = None
    # else:
    #     SM = build_cpu_source(CS) #Building Python source code
    #     SM.set_globals(GRB,SM,*gargs)
    #     CRS = create_blocks_list(larr.shape,BS,OPS)
    #     GRD = None

    # #------------------------------HDF5 File------------------------------------------#
    # filename+=".hdf5"
    # hdf5_file = h5py.File(filename, 'w', driver='mpio', comm=comm)
    # hdf_bs = hdf5_file.create_dataset("BS",(len(BS),))
    # hdf_bs[:] = BS[:]
    # hdf_as = hdf5_file.create_dataset("array_size",(len(arr0.shape)+ONE,))
    # hdf_as[:] = (time_steps,)+arr0.shape
    # hdf_aff = hdf5_file.create_dataset("AF",(ONE,))
    # hdf_aff[ZERO] = AF
    # hdf_time = hdf5_file.create_dataset("time",(1,))
    # hdf5_data_set = hdf5_file.create_dataset("data",(time_steps+ONE,arr0.shape[ZERO],arr0.shape[ONE],arr0.shape[TWO]),dtype=dType)
    # hregion = (WR[1],slice(WR[2].start-OPS,WR[2].stop-OPS,1),slice(WR[3].start-OPS,WR[3].stop-OPS,1))
    # hdf5_data_set[0,hregion[0],hregion[1],hregion[2]] = sarr[TSO-ONE,WR[1],WR[2],WR[3]]
    # cwt = 1 #Current write time
    # wb = 0  #Counter for writing on the appropriate step
    # comm.Barrier() #Ensure all processes are prepared to solve
    # #-------------------------------SWEPT RULE---------------------------------------------#
    # pargs = (SM,GRB,BS,GRD,CRS,OPS,TSO,ssb) #Passed arguments to the swept functions
    # #-------------------------------FIRST PYRAMID-------------------------------------------#
    # UpPyramid(sarr,larr,WR,BDR,up_sets,wb,pargs) #THis modifies shared array
    # wb+=1
    # comm.Barrier()
    # #-------------------------------FIRST BRIDGE-------------------------------------------#
    # #Getting x and y arrays
    # xarr = np.copy(sarr[XR])
    # yarr = np.copy(sarr[YR])
    # comm.Barrier()  #Barrier after read
    # # Bridge Step
    # Bridge(sarr,xarr,yarr,wxt,wyt,bridge_sets,wb,pargs) #THis modifies shared array
    # comm.Barrier()  #Solving Bridge Barrier
    # #------------------------------SWEPT LOOP-------------------------------#
    # #Getting next points for the local array
    # larr = np.copy(sarr[SRR])
    # comm.Barrier()
    # #Swept Octahedrons and Bridges
    # for GST in range(MGST):
    #     comm.Barrier()  #Read barrier for local array
    #     #-------------------------------FIRST OCTAHEDRON (NONSHIFT)-------------------------------------------#
    #     Octahedron(sarr,larr,SWR,SBDR,oct_sets,wb,pargs)
    #     comm.Barrier()  #Solving Barrier
    #     # Writing Step
    #     cwt,wb = hdf_swept_write(cwt,wb,sarr,WR,hdf5_data_set,hregion,MPSS,TSO,IEP)
    #     comm.Barrier()  #Write Barrier
    #     #Updating Boundary Conditions Step
    #     boundary_update(sarr,OPS,SPLITX,SPLITY) #Communicate all boundaries
    #     comm.Barrier()
    #     #-------------------------------FIRST REVERSE BRIDGE-------------------------------------------#
    #     #Getting reverse x and y arrays
    #     xarr = np.copy(sarr[YR]) #Regions are purposely switched here
    #     yarr = np.copy(sarr[XR])
    #     comm.Barrier()  #Barrier after read
    #     #Reverse Bridge Step
    #     Bridge(sarr,xarr,yarr,wxts,wyts,bridge_sets,wb,pargs) #THis modifies shared array
    #     comm.Barrier()  #Solving Bridge Barrier
    #     #-------------------------------SECOND OCTAHEDRON (SHIFT)-------------------------------------------#
    #     #Getting next points for the local array
    #     larr = np.copy(sarr[RR])
    #     comm.Barrier()
    #     #Octahedron Step
    #     Octahedron(sarr,larr,WR,BDR,oct_sets,wb,pargs)
    #     comm.Barrier()  #Solving Barrier
    #     #Write step
    #     cwt,wb = hdf_swept_write(cwt,wb,sarr,WR,hdf5_data_set,hregion,MPSS,TSO,IEP)
    #     comm.Barrier()
    #     #Updating Boundary Conditions Step
    #     boundary_update(sarr,OPS,SPLITX,SPLITY) #Communicate all boundaries
    #     comm.barrier()  #Barrier following data write
    #     #-------------------------------SECOND BRIDGE (NON-REVERSED)-------------------------------------------#
    #     #Getting x and y arrays
    #     xarr = np.copy(sarr[XR])
    #     yarr = np.copy(sarr[YR])
    #     comm.Barrier()  #Barrier after read
    #     #Bridge Step
    #     Bridge(sarr,xarr,yarr,wxt,wyt,bridge_sets,wb,pargs) #THis modifies shared array
    #     comm.Barrier()
    #     #Getting next points for the local array
    #     larr = np.copy(sarr[SRR])
    # #Last read barrier for down pyramid
    # comm.Barrier()
    # #--------------------------------------DOWN PYRAMID------------------------#
    # DownPyramid(sarr,larr,SWR,SBDR,down_sets,wb,pargs)
    # comm.Barrier()
    # #Writing Step
    # hdf_swept_write(cwt,wb,sarr,WR,hdf5_data_set,hregion,MPSS,TSO,IEP)
    # comm.Barrier()  #Write Barrier
    # # CUDA clean up - One of the last steps
    # if GRB:
    #     cuda_context.pop()
    # comm.Barrier()
    # #-------------------------------TIMING-------------------------------------#
    # stop = timer.time()
    # exec_time = abs(stop-start)
    # exec_time = comm.gather(exec_time)
    # if rank == master_rank:
    #     avg_time = sum(exec_time)/num_ranks
    #     hdf_time[0] = avg_time
    # comm.Barrier()
    # # Close file
    # hdf5_file.close()
    # comm.Barrier()
    # #This if for testing only
    # if rank == master_rank:
    #     return avg_time

if __name__ == "__main__":
    nx = ny = 512
    bs = 8
    t0 = 0
    tf = 0.1
    dt = 0.01
    dx = dy = 0.1
    gamma = 1.4
    arr = np.ones((4,nx,ny))
    X = 1
    Y = 1
    tso = 2
    ops = 2
    aff = 0.5    #Dimensions and steps
    dx = X/nx
    dy = Y/ny
    #Changing arguments
    gargs = (t0,tf,dt,dx,dy,gamma)
    swargs = (tso,ops,bs,aff,"./src/equations/euler.h","./src/equations/euler.py")
    dsweep(arr,gargs,swargs,filename="test")
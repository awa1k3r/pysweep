#Programmer: Anthony Walker
#This file is for global variable initialization
from block import create_dist_up_sets,create_dist_bridge_sets,create_dist_down_sets
from decomposition import create_shared_pool_array

def init_globals(ops,tso,af,bs,mpss):
    """Use this function to initialize globals."""
    #Setting global variables
    global carr,OPS,TSO,AF,gts,up_sets, down_sets, oct_sets, x_sets, y_sets,SM
    up_sets = create_dist_up_sets(BS,OPS)
    down_sets = create_dist_down_sets(BS,OPS)
    oct_sets = down_sets+up_sets
    x_sets,y_sets = create_dist_bridge_sets(BS,OPS,MPSS)
    carr = create_shared_pool_array(sarr[total_cpu_block].shape)
    gts = 0  #Counter for writing on the appropriate step
    OPS = ops
    TSO = tso
    AF = af
    SM

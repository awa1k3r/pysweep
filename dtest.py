from pysweep.sweep.distsweep import dsweep
import numpy as np

if __name__ == "__main__":
    # nx = ny = 120
    ny = 12
    nx = 12
    bs = 12
    t0 = 0
    gamma = 1.4
    arr = np.ones((4,nx,ny))
    # ct = 0
    # for i in range(nx):
    #     for j in range(ny):
    #         arr[0,i,j] = ct
    #         ct+=1
    # arr[:,256:,:] += 1
    X = 10
    Y = 10
    tso = 2
    ops = 2
    aff = 1 #Dimensions and steps
    dx = X/nx
    dy = Y/ny
    alpha = 5
    Fo = 0.24
    dt = Fo*(X/nx)**2/alpha
    tf = dt*100
    tf = 0.1
    dt = 0.02
    #Changing arguments
    gargs = (t0,tf,dt,dx,dy,alpha)
    swargs = (tso,ops,bs,aff,"./pysweep/equations/eqt.h","./pysweep/equations/eqt.py")
    dsweep(arr,gargs,swargs,filename="test",exid=[1])
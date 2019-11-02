#Programmer: Anthony Walker
#Use this file to generate figures for the 2D swept paper
import sys, os
sys.path.insert(0, './pysweep')
import numpy as np
from itertools import cycle
import matplotlib as mpl
mpl.use("tkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gsc
from matplotlib import cm
from collections.abc import Iterable
import matplotlib.animation as animation
from mpl_toolkits import mplot3d
from sweep.dcore import block

colors = ['dodgerblue','orange','dodgerblue','orange','dodgerblue','orange']
symbols = cycle(['o','o','o','o'])
elev = 53
azim=-48
bsx = 12
bsh = int(bsx/2)
ops = 1
nd = 4
ndy = 2
npx = nd*bsx
npy = ndy*bsx
MPSS = int(bsx/(2*ops)-1)
slb = 0
sub = npx

def make_node_surfaces(ax,colors,spacing):
    """Use this method to make node base colors"""
    for i,c in enumerate(colors):
        xx, yy = np.meshgrid([i*spacing-bsh,(i+1)*spacing-bsh], [-bsh,npy+bsh])
        zz = np.zeros(np.shape(xx))*-1
        ax.plot_surface(xx,yy,zz,color=c,alpha=0.2)

def make_block(ax,start,length,width,height,sc="blue"):
    """Use this function to make a block surface"""
    alp = 1
    xx, yy = np.meshgrid([start[0],start[0]+length], [start[1],start[1]+width])
    zz = np.ones(np.shape(xx))*start[2]
    ax.plot_surface(xx,yy,zz,color=sc,edgecolors='black',alpha=alp)
    xx, yy = np.meshgrid([start[0],start[0]+length], [start[1],start[1]+width])
    zz = np.ones(np.shape(xx))*(start[2]+height)
    ax.plot_surface(xx,yy,zz,color=sc,edgecolors='black',alpha=alp)
    xx, yy = np.meshgrid([start[2],start[2]+height], [start[1],start[1]+width])
    zz = np.ones(np.shape(xx))*(start[0])
    ax.plot_surface(zz,yy,xx,color=sc,edgecolors='black',alpha=alp)
    zz = np.ones(np.shape(xx))*(start[1])
    xx, yy = np.meshgrid([start[0],start[0]+length], [start[2],start[2]+height])
    ax.plot_surface(xx,zz,yy,color=sc,edgecolors='black',alpha=alp)
    xx, yy = np.meshgrid([start[2],start[2]+height], [start[1],start[1]+width])
    zz = np.ones(np.shape(xx))*(start[0]+length)
    ax.plot_surface(zz,yy,xx,color=sc,edgecolors='black',alpha=alp)
    zz = np.ones(np.shape(xx))*(start[1]+width)
    xx, yy = np.meshgrid([start[0],start[0]+length], [start[2],start[2]+height])
    ax.plot_surface(xx,zz,yy,color=sc,edgecolors='black',alpha=alp)


def SweptPlot():
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1,projection='3d',elev=elev,azim=azim)
    ax.set_title("UpPyramid",fontweight='bold',y=1.1)
    upsets = block.create_dist_up_sets((bsx,bsx,1),ops)
    yset,xset = block.create_dist_bridge_sets((bsx,bsx,1),ops,MPSS)
    ts = len(upsets)
    ax.set_xlabel("\n\nX")
    ax.set_ylabel("\n\nY")
    ax.set_zlabel("t")
    zlim = 20
    bsh = int(bsx/2)
    ax.set_zlim3d([0,zlim])
    ax.set_ylim3d([slb-bsh,npy+bsh])
    ax.set_xlim3d([slb-bsh,sub+bsh])
    ax.get_zaxis().set_ticks([0,10])
    ax.get_xaxis().set_ticks([0,int(bsx*nd/2),int(bsx*nd)])
    ax.get_yaxis().set_ticks([0,int(npy/2),npy])
    make_node_surfaces(ax,['red','green'],(npx+bsx)/ndy)
    #Create UpPyramids
    ct = 0
    for i in range(nd):
        for j in range(ndy):
            for k in range(1,len(upsets)+1):
                make_block(ax,(k*ops+i*bsx,k*ops+j*bsx,k),bsx-2*ops*k,bsx-2*ops*k,1,sc=colors[ct])
        ct+=1

    ms = 6
    scale = 1.2
    f = lambda x,y,z: mplot3d.proj3d.proj_transform(x,y,z, ax.get_proj())[:2]
    fl1 = mpl.lines.Line2D([0],[0], linestyle="none", c='dodgerblue', marker = 'o',markersize=ms,markeredgecolor='black')
    fl2 = mpl.lines.Line2D([0],[0], linestyle="none", c='orange', marker = 'o',markersize=ms,markeredgecolor='black')
    fl3 = mpl.lines.Line2D([0],[0], linestyle="none", c='red', marker = 'o',markersize=ms,markeredgecolor='black')
    fl4 = mpl.lines.Line2D([0],[0], linestyle="none", c='green', marker = 'o',markersize=ms,markeredgecolor='black')
    leg1 = ax.legend([fl1,fl2,fl3,fl4],[' GPU   ',' CPU    ','node 1','node 2'],markerscale=scale,ncol=1,loc="lower left", bbox_to_anchor=f(-40,0,-5),
          bbox_transform=ax.transData)
    plt.savefig('UpPyramid.png')
    ax.set_title("Y-Bridge",fontweight='bold',y=1.1)

    # Create Y-Bridges
    ct = 0
    for i in range(nd):
        for k in range(1,len(yset)+1):
            make_block(ax,(k*ops+i*bsx,bsx-ops-k*ops,k),bsx-2*ops*k,2*ops*(k)+ops,1,sc=colors[ct])
        ct+=1
    #Close Edge Y Bridges
    ct = 0
    for i in range(nd):
        for k in range(1,len(yset)+1):
            make_block(ax,(k*ops+i*bsx,0,k),bsx-2*ops*k,ops*(k),1,sc=colors[ct])
        ct+=1
    #Far Edge Y Bridges
    ct = 0
    for i in range(nd):
        for k in range(1,len(yset)+1):
            make_block(ax,(k*ops+i*bsx,npy-ops*k,k),bsx-2*ops*k,ops*(k),1,sc=colors[ct])
        ct+=1
    plt.savefig('YBridge.png')
    plt.show()


if __name__ == "__main__":
    SweptPlot()
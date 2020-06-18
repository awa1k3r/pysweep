import sys, os, yaml, numpy, warnings, subprocess, traceback, time,  mpi4py.MPI as MPI
import pysweep.core.GPUtil as GPUtil
import pysweep.core.io as io
import pysweep.core.process as process
import pysweep.core.functions as functions
import pysweep.core.block as block

class Solver(object):
    """docstring for Solver."""
    def __init__(self, initialConditions, yamlFileName=None,sendWarning=True):
        super(Solver, self).__init__()
        self.moments = [time.time(),]
        self.initialConditions = initialConditions
        self.arrayShape = numpy.shape(initialConditions)
        self.corepath = os.path.dirname(os.path.abspath(__file__))
        self.libpath = os.path.join(self.corepath,"lib")


        if yamlFileName is not None:
            self.yamlFileName = yamlFileName
            #Managing inputs
            io.yamlManager(self)
            self.initialConditions = self.initialConditions.astype(self.dtype)
        else:
            if sendWarning:
                warnings.warn('yaml not specified, requires manual input.')

    def __call__(self,start=0,stop=-1,libname=None,recompile=False):
        """Use this function to spawn processes."""
        #Grabbing start of call time
        self.moments.append(time.time())

        #set up MPI
        process.setupMPI(self)
        self.moments.append(time.time())

        #Compiling GPU kernel
        self.cudaCompiler(libname=libname,recompile=recompile)
        self.moments.append(time.time())

        #Creating time step data
        io.verbosePrint(self,'Creating time step data...\n')
        self.createTimeStepData()
        self.moments.append(time.time())

        #Creating simulatneous input and output file
        io.verbosePrint(self,'Creating output file...\n')
        io.createOutputFile(self)
        self.moments.append(time.time())

        # Creating shared array
        io.verbosePrint(self,'Creating shared memory arrays and process functions...\n')
        if self.simulation:
            block.sweptBlock(self)
        else:
            block.standardBlock(self)
        self.moments.append(time.time())
        # io.verbosePrint(self,'Running simulation...\n')
        #Process cleanup
        io.verbosePrint(self,'Cleaning up processes...\n')
        process.cleanupProcesses(self,self.moments[start],self.moments[stop])

    def __str__(self):
        """Use this function to print the object."""
        return io.getSolverPrint(self)

    def createTimeStepData(self):
        """Use this function to create timestep data."""
        self.time_steps = int((self.timeTuple[1]-self.timeTuple[0])/self.timeTuple[2])  #Number of time steps
        if self.simulation:
            self.splitx = self.blocksize[0]//2
            self.splity = self.blocksize[1]//2
            self.maxPyramidSize = self.blocksize[0]//(2*self.operating)-1 #This will need to be adjusted for differing x and y block lengths
            self.maxGlobalSweptStep = int(self.intermediate*(self.time_steps-self.maxPyramidSize)/(self.maxPyramidSize)+1)  #Global swept step  #THIS ASSUMES THAT time_steps > MOSS
            self.time_steps = int(self.maxPyramidSize*(self.maxGlobalSweptStep+1)/self.intermediate+1) #Number of time
            self.maxOctSize = 2*self.maxPyramidSize
        self.arrayShape = (self.maxOctSize+self.intermediate+1,)+self.arrayShape

    def cudaCompiler(self,libname=None,recompile=False):
        """Use this function to create compiled lib."""
        if self.clusterMasterBool:

            if libname is None:
                basename = os.path.basename(self.source['gpu']).split(".")[0]
                self.libname = os.path.join(self.libpath,"lib{}.so".format(basename))

            if not os.path.exists(self.libname) or recompile:
                io.verbosePrint(self,'Attempting to create shared library...\n')
                nvccStatement = '''nvcc -Xcompiler -fPIC -shared -DPYSWEEP_GPU_SOURCE=\'\"{}\"\' -o {} {}'''.format(self.source['gpu'],self.libname,os.path.join(self.corepath,"pysweep.cu"))
                os.system(nvccStatement)
            else:
                warnings.warn('{} already exists, code was not recompiled, set recompile=True to force recompile'.format(os.path.basename(self.libname)))
        self.comm.Barrier()

    def standardSolve():
        # -------------------------------Standard Decomposition---------------------------------------------#
        node_comm.Barrier()
        cwt = 1
        for i in range(TSO*time_steps):
            functions.Decomposition(GRB,OPS,sarr,garr,blocks,mpi_pool,DecompObj)
            node_comm.Barrier()
            #Write data and copy down a step
            if (i+1)%TSO==0 and NMB:
                hdf5_data[cwt,i1,i2,i3] = sarr[TSO,:,OPS:-OPS,OPS:-OPS]
                sarr = numpy.roll(sarr,TSO,axis=0) #Copy down
                cwt+=1
            elif NMB:
                sarr = numpy.roll(sarr,TSO,axis=0) #Copy down
            node_comm.Barrier()
            #Communicate
            functions.send_edges(sarr,NMB,GRB,node_comm,cluster_comm,comranks,OPS,garr,DecompObj)

    def sweptSolve():
        # -------------------------------SWEPT RULE---------------------------------------------#
        # -------------------------------FIRST PRISM AND COMMUNICATION-------------------------------------------#
        functions.FirstPrism(SM,GRB,Up,Yb,mpiPool,blocks,sarr,garr,total_cpu_block)
        node_comm.Barrier()
        functions.first_forward(NMB,GRB,node_comm,cluster_comm,comranks,sarr,SPLITX,total_cpu_block)
        #Loop variables
        cwt = 1 #Current write time
        gts = 0 #Initialization of global time step
        del Up #Deleting Up object after FirstPrism
        #-------------------------------SWEPT LOOP--------------------------------------------#
        step = cycle([functions.send_backward,functions.send_forward])
        for i in range(MGST):
            functions.UpPrism(GRB,Xb,Yb,Oct,mpiPool,blocks,sarr,garr,total_cpu_block)
            node_comm.Barrier()
            cwt = next(step)(cwt,sarr,hdf5_data,gsc,NMB,GRB,node_comm,cluster_comm,comranks,SPLITX,gts,TSO,MPSS,total_cpu_block)
            gts+=MPSS
        #Do LastPrism Here then Write all of the remaining data
        Down.gts = Oct.gts
        functions.LastPrism(GRB,Xb,Down,mpiPool,blocks,sarr,garr,total_cpu_block)
        node_comm.Barrier()
        next(step)(cwt,sarr,hdf5_data,gsc,NMB,GRB,node_comm,cluster_comm,comranks,SPLITX,gts,TSO,MPSS,total_cpu_block)
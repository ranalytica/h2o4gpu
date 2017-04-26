import sys
#sys.path.insert(0, "/home/arno/pogs/src/interface_py/")
import pogs as pogs
import numpy as np
from numpy import abs, exp, float32, float64, log, max, zeros

from ctypes import *
from pogs.types import *


'''
Elastic Net

   minimize    (1/2) ||Ax - b||_2^2 + \alpha * \lambda ||x||_1 + 0.5 * (1-\alpha) * \lambda ||x||_2

   for 100 values of \lambda, and alpha in [0,1]
   See <pogs>/matlab/examples/lasso_path.m for detailed description.
'''

def ElasticNet(X, y, nGPUs=0, nlambda=100, nalpha=1):
  # set solver cpu/gpu according to input args
  if((nGPUs>0) and (pogs.ElasticNetSolverGPU is None)):
    print("\nGPU solver unavailable, using CPU solver\n")
    nGPUs=0

  Solver = pogs.ElasticNetSolverGPU if(nGPUs>0) else pogs.ElasticNetSolverCPU
#  Solver = pogs.ElasticNetSolverCPU
  assert Solver != None, "Couldn't instantiate ElasticNetSolver"

  sharedA = 0
  sourceme = 0
  sourceDev = 0
  nThreads = 1 if(nGPUs==0) else nGPUs # not required number of threads, but normal.  Bit more optimal to use 2 threads for CPU, but 1 thread per GPU is optimal.
  intercept = 1
  standardize = 0
  lambda_min_ratio = 1e-9
  nLambdas = nlambda
  nAlphas = nalpha

  if standardize:
    print ("implement standardization transformer")
    exit()

  # Setup Train/validation Set Split
  morig = X.shape[0]
  norig = X.shape[1]
  print("Original m=%d n=%d" % (morig,norig))
  fortran = X.flags.f_contiguous
  print("fortran=%d" % (fortran))

  
  # Do train/valid split
  H=int(0.8*morig)
  print("Size of Train/valid rows H=%d" % (H))
  trainX = np.copy(X[0:H,:])
  trainY = np.copy(y[0:H])
  validX = np.copy(X[H:-1,:])
  validY = np.copy(y[H:-1])
  mTrain = trainX.shape[0]
  mvalid = validX.shape[0]
  print("mTrain=%d mvalid=%d" % (mTrain,mvalid))
  
  ## TODO: compute these in C++ (CPU or GPU)
  sdtrainY = np.sqrt(np.var(trainY))
  print("sdtrainY: " + str(sdtrainY))
  meantrainY = np.mean(trainY)
  print("meantrainY: " + str(meantrainY))

  ## TODO: compute these in C++ (CPU or GPU)
  sdvalidY = np.sqrt(np.var(validY))
  print("sdvalidY: " + str(sdvalidY))
  meanvalidY = np.mean(validY)
  print("meanvalidY: " + str(meanvalidY))

  ## TODO: compute this in C++ (CPU or GPU)
  # compute without intercept column
  #weights = 1./mTrain
  weights = 1. # like current cpp driver
  if intercept==1:
    lambda_max0 = weights * max(abs(trainX.T.dot(trainY-meantrainY)))
  else:
    lambda_max0 = weights * max(abs(trainX.T.dot(trainY)))

  print("lambda_max0: " + str(lambda_max0))

  if intercept==1:
    trainX = np.hstack([trainX, np.ones((trainX.shape[0],1),dtype=trainX.dtype)])
    validX = np.hstack([validX, np.ones((validX.shape[0],1),dtype=validX.dtype)])
    n = trainX.shape[1]
    print("New n=%d" % (n))



  ## Constructor
  print("Setting up solver")
  enet = Solver(sharedA, nThreads, nGPUs, 'c' if fortran else 'r', intercept, standardize, lambda_min_ratio, nLambdas, nAlphas)

  ## First, get backend pointers
  print("Uploading")
  print(trainX.dtype)
  print(trainY.dtype)
  print(validX.dtype)
  print(validY.dtype)
  a,b,c,d = enet.upload_data(sourceDev, trainX, trainY, validX, validY)

  ## Solve
  print("Solving")
  enet.fit(sourceDev, mTrain, n, mvalid, intercept, standardize, lambda_max0, sdtrainY, meantrainY, sdvalidY, meanvalidY, a, b, c, d)
  print("Done Solving")

  return enet

if __name__ == "__main__":
  import numpy as np
  from numpy.random import randn
#  m=1000
#  n=100
#  A=randn(m,n)
#  x_true=(randn(n)/n)*float64(randn(n)<0.8)
#  b=A.dot(x_true)+0.5*randn(m)
  import pandas as pd
  import feather
  #df = feather.read_dataframe("../../../h2oai-prototypes/glm-bench/ipums.feather")
  df = pd.read_csv("../cpp/ipums.txt", sep=" ", header=None)
  print(df.shape)
  X = np.array(df.iloc[:,:df.shape[1]-1], dtype='float32', order='C')
  y = np.array(df.iloc[:, df.shape[1]-1], dtype='float32', order='C')
  ElasticNet(X, y, nGPUs=4, nlambda=100, nalpha=16)
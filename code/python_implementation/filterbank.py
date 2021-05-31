from numpy.lib.function_base import blackman
import scipy.fftpack as fftfuncs
from scipy.linalg import dft
import numpy
import math

def filterbank(sig, bandlimits=[0,200,400,800,1600,3200], maxfreq=4096):
    
    transformed_sig = fftfuncs.fft(sig)
    
    n = len(sig)
    nbands = len(bandlimits)
    iters = nbands - 1
    bl = [0]*iters
    br = [0]*iters

    for i in range(1,iters):
        bl[i] = math.floor(bandlimits[i]/maxfreq*n/2)+1
        br[i] = math.floor(n/2)

    bl[nbands-2] = math.floor(bandlimits[i]/maxfreq*n/2)+1
    br[nbands-2] = math.floor(n/2)
    
    output = numpy.zeros((n,nbands))

    for i in range(1,nbands):
        output[bl[i]:br[i]:i] = transformed_sig[bl[i]:br[i]]
        output[n+1-br[i]:n+1-bl[i]:i] = transformed_sig[n+1-br[i]:n+1-bl[i]]
        

    output[0,0] = 0

    return output
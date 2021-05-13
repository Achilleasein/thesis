import scipy.fftpack as fftfuncs

def filterbank(sig, bandlimits=[0,200,400,800,1600,3200], maxfreq=4096):
    
    fftfuncs.fft()
    return 0 
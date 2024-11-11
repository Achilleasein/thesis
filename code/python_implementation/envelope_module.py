# envelope_module.py

import numpy as np
from scipy.signal import get_window
from numpy.fft import fft, ifft

def get_envelope(signal, fs, window_length=0.4):
    """
    Extracts the envelope of a signal using full-wave rectification and convolution with a Hanning window.
    
    Parameters:
        signal (np.ndarray): The input signal.
        fs (int): Sampling frequency of the signal.
        window_length (float): Length of the Hanning window in seconds.
        
    Returns:
        np.ndarray: The envelope of the input signal.
    """
    # Full-wave rectification
    rectified_signal = np.abs(signal)

    # Create half Hanning window
    window_samples = int(window_length * fs) // 2  # Use half-window length
    hanning_window = get_window('hann', window_samples * 2)
    half_window = hanning_window[:window_samples]

    # Convolve in the frequency domain
    signal_freq = fft(rectified_signal, n=rectified_signal.size + half_window.size - 1)
    window_freq = fft(half_window, n=signal_freq.size)
    envelope_freq = signal_freq * window_freq
    envelope = np.real(ifft(envelope_freq))

    # Trim the result to the original signal length
    envelope = envelope[:len(rectified_signal)]
    return envelope

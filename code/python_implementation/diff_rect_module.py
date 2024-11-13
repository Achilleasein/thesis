# diff_rect_module.py

import numpy as np

def diff_rect(signal, fs):
    """
    Differentiates a signal in time and applies half-wave rectification.

    Parameters:
        signal (np.ndarray): The input signal (envelope).
        fs (int): Sampling frequency of the signal.

    Returns:
        np.ndarray: The differentiated and half-wave rectified signal.
    """
    # Differentiate the signal in time
    differentiated_signal = np.diff(signal, prepend=signal[0])

    # Half-wave rectification (keep only positive values)
    half_wave_rectified_signal = np.maximum(differentiated_signal, 0)
    
    return half_wave_rectified_signal

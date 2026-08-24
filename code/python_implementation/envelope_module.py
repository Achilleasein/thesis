# envelope_module.py

"""Amplitude-envelope extraction: rectify, then smooth with a half-Hann window."""
import logging

import numpy as np
from scipy.signal import get_window, oaconvolve

logger = logging.getLogger(__name__)

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
    signal = np.asarray(signal)
    n = signal.size
    logger.debug("get_envelope: start (len=%d, fs=%d, window_length=%.3fs)", n, fs, window_length)

    # Full-wave rectification
    rectified_signal = np.abs(signal)
    logger.debug("Rectified signal computed (len=%d)", rectified_signal.size)

    # Create half Hanning window
    window_samples = int(window_length * fs) // 2  # Use half-window length
    if window_samples <= 0:
        logger.warning("Computed window_samples <= 0 (window_length=%.3f, fs=%d). Forcing to 1.", window_length, fs)
        window_samples = 1
    # Take the DECAYING half (second half of the full window), matching
    # hwindow.m's cos(a*pi/hannlen/2)^2 which starts near 1 and falls to 0.
    # The rising half would ramp up over the whole window before an onset's
    # energy is fully counted, turning the sharp attack that diff_rect looks
    # for into a broad plateau. This half gives a fast attack, slow decay.
    hanning_window = get_window('hann', window_samples * 2)
    half_window = hanning_window[window_samples:]
    logger.debug("Half Hanning window created (samples=%d)", half_window.size)

    # Convolve, then trim back to the original signal length.
    #
    # Overlap-add is the right algorithm here: the window is ~1200x shorter than
    # the signal, so a single FFT spanning the whole track wastes almost all of
    # its work. The previous implementation did exactly that -- a complex FFT at
    # len(signal) + len(window) - 1, an arbitrary length that is typically far
    # from a fast one (and can be dominated by a large prime factor, forcing the
    # slow Bluestein path). oaconvolve blocks the work and uses real FFTs at
    # chosen fast lengths: measured 49x faster on a 244 s track (4.85s -> 0.10s)
    # and identical to within float64 round-off (~2e-15 relative).
    envelope = oaconvolve(rectified_signal, half_window, mode='full')[:rectified_signal.size]
    logger.debug("Convolution completed (len=%d)", envelope.size)

    logger.info("Envelope extraction done (len=%d, fs=%d, window_length=%.3fs)", envelope.size, fs, window_length)
    return envelope

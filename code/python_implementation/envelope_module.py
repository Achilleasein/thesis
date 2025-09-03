# envelope_module.py

import numpy as np
from scipy.signal import get_window
from numpy.fft import fft, ifft
import logging

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
    hanning_window = get_window('hann', window_samples * 2)
    half_window = hanning_window[:window_samples]
    logger.debug("Half Hanning window created (samples=%d)", half_window.size)

    # Convolve in the frequency domain
    fft_len = rectified_signal.size + half_window.size - 1
    logger.debug("FFT length for convolution: %d", fft_len)
    signal_freq = fft(rectified_signal, n=fft_len)
    window_freq = fft(half_window, n=fft_len)
    envelope_freq = signal_freq * window_freq
    envelope = np.real(ifft(envelope_freq))
    logger.debug("IFFT completed (len=%d)", envelope.size)

    # Trim the result to the original signal length
    envelope = envelope[:len(rectified_signal)]
    logger.debug("Envelope trimmed to original length (len=%d)", envelope.size)

    logger.info("Envelope extraction done (len=%d, fs=%d, window_length=%.3fs)", envelope.size, fs, window_length)
    return envelope

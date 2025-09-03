# diff_rect_module.py

import numpy as np
import logging

logger = logging.getLogger(__name__)

def diff_rect(signal, fs):
    """
    Differentiates a signal in time and applies half-wave rectification.

    Parameters:
        signal (np.ndarray): The input signal (envelope).
        fs (int): Sampling frequency of the signal.

    Returns:
        np.ndarray: The differentiated and half-wave rectified signal.
    """
    signal = np.asarray(signal)
    n = signal.size
    logger.debug("diff_rect: start (len=%d, fs=%d)", n, fs)

    # Differentiate the signal in time
    differentiated_signal = np.diff(signal, prepend=signal[0])
    logger.debug("diff_rect: differentiated (len=%d)", differentiated_signal.size)

    # Half-wave rectification (keep only positive values)
    half_wave_rectified_signal = np.maximum(differentiated_signal, 0)
    logger.debug("diff_rect: half-wave rectified (len=%d, nonzero=%d)",
                 half_wave_rectified_signal.size, int(np.count_nonzero(half_wave_rectified_signal)))

    logger.info("diff_rect: done (len=%d, fs=%d)", half_wave_rectified_signal.size, fs)
    return half_wave_rectified_signal

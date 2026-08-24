# diff_rect_module.py

"""Time differentiation plus half-wave rectification: the onset detector."""
import logging

import numpy as np

logger = logging.getLogger(__name__)

def diff_rect(signal):
    """
    Differentiates a signal in time and applies half-wave rectification.

    The operation is sample-based, so unlike the other pipeline stages this one
    needs no sampling frequency.

    Parameters:
        signal (np.ndarray): The input signal (envelope).

    Returns:
        np.ndarray: The differentiated and half-wave rectified signal.
    """
    signal = np.asarray(signal)
    logger.debug("diff_rect: start (len=%d)", signal.size)

    # Differentiate the signal in time
    differentiated_signal = np.diff(signal, prepend=signal[0])
    logger.debug("diff_rect: differentiated (len=%d)", differentiated_signal.size)

    # Half-wave rectification (keep only positive values)
    half_wave_rectified_signal = np.maximum(differentiated_signal, 0)
    logger.debug("diff_rect: half-wave rectified (len=%d, nonzero=%d)",
                 half_wave_rectified_signal.size, int(np.count_nonzero(half_wave_rectified_signal)))

    logger.info("diff_rect: done (len=%d)", half_wave_rectified_signal.size)
    return half_wave_rectified_signal

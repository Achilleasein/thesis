# comb_filter_module.py

import numpy as np
from scipy.fft import rfft, next_fast_len  # real FFT for speed/memory
import logging

logger = logging.getLogger(__name__)


def create_comb_filter(fs, tempo, num_impulses=3):
    """
    Creates a comb filter with a specified tempo and number of impulses.

    Parameters:
        fs (int): Sampling frequency.
        tempo (float): Tempo in beats per minute (BPM).
        num_impulses (int): Number of impulses in the comb filter.

    Returns:
        np.ndarray: The comb filter in the time domain.
    """
    logger.debug("create_comb_filter: fs=%d, tempo=%.3f BPM, num_impulses=%d", fs, float(tempo), num_impulses)
    # Ensure at least one-sample period to avoid zero/negative sizes
    period = max(1, int(fs * 60.0 / float(tempo)))  # Period of the comb filter in samples
    logger.debug("create_comb_filter: computed period=%d samples", period)
    # Comb length covers num_impulses impulses spaced by period
    comb_filter = np.zeros(period * (num_impulses - 1) + 1, dtype=float)
    comb_filter[::period] = 1.0  # Set impulses at periodic intervals
    logger.info("create_comb_filter: created filter (length=%d, impulses=%d)", comb_filter.size, num_impulses)
    return comb_filter


def analyze_tempo(signal, fs, tempos, num_impulses=3):
    """
    Analyzes the energy of a signal convolved with comb filters for different tempos.

    Parameters:
        signal (np.ndarray): Input signal (differentiated and rectified).
        fs (int): Sampling frequency.
        tempos (np.ndarray): Array of tempos (in BPM) to analyze.
        num_impulses (int): Number of impulses in the comb filters.

    Returns:
        np.ndarray: Energy of the signal for each tempo.
    """
    logger.info("analyze_tempo: start (len=%d, fs=%d, tempos=%d..%d BPM, step≈%.3f, num_impulses=%d)",
                np.asarray(signal).size, fs, int(np.min(tempos)), int(np.max(tempos)),
                float(tempos[1] - tempos[0]) if len(tempos) > 1 else float('nan'), num_impulses)

    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1:
        signal = signal.ravel()
        logger.debug("analyze_tempo: signal reshaped to 1D (len=%d)", signal.size)

    # Determine an efficient FFT length:
    min_tempo = float(np.min(tempos))
    max_period = max(1, int(fs * 60.0 / min_tempo))  # largest spacing among tempos
    n_desired = signal.size + max_period
    n_fast = next_fast_len(n_desired)
    logger.debug("analyze_tempo: n_desired=%d, n_fast=%d (max_period=%d)", n_desired, n_fast, max_period)

    # Compute real FFT of the signal once (reuse for all tempos)
    signal_freq = rfft(signal, n=n_fast)
    logger.debug("analyze_tempo: computed signal FFT (len=%d)", signal_freq.size)

    energies = []
    # We can compute the energy directly in the frequency domain using Parseval's theorem,
    # avoiding an inverse FFT for each tempo.
    scale = 1.0 / n_fast  # Parseval scaling for numpy/scipy FFT conventions

    for i, tempo in enumerate(tempos):
        # Create comb filter and transform with the same FFT length
        comb_filter = create_comb_filter(fs, float(tempo), num_impulses)
        comb_filter_freq = rfft(comb_filter, n=n_fast)

        # Energy of the convolution in time domain equals (1/N) * sum |X[k]*H[k]|^2
        yh_mag2 = np.abs(signal_freq * comb_filter_freq) ** 2
        energy = float(np.sum(yh_mag2) * scale)
        energies.append(energy)

        if i % max(1, len(tempos)//10) == 0 or i == len(tempos) - 1:
            logger.debug("analyze_tempo: tempo=%.2f BPM -> energy=%.6e (%d/%d)",
                         float(tempo), energy, i + 1, len(tempos))

    energies = np.array(energies, dtype=float)
    best_idx = int(np.argmax(energies)) if energies.size else -1
    best_tempo = float(tempos[best_idx]) if best_idx >= 0 else float('nan')
    logger.info("analyze_tempo: done (best_tempo=%.2f BPM, max_energy=%.6e)", best_tempo,
                float(energies[best_idx]) if best_idx >= 0 else float('nan'))
    return energies

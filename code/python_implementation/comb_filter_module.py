# comb_filter_module.py

import numpy as np
from scipy.fft import rfft, next_fast_len  # real FFT for speed/memory


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
    # Ensure at least one-sample period to avoid zero/negative sizes
    period = max(1, int(fs * 60.0 / float(tempo)))  # Period of the comb filter in samples
    # Comb length covers num_impulses impulses spaced by period
    comb_filter = np.zeros(period * (num_impulses - 1) + 1, dtype=float)
    comb_filter[::period] = 1.0  # Set impulses at periodic intervals
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
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1:
        signal = signal.ravel()

    # Determine an efficient FFT length:
    # - Pad enough so the comb filter length fits when convolving in frequency domain
    # - Use next_fast_len for speed
    min_tempo = float(np.min(tempos))
    max_period = max(1, int(fs * 60.0 / min_tempo))  # largest spacing among tempos
    n_desired = signal.size + max_period
    n_fast = next_fast_len(n_desired)

    # Compute real FFT of the signal once (reuse for all tempos)
    signal_freq = rfft(signal, n=n_fast)

    energies = []
    # We can compute the energy directly in the frequency domain using Parseval's theorem,
    # avoiding an inverse FFT for each tempo.
    scale = 1.0 / n_fast  # Parseval scaling for numpy/scipy FFT conventions

    for tempo in tempos:
        # Create comb filter and transform with the same FFT length
        comb_filter = create_comb_filter(fs, float(tempo), num_impulses)
        comb_filter_freq = rfft(comb_filter, n=n_fast)

        # Energy of the convolution in time domain equals (1/N) * sum |X[k]*H[k]|^2
        yh_mag2 = np.abs(signal_freq * comb_filter_freq) ** 2
        energy = float(np.sum(yh_mag2) * scale)
        energies.append(energy)

    return np.array(energies, dtype=float)

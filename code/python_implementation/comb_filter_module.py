# comb_filter_module.py

import numpy as np
from scipy.fft import rfft, irfft, next_fast_len  # real FFT for speed/memory
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
    tempos = np.asarray(tempos, dtype=float)

    # Determine an efficient FFT length:
    min_tempo = float(np.min(tempos))
    max_period = max(1, int(fs * 60.0 / min_tempo))  # largest spacing among tempos
    n_desired = signal.size + max_period
    n_fast = next_fast_len(n_desired)
    logger.debug("analyze_tempo: n_desired=%d, n_fast=%d (max_period=%d)", n_desired, n_fast, max_period)

    # Compute the real FFT of the signal once; its power spectrum |X[k]|^2 does
    # not depend on the comb filter. (.real**2 + .imag**2 avoids the sqrt that
    # np.abs(...)**2 would compute and then immediately undo.)
    signal_freq = rfft(signal, n=n_fast)
    psd = signal_freq.real ** 2 + signal_freq.imag ** 2  # |X[k]|^2, shape (K,)
    logger.debug("analyze_tempo: computed signal FFT (len=%d)", signal_freq.size)

    # The original implementation evaluated, for every tempo,
    #     energy = (1/N) * sum_{k=0}^{K-1} |X[k]|^2 * |H[k]|^2          (K = N//2+1)
    # via a fresh length-N FFT of the comb filter. We compute the identical
    # quantity with NO per-tempo FFT by exploiting the comb's structure.
    #
    # A comb of M impulses spaced by `period` is an impulse train, so
    #   |H[k]|^2 = sum_{a,b} exp(-j 2pi k (a-b) period / N).
    # Summed over the FULL spectrum against |X[k]|^2 this telescopes into the
    # signal's autocorrelation R (R = IFFT(|X|^2), one inverse FFT for ALL
    # tempos), sampled at multiples of `period`:
    #   S_full(tempo) = N * sum_{a,b} R[((a-b)*period) mod N].
    # The original sums only the half (rfft) spectrum, which relates to the full
    # spectrum by S_half = (S_full + DC + Nyquist) / 2, with the DC and Nyquist
    # bins (H[0]=M; H[N/2] depends on period parity) added back exactly.
    R = irfft(psd, n=n_fast)  # circular autocorrelation, R[m] = sum_n x[n]x[(n+m) mod N]

    # Match the original integer-sample period quantisation (int() truncates).
    periods = np.maximum(1, (fs * 60.0 / tempos).astype(np.int64))  # (T,)

    # All (a-b) impulse-index differences, e.g. M=3 -> [0,-1,-2, 1,0,-1, 2,1,0].
    lags = np.arange(num_impulses)
    lag_diffs = (lags[:, None] - lags[None, :]).ravel()                # (M*M,)
    idx = (lag_diffs[None, :] * periods[:, None]) % n_fast             # (T, M*M)
    s_full = n_fast * R[idx].sum(axis=1)                               # (T,)

    # DC bin (k=0): X[0]=sum(signal), H[0]=M -> contribution is constant in tempo.
    dc = psd[0] * float(num_impulses ** 2)
    # Nyquist bin exists only when N is even; H[N/2] = sum_m (-1)^(m*period).
    if n_fast % 2 == 0:
        odd_sum = 1.0 if num_impulses % 2 == 1 else 0.0  # sum_m (-1)^m over M terms
        h_nyq = np.where(periods % 2 == 0, float(num_impulses), odd_sum)
        nyquist = psd[-1] * h_nyq ** 2
    else:
        nyquist = 0.0

    # energy = S_half / N = (S_full + DC + Nyquist) / (2N)
    energies = (s_full + dc + nyquist) / (2.0 * n_fast)

    if logger.isEnabledFor(logging.DEBUG):
        for i in range(0, len(tempos), max(1, len(tempos) // 10)):
            logger.debug("analyze_tempo: tempo=%.2f BPM -> energy=%.6e (%d/%d)",
                         float(tempos[i]), float(energies[i]), i + 1, len(tempos))

    energies = np.asarray(energies, dtype=float)
    best_idx = int(np.argmax(energies)) if energies.size else -1
    best_tempo = float(tempos[best_idx]) if best_idx >= 0 else float('nan')
    logger.info("analyze_tempo: done (best_tempo=%.2f BPM, max_energy=%.6e)", best_tempo,
                float(energies[best_idx]) if best_idx >= 0 else float('nan'))
    return energies

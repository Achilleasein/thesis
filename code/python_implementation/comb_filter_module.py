# comb_filter_module.py

"""Comb-filter tempo estimation: energy of a signal against a bank of combs."""
import logging

import numpy as np
from scipy.fft import rfft, irfft, next_fast_len  # real FFT for speed/memory

logger = logging.getLogger(__name__)


def create_comb_filter(fs, tempo, num_impulses=3):
    """
    Creates a comb filter with a specified tempo and number of impulses.

    Note: ``analyze_tempo`` no longer builds these filters -- it evaluates the
    same energies analytically from the signal's autocorrelation. This function
    is kept as the readable reference definition of the comb the maths encodes,
    and is exercised by the test suite.

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


def combine_band_energies(per_band_energies):
    """
    Sums per-band tempo-energy curves after standardising each one.

    Raw band energies differ by orders of magnitude -- at 44.1 kHz the 1-200 Hz
    band carries roughly 60x the energy of the 3200-5000 Hz band -- so a plain
    sum is in effect the lowest band's opinion alone, and the filterbank's other
    five votes are lost in the rounding. That defeats the point of splitting the
    signal into bands at all.

    Standardising each curve to zero mean and unit variance first makes the
    contributions scale-free: what gets summed is "how many standard deviations
    above its own average does this band favour this tempo". A useful side
    effect is that a band whose curve is mostly noise has a large spread, so its
    jagged peaks are divided down -- noisy bands lose influence without needing
    an explicit quality heuristic.

    Parameters:
        per_band_energies (Sequence[np.ndarray]): One energy curve per band, all
            the same length and on the same tempo grid.

    Returns:
        np.ndarray: The combined curve, in units of per-band standard deviations.
    """
    curves = [np.asarray(e, dtype=float) for e in per_band_energies]
    if not curves:
        raise ValueError("combine_band_energies needs at least one band.")

    total = np.zeros_like(curves[0])
    used = 0
    for idx, energies in enumerate(curves, start=1):
        spread = energies.std()
        # A flat band expresses no preference between tempos, and a failed band
        # contributes zeros (see the handler in rhythm_detection.main). Either
        # way there is nothing to normalise, and dividing would give NaNs.
        if not np.isfinite(spread) or spread == 0.0:
            logger.warning("combine_band_energies: band %d is flat or non-finite; skipping it", idx)
            continue
        total += (energies - energies.mean()) / spread
        used += 1

    logger.info("combine_band_energies: combined %d of %d band(s)", used, len(curves))
    return total


def find_fundamental_tempo(tempos, energies):
    """
    Picks the tempo of the strongest interior peak of a tempo-energy curve.

    A plain argmax is unsafe here. A comb filter at half the true tempo still
    lands on every other beat, so an octave alias scores highly -- and when that
    alias sits at the edge of the search range (60 BPM aliasing a true 120) it
    has no neighbour on one side that could disqualify it, so argmax returns a
    boundary value rather than a peak. Restricting the choice to interior local
    maxima rejects those endpoints; the true tempo shows up as a real peak.

    Parameters:
        tempos (np.ndarray): Tempo grid (BPM), matching `energies`.
        energies (np.ndarray): Comb-filter energy at each tempo.

    Returns:
        float: Tempo in BPM of the strongest interior peak, falling back to the
        global maximum when the curve has no interior peak at all.
    """
    tempos = np.asarray(tempos, dtype=float)
    energies = np.asarray(energies, dtype=float)

    if energies.size >= 3:
        mid = energies[1:-1]
        interior = np.flatnonzero((mid > energies[:-2]) & (mid > energies[2:])) + 1
    else:
        interior = np.empty(0, dtype=np.int64)

    if interior.size:
        best = int(interior[np.argmax(energies[interior])])
        logger.info("find_fundamental_tempo: %d interior peak(s), strongest at %.2f BPM",
                    interior.size, float(tempos[best]))
    else:
        best = int(np.argmax(energies))
        logger.warning("find_fundamental_tempo: no interior peak in the tempo curve; "
                       "falling back to the global maximum at %.2f BPM (the search "
                       "range may be too narrow)", float(tempos[best]))
    return float(tempos[best])


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

    # Determine an efficient FFT length. The comb spans (num_impulses - 1)
    # periods, so the autocorrelation is sampled at lags up to
    # (num_impulses - 1) * max_period; the zero padding must cover that or those
    # lags wrap around the circular FFT and pick up a spurious, tempo-dependent
    # term (measured at ~2.6% of the energy -- comparable to the tempo peak
    # itself -- when padding only one period).
    min_tempo = float(np.min(tempos))
    max_period = max(1, int(fs * 60.0 / min_tempo))  # largest spacing among tempos
    max_lag = (num_impulses - 1) * max_period
    n_desired = signal.size + max_lag + 1
    n_fast = next_fast_len(n_desired)
    logger.debug("analyze_tempo: n_desired=%d, n_fast=%d (max_period=%d, max_lag=%d)",
                 n_desired, n_fast, max_period, max_lag)

    # Compute the real FFT of the signal once; its power spectrum |X[k]|^2 does
    # not depend on the comb filter. (.real**2 + .imag**2 avoids the sqrt that
    # np.abs(...)**2 would compute and then immediately undo.)
    # (astroid cannot infer scipy.fft.rfft's return type and takes it for a
    # tuple, hence the local no-member suppression on the two lines below.)
    signal_freq = rfft(signal, n=n_fast)
    # pylint: disable=no-member
    psd = signal_freq.real ** 2  # |X[k]|^2, shape (K,)
    psd += signal_freq.imag ** 2  # accumulate in place: one less K-sized temporary
    # pylint: enable=no-member
    del signal_freq  # ~90 MB for a 4-minute track; free it before the inverse FFT

    # Drop the k=0 bin. diff_rect's output is half-wave rectified and therefore
    # strictly non-negative, so X[0] = sum(signal) is huge and contributes the
    # same pedestal to every autocorrelation lag -- the periodic structure we
    # actually want rides on top of it as a ~2% ripple. Zeroing this bin is
    # equivalent to mean-centring the signal and raises peak-over-pedestal
    # contrast by roughly an order of magnitude.
    # NOTE: deliberate deviation from timecomb.m, which sums the full spectrum.
    psd[0] = 0.0
    logger.debug("analyze_tempo: computed signal FFT (len=%d), DC bin removed", psd.size)

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
    # Identically zero now that psd[0] is cleared above; kept so the expression
    # below still mirrors the S_half = (S_full + DC + Nyquist) / 2 derivation.
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

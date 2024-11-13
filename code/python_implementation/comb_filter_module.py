# comb_filter_module.py

import numpy as np
from numpy.fft import fft, ifft

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
    period = int(fs * 60 / tempo)  # Period of the comb filter in samples
    comb_filter = np.zeros(period * (num_impulses - 1) + 1)
    comb_filter[::period] = 1  # Set impulses at periodic intervals
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
    # Transform the signal to the frequency domain
    signal_freq = fft(signal, n=signal.size + max(int(fs * 60 / tempos.min()), len(signal)))

    energies = []

    for tempo in tempos:
        # Create comb filter in time domain
        comb_filter = create_comb_filter(fs, tempo, num_impulses)

        # Transform comb filter to frequency domain
        comb_filter_freq = fft(comb_filter, n=signal_freq.size)

        # Convolve by multiplying in the frequency domain
        convolved_freq = signal_freq * comb_filter_freq

        # Transform back to the time domain
        convolved_signal = np.real(ifft(convolved_freq))

        # Calculate energy of the convolved signal
        energy = np.sum(convolved_signal ** 2)
        energies.append(energy)

    return np.array(energies)

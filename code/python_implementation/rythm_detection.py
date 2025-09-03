# rhythm_detection.py

import numpy as np
import matplotlib.pyplot as plt
import numpy as np

from comb_filter_module import analyze_tempo
from diff_rect_module import diff_rect
from envelope_module import get_envelope
from filterbank_module import read_mp3, create_filterbank


# Define the frequency bands following Scheirer (1998)
def get_scheirer_bands(fs):
    nyquist = fs / 2
    return [
        (1, 200),  # Band 1: 1-200 Hz (avoid 0 Hz)
        (200, 400),  # Band 2: 200-400 Hz
        (400, 800),  # Band 3: 400-800 Hz
        (800, 1600),  # Band 4: 800-1600 Hz
        (1600, 3200),  # Band 5: 1600-3200 Hz
        (3200, min(nyquist, 5000))  # Band 6: 3200 Hz to Nyquist Frequency (or a cap if fs is high)
    ]


# List of MP3 file paths
file_paths = [
    '../../music_files/pathfinder.mp3',
    '../../music_files/celebration.mp3'  # Replace with the actual path to the second MP3
]

tempo_range = np.arange(60, 180, 1)  # Analyze tempos from 60 to 180 BPM with 1 BPM resolution

for filename in file_paths:
    print(f"Processing file: {filename}")

    signal, fs = read_mp3(filename)

    bands = get_scheirer_bands(fs)

    filtered_signals = create_filterbank(signal, fs, bands)

    # Calculate the envelope, diff-rect, and comb filter energies for each band
    t = np.arange(len(signal)) / fs
    plt.figure(figsize=(12, 15))
    plt.suptitle(f'Analysis for {filename}', fontsize=16)

    # Plot original signal
    plt.subplot(len(bands) + 1, 1, 1)
    plt.plot(t, signal)
    plt.title('Original Signal')
    plt.xlabel('Time [s]')
    plt.ylabel('Amplitude')

    total_energies = np.zeros_like(tempo_range, dtype=float)

    for i, filtered_signal in enumerate(filtered_signals):
        # Step 1: Calculate envelope
        envelope = get_envelope(filtered_signal, fs)

        # Step 2: Apply diff-rect
        diff_rect_signal = diff_rect(envelope, fs)

        # Step 3: Apply comb filter analysis
        energies = analyze_tempo(diff_rect_signal, fs, tempo_range)
        total_energies += energies

        # Plot diff-rect signal
        plt.subplot(len(bands) + 1, 1, i + 2)
        plt.plot(tempo_range, energies)
        plt.title(f'Tempo Energies for Band {i + 1}: {bands[i][0]}-{bands[i][1]} Hz')
        plt.xlabel('Tempo (BPM)')
        plt.ylabel('Energy')

    # Plot total energies across all bands
    plt.figure()
    plt.plot(tempo_range, total_energies)
    plt.title('Total Tempo Energies Across All Bands')
    plt.xlabel('Tempo (BPM)')
    plt.ylabel('Energy')

    # Find the fundamental tempo
    fundamental_tempo = tempo_range[np.argmax(total_energies)]
    print(f"Fundamental Tempo: {fundamental_tempo} BPM")

    plt.show()

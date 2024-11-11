# rhythm_detection.py

import numpy as np
import matplotlib.pyplot as plt
from filterbank_module import read_mp3, create_filterbank
from envelope_module import get_envelope  # Import the envelope extraction function

# Define the frequency bands following Scheirer (1998)
def get_scheirer_bands(fs):
    nyquist = fs / 2
    return [
        # (1, 200),                       # Band 1: 1-200 Hz (avoid 0 Hz)
        # (200, 400),                     # Band 2: 200-400 Hz
        # (400, 800),                     # Band 3: 400-800 Hz
        (800, 1600),                    # Band 4: 800-1600 Hz
        (1600, 3200),                   # Band 5: 1600-3200 Hz
        (3200, min(nyquist, 5000))      # Band 6: 3200 Hz to Nyquist Frequency (or a cap if fs is high)
    ]

# Path to the MP3 file
filename = '../../music_files/pathfinder.mp3'

# Read the MP3 file
signal, fs = read_mp3(filename)

# Get frequency bands based on the sampling rate
bands = get_scheirer_bands(fs)

# Apply the filterbank to detect rhythm-related frequency bands
filtered_signals = create_filterbank(signal, fs, bands)

# Calculate and plot the envelope of each band
t = np.arange(len(signal)) / fs
plt.figure(figsize=(12, 10))

# Plot original signal
plt.subplot(len(bands) + 1, 1, 1)
plt.plot(t, signal)
plt.title('Original Signal')
plt.xlabel('Time [s]')
plt.ylabel('Amplitude')

# Plot envelopes of each filtered signal
for i, filtered_signal in enumerate(filtered_signals):
    envelope = get_envelope(filtered_signal, fs)
    plt.subplot(len(bands) + 1, 1, i + 2)
    plt.plot(t, envelope)
    plt.title(f'Envelope of Band {i+1}: {bands[i][0]}-{bands[i][1]} Hz')
    plt.xlabel('Time [s]')
    plt.ylabel('Amplitude')

plt.tight_layout()
plt.show()

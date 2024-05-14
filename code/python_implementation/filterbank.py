import numpy as np
from scipy.signal import butter, lfilter

def butter_bandpass(lowcut, highcut, fs, order=5):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def create_filterbank(signal, fs, bands, order=5):
    filtered_signals = []
    for (lowcut, highcut) in bands:
        filtered_signal = bandpass_filter(signal, lowcut, highcut, fs, order)
        filtered_signals.append(filtered_signal)
    return filtered_signals

# Example usage
if __name__ == "__main__":
    # Generate a sample signal
    fs = 1000.0  # Sample rate, Hz
    T = 1.0     # Duration in seconds
    t = np.linspace(0, T, int(fs * T), endpoint=False)
    # Create a sample signal: a mix of 50 Hz and 150 Hz
    signal = np.sin(2 * np.pi * 50.0 * t) + 0.5 * np.sin(2 * np.pi * 150.0 * t)

    # Define the frequency bands for the filterbank
    bands = [
        (20, 80),   # Band 1: 20-80 Hz
        (80, 160),  # Band 2: 80-160 Hz
        (160, 240), # Band 3: 160-240 Hz
    ]

    # Create the filterbank
    filtered_signals = create_filterbank(signal, fs, bands)

    # Optionally, plot the results
    import matplotlib.pyplot as plt
    plt.figure(figsize=(12, 8))
    plt.subplot(4, 1, 1)
    plt.plot(t, signal)
    plt.title('Original Signal')
    for i, filtered_signal in enumerate(filtered_signals):
        plt.subplot(4, 1, i + 2)
        plt.plot(t, filtered_signal)
        plt.title(f'Filtered Signal Band {i+1}: {bands[i][0]}-{bands[i][1]} Hz')
    plt.tight_layout()
    plt.show()
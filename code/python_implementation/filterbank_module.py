import numpy as np
from scipy.signal import butter, lfilter
from pydub import AudioSegment

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

def read_mp3(filename):
    audio = AudioSegment.from_mp3(filename)
    data = np.array(audio.get_array_of_samples())
    if audio.channels == 2:
        data = data.reshape((-1, 2))
        data = data[:, 0]
    fs = audio.frame_rate
    return data, fs

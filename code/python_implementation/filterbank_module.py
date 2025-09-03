import numpy as np
from scipy.signal import butter, lfilter
from pydub import AudioSegment
import logging

logger = logging.getLogger(__name__)

def butter_bandpass(lowcut, highcut, fs, order=5):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    logger.debug("Designed bandpass filter: low=%.3fHz high=%.3fHz fs=%d order=%d (normalized: [%.6f, %.6f])",
                 lowcut, highcut, fs, order, low, high)
    return b, a

def bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    logger.debug("Applied bandpass filter: low=%.3fHz high=%.3fHz fs=%d order=%d len=%d",
                 lowcut, highcut, fs, order, len(y))
    return y

def create_filterbank(signal, fs, bands, order=5):
    logger.info("Creating filterbank with %d band(s), fs=%d, order=%d", len(bands), fs, order)
    filtered_signals = []
    for idx, (lowcut, highcut) in enumerate(bands, start=1):
        logger.info("  Band %d/%d: %.3f-%.3f Hz", idx, len(bands), lowcut, highcut)
        filtered_signal = bandpass_filter(signal, lowcut, highcut, fs, order)
        logger.debug("  Band %d output length: %d", idx, len(filtered_signal))
        filtered_signals.append(filtered_signal)
    logger.info("Filterbank created.")
    return filtered_signals

def read_mp3(filename):
    logger.info("Reading MP3: %s", filename)
    audio = AudioSegment.from_mp3(filename)
    data = np.array(audio.get_array_of_samples())
    if audio.channels == 2:
        data = data.reshape((-1, 2))
        data = data[:, 0]
        logger.debug("Stereo to mono: took left channel, samples=%d", len(data))
    fs = audio.frame_rate
    logger.info("MP3 loaded: channels=%d fs=%d samples=%d duration=%.2fs",
                audio.channels, fs, len(data), len(data) / float(fs) if fs else -1.0)
    return data, fs

"""Audio decoding and the Butterworth filterbank that splits it into bands."""
import logging

import numpy as np
from scipy.signal import butter, sosfilt
import soundfile as sf

logger = logging.getLogger(__name__)

def butter_bandpass(lowcut, highcut, fs, order=5):
    # Second-order sections (SOS), not transfer-function (b, a): for the low
    # bands the normalised cutoffs are tiny (e.g. 1/22050) and a high-order
    # (b, a) polynomial is so ill-conditioned that lfilter overflows to inf/NaN.
    # SOS keeps each biquad well-conditioned, so the cascade stays stable.
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    sos = butter(order, [low, high], btype='band', output='sos')
    logger.debug("Designed bandpass filter: low=%.3fHz high=%.3fHz fs=%d order=%d (normalized: [%.6f, %.6f])",
                 lowcut, highcut, fs, order, low, high)
    return sos

def bandpass_filter(data, lowcut, highcut, fs, order=5):
    sos = butter_bandpass(lowcut, highcut, fs, order=order)
    y = sosfilt(sos, data)
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

def _read_with_audioread(filename):
    """Fallback decoder for formats libsndfile cannot read.

    audioread uses whatever audio backend the OS provides (and does not require
    a system ffmpeg install). It yields interleaved 16-bit PCM buffers, which we
    concatenate and normalise to float in [-1, 1].
    """
    # Imported lazily: audioread is only needed for the formats libsndfile
    # cannot handle, so the common path does not pay for it.
    import audioread  # pylint: disable=import-outside-toplevel

    with audioread.audio_open(filename) as f:
        fs = f.samplerate
        channels = f.channels
        chunks = [np.frombuffer(buf, dtype="<i2") for buf in f]

    if chunks:
        data = np.concatenate(chunks).astype(np.float64) / 32768.0
    else:
        data = np.zeros(0, dtype=np.float64)

    if channels and channels > 1:
        data = data.reshape((-1, channels))
    return data, fs


def read_audio(filename):
    """Read an audio file to a mono float signal and its sample rate.

    Uses soundfile (libsndfile) first, which natively decodes WAV/FLAC/OGG and,
    with the libsndfile bundled in recent wheels, MP3 as well. Falls back to
    audioread for anything libsndfile cannot handle. Neither backend requires a
    system ffmpeg install (unlike the previous pydub implementation).
    """
    logger.info("Reading audio: %s", filename)
    try:
        data, fs = sf.read(filename, always_2d=True)
        logger.debug("Decoded with soundfile: shape=%s fs=%d", data.shape, fs)
    except Exception as e:
        logger.warning("soundfile could not read %s (%s); falling back to audioread", filename, e)
        data, fs = _read_with_audioread(filename)

    # Downmix to a single mono channel (mean across channels)
    data = np.asarray(data, dtype=np.float64)
    if data.ndim == 2 and data.shape[1] > 1:
        logger.debug("Downmixing %d channels to mono", data.shape[1])
        data = data.mean(axis=1)
    else:
        data = data.reshape(-1)

    fs = int(fs)
    logger.info("Audio loaded: fs=%d samples=%d duration=%.2fs",
                fs, len(data), len(data) / float(fs) if fs else -1.0)
    return data, fs

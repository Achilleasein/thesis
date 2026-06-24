"""Cross-platform smoke tests for the rhythm-detection pipeline.

These run headless (no GUI, no display) and are the verification target for
the CI matrix: if they pass on Windows/macOS/Linux across several Python
versions, the dependency stack and the core algorithm are sound on those
platforms.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPL_DIR = REPO_ROOT / "code" / "python_implementation"
MUSIC_DIR = REPO_ROOT / "music_files"
sys.path.insert(0, str(IMPL_DIR))

from comb_filter_module import analyze_tempo, create_comb_filter  # noqa: E402
from diff_rect_module import diff_rect  # noqa: E402
from envelope_module import get_envelope  # noqa: E402
from filterbank_module import create_filterbank, read_audio  # noqa: E402

TEMPO_RANGE = np.arange(60, 181, 1.0)


def _index_of(tempo: float) -> int:
    return int(np.argmin(np.abs(TEMPO_RANGE - tempo)))


def test_comb_filter_shape():
    """A comb filter for a given tempo has the expected impulses."""
    fs = 8000
    comb = create_comb_filter(fs, tempo=120, num_impulses=3)
    period = int(fs * 60 / 120)
    assert comb.sum() == 3
    assert comb[0] == 1.0
    assert comb[period] == 1.0
    assert comb[2 * period] == 1.0


def test_analyze_tempo_prefers_true_tempo():
    """An impulse train at 120 BPM scores higher at 120 than at off-beat tempos."""
    fs = 11025
    bpm = 120
    period = int(fs * 60 / bpm)
    signal = np.zeros(period * 40, dtype=float)  # ~20 s of clicks
    signal[::period] = 1.0

    energies = analyze_tempo(signal, fs, TEMPO_RANGE)

    assert energies.shape == TEMPO_RANGE.shape
    assert np.all(np.isfinite(energies))
    # 120 BPM should beat clearly non-harmonic neighbours.
    assert energies[_index_of(120)] > energies[_index_of(100)]
    assert energies[_index_of(120)] > energies[_index_of(140)]


@pytest.mark.parametrize("name", ["celebration.mp3", "pathfinder.mp3"])
def test_decode_bundled_audio(name):
    """soundfile/audioread can decode the bundled MP3s on this platform."""
    path = MUSIC_DIR / name
    assert path.is_file(), f"missing test asset: {path}"
    signal, fs = read_audio(str(path))
    assert fs > 0
    assert signal.ndim == 1
    assert len(signal) > fs  # at least one second of audio
    assert np.all(np.isfinite(signal))


def test_full_pipeline_produces_bpm():
    """End-to-end: decode -> filterbank -> envelope -> diff-rect -> tempo."""
    signal, fs = read_audio(str(MUSIC_DIR / "celebration.mp3"))
    signal = signal[: fs * 20]  # 20 s slice keeps CI fast

    bands = create_filterbank(signal, fs, [(1, 200), (200, 400)])
    total = np.zeros_like(TEMPO_RANGE)
    for band in bands:
        envelope = get_envelope(band, fs)
        onsets = diff_rect(envelope, fs)
        total += analyze_tempo(onsets, fs, TEMPO_RANGE)

    detected = TEMPO_RANGE[int(np.argmax(total))]
    assert TEMPO_RANGE.min() <= detected <= TEMPO_RANGE.max()

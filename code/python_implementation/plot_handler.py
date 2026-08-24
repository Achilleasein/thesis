"""Rendering and saving of the analysis figures for one analysed track."""
import os
from typing import Sequence, Tuple

# Select a non-interactive backend so figures can be saved in a subprocess with
# no display attached. matplotlib.use() must run before pyplot is imported, so
# the imports below are deliberately not at the top of the module.
import matplotlib
matplotlib.use("Agg")
# pylint: disable=wrong-import-position
import matplotlib.pyplot as plt
import numpy as np

from comb_filter_module import combine_band_energies, find_fundamental_tempo
# pylint: enable=wrong-import-position


def decimate_for_plot(
    time_axis: np.ndarray,
    signal: np.ndarray,
    max_points: int = 8000,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Reduce a waveform to a plottable overview without losing its extremes.

    Plotting every sample of a multi-minute track pushes millions of points at a
    few thousand pixels of axis -- ~0.8 GB of peak memory for a 4-minute file,
    and none of it visible. Taking every k-th sample would be cheap but would
    miss the peaks between samples and draw the track quieter than it is, so
    keep the min AND max of each block: the outline still spans the true
    amplitude range at every horizontal position.

    Returns the input unchanged when it is already small enough.
    """
    n = signal.size
    if n <= max_points or max_points < 2:
        return time_axis, signal

    block = int(np.ceil(n / (max_points // 2)))
    usable = (n // block) * block
    blocks = signal[:usable].reshape(-1, block)

    out = np.empty(blocks.shape[0] * 2, dtype=float)
    out[0::2] = blocks.min(axis=1)
    out[1::2] = blocks.max(axis=1)
    # Both the min and max of a block are drawn at the block's start time, so
    # each block becomes a short vertical stroke spanning its amplitude range.
    out_t = np.repeat(time_axis[:usable:block], 2)
    return out_t, out


def safe_basename(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base)


def save_plots(
    input_filename: str,
    time_axis: np.ndarray,
    original_signal: np.ndarray,
    bands: Sequence[Tuple[float, float]],
    tempo_range: np.ndarray,
    per_band_energies: Sequence[np.ndarray],
    results_dir: str,
) -> Tuple[str, str, float]:
    """
    Create and save the analysis plots:
      - Figure 1: Original signal and per-band tempo energies
      - Figure 2: Total tempo energies across all bands

    Parameters:
        input_filename: Path of the audio file being analyzed (used for titles and naming)
        time_axis: Time vector for the original signal
        original_signal: The raw audio signal
        bands: Sequence of (low, high) tuples for each band
        tempo_range: Array of tempos (BPM)
        per_band_energies: Sequence of arrays, one per band, energies vs tempo
        results_dir: Directory to save the figures

    Returns:
        (analysis_png_path, total_png_path, fundamental_tempo)
    """
    os.makedirs(results_dir, exist_ok=True)

    # Aggregate the bands, standardising each so they carry equal weight rather
    # than letting the high-energy low band decide the answer on its own.
    total_energies = combine_band_energies(per_band_energies)

    # Figure 1: Original + per-band energies
    fig1 = plt.figure(figsize=(12, 15))
    fig1.suptitle(f"Analysis for {os.path.basename(input_filename)}", fontsize=16)

    # Original signal
    ax1 = fig1.add_subplot(len(bands) + 1, 1, 1)
    ax1.plot(*decimate_for_plot(time_axis, np.asarray(original_signal, dtype=float)))
    ax1.set_title("Original Signal")
    ax1.set_xlabel("Time [s]")
    ax1.set_ylabel("Amplitude")

    # Per-band energies
    for i, (band, energies) in enumerate(zip(bands, per_band_energies), start=2):
        ax = fig1.add_subplot(len(bands) + 1, 1, i)
        ax.plot(tempo_range, energies)
        low, high = band
        ax.set_title(f"Tempo Energies for Band {i - 1}: {low}-{high} Hz")
        ax.set_xlabel("Tempo (BPM)")
        ax.set_ylabel("Energy")

    # Figure 2: Total energies
    fig2 = plt.figure(figsize=(10, 4))
    ax_total = fig2.add_subplot(1, 1, 1)
    ax_total.plot(tempo_range, total_energies)
    ax_total.set_title("Combined Tempo Energies Across All Bands (per-band standardised)")
    ax_total.set_xlabel("Tempo (BPM)")
    # Not raw energy any more: each band was standardised before summing, so the
    # unit is per-band standard deviations above that band's own mean.
    ax_total.set_ylabel("Combined score (sigma)")

    # Fundamental tempo (strongest interior peak, not a boundary argmax --
    # see find_fundamental_tempo for why that distinction matters here)
    fundamental_tempo = find_fundamental_tempo(tempo_range, total_energies)

    # Paths
    base = safe_basename(input_filename)
    analysis_path = os.path.join(results_dir, f"{base}_analysis.png")
    total_path = os.path.join(results_dir, f"{base}_total.png")

    # Save figures
    fig1.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig1.savefig(analysis_path, dpi=150, bbox_inches="tight")
    print(f"SAVED: {os.path.abspath(analysis_path)}")

    fig2.tight_layout()
    fig2.savefig(total_path, dpi=150, bbox_inches="tight")
    print(f"SAVED: {os.path.abspath(total_path)}")

    # Cleanup
    plt.close(fig1)
    plt.close(fig2)

    return analysis_path, total_path, fundamental_tempo

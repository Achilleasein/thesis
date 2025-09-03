import os
from typing import Iterable, Sequence, Tuple

# Use a non-interactive backend so figures can be saved in a subprocess without display
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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

    # Aggregate total energies
    total_energies = np.zeros_like(tempo_range, dtype=float)
    for e in per_band_energies:
        total_energies += np.asarray(e, dtype=float)

    # Figure 1: Original + per-band energies
    fig1 = plt.figure(figsize=(12, 15))
    fig1.suptitle(f"Analysis for {os.path.basename(input_filename)}", fontsize=16)

    # Original signal
    ax1 = fig1.add_subplot(len(bands) + 1, 1, 1)
    ax1.plot(time_axis, original_signal)
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
    ax_total.set_title("Total Tempo Energies Across All Bands")
    ax_total.set_xlabel("Tempo (BPM)")
    ax_total.set_ylabel("Energy")

    # Fundamental tempo
    fundamental_tempo = float(tempo_range[int(np.argmax(total_energies))])

    # Paths
    base = safe_basename(input_filename)
    analysis_path = os.path.join(results_dir, f"{base}_analysis.png")
    total_path = os.path.join(results_dir, f"{base}_total.png")

    # Save figures
    try:
        fig1.tight_layout(rect=[0, 0.03, 1, 0.95])
    except Exception:
        pass
    fig1.savefig(analysis_path, dpi=150, bbox_inches="tight")
    print(f"SAVED: {os.path.abspath(analysis_path)}")

    fig2.tight_layout()
    fig2.savefig(total_path, dpi=150, bbox_inches="tight")
    print(f"SAVED: {os.path.abspath(total_path)}")

    # Cleanup
    plt.close(fig1)
    plt.close(fig2)

    return analysis_path, total_path, fundamental_tempo
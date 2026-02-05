"""
Signal computation module entry point.

Computes quarterly signals from the Knowledge Graph:
- AI-language intensity (capability mentions per document)
- Product/capability mention frequency
- Risk disclosure density

Usage:
    python -m measures.main                  # Compute all signals
    python -m measures.main --output dir     # Export to directory
    python -m measures.main --stats          # Show summary only
"""

import argparse
from pathlib import Path

from config import PROCESSED_DATA_DIR, setup_logging
from measures.quarterly import compute_quarterly_signals, print_signals

logger = setup_logging(__name__)


def main():
    """Compute signals from knowledge graph."""
    parser = argparse.ArgumentParser(
        description="Signal Computation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for signal files",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show summary statistics only",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Signal Computation Pipeline")
    print("=" * 60)

    # Compute quarterly signals
    print("\n1. Computing quarterly signals...")
    signals = compute_quarterly_signals()
    print_signals(signals)

    # Export signals
    output_dir = Path(args.output) if args.output else PROCESSED_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "quarterly_signals.csv"
    signals.to_csv(csv_path)
    print(f"\nSignals exported to: {csv_path}")

    print("\n" + "=" * 60)
    print("Signal computation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

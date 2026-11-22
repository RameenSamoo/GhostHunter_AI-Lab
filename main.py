"""Ghost Hunter 2D - entry point.

    python main.py                 play
    python main.py --seed 42       reproducible mazes, ghost walks and noise
    python main.py --mute          no sound
    python main.py --regen-assets  rebuild sprites (assets/) and sounds (audio/)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ghost Hunter 2D")
    parser.add_argument("--seed", type=int, default=None, help="random seed for a reproducible run")
    parser.add_argument("--mute", action="store_true", help="start with sound off")
    parser.add_argument("--regen-assets", action="store_true", help="regenerate sprites and sounds")
    args = parser.parse_args()

    from ui.app import App
    App(seed=args.seed, mute=args.mute, regen_assets=args.regen_assets).run()


if __name__ == "__main__":
    main()

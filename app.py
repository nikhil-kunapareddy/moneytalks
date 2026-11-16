"""Entry point for the MoneyTalks Mac app.

Run from source with ``python app.py``; packaged into MoneyTalks.app by
``packaging/build_macos.sh``. ``python app.py --smoke-test`` checks the
bundle without opening a window.
"""

import sys

from src.desktop import main

if __name__ == "__main__":
    sys.exit(main())

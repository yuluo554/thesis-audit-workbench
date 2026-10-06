"""`python -m taw` 入口（与 console_script `taw` 同一 main，双入口契约见 plan/03）。"""

import sys

from taw.cli import main

if __name__ == "__main__":
    sys.exit(main())

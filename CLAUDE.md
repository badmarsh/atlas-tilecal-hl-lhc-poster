# CLAUDE.md

The working rules for this poster live in **[AGENTS.md](AGENTS.md)** — read it
before editing anything. It covers the build loop (`build/build.sh`), the silent
tikzposter overflow trap, the locked-PDF stale-preview trap, and how to reclaim
vertical space when a card overflows. The single source of truth for "does the
layout fit" is `build/check_fit.py` returning `PASS`.

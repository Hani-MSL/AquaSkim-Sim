"""Render one system-validation animation from prepared logged CSV data."""
from __future__ import annotations
import argparse
from aquaskim.phase10_15 import render_one

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("validated", "time_limit", "boundary", "timeline"), required=True)
    args = parser.parse_args()
    render_one(args.kind)
    print(f"[RENDER] Complete: {args.kind}")

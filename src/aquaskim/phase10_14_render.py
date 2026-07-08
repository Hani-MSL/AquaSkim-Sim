"""Render one payload-manoeuvre animation in an isolated process."""
from __future__ import annotations
import argparse
from aquaskim.phase10_14 import render_one
if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--kind",choices=("stability","step","turn","zigzag"));args=parser.parse_args();render_one(args.kind);print(f"[RENDER] Complete: {args.kind}")

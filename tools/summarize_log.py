#!/usr/bin/env python3
"""Summarize valid diagnostic records; durations are log observations, not frames."""
import argparse
import re
import sys
from pathlib import Path

REQUIRED = {"entry", "time_us", "outcome", "desired", "displayed"}
FIELD = re.compile(r"([a-z_]+)=([0-9a-fA-F]{8})$")


def parse_snapshots(text):
    records, warnings, current = [], [], {}
    bad = False
    start = 1

    def finish():
        if current:
            missing = REQUIRED - current.keys()
            if bad or missing:
                warnings.append(f"record at line {start}: malformed/incomplete; missing {sorted(missing)}")
            else:
                records.append(current.copy())

    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        key = line.partition("=")[0]
        if key == "build_id" or (key == "entry" and "entry" in current):
            finish(); current = {}; bad = False; start = number
        match = FIELD.fullmatch(line)
        if not match:
            warnings.append(f"line {number}: expected key=eight-digit hex"); bad = True; continue
        key, value = match.groups()
        if key in current:
            warnings.append(f"line {number}: duplicate {key}"); bad = True
        current[key] = int(value, 16)
    finish()
    return records, warnings


def completions(records):
    pending = previous = None
    for r in records:
        new_session = previous and (r.get("build_id") != previous.get("build_id") or r["entry"] != previous["entry"] + 1)
        if new_session:
            pending = None
        desired, displayed = r["desired"], r["displayed"]
        if desired > 100 or r["outcome"]:
            pending = None
        elif desired != displayed:
            if pending is None or pending[0] != desired:
                pending = desired, r["time_us"]
        elif pending:
            if pending[0] == displayed:
                yield displayed, ((r["time_us"] - pending[1]) & 0xffffffff) / 1_000_000
            pending = None
        previous = r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--power", action="store_true", help="Show raw power/visibility observations")
    args = parser.parse_args()
    records, warnings = parse_snapshots(args.log.read_text())
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if not records:
        raise SystemExit("No complete diagnostic snapshots")
    builds = sorted({r.get("build_id") for r in records}, key=lambda x: -1 if x is None else x)
    print(f"snapshots={len(records)} builds=" + ",".join("legacy/unknown" if b is None else f"{b:08x}" for b in builds))
    print("outcomes=" + ",".join(f"{v:08x}" for v in sorted({r["outcome"] for r in records})))
    last = records[-1]
    for key in ("ticks", "creates", "layouts", "clock_resyncs", "cached_restores", "installed", "rollback",
                "callback_gaps", "fault_stage", "fault_code", "worker_lock_error", "usb_pauses"):
        if key in last:
            print(f"last_{key}={last[key]:08x}")
    for percent, duration in completions(records):
        print(f"completed={percent}% observed_seconds={duration:.3f}")
    print("Timing: first logged mismatch to first logged match; USB/cap gaps and extra 71.6-minute wraps are not measurable.")
    if args.power:
        previous_state = previous = None
        session = 0
        for r in records:
            if previous is None or r.get("build_id") != previous.get("build_id") or r["entry"] != previous["entry"] + 1:
                session += 1; previous_state = None
            keys = ("exists", "charging", "ac", "raw_percent", "desired", "displayed", "native_visible", "text_visible")
            state = tuple(r.get(k) for k in keys)
            if state != previous_state:
                fields = " ".join(f"{k}={r[k]:08x}" for k in keys if k in r)
                print(f"power stream_segment={session} entry={r['entry']:02x} clock_low_us={r['time_us']:08x} {fields}")
            previous_state, previous = state, r


if __name__ == "__main__":
    main()

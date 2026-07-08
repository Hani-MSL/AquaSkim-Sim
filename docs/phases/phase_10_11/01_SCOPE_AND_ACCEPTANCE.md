# Phase 10.11 — Reference Mission Fidelity and Visual Evidence

## Purpose

This phase strengthens the evidence that a reviewer sees after the source
integrity recovery. It operates only on the non-interactive reference mission
and its versioned nominal/high-loading scenarios.

## Non-goals

- No Word report is generated.
- No delivery ZIP is generated.
- No release build is enabled.
- No historical quota-based module is called.
- No manual trajectory is drawn in place of a numerical state history.

## Behavioural refinements

The reference policy adds a `minimum_search_before_diversion_s` launch interval.
A target may still be detected during coverage, but the craft must first begin a
visible, logged coverage motion before a debris diversion can be assigned.
This prevents an immediate home-area target from creating a visually ambiguous
opening sequence.

## Visual acceptance

Six GIF and six MP4 outputs are required. Each GIF must have at least 96 frames
and at least 9 seconds of duration. The contact sheet samples five evenly spaced
frames from every GIF.

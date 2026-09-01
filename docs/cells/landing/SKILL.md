---
name: landing
description: This repository's own procedure for taking a change from a fresh branch to an open pull request — the order the steps run in, the guards that must pass before a commit, what the pull request body states, and when the plugin version is bumped. Use when a change here is ready to build, validate, commit or publish, when opening a pull request for one, or when deciding what a change owes before it is proposed; not for how a review is run once the pull request exists, not for what a change is for, and not for appending to a record afterwards.
---

# landing

**Purpose:** carry this repository's own landing procedure, so a session taking a change from a branch to a pull request does the steps in the order that works here. **Audience:** any session in this repository with a change ready to validate, commit or publish. **Success:** a session that has read this leaves a branch, a commit and a pull request that the guards and the owner's merge-time read all accept, without having been told the order.

## The flow

Branch first (`main` refuses direct pushes) → settle the brief, then the artifact against a cold check or a recorded truncation → build → `python tools/lint.py` and `python tools/check_version_bump.py` → commit → publish the branch, open the PR, run the experience session the change bought or record the one line declining it, run the review, reconcile external reviewer comments — in that order, without being asked; on a change that has a PR, running the review is a check, never a question. A batch rewriting what the material instructs buys one more, or the line declining it. [D-178]

## What the pull request owes

The PR body states `Closes #N`, or one line saying it closes none and why. A shipped-zone change bumps the plugin version.

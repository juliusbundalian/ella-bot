# ELLA Auto-Pull Service: Documentation & Troubleshooting Guide

This document explains the architecture of the **ELLA Auto-Pull Service**, details known issues (specifically the `.git/AUTO_MERGE` lock bug), and provides step-by-step instructions for troubleshooting and resolving automatic pull failures.

---

## 1. System Overview

The ELLA Auto-Pull service automatically fetches and pulls updates from GitHub whenever an active internet connection is detected.

* **Service Unit:** `~/.config/systemd/user/ella-auto-pull.service`
* **Execution Script:** `scripts/auto_pull_on_connect.sh`
* **Log Location:** `data/logs/auto_pull.log`
* **Check Interval:** Default 15 seconds

### How the Script Works
1. **Connectivity Check:** Polls `https://github.com` via `curl` (or `ping`).
2. **State Transition:** Triggers an update check when network status transitions from `OFFLINE` to `ONLINE`.
3. **Dirty Working Tree Handling:** Stashes local uncommitted changes before fetching (`git stash save "auto-pull-stash-..."`).
4. **Fetch & Pull:** Runs `git fetch origin`. If `HEAD` differs from `origin/${current_branch}`, executes `git pull origin ${current_branch}`.
5. **Stash Restore:** Restores uncommitted changes (`git stash pop`).

---

## 2. Known Issues & Root Cause Analysis

### Issue: Auto-Pull Failing or Stuck in Stash Loop

#### Symptom Log Output (`data/logs/auto_pull.log`)
```text
[2026-08-31 15:34:40] Internet connection detected. Checking for updates on branch 'temp/main'...
[2026-08-31 15:34:40] Local uncommitted changes detected. Stashing changes...
error: cannot lock ref 'AUTO_MERGE': unable to resolve reference 'AUTO_MERGE': reference broken
[2026-08-31 15:34:40] Executing git fetch origin...
[2026-08-31 15:34:42] Repository is already up to date.
[2026-08-31 15:34:42] Restoring local stashed changes...
error: update_ref failed for ref 'AUTO_MERGE': unable to resolve reference 'AUTO_MERGE': reference broken
The stash entry is kept in case you need it again.
```

#### Causes
1. **Corrupted `.git/AUTO_MERGE` File (Primary Cause)**
   - An empty (0-byte) file exists at `.git/AUTO_MERGE`, left behind from an interrupted merge operation.
   - Any `git stash` or `git pull` attempt fails to update references due to this broken lock file.
   - Because `git stash pop` fails, stashes accumulate repeatedly in `git stash list`.

2. **Uncommitted Local Changes in Tracked Files**
   - Files like `config/settings.ini` or `data/profiles.json` have active local edits.
   - Whenever the system detects network connectivity, it initiates the stash -> fetch -> pop pipeline, which repeatedly fails due to Cause #1.

3. **Branch Mismatch**
   - The script pulls from `origin/${current_branch}`. If the active checked-out branch is `temp/main`, it will only pull updates from `origin/temp/main` and ignore updates made to `origin/main`.

---

## 3. Resolution & Recovery Steps

To resolve this issue and restore auto-pull functionality, execute the following commands in the `ella-bot` root directory:

### Step 1: Remove the Corrupt `AUTO_MERGE` Reference
```bash
rm -f .git/AUTO_MERGE
```

### Step 2: Clear Accumulated Auto-Pull Stashes
Check existing stashes:
```bash
git stash list
```
Clear redundant auto-pull stashes:
```bash
git stash clear
```

### Step 3: Align to the Correct Branch
Verify active branch:
```bash
git branch -a
```
Switch to the primary branch (`main`):
```bash
git checkout main
```

### Step 4: Test Auto-Pull Script Manually
Run a single manual check to verify execution without systemd:
```bash
./scripts/auto_pull_on_connect.sh --once
```

---

## 4. Service Management Reference

| Action | Command |
|---|---|
| **Check Service Status** | `systemctl --user status ella-auto-pull.service` |
| **Restart Service** | `systemctl --user restart ella-auto-pull.service` |
| **Stop Service** | `systemctl --user stop ella-auto-pull.service` |
| **View Service Logs** | `cat data/logs/auto_pull.log` |
| **Reinstall Service** | `./scripts/install_auto_pull_service.sh` |

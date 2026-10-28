---
name: branch-and-pr
description: Git workflow for the team. Use when starting a piece of work (create a branch) or when work is finished (commit, push, open a PR into main). Each person works on their own branch for one item.
---

# Branch and PR workflow

One person, one item, one branch, one PR into `main`. Never commit directly to `main`.

## Branch naming

`<name>-<work>`: lowercase, hyphen-separated, short.

- `<name>`: the person's first name or handle (take it from `git config user.name` if the user
  has not said; confirm it once).
- `<work>`: 2-4 words describing the item, e.g. `joshua-setup-fixes`, `sam-baseline-zscore`,
  `ana-streamlit-events`.

## Starting work

1. Confirm the item with the user (one clear piece of work; if it is really two, make two branches).
2. `git fetch origin && git switch main && git pull --ff-only`
3. `git switch -c <name>-<work>`
4. If the working tree has unrelated uncommitted changes, stop and ask before switching.

## While working

- Small commits with imperative messages that say what and why (`Add rolling MAD baseline`).
- Pull `main` into the branch (`git fetch origin && git merge origin/main`) before opening the PR
  and resolve conflicts locally.
- Do not commit secrets, the partner API key, `.env`, virtualenvs, partner datasets or generated
  `artifacts/` / `reports/`. Reviewed TAI code and documentation in `data/tai_work/` are tracked;
  do not rewrite or delete raw files in `data/`.

## Finishing: open the PR

1. Check the work: run the relevant script/tests/app and note exactly what you ran.
   Check `git status` and `git diff origin/main...HEAD --stat` for stray files.
2. Commit anything left, then `git push -u origin <branch>`.
3. Open the PR into `main` with the GitHub CLI, using `.agents/templates/PR.md` for the body:

   ```bash
   gh pr create --base main --head <branch> --title "<title>" --body-file <body.md>
   ```

   If `gh` is unavailable or not authenticated, push and give the user the compare URL
   (`https://github.com/<owner>/<repo>/pull/new/<branch>`) plus the title and body to paste.
4. Report the PR URL to the user. Do not merge it; a teammate (or the user) reviews and merges.

## PR title and description

- **Title:** imperative, under about 70 characters, describing the outcome
  (`Add rolling MAD anomaly baseline`). Optionally prefix the stage (`Baseline:`).
- **Body:** fill the template: summary, what changed, how to run/verify (exact commands), results
  (recorded numbers only, no invented metrics), decisions logged in `data/tai_work/DECISIONS.md`, limitations
  or follow-ups, and anything reviewers should check (data touched, new dependencies).
- Link the relevant `data/tai_work/DECISIONS.md` entries rather than repeating them.

## Rules

- Never force-push `main`, and never force-push a shared branch unless the user explicitly asks.
- Don't open a PR with failing or unrun checks without saying so at the top of the description.
- Keep PRs focused on the one item; unrelated fixes go on their own branch.

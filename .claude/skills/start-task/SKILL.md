---
name: start-task
description: Pick up an assigned GitHub issue from the project Backlog, refine it into a detailed user story, move it to Ready, create the correct feature branch, implement the feature or fix, commit, verify with the user, merge the feature branch directly into dev, raise a PR from dev to main, and move the issue to In Review. Use whenever a developer starts working on a new task.
trigger: /start-task
---

# /start-task

Pick up your next assigned task from GitHub, branch, implement, verify, merge into dev, and raise a PR to main — in one guided flow.

## Usage

```
/start-task                    # list your assigned Backlog issues, pick one, full flow
/start-task <issue-number>     # jump straight to a specific issue number, skip listing
/start-task --branch-only      # only do the branch setup step (skip listing and PR)
/start-task --pr-only          # only raise the dev→main PR for the current state of dev
```

## What You Must Do When Invoked

Follow these phases in order. Do not skip phases unless a sub-command flag was given.

---

## Phase 0 — Detect Repo, User, and Project

```bash
# Repo info
REPO_REMOTE=$(git remote get-url origin 2>/dev/null)
REPO_OWNER=$(echo "$REPO_REMOTE" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
REPO_NAME=$(echo "$REPO_REMOTE" | sed -E 's|.*github\.com[:/][^/]+/([^/.]+).*|\1|')

# Current GitHub user
CURRENT_USER=$(gh api user --jq '.login' 2>/dev/null)

# Current git branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)

echo "Repo: $REPO_OWNER/$REPO_NAME"
echo "User: $CURRENT_USER"
echo "Branch: $CURRENT_BRANCH"
```

If any of these are empty, tell the user what's missing and stop:
- Empty `REPO_OWNER/REPO_NAME`: not inside a git repo with a GitHub remote
- Empty `CURRENT_USER`: run `gh auth login` first

---

## Phase 1 — Find Your Assigned Tasks

If the user gave a specific issue number (`/start-task 7`), skip to Phase 2 with that number.

Otherwise, list all open issues assigned to the current user:

```bash
gh issue list \
  --repo "$REPO_OWNER/$REPO_NAME" \
  --assignee "@me" \
  --state open \
  --json number,title,labels,milestone,body \
  --limit 50
```

Parse and display cleanly. Show milestone (sprint) and labels for each:

```
Your assigned issues:

  #3   Add POST /auth/register endpoint         [backend]  Sprint 1
  #7   Build API keys dashboard page            [frontend] Sprint 1
  #11  Fix OSRM container not starting on boot  [infra]    Sprint 2

Which issue do you want to work on? (enter number)
```

Wait for the user to pick an issue number. Store it as `ISSUE_NUMBER`.

If the list is empty: print "No issues are currently assigned to you. Ask the project lead to assign you an issue, or run `/plan-project assign`." and stop.

---

## Phase 2 — Fetch Full Issue Details

```bash
gh issue view $ISSUE_NUMBER \
  --repo "$REPO_OWNER/$REPO_NAME" \
  --json number,title,body,labels,assignees,milestone,state,url
```

Store `ISSUE_TITLE`, `ISSUE_BODY`, `ISSUE_URL`.

Also get the issue's node ID for project board mutations later:
```bash
gh api repos/$REPO_OWNER/$REPO_NAME/issues/$ISSUE_NUMBER --jq '.node_id'
```

Store as `ISSUE_NODE_ID`.

---

## Phase 3 — Generate Refined User Story

Read the issue title and body. Produce a detailed, implementation-ready user story from it.

**Expanded user story format:**

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Issue #NUMBER — TITLE
 URL: ISSUE_URL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**User Story**
As a [who uses this feature, inferred from the issue]
I want [what the feature does]
So that [why it matters]

**What to Build**
[2-4 sentences describing exactly what needs to be implemented.
Be specific: which files to create/edit, which endpoints, which UI components,
which database tables if relevant. Use the existing codebase structure.]

**Acceptance Criteria**
- [ ] [Specific, testable condition — what done looks like]
- [ ] [Specific, testable condition]
- [ ] [Specific, testable condition]
- [ ] Tests pass / no build errors

**Implementation Notes**
[Any warnings, edge cases, or pitfalls inferred from the codebase or issue body.
List files the developer will likely need to touch.]

**Out of Scope**
[Anything that sounds related but should NOT be included in this PR.]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**To make the "What to Build" section accurate**, read the relevant parts of the codebase first:
- Check the directory structure: `find . -type f -name "*.js" -o -name "*.ts" -o -name "*.py" | head -40`
- Read the main entry files for the service being modified
- Look at how similar features are already implemented (pattern matching)

Print the refined user story. Then ask:
```
Does this look correct? (yes / no — if no, tell me what to change)
```

Wait for confirmation. If the user wants changes, update the user story and confirm again.

---

## Phase 4 — Move Issue to "Ready" on the Project Board

Find the project board and move this issue from "Backlog" to "Ready".

**Step 1 — Find the project:**
```bash
gh project list --owner "$REPO_OWNER" --format json --limit 20 2>/dev/null | \
  jq --arg name "$REPO_NAME" '.projects[] | select(.title | ascii_downcase | contains($name | ascii_downcase))'
```

Store `PROJECT_NUMBER` and then get the full project metadata:
```bash
gh api graphql -f query='
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      fields(first: 20) {
        nodes {
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
        }
      }
    }
  }
}
' -f owner="$REPO_OWNER" -F number=$PROJECT_NUMBER
```

If the owner is an org, replace `user` with `organization` in this query.

Store `PROJECT_ID`, `STATUS_FIELD_ID`, and the option IDs for "Backlog" and "Ready".

**Step 2 — Find the project item for this issue:**
```bash
gh api graphql -f query='
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          id
          content {
            ... on Issue { number }
          }
        }
      }
    }
  }
}
' -f projectId="$PROJECT_ID" --jq ".data.node.items.nodes[] | select(.content.number == $ISSUE_NUMBER) | .id"
```

Store as `PROJECT_ITEM_ID`.

If the issue is not on the board yet (no item found), add it first:
```bash
gh api graphql -f query='
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
' -f projectId="$PROJECT_ID" -f contentId="$ISSUE_NODE_ID" --jq '.data.addProjectV2ItemById.item.id'
```

**Step 3 — Set status to "Ready":**
```bash
gh api graphql -f query='
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item { id }
  }
}
' -f projectId="$PROJECT_ID" \
  -f itemId="$PROJECT_ITEM_ID" \
  -f fieldId="$STATUS_FIELD_ID" \
  -f optionId="$READY_OPTION_ID"
```

Print: `✓ Issue #$ISSUE_NUMBER moved to Ready on the project board.`

If the project board is not found or the update fails, print a warning and continue — the board update is not blocking.

---

## Phase 5 — Set Up the Feature Branch

Determine the correct base branch. The base branch is where this feature will eventually be merged into (typically `dev`, `develop`, or `main` depending on the project).

**Detect the dev branch:**
```bash
# Check for common dev branch names
git branch -r | grep -E 'origin/(dev|develop|development)' | head -3
```

If `origin/dev` exists → base branch is `dev`.
If `origin/develop` exists → base branch is `develop`.
If neither exists → base branch is `main`.

Ask the user if the detected base branch is correct:
```
Base branch detected as: dev
Is this correct? (yes / enter the correct branch name)
```

Store the confirmed branch as `BASE_BRANCH`.

**Pull latest:**
```bash
git checkout $BASE_BRANCH
git pull origin $BASE_BRANCH
```

**Create feature branch name** from the issue:
- Format: `feature/issue-NUMBER-short-description`
- Short description: take the issue title, lowercase, replace spaces with hyphens, max 40 chars, strip special chars
- Example: Issue #4 "Add POST /auth/register endpoint" → `feature/issue-4-auth-register`
- For bug fixes: use `fix/issue-NUMBER-description` instead of `feature/`

```bash
BRANCH_NAME="feature/issue-$ISSUE_NUMBER-$(echo '$ISSUE_TITLE' | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/-\+/-/g' | cut -c1-40 | sed 's/-$//')"
echo "Branch: $BRANCH_NAME"
```

Show the branch name and confirm:
```
Feature branch will be: feature/issue-4-auth-register
Looks good? (yes / enter a different name)
```

**Create and switch to the branch:**
```bash
git checkout -b $BRANCH_NAME
```

Print: `✓ Now on branch: $BRANCH_NAME`

---

## Phase 6 — Move Issue to "In Progress"

Update the board status now that coding is starting:

```bash
gh api graphql -f query='
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item { id }
  }
}
' -f projectId="$PROJECT_ID" \
  -f itemId="$PROJECT_ITEM_ID" \
  -f fieldId="$STATUS_FIELD_ID" \
  -f optionId="$IN_PROGRESS_OPTION_ID"
```

Print: `✓ Issue #$ISSUE_NUMBER moved to In Progress.`

---

## Phase 7 — Implement the Feature

Print the user story acceptance criteria as a checklist reminder:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Working on: #ISSUE_NUMBER — TITLE
 Branch: BRANCH_NAME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Acceptance criteria to hit:
  - [ ] [criterion 1]
  - [ ] [criterion 2]
  - [ ] [criterion 3]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then help the user implement the feature based on the user story:

1. Read the relevant files identified in Phase 3 ("What to Build")
2. Implement the changes one file at a time
3. After each logical chunk, commit:
   ```bash
   git add path/to/changed/file.js
   git commit -m "issue #$ISSUE_NUMBER: [what this commit does]"
   ```
4. Keep commits small and named with the issue number so they auto-link to the GitHub issue

**Commit message format:** `issue #N: short description of what changed`
Never use `git add .` — always add specific files to avoid committing `.env`, node_modules, or data files.

Continue implementing until all acceptance criteria are met. Then move to Phase 8.

---

## Phase 8 — Test, Verify, and Iterate

Once the initial implementation is complete, **stop and ask the user to run the app and verify it works** before touching the branches.

Print:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Implementation done — please test it now
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run the app and check the acceptance criteria:
  - [ ] [criterion 1]
  - [ ] [criterion 2]
  - [ ] [criterion 3]

How to start the app (adjust for this project):
  docker-compose up --build    # full stack
  npm run dev                  # frontend only
  node app.js                  # backend only

Type "ok" when everything works, or describe what needs fixing.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Wait for the user's response.

**If the user reports issues or requests changes:**
1. Implement the fix or change
2. Commit immediately after each fix:
   ```bash
   git add path/to/file.js
   git commit -m "issue #$ISSUE_NUMBER: fix [what was wrong]"
   ```
3. Print: "Fix applied — test again and let me know if anything else needs changing."
4. Repeat this loop until the user confirms everything works.

Do not proceed to Phase 9 until the user explicitly confirms the app is working correctly (e.g. "ok", "looks good", "all good", "done").

---

## Phase 9 — Merge Feature Branch into dev

Once the user confirms the app is working, merge the feature branch directly into `BASE_BRANCH` (no pull request for this step).

```bash
git checkout $BASE_BRANCH
git pull origin $BASE_BRANCH
git merge --no-ff $BRANCH_NAME -m "issue #$ISSUE_NUMBER: merge $BRANCH_NAME into $BASE_BRANCH"
```

If there are merge conflicts:
```bash
git status   # see which files conflict
# Resolve conflicts in the listed files, then:
git add conflicting-file.js
git merge --continue
```

After a clean merge, push dev:
```bash
git push origin $BASE_BRANCH
```

Print: `✓ $BRANCH_NAME merged into $BASE_BRANCH and pushed.`

Optionally clean up the feature branch:
```bash
git branch -d $BRANCH_NAME
git push origin --delete $BRANCH_NAME
```

Ask: "Delete the feature branch locally and remotely? (yes / no)"
Only delete if the user confirms.

---

## Phase 10 — Raise PR from dev to main

Now raise the pull request for review — from `BASE_BRANCH` (dev) to `main`.

```bash
gh pr create \
  --repo "$REPO_OWNER/$REPO_NAME" \
  --base main \
  --head "$BASE_BRANCH" \
  --title "issue #$ISSUE_NUMBER: $ISSUE_TITLE" \
  --body "$(cat <<'PREOF'
Closes #ISSUE_NUMBER

## What this PR does
WHAT_TO_BUILD_SECTION_FROM_USER_STORY

## Acceptance criteria
- [ ] CRITERION_1
- [ ] CRITERION_2
- [ ] CRITERION_3

## How to test
1. Pull the dev branch and run the app
2. Test the relevant endpoint / UI flow
3. Verify all acceptance criteria above are met

## Notes
_Any implementation decisions, trade-offs, or things reviewers should know._
PREOF
)"
```

Fill in the template with the actual user story content from Phase 3.

Print:
```
✓ PR created: https://github.com/REPO_OWNER/REPO_NAME/pull/PR_NUMBER

Next steps:
  - Teammate or lead reviews the PR on GitHub
  - If changes are requested: make them on dev, push — the PR updates automatically
  - Once approved, the lead merges dev → main
```

---

## Phase 11 — Move Issue to "In Review"

```bash
gh api graphql -f query='
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId,
    itemId: $itemId,
    fieldId: $fieldId,
    value: { singleSelectOptionId: $optionId }
  }) {
    projectV2Item { id }
  }
}
' -f projectId="$PROJECT_ID" \
  -f itemId="$PROJECT_ITEM_ID" \
  -f fieldId="$STATUS_FIELD_ID" \
  -f optionId="$IN_REVIEW_OPTION_ID"
```

Print final summary:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Done! Issue #ISSUE_NUMBER is In Review.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Feature branch: BRANCH_NAME (merged into BASE_BRANCH)
  PR:             https://github.com/REPO_OWNER/REPO_NAME/pull/PR_NUMBER
  Board:          issue moved to "In Review"

What happens next:
  1. Lead reviews the PR (dev → main) on GitHub
  2. If changes requested → make them on dev and push — PR updates automatically
  3. Lead merges → issue moves to Done
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## For /start-task --branch-only

Skip Phases 1–4 and 6–11. Only do Phase 5 (branch setup). Ask the user for the issue number and branch name directly.

---

## For /start-task --pr-only

Skip Phases 1–9. Only do Phases 10–11. Run from the current state of `BASE_BRANCH` (detected via `git branch -r`). Infer the issue number from the most recent commit message or ask the user. Raise a PR from `BASE_BRANCH` to `main`.

---

## Error handling

**"Issue not found"**: The issue number doesn't exist or is closed. Ask the user to double-check.

**"Project board not found"**: Run `/plan-project setup` to create it first.

**"Branch already exists"**: The branch was created before. Ask: "Branch already exists. Do you want to (1) switch to it and continue, or (2) create a new branch with a different name?"
```bash
git checkout $BRANCH_NAME
```

**"gh: authentication required"**: Run `gh auth login` first.

**"Merge conflict on merge into dev"**: Resolve the conflicts, then:
```bash
git status                    # see conflicting files
# Edit the conflicting files to resolve the markers, then:
git add conflicting-file.js
git merge --continue
git push origin $BASE_BRANCH
```

**"PR already exists for dev → main"**: GitHub will show a link to the existing PR. Push new commits to dev — the open PR updates automatically. No need to create another.

**Board status update fails**: Log the error but do not stop. Tell the user to manually update the board if needed.

---
name: plan-project
description: Set up a GitHub Project board for the current repo if one does not exist, gather requirements from the user, refine them into properly ordered user stories, create GitHub issues, plan sprints with milestones, and assign tasks to teammates. Use when starting a project from scratch or planning a new sprint.
trigger: /plan-project
---

# /plan-project

Turn ideas and requirements into a live GitHub Project board with user stories, sprint milestones, and teammate assignments — all from the terminal.

## Usage

```
/plan-project                     # detect repo, check for project, run full planning flow
/plan-project sprint              # only plan the next sprint from existing backlog
/plan-project setup               # only create the project board (no issues yet)
/plan-project assign              # only reassign issues to teammates
```

## What You Must Do When Invoked

Follow these phases in order. Do not skip phases. Check for the sub-command flag first and jump to the relevant phase if given.

---

## Phase 0 — Detect Repo and GitHub Auth

```bash
# Get repo info from git remote
REPO_REMOTE=$(git remote get-url origin 2>/dev/null)
REPO_OWNER=$(echo "$REPO_REMOTE" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
REPO_NAME=$(echo "$REPO_REMOTE" | sed -E 's|.*github\.com[:/][^/]+/([^/.]+).*|\1|')
echo "Repo: $REPO_OWNER/$REPO_NAME"

# Confirm gh is authenticated
gh auth status 2>&1 | head -5
CURRENT_USER=$(gh api user --jq '.login' 2>/dev/null)
echo "GitHub user: $CURRENT_USER"
```

If `REPO_OWNER` or `REPO_NAME` is empty: tell the user "Not inside a git repository with a GitHub remote" and stop.
If `CURRENT_USER` is empty: tell the user to run `gh auth login` first and stop.

---

## Phase 1 — Check for Existing GitHub Project

```bash
gh project list --owner "$REPO_OWNER" --format json --limit 20 2>/dev/null
```

Parse the JSON output. Look for a project whose `title` matches or contains `$REPO_NAME` (case-insensitive).

**If a matching project is found:**
- Print: `✓ Found existing project: "[title]" (#[number])`
- Store the project number as `PROJECT_NUMBER`
- Show current board stats:
  ```bash
  gh project view $PROJECT_NUMBER --owner "$REPO_OWNER" --format json 2>/dev/null | jq '{title, url, number}'
  gh issue list --repo "$REPO_OWNER/$REPO_NAME" --json number,title,assignees,milestone,labels --limit 100 2>/dev/null | jq 'length'
  ```
- Ask the user: "A project board already exists. Do you want to (1) add new issues to this sprint, (2) plan the next sprint from the backlog, or (3) start fresh?" Wait for their answer before continuing.
- If continuing, skip Phase 2 entirely and go to Phase 3.

**If no matching project is found:**
- Continue to Phase 2.

---

## Phase 2 — Prompt User to Create the Project Board Manually

> **Why manual?** The GitHub CLI and API can create a blank project, but they cannot create or configure Status field columns (Backlog, Ready, In Progress, etc.). Project templates in the GitHub UI are the only way to get a pre-configured board with the right columns. Do not attempt `gh project create` — it produces a blank board with no usable columns.

Print this message to the user and wait for them to complete each step before continuing:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ACTION REQUIRED — Create the GitHub Project manually
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The GitHub CLI cannot create project columns — you need to do
this once in the browser using a sprint template.

Step 1 — Open GitHub Projects:
  https://github.com/REPO_OWNER?tab=projects
  (replace REPO_OWNER with the actual owner)

Step 2 — Click "New project"

Step 3 — Choose a template
  Pick a sprint or scrum template that includes these columns:
    Backlog → Ready → In Progress → In Review → Done
  Recommended built-in templates:
    • "Team backlog"  — has Backlog, Ready, In Progress, Done
    • "Scrum"         — has full sprint fields including sprints
  If you have a saved custom template, use that instead.

Step 4 — Name the project
  Use exactly: REPO_NAME

Step 5 — Link the project to this repository
  Inside the new project → Settings → Linked repositories
  → Add repository → REPO_OWNER/REPO_NAME

Step 6 — Come back here and type "done"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Wait for the user to type "done" (or confirm they've finished) before continuing.

**After confirmation — verify the project now exists:**
```bash
gh project list --owner "$REPO_OWNER" --format json --limit 20 2>/dev/null
```

Look for a project matching `$REPO_NAME`. If still not found, tell the user:
"Project not detected yet. Double-check the project name matches exactly, then type 'done' again."
Repeat the verification until it is found. Store the project number as `PROJECT_NUMBER`.

**Read the project's field configuration:**
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
' -f owner="$REPO_OWNER" -F number=$PROJECT_NUMBER --jq '.data.user.projectV2'
```

If the owner is an organization, replace `user(login:...)` with `organization(login:...)`.

Store `PROJECT_ID`, `STATUS_FIELD_ID`, and the option IDs for each status column.

Print the detected columns so the user can confirm they match:
```
✓ Project found: "REPO_NAME" (#PROJECT_NUMBER)
  Status columns detected:
    • Backlog      (id: ...)
    • Ready        (id: ...)
    • In Progress  (id: ...)
    • In Review    (id: ...)
    • Done         (id: ...)
```

If fewer than 4 Status options are detected, warn the user: "Your project template may be missing some columns. Expected: Backlog, Ready, In Progress, In Review, Done. You can add missing columns in the project Settings on GitHub, then type 'continue'." Wait before proceeding.

Print: `✓ Project board ready. Continuing with planning...`

---

## Phase 3 — Requirements Gathering

Ask the user the following questions. Wait for their answers before proceeding. This is the most important phase — collect everything needed to write good user stories.

Ask these questions clearly, one block at a time:

**Question block 1 — Project context:**
```
What is this project trying to accomplish? (2-3 sentences describing the goal)
Who are the end users? (e.g. "developers who need maps", "admin team", "mobile users")
What is the deadline or target sprint count?
```

**Question block 2 — Features / requirements:**
```
List the features or tasks you want to build. You can be rough — bullet points, notes,
half-formed ideas, pasted from a doc. I will refine them into proper user stories.

If you have existing issues on the board, say "use existing issues" and I will
pull them from GitHub instead.
```

**Question block 3 — Team:**
```
Who are your teammates? List their GitHub usernames.
Do you want to assign tasks now, or leave them unassigned?
What are each person's areas (frontend, backend, infra, etc.)?
```

Wait for all three answers before moving to Phase 4.

---

## Phase 4 — Refine into User Stories

Take the raw requirements the user gave and transform each one into a proper user story.

**User story format:**

```markdown
**Title:** [Short, action-oriented title — max 60 chars]

**As a** [user type from Phase 3]
**I want** [to accomplish something specific]
**So that** [I get a concrete benefit]

**Acceptance Criteria:**
- [ ] [Specific, testable condition 1]
- [ ] [Specific, testable condition 2]
- [ ] [Specific, testable condition 3]

**Labels:** [backend|frontend|infra|bug|enhancement|docs]
**Priority:** [P0 = critical | P1 = high | P2 = normal | P3 = nice-to-have]
**Size:** [XS=<1hr | S=1-4hr | M=4-8hr | L=2+ days]
**Blocked by:** [issue # if dependent on another, else "none"]
```

**Ordering rules:**
1. Place foundation work first (database schema, auth, core API before UI)
2. Place items with `Blocked by` dependencies after their blockers
3. Group related items together
4. P0 items go to Sprint 1, P1 to Sprint 2, P2+ to backlog

Print all the refined user stories in the format above so the user can review them. Then ask:
```
Here are the refined user stories. Do you want to:
(1) Approve and create all issues
(2) Edit any stories before creating
(3) Remove any stories
```

Wait for confirmation before Phase 5.

---

## Phase 5 — Create GitHub Issues

For each approved user story, create a GitHub issue:

```bash
gh issue create \
  --repo "$REPO_OWNER/$REPO_NAME" \
  --title "STORY_TITLE" \
  --body "STORY_BODY" \
  --label "LABEL" \
  --assignee "GITHUB_USERNAME_OR_EMPTY"
```

**Important:**
- The body should be the full user story in the format from Phase 4
- If assigning, use the teammate GitHub username from Phase 3
- If no assignee decided yet, omit `--assignee`
- Create issues one at a time and store each returned issue number

Print progress as issues are created:
```
✓ #4 — Add user registration endpoint
✓ #5 — Build login page UI
✓ #6 — API key management dashboard
...
```

---

## Phase 6 — Add Issues to Project Board and Set Fields

For each created issue, add it to the project board and set Status, Priority, and Size fields.

**Step 1 — Get the issue's node ID:**
```bash
gh api repos/$REPO_OWNER/$REPO_NAME/issues/ISSUE_NUMBER --jq '.node_id'
```

**Step 2 — Add to project:**
```bash
gh api graphql -f query='
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
' -f projectId="PROJECT_ID" -f contentId="ISSUE_NODE_ID" --jq '.data.addProjectV2ItemById.item.id'
```

Store the returned item ID as `ITEM_ID`.

**Step 3 — Set Status to "Backlog":**
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
' -f projectId="PROJECT_ID" \
  -f itemId="ITEM_ID" \
  -f fieldId="STATUS_FIELD_ID" \
  -f optionId="BACKLOG_OPTION_ID"
```

**Step 4 — Set Priority and Size fields** (if they exist on the board):
Repeat the mutation above with the Priority and Size field IDs and the appropriate option IDs.

If Priority or Size fields do not exist, skip silently. Do not try to create them via API.

---

## Phase 7 — Sprint Planning

Group the issues into sprints. One sprint = 1–2 weeks of work. Use these rules:

- Sprint 1: All P0 issues + the first P1 issues that fit within the sprint capacity
- Sprint 2: Remaining P1 issues
- Sprint 3+: P2 and P3 issues

**Sprint capacity estimate:**
- Count teammates
- Assume ~20 story points per person per sprint (S=1pt, M=2pt, L=5pt, XS=0.5pt)
- Fill Sprint 1 up to capacity, overflow to Sprint 2

Create a GitHub milestone for each sprint:

```bash
gh api repos/$REPO_OWNER/$REPO_NAME/milestones \
  --method POST \
  --field title="Sprint 1" \
  --field description="Foundation: auth, database, core API" \
  --field due_on="YYYY-MM-DDT00:00:00Z"
```

Calculate due dates: Sprint 1 ends 2 weeks from today, Sprint 2 ends 4 weeks from today, etc.

Assign milestone to each issue:
```bash
gh issue edit ISSUE_NUMBER --repo "$REPO_OWNER/$REPO_NAME" --milestone "Sprint 1"
```

---

## Phase 8 — Final Summary

Print a clean summary of what was created:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Project: REPO_NAME
 Board:   https://github.com/users/REPO_OWNER/projects/PROJECT_NUMBER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sprint 1 (due: DATE) — N issues
  #4  Add user registration endpoint       @username   M
  #5  Build login page UI                  @username   M
  ...

Sprint 2 (due: DATE) — N issues
  #8  API key dashboard                    @username   L
  ...

Backlog — N issues
  #11 Integrate Pelias geocoder            unassigned  L
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Next: teammates run /start-task to pick up their assigned issue.
```

---

## For /plan-project sprint (sprint-only mode)

Skip Phases 2–5. Start from Phase 6 using existing issues.

1. List all open issues currently in "Backlog":
   ```bash
   gh issue list --repo "$REPO_OWNER/$REPO_NAME" --state open --json number,title,assignees,milestone,labels --limit 100
   ```

2. Ask the user which issues to include in the next sprint and who to assign them to.

3. Run Phases 7–8.

---

## For /plan-project assign (reassign mode)

1. List all open issues and their current assignees:
   ```bash
   gh issue list --repo "$REPO_OWNER/$REPO_NAME" --state open --json number,title,assignees --limit 100
   ```

2. Ask the user which issues to reassign and to whom.

3. Update each issue:
   ```bash
   gh issue edit ISSUE_NUMBER --repo "$REPO_OWNER/$REPO_NAME" --add-assignee "NEW_USER" --remove-assignee "OLD_USER"
   ```

---

## GraphQL owner type note

All GraphQL queries above use `user(login: $owner)`. If the repo belongs to a GitHub **organization** (check: `gh api orgs/$REPO_OWNER` returns 200), replace `user` with `organization` in all queries:
```graphql
organization(login: $owner) { projectV2(number: $number) { ... } }
```

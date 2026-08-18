---
name: new-issue
description: Create a new GitHub issue interactively from any repo. Detects issue type (bug/feature/chore/docs) from the description, generates a structured body with acceptance criteria, confirms with the user, creates the issue, and adds it to the project board as Backlog. Use whenever a developer or PM wants to log a new task, bug, or feature request.
trigger: /new-issue
---

# /new-issue

Create a well-structured GitHub issue in one guided flow — from a rough description to a board-ready ticket.

## Usage

```
/new-issue                          # fully interactive — ask for everything
/new-issue "add dark mode toggle"   # seed description provided, skip the opening prompt
```

## What You Must Do When Invoked

Follow these phases in order.

---

## Phase 0 — Detect Repo and User

```bash
REPO_REMOTE=$(git remote get-url origin 2>/dev/null)
REPO_OWNER=$(echo "$REPO_REMOTE" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
REPO_NAME=$(echo "$REPO_REMOTE" | sed -E 's|.*github\.com[:/][^/]+/([^/.]+).*|\1|')
CURRENT_USER=$(gh api user --jq '.login' 2>/dev/null)

echo "Repo: $REPO_OWNER/$REPO_NAME"
echo "User: $CURRENT_USER"
```

If `REPO_OWNER` or `REPO_NAME` is empty: print "Not inside a git repo with a GitHub remote." and stop.
If `CURRENT_USER` is empty: print "Run `gh auth login` first." and stop.

---

## Phase 1 — Gather the Description and Type

If the user provided a seed description (e.g. `/new-issue "add dark mode toggle"`), use that as the raw description and skip asking. Otherwise ask:

```
What's the issue about? (describe in one sentence)
```

**Auto-detect issue type** from the description using keyword heuristics:

| Keywords present | Type |
|---|---|
| fix, bug, error, broken, crash, regression, wrong, incorrect, fails, doesn't work | `bug` |
| add, build, implement, create, introduce, support, enable, integrate | `feature` |
| refactor, clean, move, rename, extract, reorganise, consolidate | `chore` |
| docs, document, readme, comment, guide, explain | `docs` |
| (none of the above) | `task` |

Show the detected type and confirm:

```
Detected type: feature
Is this correct? (yes / bug / chore / docs / task)
```

Wait for response. Update `TYPE` if the user corrects it.

Then ask two quick follow-up questions:

```
Priority? (P0 — critical  /  P1 — high  /  P2 — normal  /  skip)
Assign to yourself? (yes / no)
```

Store as `PRIORITY` (may be empty if skipped) and `ASSIGN_SELF`.

Now ask for a title if the seed description is not title-length:

```
Issue title: (press enter to use: "Add dark mode toggle")
```

If the user presses enter, derive a clean title from the description (title-case, max 60 chars). Store as `TITLE`.

---

## Phase 2 — Generate Structured Issue Body

Use the confirmed `TYPE` to pick the right template. Fill in every section using what you know from the description and codebase context.

### Template: `bug`

```markdown
## Description
[one-line summary of the bug]

## Steps to Reproduce
1. [first step]
2. [second step]
3. [observe the problem]

## Expected Behaviour
[what should happen]

## Actual Behaviour
[what currently happens — error message, wrong output, etc.]

## Acceptance Criteria
- [ ] Bug no longer reproduces following the steps above
- [ ] No regression in related functionality
- [ ] Tests pass / no build errors
```

### Template: `feature` or `task`

```markdown
## User Story
As a [inferred actor — developer / end user / admin]
I want [what the feature does]
So that [why it matters]

## What to Build
[2–3 sentences — specific and actionable. Reference files, endpoints, or UI components if known.]

## Acceptance Criteria
- [ ] [specific, testable condition]
- [ ] [specific, testable condition]
- [ ] [specific, testable condition]
- [ ] Tests pass / no build errors
```

### Template: `chore` or `docs`

```markdown
## Description
[what needs to change and why]

## Done When
- [ ] [condition 1]
- [ ] [condition 2]
```

Print the full generated body to the user and ask:

```
Does this look correct? (yes / no — tell me what to change)
```

Wait. If no, apply the requested changes and print again. Repeat until confirmed.

---

## Phase 3 — Create the Issue

Build the `gh issue create` command:

```bash
gh issue create \
  --repo "$REPO_OWNER/$REPO_NAME" \
  --title "$TITLE" \
  --body "$BODY"
  # append --assignee "@me" if ASSIGN_SELF=yes
```

**Labels:** Attempt to apply a priority label if `PRIORITY` was given:

```bash
# Check if the label exists first
LABEL_EXISTS=$(gh label list --repo "$REPO_OWNER/$REPO_NAME" --json name --jq ".[].name" | grep -x "$PRIORITY" || true)
if [ -n "$LABEL_EXISTS" ]; then
  # add --label "$PRIORITY" to the gh issue create command
fi
# If label doesn't exist, skip silently — do NOT create it or fail
```

Store the returned issue number as `ISSUE_NUMBER` and the URL as `ISSUE_URL`.

---

## Phase 4 — Add to Project Board

Find the project board for this repo:

```bash
PROJECT_JSON=$(gh project list --owner "$REPO_OWNER" --format json --limit 20 2>/dev/null)
PROJECT_NUMBER=$(echo "$PROJECT_JSON" | jq --arg name "$REPO_NAME" \
  '[.projects[] | select(.title | ascii_downcase | contains($name | ascii_downcase))] | .[0].number')
```

If no project found, print a warning and skip to Phase 5.

Get the project ID and Status field:

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

If the owner is an org, replace `user` with `organization`.

Store `PROJECT_ID`, `STATUS_FIELD_ID`, and `BACKLOG_OPTION_ID` (the option whose name matches "Backlog", case-insensitive).

Get the issue's node ID:

```bash
ISSUE_NODE_ID=$(gh api repos/$REPO_OWNER/$REPO_NAME/issues/$ISSUE_NUMBER --jq '.node_id')
```

Add to project:

```bash
ITEM_ID=$(gh api graphql -f query='
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
' -f projectId="$PROJECT_ID" -f contentId="$ISSUE_NODE_ID" --jq '.data.addProjectV2ItemById.item.id')
```

Set status to Backlog:

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
  -f itemId="$ITEM_ID" \
  -f fieldId="$STATUS_FIELD_ID" \
  -f optionId="$BACKLOG_OPTION_ID"
```

---

## Phase 5 — Summary

Print:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Created: #ISSUE_NUMBER — TITLE
 Type:    TYPE
 URL:     ISSUE_URL
 Board:   added to Backlog ✓  (or: no project board found)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run /start-task #ISSUE_NUMBER when you're ready to work on it.
```

---

## Error Handling

**"Label not found"** — skip label, warn, continue. Never fail the whole flow over a missing label.

**"Project board not found"** — print "⚠ No project board found for this repo. Issue created without board placement." and continue to summary.

**"gh: authentication required"** — print "Run `gh auth login` first." and stop.

**"Repository not found"** — print "Check that you're in the right directory and the remote is correct." and stop.

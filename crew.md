# Crew Standing Orders

You're crew on this ship. You receive watch orders from the First Mate and execute bounded work sessions.

## Starting a Watch

1. Read your watch orders (provided by Mate)
2. Read the assigned ticket at the path in your orders
3. Check for previous logs in ship/logs/{project}/{ticket-id}/
4. If continuing work, read the most recent log's "Left off" and "Next steps"
5. Confirm the branch exists or create it: `git checkout -b {branch-name}`
6. Start working within the ticket's scope

## During a Watch

- **Stay within scope.** If scope seems wrong, flag it, don't expand it.
- **Save frequently.** Write files as you go - Mate/Captain will handle commits.
- **Watch for spin.** If you've tried the same approach twice without progress, end watch, checkpoint.
- **Watch for context strain.** If you're getting confused or the session is long, end watch, checkpoint.
- **If blocked on something external**, don't spin. Note it and end the watch.

## Ending a Watch

When the Captain says "checkpoint" or "end watch", OR when you've made progress you'd be sad to lose, OR when you're blocked or spinning:

1. **Ensure all files are saved** (Mate/Captain will handle commits)

2. **Write a log** to `ship/logs/{project}/{ticket-id}/{YYYY-MM-DD-HHMM}.md`:

```
# {ticket-id} - {YYYY-MM-DD-HHMM}

**Ticket:** [{ticket-id}](../../../projects/{project}/tickets/{ticket-id}.md)

## Did
{What you accomplished this watch - be specific}

## Left off
{Current state - exactly where things stand, what files were modified, what's working/not}

## Next steps
1. {Concrete next action - specific enough to start immediately}
2. {Concrete next action}

## Handoff confidence
{1-5: How smooth will handoff be? 5 = next crew can start immediately, 1 = significant context may be lost}

## Notes (optional)
{Discoveries, concerns, ideas, things to revisit}
```

3. **Update the ticket's "Current state" section** to reflect where things stand

4. **Add entry to ticket's "Watch history"** section with hyperlink to log:
   ```
   ## Watch History

   - **2026-01-20-1400** - [Log](../../../logs/{project}/{ticket-id}/2026-01-20-1400.md) - Investigation complete, identified files for removal
   - **2026-01-21-0900** - [Log](../../../logs/{project}/{ticket-id}/2026-01-21-0900.md) - Implementation complete, changes staged
   ```

   **Linking is critical.** Without links, logs are hard to find. Always use relative markdown links.

5. **Say "Watch complete"** so the Captain/Mate knows you're done

## Git Restrictions

**Crew have READ-ONLY git access.** You may:
- `git status`, `git diff`, `git log` - check state
- `git checkout <branch>` - switch to existing branch
- `git checkout -b <branch>` - create new branch

**You may NOT:**
- `git commit` - Mate/Captain handles commits
- `git push` - Mate/Captain handles pushes
- `git add` - Don't stage; just save files
- `git reset`, `git revert`, etc. - No destructive operations

This boundary ensures clean handoffs. Write your code, write your log, and Mate/Captain will commit everything together.

## What Gets Committed (by Mate/Captain)

- All code changes on your branch
- Your log file (new file in ship/logs/)
- Your assigned ticket's "Current state" and "Watch history" sections

## What You Don't Touch

- **queue.md** - Mate owns this. Never modify.
- **Other tickets** - Only your assigned ticket.
- **captain.md** - Read only.
- **inbox/** - Don't write here; escalate verbally or in your log.

## Your Authorities

- Implementation decisions within the spec
- Refactoring that serves the goal
- Adding tests
- Exploring approaches
- Creating helper files, scripts, etc.
- **Code formatting and linting** (terraform fmt, prettier, rubocop, etc.) - these are part of implementation work

## Tool Restrictions

### Bash Access

Your `allowed_tools` are set by Mate when dispatching. For security:

- **Research/read-only watches** get scoped Bash patterns like `Bash(git status*)`, `Bash(git log*)`, `Bash(git diff*)` - not broad `Bash` access
- **Implementation watches** may get broader Bash access for running tests, linters, etc.
- If you need a Bash command that isn't in your allowed_tools, note it in your log - don't try to work around it

### Other Restrictions

Your watch orders may include additional tool restrictions. Common examples:
- Read-only watches (no code changes)
- No external API calls
- Specific tools disabled

If you need a restricted capability to complete the work, note it in your log and end the watch. Mate can dispatch a follow-up with different restrictions.

## Not Your Call

- Changing the goal or scope (flag it, don't do it)
- Modifying other tickets
- Merging to main
- Assigning yourself new work (Mate dispatches)
- Deciding "this ticket is actually done" if criteria aren't met

## If Blocked

Don't spin. Update the ticket's "Blocked on" section with:
- Exactly what external thing you need
- Who might be able to provide it
- What you tried

Then write your log and end the watch. Blocking is not failure - it's information.

## Log Quality Check

Before ending a watch, verify: Could a completely fresh Claude Code session read this log + the ticket and continue without asking clarifying questions?

If not, add what's missing.

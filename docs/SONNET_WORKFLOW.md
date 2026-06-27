# Driving the build with Claude Sonnet — workflow & context hygiene

This is the operator's manual for building the milestones in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) cheaply and reliably with
Claude Sonnet. It tells you **exactly what to paste**, **when to `/clear` vs
`/compact`**, and **when to escalate back to Opus**.

---

## The one idea that makes this efficient

**The source of truth lives on disk, not in the conversation.** The plan doc,
the committed code, and the passing test gates are the project's memory. The chat
history is disposable scaffolding.

Consequence: you should **`/clear` aggressively between milestones**. A fresh
Sonnet session that re-reads two or three plan sections costs far fewer tokens
than one long session dragging the entire history of M0–M5 into every reply.
Long contexts also make Sonnet *worse* (more drift, more "creative"
reinterpretation), not just pricier.

### `/clear` vs `/compact` — the rule
- **`/clear`** — wipe the conversation, keep settings/model. Use **between
  milestones**, every time, after the gate passes and the work is committed.
- **`/compact`** — summarize the conversation to shrink it but keep continuity.
  Use **only within a single milestone** when a debugging session has grown long
  and you don't want to lose the thread of what you've already tried.
- Never carry a finished milestone's chat into the next one. There's nothing in
  it the plan + the committed code doesn't already capture.

> **Always commit before you `/clear`.** The commit is what survives the wipe.
> If a milestone isn't committed and you clear, you've thrown away the only
> durable record of the conversation's output.

---

## First moves — handing off from this Opus session

You're currently in the Opus planning session with M0 already built and green.
Do this, in order:

1. **Commit M0** (ask Opus, or run it yourself):
   ```bash
   git add -A && git commit -m "feat: scaffold project (M0)"
   ```
2. **Switch the model to Sonnet:** type `/model sonnet`.
3. **Drop the planning context:** type `/clear`. (The plan is on disk — you lose
   nothing. This is the single biggest token saver in the whole process.)
4. **Optional but recommended:** `/effort medium`. Sonnet at medium effort
   handles spec-driven implementation well and burns far fewer tokens than high.
   Save high effort for when something is actually stuck.
5. **Start M1** with the prompt below.

That's the whole handoff: commit → `/model sonnet` → `/clear` → `/effort medium`
→ paste M1 prompt.

---

## The reusable milestone prompt

Every milestone uses the same shape. Only the milestone number and the
"read sections" list change.

```
Read these sections of docs/IMPLEMENTATION_PLAN.md, then stop and confirm you've
read them: §17 (conventions) and <SECTIONS FOR THIS MILESTONE>.

Then implement milestone <Mn> exactly as specified in §15. When done, run that
milestone's Acceptance gate and show me the full command output.

Rules:
- Do NOT start the next milestone. Stop at the gate.
- Follow the injection seams in §2 (no datetime.now()/subprocess outside their
  designated modules).
- If a spec detail is genuinely missing, follow §17: pick the simplest behavior
  consistent with the contracts and leave a `# TODO(plan):` comment. Do not
  expand scope.
```

Telling Sonnet which sections to read (instead of "read the plan") keeps it from
pulling the whole 400-line doc into context every time — meaningful token
savings across seven milestones.

---

## Per-milestone quick reference

For each row: paste the reusable prompt with that milestone's sections, let
Sonnet finish and show the green gate, **commit**, then **`/clear`** before the
next row.

| Milestone | Sections to tell Sonnet to read | Suggested commit message | After the gate |
|---|---|---|---|
| **M1** Models, errors, time ranges | §5, §6, §7, §14, §15 (M1) | `feat: add models, errors, time ranges (M1)` | commit → `/clear` |
| **M2** Git collection | §6, §8, §5, §14, §15 (M2) | `feat: collect and parse git commits (M2)` | commit → `/clear` |
| **M3** Template summarizer | §5, §10, §14, §15 (M3) | `feat: deterministic template summarizer (M3)` | commit → `/clear` |
| **M4** Renderers | §5, §11, §14, §15 (M4) | `feat: text and markdown renderers (M4)` | commit → `/clear` |
| **M5** Config + CLI wiring | §9, §12, §13, §14, §15 (M5) | `feat: config loading and CLI orchestration (M5)` | commit → `/clear` |
| **M6** Integration + docs | §14, §15 (M6), §16, §11 | `test: end-to-end integration; docs (M6)` | commit → `/clear` |
| **M7** CI/CD + release | §15 (M7), §4 | `ci: add GitHub Actions and release hygiene (M7)` | commit (PR) |

### Milestone-specific notes
- **M2 is the riskiest milestone.** The git-log delimiter format and the
  numstat parse (§8.3–§8.4) are where a cheaper model is most likely to slip. If
  the collector tests fail twice in a row, don't keep re-prompting Sonnet —
  escalate (see below). Also remind it explicitly: *"the binary-file (`-`),
  empty-body, and merge-commit edge cases each need a test."*
- **M5 introduces the pure `run(...)` function** (§14). Make sure Sonnet factors
  orchestration into `run(config, *, now, runner) -> str` so the CLI callback
  stays a thin shell and tests can inject fakes. If it crams logic into the Typer
  callback, push back: *"extract a pure run() per §14 so it's testable without
  invoking the CLI."*
- **M6** is mostly the integration test + README. Have Sonnet also verify the
  whole tool against this repo: `standup -f markdown`.
- **M7** ends in a PR, not just a commit — let CI be the gate.

---

## When to escalate back to Opus

Sonnet is the right default for spec-driven implementation. Switch to Opus
(`/model opus`, and consider `/effort high`) only when:

- A gate **fails twice** and Sonnet's fixes are going in circles.
- The failure is a **design/architecture** question, not a typo (e.g. "the
  parser approach in the plan doesn't handle X" — that's a real plan gap worth
  Opus's judgment).
- You're touching the **M2 parser** or the **M5 dependency-injection seam** and
  it's not converging.

After Opus unblocks it, switch back: `/model sonnet`, `/clear`, resume the
milestone. Don't run whole milestones on Opus out of caution — it's the
expensive path and the gates already catch regressions.

---

## If Sonnet drifts mid-milestone

- **It starts the next milestone unprompted** → stop it: *"Stop. You're only
  building <Mn>. Revert anything outside its scope and run just the <Mn> gate."*
- **It invents scope or a dependency** → *"§4 fixes the dependencies and §17
  says don't expand scope. Remove that and use the stdlib/specified approach."*
- **The session has gotten long while debugging one gate** → `/compact`, then
  continue. Don't `/clear` mid-milestone (you'd lose what's already been tried).
- **It edited the plan doc** → that's not its job. *"Leave
  docs/IMPLEMENTATION_PLAN.md unchanged; implement against it."*

---

## Daily-driver checklist (print this mentally)

1. `/model sonnet`, `/effort medium`
2. Paste milestone prompt (with that milestone's sections)
3. Sonnet implements → shows **green gate**
4. Review the diff briefly
5. `git commit` with the conventional message
6. `/clear`
7. Next milestone → back to step 2

Seven clean loops, one milestone each, the plan doc as the spine. That's the
whole build.

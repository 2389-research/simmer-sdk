# Agency Board Test: Creative/Subjective (DND Adventure Hook)

**Date:** 2026-03-22
**Task:** Seedless DND adventure hook, judge-only (no evaluator), Agency-composed judge board
**Branch:** simmer-judge-board-agency
**Duration:** ~10 min (no evaluator waits)

---

## Trajectory

| Iter | Narrative Tension | Player Agency (PRIMARY) | Specificity | Composite | Key Change |
|------|-------------------|------------------------|-------------|-----------|------------|
| 1    | 7                 | 7                      | 7           | 7.0       | Initial seed — 3-thread structure, tidal clock, 4-way convergence |
| 2    | 8                 | 8                      | 7           | 7.7       | Three distinct climax locations, Tomas interruption, faction fallout |
| 3    | 9                 | 9                      | 9           | 9.0       | Mid-thread forks (Neshka, Elda refuses), inline stat blocks, anchor-stone |

**Best:** Iteration 3 (9.0/10). Monotonic improvement, no regressions.

---

## Cross-Run Comparison (all DND adventure hook tests)

| Run | Config | Final | Tension | Agency (P) | Specificity | Regressions |
|-----|--------|-------|---------|------------|-------------|-------------|
| v3 R1 | Single judge | 8.7 | 8 | 9 | 9 | 0 |
| v3 R2 | Single judge | 9.0 | 9 | 9 | 9 | 0 |
| v3 R3 | Single judge | 8.7 | 9 | 8 | 9 | 0 |
| **Agency board** | **3 judges + deliberation** | **9.0** | **9** | **9** | **9** | **0** |

Scores are comparable — 9.0 matches the best single-judge run (R2). But scores alone don't tell the story. The artifact quality is where the difference shows.

---

## Artifact Quality Comparison

### What every single-agent version had (R1/R2/R3)
- Setup with a hook (haunted lighthouse, stormy coast)
- Named NPCs with basic motivations
- A ticking clock
- Branching resolution options (3-4 paths at the climax)
- Good sensory detail and names
- Playable — a DM could run it

### What the Agency board version added

**1. Mid-thread forks, not just end-of-adventure branching.**

The single-agent versions branch at the climax: "you've reached the lighthouse, here are 4 ways to resolve it." The Agency version branches WITHIN each thread:

- Thread A: Neshka (a drowned one who remembers her name) offers to betray her masters if the party destroys the anchor-stone. Accept = fight 2 enemies but permanently close the shrine. Refuse = fight all 3 but keep options open for Maren. This is a decision IN THE MIDDLE of the thread that changes the climax.
- Thread B: Elda doesn't want to be rescued. Her lungs are failing; the villain's ritual is keeping her alive. The party must choose: honor her wish, drag her out (she'll die), or negotiate with the villain. This reframes the entire thread from "rescue mission" to "whose agency matters — yours or hers?"
- Thread C: Vorrow offers Elda's location in exchange for assassinating Brother Silt. Accept = teleported into another thread's climax. Refuse = fight + scrying pool reveals location anyway.

The single-agent versions had ONE major decision point. This version has 3+ genuine decisions BEFORE the climax.

**2. The Tomas interruption — a mid-session moral dilemma with mechanical cost.**

90 minutes in, regardless of which thread the party is following, a drowned one drags a 12-year-old kid underwater. The party must choose:
- Dive in: DC 14 Athletics, disadvantage on underwater attacks, costs 30+ minutes of the tidal clock
- Ignore: Tomas's mother screams his name for the rest of the session, all townsfolk refuse further help

This is sophisticated adventure design. It's a no-win choice that costs something either way. The single-agent versions had ticking clocks but no mid-session forced choice that trades quest progress for moral obligation.

**3. Faction fallout — actions have consequences beyond the immediate thread.**

Whichever thread resolves the rescue, the surviving faction retaliates within the hour:
- Destroyed the shrine? Vorrow sends bone constructs into town.
- Killed Silt? His converts sabotage the docks.
- Killed Vorrow? More drowned ones surface.

This creates a 4th act that most DND hooks don't have. The party can't just "win" — they have to deal with the fallout of their choices. None of the single-agent versions had this.

**4. Inline stat blocks and DCs throughout.**

Every NPC has AC, HP, attack bonuses. Every check has a DC. Every combat encounter has CR. A DM can literally run this without opening any rulebook. The single-agent versions had some stats but not consistently throughout.

**5. NPC motivation table with betrayal triggers.**

A quick-reference table showing what each NPC wants and when they'll turn on the party. This is a DM tool — glanceable during play. No single-agent version produced this.

**6. "Elda doesn't want to leave."**

This is the standout creative choice. Thread B's resolution isn't "rescue the mayor" — it's "the mayor doesn't want to be rescued, and forcing her means she dies." This turns a straightforward rescue into a moral dilemma. None of the single-agent versions had a twist of this quality.

---

## Why the Board Produced Better Creative Output

The text/creative judge panel has three lenses:
- **Craft** — structure, pacing, technique
- **Reader** — engagement, clarity, emotional impact
- **Domain** — factual accuracy, genre conventions

Each lens likely contributed different improvements:

| Feature Added | Likely Source |
|---|---|
| Mid-thread forks | **Craft** — "the middle section is linear, add decision points within threads" |
| Tomas interruption | **Reader** — "the session needs an emotional beat that makes players feel the stakes personally" |
| Inline stat blocks | **Domain** — "a DM can't run this cold without DCs and stat blocks for every encounter" |
| Faction fallout | **Craft** — "the ending is too clean, add consequences that extend the climax" |
| NPC betrayal table | **Domain** — "DMs need quick reference during play, not just prose" |
| Elda doesn't want to leave | **Reader** — "the rescue is too straightforward, subvert the expectation" |

A single judge might notice 1-2 of these. The board's three perspectives each contributed a different dimension of improvement. The deliberation surfaced which improvements had the highest leverage, and the synthesis picked one per iteration.

---

## Performance Notes

- **No regressions.** 7.0 → 7.7 → 9.0 monotonic climb. This is the cleanest trajectory across all board runs.
- **Fast.** ~10 min total for 3 iterations with no evaluator. Compare to 30-60 min for the extraction prompt tests.
- **Agency composition cost:** 3 judges × 3 iterations = 9 judge subagent dispatches + 3 deliberation rounds + 3 synthesis steps. On a creative task this is pure API calls with no evaluator wait, so the overhead is minimal.
- **Self-score accuracy:** 9.0 for an artifact that genuinely reads as a 9/10 adventure hook. The board's multi-perspective scoring seems well-calibrated on creative tasks as well as engineering tasks.

---

## Key Takeaway

The Agency board on creative tasks doesn't just match the single agent — it produces a **qualitatively different** artifact. The single agent writes good adventure hooks. The board writes adventure hooks with design elements (mid-thread forks, moral interruptions, faction fallout, mechanical specificity) that reflect multiple expert perspectives.

The scores are similar (9.0 vs 9.0) because the single agent was already good at creative writing. But the output is richer in ways that a score can't fully capture — branching depth, mechanical completeness, moral complexity, DM usability.

This is the strongest argument for the board on creative tasks: it's not about catching errors (the single agent doesn't make many), it's about surfacing improvements that one perspective wouldn't think of.

---

## Updated Cross-Configuration Comparison (Full Testing Arc)

| Config | Best Use Case | Extraction (engineering) | Creative (DND) |
|---|---|---|---|
| Single agent | Fast iteration, simple tasks | 6.5 (inflated) | 8.7-9.0 |
| Board (manual profiles) | Plateau-breaking | 5.0 | Not tested |
| Board (synthesis fix) | Focused improvement | 5.0 | Not tested |
| **Agency judges + std gen** | **Engineering tasks** | **6.4 (best actual quality)** | Not tested |
| **Agency board (creative)** | **Creative/subjective tasks** | N/A | **9.0 (richer artifact)** |
| Agency full (judges + gen) | Not recommended | 5.0 (gen overrode ASI) | Not tested |

**Recommended configuration:** Agency-composed judge board for both creative and engineering tasks. Standard generator (faithful ASI execution). The synthesis fixes (mutation bounds, focused ASI, deliberation summaries) are critical in both modes.

# Report status against the UCS503L structure

Estimated by artefact completeness (a chapter written and backed by evidence = 100%).
Code is further along than the report: the simulation core is ~85% of the MVP, the
report as a whole is ~40%.

| Ch | Title | Status | Notes |
| --- | --- | --- | --- |
| 1 | Introduction | Done | Matches 1.1 to 1.7 |
| 2 | Feasibility Study | Done | Matches 2.1 to 2.6 |
| 3 | SDLC Model Selection | Written | Iterative with evaluation; execution shown through four iterations and their commits |
| 4 | Requirements Engineering | Written | 15 FR, 10 NFR (with measured values), traceability. Elicitation says plainly that no interviews were held |
| 5 | System Analysis | Written | Existing vs proposed system, use-case diagram, 7 use-case descriptions |
| 6 | System Design | Written | Architecture, UML (as built), state diagrams, deployment, ER (no database, explained), DFD, interface with screenshots; appendices A and B hold the pre-build drawings; D9 class diagram rewritten to match the code |
| 7 | Planning and Management | Written, **one gap** | WBS, schedule, Gantt, risk register done. **Task allocation (7.4) left blank for the team**: it is not recorded anywhere |
| 8 | Implementation | Written | Stack, modules, algorithms, validation table, error handling, security |
| 9 | Software Testing | Written | Plan, objectives, strategy, unit, integration, system, acceptance against the five objectives |
| 10 | Test Case Design | Written | 37 black-box cases with actual results, 19 browser checks, 19 defects, execution summary, coverage 98.2% / 96.2%, performance, security |
| 11 | Deployment and Maintenance | Written | Install, troubleshooting from real problems, user manual, four maintenance types |
| 12 | Conclusion | Written | Honest: objective 2 partly met; recovery claim from the literature not reproduced |

**Remaining before submission:** fill Chapter 7.4; decide whether to keep the note on AI-assisted review in 3.4;
convert Mermaid and PlantUML to images if the course needs a PDF; have the team read Chapters 3 and 7 for
accuracy about who did what and when.

## Defects

The defect log (19 defects with severity, priority, cause, correction and retest, plus the test-case defects) is in [Chapter 10.5](report/Chapter10-Test-Case-Design-and-Management.md#105-defect-and-bug-management); it is the single source of truth.

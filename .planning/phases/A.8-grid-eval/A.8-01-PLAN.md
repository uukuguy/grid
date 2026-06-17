<plan phase="A.8" name="grid-eval CI Enhancement">
<objective>
Enhance existing eval-ci.yml workflow with concurrency control and test summary reporting. The web dashboard for eval results is a separate UI project (deferred).
</objective>

<review_protocol>none</review_protocol>

<tasks>
- [ ] T1: Add concurrency group to prevent duplicate CI runs for the same ref
- [ ] T2: Add test summary report generation that lists all eval suite outputs in the GitHub step summary
</tasks>

<verification>
- [ ] YAML syntax valid (workflow file parses correctly)
</verification>

<notes>
The existing eval-ci.yml workflow was already comprehensive: unit/integration tests, mock suite runs (provider/memory/resilience), benchmark runs (GAIA/SWE-bench/τ-bench), regression detection with PR commenting, and artifact upload. This phase adds polish: concurrency control and summary reports.
</notes>
</plan>

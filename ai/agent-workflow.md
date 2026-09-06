# Mercury Agent Workflow

1. Read `AGENTS.md`, the relevant `docs/` file, and nearby source or tests.
2. Identify the owning layer and the smallest change that can satisfy the request.
3. For non-trivial analytics, schema, API, or security work, state the plan and affected files before editing.
4. Implement the change while preserving data contracts and project conventions.
5. Run the cheapest focused validation first, then broader checks proportional to risk.
6. Review the final diff and report modified files, validation evidence, and remaining gaps.

For debugging, identify the root cause before changing code. Never present planned architecture as verified implementation.
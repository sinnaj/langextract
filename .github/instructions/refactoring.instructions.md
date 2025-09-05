# Standard instruction: Refactoring checklist

1. **Clean-up outdated artifacts**

   - After refactoring, scan for obsolete code, files, or folders.
   - Delete or migrate anything no longer referenced.

2. **Keep test coverage healthy**

   - If the original code had unit / integration tests, update them.
   - If coverage was missing, create new tests under the project-relative path `/tests`.
   - Ensure the entire test suite passes locally _and_ in CI/CD.

3. **Preserve behaviour & contracts**

   - Maintain public APIs and user-facing behaviour unless the refactor intentionally introduces a breaking change.
   - If breaking changes are required, flag them clearly in the PR title, description, and release notes.

4. **Document the change**

   - Update inline docstrings, comments, and any affected markdown or code examples.
   - Add a succinct entry to `CHANGELOG.md` (or equivalent) describing what, why, and any migration steps.

5. **Run quality gates**

   - Lint, format, and type-check (e.g. `eslint`, `prettier`, `black`, `ruff`, `mypy`, etc.).
   - Address all warnings or justify exceptions in the PR.

6. **Validate performance & footprint**

   - Compare key benchmarks or memory usage to pre-refactor baselines.
   - If regression is unavoidable, document the rationale.

7. **Update configuration & CI**
   - Adjust build scripts, Dockerfiles, deployment manifests, or feature flags affected by the refactor.
   - Verify pipelines (GitHub Actions, Jenkins, etc.) still succeed.

> **Remember:** A refactor is finished only when the system behaves the same (or better) _and_ the codebase stays coherent, tested, and documented.
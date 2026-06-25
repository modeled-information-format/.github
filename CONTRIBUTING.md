# Contributing to attested-delivery/.github

Thank you for your interest in contributing. This repository holds the org-wide
shared workflows, community health files, and attestation patterns for the
`attested-delivery` organization.

## How to Contribute

### Reporting Bugs

1. **Search existing issues** at [github.com/attested-delivery/.github/issues](https://github.com/attested-delivery/.github/issues) to avoid duplicates.
2. If no existing issue matches, [open a new bug report](https://github.com/attested-delivery/.github/issues/new?template=bug_report.yml).
3. Include as much detail as possible: steps to reproduce, expected vs actual behavior, environment details, and logs or screenshots.

### Suggesting Features

1. **Check discussions and issues** to see if the feature has already been proposed.
2. [Open a feature request](https://github.com/attested-delivery/.github/issues/new?template=feature_request.yml) with a clear description of the problem and your proposed solution.

### Submitting Pull Requests

1. **Fork the repository** and create a branch from `main`.
2. **Make your changes** in a focused, well-scoped branch.
3. **Update documentation** if your changes affect public APIs or user-facing behavior.
4. **Open a pull request** against `main` using the PR template.

## Development Setup

This repository holds GitHub configuration (workflows, community health files) —
there is no application build or test suite. The development loop is:

1. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/.github.git
   cd .github
   ```
2. Validate workflow changes with [actionlint](https://github.com/rhysd/actionlint):
   ```bash
   actionlint .github/workflows/<changed-file>.yml
   ```
3. Every `uses:` reference must be pinned to a full 40-char commit SHA; the
   `pin-check` required CI check enforces this on every pull request.

## Code Style

- Follow the existing code style and conventions in the project.
- Keep changes focused: one logical change per commit.

## Commit Messages

Use clear, descriptive commit messages:

```text
<type>: <short summary>

<optional body with more detail>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

## Pull Request Process

1. Fill out the PR template completely.
2. Link related issues using `Fixes #123` or `Closes #456`.
3. Ensure all CI checks pass.
4. Request a review from a maintainer or code owner.
5. Address review feedback promptly.
6. Once approved, a maintainer will merge your PR.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Questions?

- Open a [discussion](https://github.com/attested-delivery/.github/discussions) for general questions.
- Check the [support document](SUPPORT.md) for additional resources.

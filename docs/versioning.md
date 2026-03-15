# Versioning

This repository uses Semantic Versioning for tagged releases.

## Version Scheme

- `MAJOR`: incompatible public workflow or interface changes
- `MINOR`: backward-compatible feature additions
- `PATCH`: backward-compatible fixes, tooling updates, and maintenance changes

Current package version is defined in:

- `pyproject.toml`
- `src/forex/__init__.py`

These values should be kept in sync.

## Release Flow

1. Update `CHANGELOG.md`
2. Bump the version metadata in one step:

```bash
make bump-version VERSION=0.1.1
```

3. Confirm the changelog and version metadata are ready, then run:
4. Create and push a git tag in the format `vX.Y.Z`

Example:

```bash
git tag v0.1.1
git push origin v0.1.1
```

## CI Release Behavior

The release workflow runs on version tags matching `v*`.

It validates that:

- the git tag matches the package version in `pyproject.toml`
- the release preflight passes
- the package builds successfully

It then uploads build artifacts to the GitHub release for that tag.

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
2. Bump the version in `pyproject.toml`
3. Bump `forex.__version__` in `src/forex/__init__.py`
4. Run:

```bash
make check-core
make check-hygiene
```

5. Create and push a git tag in the format `vX.Y.Z`

Example:

```bash
git tag v0.1.1
git push origin v0.1.1
```

## CI Release Behavior

The release workflow runs on version tags matching `v*`.

It validates that:

- the git tag matches the package version in `pyproject.toml`
- the package builds successfully

It then uploads build artifacts to the GitHub release for that tag.


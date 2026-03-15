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

3. Validate release metadata and changelog coverage:

```bash
make check-release-metadata
```

4. Run the full preflight:

```bash
make release-check
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
- the changelog includes both `[Unreleased]` and a release entry for the tagged version
- the release preflight passes
- the package builds successfully
- release artifacts include a `SHA256SUMS.txt` checksum manifest

It then uploads build artifacts to the GitHub release for that tag.

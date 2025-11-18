# Building and Publishing

## Automated Publishing (Recommended)

The project is configured to automatically publish to PyPI when a new GitHub release is created.

### Prerequisites

1. Configure PyPI Trusted Publishing on https://pypi.org/manage/account/publishing/
   - Project name: `netbox-notices`
   - Owner: `jsenecal`
   - Repository name: `netbox-notices`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`

### Creating a New Release

1. Update version number in code:
   ```bash
   bumpver update --patch   # or --minor, or --major
   ```
   This will:
   - Update version in `pyproject.toml`, `README.md`, and `notices/__init__.py`
   - Create a git commit
   - Create a git tag (e.g., `v0.1.1`)
   - Push the commit and tag to GitHub

2. Create a GitHub Release:
   - Go to https://github.com/jsenecal/netbox-notices/releases/new
   - Select the tag that was just pushed (e.g., `v0.1.1`)
   - Generate release notes or write custom notes
   - Click "Publish release"

3. The GitHub Action will automatically:
   - Build the distribution packages
   - Publish to PyPI using trusted publishing (no API tokens needed!)

## Manual Publishing (Alternative)

If you need to publish manually:

```bash
# Install build tools
pip install bumpver build twine

# Update version
bumpver update --patch   # or --minor, or --major

# Build distribution
python -m build

# Test upload (optional)
twine upload -r testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

Note: Manual publishing requires PyPI API tokens configured in `~/.pypirc`

# justfile
set shell := ["bash", "-euo", "pipefail", "-c"]

help:
    @just --list

format:
    ruff check . --fix
    ruff format .

# ---------- helpers ----------

_git_clean:
  @git update-index -q --refresh
  @test -z "$(git status --porcelain=v1)" || { \
    echo "ERROR: git working tree is not clean."; \
    git status --porcelain=v1; \
    exit 1; \
  }

_current_version:
  @python -c "import tomli; f = open('pyproject.toml', 'rb'); data = tomli.load(f); print(data['project']['version'])"

_confirm_typed expected:
  #!/usr/bin/env bash
  echo "Type '{{expected}}' to continue:"
  read -r typed
  test "$typed" = "{{expected}}" || { echo "Aborted."; exit 1; }

_next_minor_dev ver:
  @python -c "from packaging.version import Version; import sys; v = Version(sys.argv[1]); print(f'{v.major}.{v.minor+1}.0.dev0')" "{{ver}}"

# ---------- public recipes ----------

# Usage: just release 0.2.0
release ver:
  just _git_clean
  @echo "Current version: $(just _current_version)"
  @echo "Requested release version: {{ver}}"
  just _confirm_typed {{ver}}

  # Set release version explicitly
  @python -c "import re; f = open('pyproject.toml', 'r'); content = f.read(); f.close(); content = re.sub(r'^version = \".*\"', 'version = \"{{ver}}\"', content, flags=re.MULTILINE); f = open('pyproject.toml', 'w'); f.write(content); f.close()"

  # Commit version bump
  git add pyproject.toml
  # git commit -m "Release {{ver}}"

  # Build + sanity-check artifacts
  rm -rf dist
  python -m build

  # Publish and tag
  python -m twine upload dist/*
  git tag -a "v{{ver}}" -m "v{{ver}}"
  git push --follow-tags

  # Bump main to next minor dev0
  @next_dev="$(just _next_minor_dev {{ver}} | tr -d '\n\r' | xargs)"; \
    if [ -z "${next_dev}" ] || ! echo "${next_dev}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then \
      echo "ERROR: Failed to calculate next dev version. Got: '${next_dev}'"; \
      exit 1; \
    fi; \
    echo "Bumping to ${next_dev}"; \
    python -c "import re; f = open('pyproject.toml', 'r'); content = f.read(); f.close(); content = re.sub(r'^version = \".*\"', 'version = \"${next_dev}\"', content, flags=re.MULTILINE); f = open('pyproject.toml', 'w'); f.write(content); f.close()"; \
    git add pyproject.toml; \
    git commit -m "Start ${next_dev} development"; \
    git push


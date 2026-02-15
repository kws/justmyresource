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
  @poetry version -s

_confirm_typed expected:
  #!/usr/bin/env bash
  echo "Type '{{expected}}' to continue:"
  read -r typed
  test "$typed" = "{{expected}}" || { echo "Aborted."; exit 1; }

_next_minor_dev ver:
  @poetry run python -c "from packaging.version import Version; import sys; v = Version(sys.argv[1]); print(f'{v.major}.{v.minor+1}.0.dev0')" "{{ver}}"

# ---------- public recipes ----------

# Usage: just release 0.2.0
release ver:
  just _git_clean
  @echo "Current Poetry version: $(poetry version -s)"
  @echo "Requested release version: {{ver}}"
  just _confirm_typed {{ver}}

  # Set release version explicitly
  poetry version {{ver}}

  # Commit version bump (adjust lockfile policy below)
  git add pyproject.toml
  # If you *do* commit lockfiles for your project, uncomment:
  # git add poetry.lock

  # git commit -m "Release {{ver}}"

  # Build + sanity-check artifacts
  rm -rf dist
  poetry build

  # Publish and tag
  poetry publish
  git tag -a "v{{ver}}" -m "v{{ver}}"
  git push --follow-tags

  # Bump main to next minor dev0
  @next_dev="$(poetry run python -c "from packaging.version import Version; import sys; v = Version(sys.argv[1]); print(f'{v.major}.{v.minor+1}.0.dev0')" "{{ver}}" 2>/dev/null | tr -d '\n\r' | xargs)"; \
    if [ -z "${next_dev}" ] || ! echo "${next_dev}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then \
      echo "ERROR: Failed to calculate next dev version. Got: '${next_dev}'"; \
      exit 1; \
    fi; \
    echo "Bumping to ${next_dev}"; \
    poetry version "${next_dev}"; \
    git add pyproject.toml; \
    git commit -m "Start ${next_dev} development"; \
    git push


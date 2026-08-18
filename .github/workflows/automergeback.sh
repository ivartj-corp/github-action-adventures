#!/usr/bin/env bash

set -euo pipefail

dry_run=
debug=

function usage {
  echo "usage: $0 [--dry-run] SOURCE_BRANCH"
}

function main {
  opts="$(getopt -n "$0" -o hx \
    --long help \
    --long dry-run \
    --long debug \
    --long no-fetch \
    -- "$@"
  )"
  eval set -- "$opts"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h)
        usage
        exit
        ;;
      --dry-run)
        dry_run=y
        shift
        ;;
      --debug|-x)
        debug=y
        shift
        ;;
      --)
        shift
        break
        ;;
    esac
  done
  if [[ $# -ne 1 ]]; then
    usage >&2
    exit 1
  fi
  source_branch="$1"

  if ! gh auth status &>/dev/null; then
    echo "$0: Please run \`gh auth login\`"
    exit 1
  fi

  if [[ -n $debug ]]; then
    set -x
  fi

  mergeback "$source_branch"
}

function mergeback {
  local source_branch target_branch source2target
  source_branch="$1"
  declare -A source2target=(
    [main]=test
    [test]=dev
  )
  target_branch="${source2target[$source_branch]:-}"

  if [[ -z $target_branch ]]; then
    echo "$0: no target branch for source branch '$source_branch' exiting" >&2
    exit
  fi

  if [[ -z $dry_run ]]; then
    # Make sure we have the full commit history of both branches (no shallow clones).
    # Not run on dry run so that we can maintain the illusion that the target branch is updated on a second call to this function.
    git fetch origin "refs/heads/${source_branch}:refs/remotes/origin/${source_branch}" --force
    git fetch origin "refs/heads/${target_branch}:refs/remotes/origin/${target_branch}" --force
  fi

  if git merge-base --is-ancestor "origin/$source_branch" "origin/$target_branch"; then
    printf "$0: Source branch '%s' is already part of the history of target branch '%s'\n" "$source_branch" "$target_branch" >&2
    exit
  fi

  git checkout -B "mergeback/$target_branch" "origin/$target_branch"
  if git merge --no-ff "origin/$source_branch" -m "Automerging $source_branch into $target_branch"; then

    # VALIDATE HERE
    # IF VALIDATION FAILS, CREATE PR WITH ERROR

    echo "$0: pushing merge to $target_branch" >&2
    if [[ -z $dry_run ]]; then
      git push origin "HEAD:$target_branch"
    else
      git update-ref "refs/remotes/origin/$target_branch" HEAD
    fi

    mergeback "$target_branch"
  else
    echo "$0: merge conflict, creating PR" >&2
    if [[ -z $dry_run ]]; then
      gh pr create \
        --title "Mergeback from '$source_branch' to '$target_branch'" \
        --body "Unable to automatically mergeback because of merge conflict." \
        --head "$source_branch" \
        --base "$target_branch" \
        --label mergeback-ci-failure
    fi
  fi
}

main "$@"

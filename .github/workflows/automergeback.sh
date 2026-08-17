#!/usr/bin/env bash

set -euo pipefail

dry_run=
debug=

function usage {
  echo "usage: $0 [--dry-run] SOURCE_BRANCH TARGET_BRANCH"
}

opts="$(getopt -n "$0" -o hx \
  --long help \
  --long dry-run \
  --long debug \
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
if [[ $# -ne 2 ]]; then
  usage >&2
  exit 1
fi
source_branch="$1"
target_branch="$2"

if ! gh auth status &>/dev/null; then
  echo "$0: Please run \`gh auth login\`"
  exit 1
fi

if [[ -n $debug ]]; then
  set -x
fi

# make sure we have the full commit history of both branches (no shallow clones)
git fetch origin "refs/heads/${source_branch}:refs/remotes/origin/${source_branch}" --force
git fetch origin "refs/heads/${target_branch}:refs/remotes/origin/${target_branch}" --force

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
  fi
else
  echo "$0: merge conflict, creating PR" >&2
  if [[ -z $dry_run ]]; then
    gh pr create \
      --title "Mergeback from '$source_branch' to '$target_branch'" \
      --head "$source_branch" \
      --base "$target_branch" \
      --label mergeback-ci-failure
  fi
fi


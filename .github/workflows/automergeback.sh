#!/usr/bin/env bash

set -euo pipefail

dry_run=
debug=
mergeback_pr_label=
validate_merge_command=true
recurse=

function usage {
  echo "Usage: $0 SOURCE_BRANCH"
  cat <<'EOF'
  [--mergeback-pr-label=PULL_REQUEST_LABEL]
  [--validate-merge-command=BASH_COMMAND]
  [--dry-run] [--debug] [--recurse]

Description:

  After hotfixes are applied to the main and test branches, this script should
  merge those hotfixes back to the upstream branches. For the main branch, the
  upstream branch is the test branch, and for the test branch it is the dev
  branch.

  If the script encounters a merge conflict or if the command specified in
  `--validate-merge-command=` fails after the merge, the script will create a
  GitHub pull request with the label specified in `--mergeback-pr-label=`.

EOF
}

function main {
  opts="$(getopt -n "$0" -o hx \
    --long help \
    --long dry-run \
    --long debug \
    --long recurse \
    --long mergeback-pr-label: \
    --long validate-merge-command: \
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
      --recurse)
        recurse=y
        shift
        ;;
      --mergeback-pr-label)
        mergeback_pr_label="$2"
        shift 2
        ;;
      --validate-merge-command)
        validate_merge_command="$2"
        shift 2
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
    echo "$0: Please run \`gh auth login\`" >&2
    exit 1
  fi

  if ! (git diff --quiet && git diff --quiet --cached); then
    echo "$0: clean changes before running this command" >&2
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

  # Make sure we have the full commit history of both branches (no shallow clones).
  git_fetch_args=(
    origin
    "refs/heads/${source_branch}:refs/remotes/origin/${source_branch}"
    "refs/heads/${target_branch}:refs/remotes/origin/${target_branch}"
    --force
    --quiet
  )
  if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
    git_fetch_args+=(--unshallow)
  fi
  if [[ -z $dry_run ]]; then
    # Not run on dry run so that we can maintain the illusion that the target branch is updated on a second call to this function.
    git fetch "${git_fetch_args[@]}"
  fi

  if git merge-base --is-ancestor "origin/$source_branch" "origin/$target_branch"; then
    printf "$0: Source branch '%s' is already part of the history of target branch '%s'\n" "$source_branch" "$target_branch" >&2
    exit
  fi

  local mergeback_branch
  mergeback_branch="mergeback/${target_branch}-$(git rev-list -n1 --abbrev-commit --abbrev=8 "origin/${source_branch}")"
  git checkout -B "$mergeback_branch" "origin/$target_branch" --no-track --quiet
  if git merge --no-ff "origin/$source_branch" -m "Automerging $source_branch into $target_branch" >/dev/null; then
    echo "$0: Successfully merged code without merge conflict" >&2

    if (eval "$validate_merge_command"); then
      echo "$0: Merged code passed validation; pushing merge to $target_branch" >&2
      if [[ -z $dry_run ]]; then
        git push origin "HEAD:$target_branch" --quiet
      else
        git update-ref "refs/remotes/origin/$target_branch" HEAD
      fi

      if [[ -n $recurse ]]; then
        # If we use GITHUB_TOKEN, there is a safeguard against workflows
        # triggering other workflows, so we we need to recurse within the
        # workflow.
        mergeback "$target_branch"
      fi
    else
      echo "$0: Merged code failed validation; pushing branch and creating PR." >&2

      echo "$0: Pushing branch for PR..." >&2
      if [[ -z $dry_run ]]; then
        git push origin "$mergeback_branch" --force --quiet
      fi

      local gh_pr_create_args
      gh_pr_create_args=(
        --title "Mergeback from '$source_branch' to '$target_branch'"
        --body "Merged code failed validation, so automatic merge was aborted."
        --head "$mergeback_branch"
        --base "$target_branch"
      )
      if [[ -n $mergeback_pr_label ]]; then
        gh_pr_create_args+=(--label "$mergeback_pr_label")
      fi
      echo "$0: Creating PR..." >&2
      if [[ -z $dry_run ]]; then
        gh pr create "${gh_pr_create_args[@]}"
      fi
    fi
  else
    echo "$0: Merge conflict; pushing branch based on $source_branch and creating PR" >&2

    git merge --abort
    git reset --hard "origin/${source_branch}" --quiet
    echo "$0: Pushing branch for PR..." >&2
    if [[ -z $dry_run ]]; then
      git push origin "$mergeback_branch" --force --quiet
    fi

    local gh_pr_create_args
    gh_pr_create_args=(
      --title "Mergeback from '$source_branch' to '$target_branch'"
      --body "Unable to automatically mergeback because of merge conflict."
      --head "$mergeback_branch"
      --base "$target_branch"
    )
    if [[ -n $mergeback_pr_label ]]; then
      gh_pr_create_args+=(--label "$mergeback_pr_label")
    fi
    echo "$0: Creating PR..." >&2
    if [[ -z $dry_run ]]; then
      gh pr create "${gh_pr_create_args[@]}"
    fi
  fi
}

main "$@"

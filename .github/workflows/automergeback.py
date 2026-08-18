#!/usr/bin/env python3
"""\
After hotfixes are applied to the main and test branches, this script should
merge those hotfixes back to the upstream branches. For the main branch, the
upstream branch is the test branch, and for the test branch it is the dev
branch.

If the script encounters a merge conflict or if the command specified in
`--validate-merge-command=` fails after the merge, the script will create a
GitHub pull request with the label specified in `--mergeback-pr-label=`.

`--dry-run` and `--debug` are intended for local testing.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import typing


logger = logging.getLogger(os.path.basename(__file__))

SOURCE_TO_TARGET_BRANCH = {
    "main": "test",
    "test": "dev",
}


def run(*args: str, check: bool = True, quiet_stdout: bool = False) -> subprocess.CompletedProcess[bytes]:
    """Run a command, logging it first, and (by default) raising on failure."""
    logger.debug("+ %s", " ".join(args))
    return subprocess.run(
        args,
        check=check,
        stdout=subprocess.DEVNULL if quiet_stdout else None,
    )


def main() -> int:
    argument_parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = argument_parser.add_argument("source_branch", help="Branch which has received updates that we wish to merge back to the target branch.")
    _ = argument_parser.add_argument("--validate-merge-command", default="true", help="Shell command to run after a successful merge to validate the merged code.")
    _ = argument_parser.add_argument("--mergeback-pr-label", help="GitHub label to attach to pull requests that will be created if the code cannot be safely merged.")
    _ = argument_parser.add_argument("--dry-run", action="store_true", default=False, help="Do not fetch, push or create pull requests.")
    _ = argument_parser.add_argument("--debug", action="store_true", default=False, help="Print every command before running it.")

    args = argument_parser.parse_args(sys.argv[1:])

    source_branch = typing.cast(str, args.source_branch)
    validate_merge_command = typing.cast(str, args.validate_merge_command)
    mergeback_pr_label = typing.cast(str | None, args.mergeback_pr_label)
    dry_run = typing.cast(bool, args.dry_run)
    debug = typing.cast(bool, args.debug)

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, format="%(name)s: %(message)s")

    if shutil.which("git") is None:
        logger.critical("git not in PATH")
        return 1
    if shutil.which("gh") is None:
        logger.critical("gh (GitHub CLI) not in PATH")
        return 1

    target_branch = SOURCE_TO_TARGET_BRANCH.get(source_branch)
    if target_branch is None:
        logger.critical("no target branch for source branch %r, exiting", source_branch)
        return 1

    if subprocess.run(["gh", "auth", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        logger.critical("Please run `gh auth login`")
        return 1

    if subprocess.run(["git", "diff", "--quiet"]).returncode != 0 or subprocess.run(["git", "diff", "--quiet", "--cached"]).returncode != 0:
        logger.critical("clean changes before running this command")
        return 1

    return mergeback(source_branch, target_branch, validate_merge_command, mergeback_pr_label, dry_run)


def mergeback(source_branch: str, target_branch: str, validate_merge_command: str, mergeback_pr_label: str | None, dry_run: bool) -> int:
    logger.info("Making sure we have the full commit history of both branches (no shallow clones).")
    is_shallow_repository = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"], check=True, capture_output=True, text=True,
    ).stdout.strip() == "true"

    if not dry_run:
        # Not run on dry run so that we can maintain the illusion that the target branch is updated on a second call.
        git_fetch_args = [
            "git", "fetch", "origin",
            f"refs/heads/{source_branch}:refs/remotes/origin/{source_branch}",
            f"refs/heads/{target_branch}:refs/remotes/origin/{target_branch}",
            "--force", "--quiet",
        ]
        if is_shallow_repository:
            git_fetch_args.append("--unshallow")
        _ = run(*git_fetch_args)

    if subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{source_branch}", f"origin/{target_branch}"]).returncode == 0:
        logger.info("Source branch %r is already part of the history of target branch %r", source_branch, target_branch)
        return 0

    source_commit = subprocess.run(
        ["git", "rev-list", "-n1", "--abbrev-commit", "--abbrev=8", f"origin/{source_branch}"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    mergeback_branch = f"mergeback/{target_branch}-{source_commit}"

    logger.info("Creating initial mergeback %s branch based on target branch %s", mergeback_branch, target_branch)
    _ = run("git", "checkout", "-B", mergeback_branch, f"origin/{target_branch}", "--no-track", "--quiet")

    logger.info("Attempting to merge source branch %s", source_branch)
    merge_result = subprocess.run(
        ["git", "merge", "--no-ff", f"origin/{source_branch}", "-m", f"Automerging {source_branch} into {target_branch}"],
        stdout=subprocess.DEVNULL,
    )

    if merge_result.returncode == 0:
        logger.info("Successfully merged code without merge conflict")

        validation_result = subprocess.run(validate_merge_command, shell=True)
        if validation_result.returncode == 0:
            logger.info("Merged code passed validation; pushing merge to %s", target_branch)
            if not dry_run:
                _ = run("git", "push", "origin", f"HEAD:{target_branch}", "--quiet")
            else:
                _ = run("git", "update-ref", f"refs/remotes/origin/{target_branch}", "HEAD")
            return 0

        logger.info("Merged code failed validation; pushing branch and creating PR.")
        return push_branch_and_create_pr(source_branch, target_branch, mergeback_branch, mergeback_pr_label, dry_run,
                                          body="Merged code failed validation, so automatic merge was aborted.")

    logger.info("Encountered merge conflict.")
    logger.info("Resetting %s to source branch %s.", mergeback_branch, source_branch)
    _ = run("git", "merge", "--abort")
    _ = run("git", "reset", "--hard", f"origin/{source_branch}", "--quiet")

    return push_branch_and_create_pr(source_branch, target_branch, mergeback_branch, mergeback_pr_label, dry_run,
                                      body="Unable to automatically mergeback because of merge conflict.")


def push_branch_and_create_pr(source_branch: str, target_branch: str, mergeback_branch: str, mergeback_pr_label: str | None, dry_run: bool, body: str) -> int:
    logger.info("Pushing %s.", mergeback_branch)
    if not dry_run:
        _ = run("git", "push", "origin", mergeback_branch, "--force", "--quiet")

    logger.info("Creating pull request.")
    gh_pr_create_args = [
        "gh", "pr", "create",
        "--title", f"Mergeback from '{source_branch}' to '{target_branch}'",
        "--body", body,
        "--head", mergeback_branch,
        "--base", target_branch,
    ]
    if mergeback_pr_label:
        gh_pr_create_args += ["--label", mergeback_pr_label]
    if not dry_run:
        _ = run(*gh_pr_create_args)

    return 0


if __name__ == "__main__":
    sys.exit(main())

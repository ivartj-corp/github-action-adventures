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
import shlex
import subprocess
import sys
import typing


logger = logging.getLogger(os.path.basename(__file__))

SOURCE_TO_TARGET_BRANCH = {
    "main": "test",
    "test": "dev",
}


def run(
    base_command: str, *extra_args: str, check: bool = True, stdout: int | None = None, stderr: int | None = None, capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command, logging it first, and (by default) raising on failure."""
    args = [*shlex.split(base_command), *extra_args]
    logger.debug("+ %s", " ".join(args))
    return subprocess.run(
        args,
        check=check,
        stdout=stdout,
        stderr=stderr,
        text=True,
        capture_output=capture_output,
    )


def main() -> int:
    argument_parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = argument_parser.add_argument(
        "source_branch",
        help="Branch which has received updates that we wish to merge back to the target branch.",
    )
    _ = argument_parser.add_argument(
        "--mergeback-pr-label",
        help="GitHub label to attach to pull requests that will be created if the code cannot be safely merged.",
    )
    _ = argument_parser.add_argument(
        "--dry-run",
        help="Do not fetch, push or create pull requests.",
        action="store_true",
        default=False,
    )
    _ = argument_parser.add_argument(
        "--debug",
        help="Print every command before running it.",
        action="store_true",
        default=False,
    )

    args = argument_parser.parse_args(sys.argv[1:])

    source_branch = typing.cast(str, args.source_branch)
    mergeback_pr_label = typing.cast(str | None, args.mergeback_pr_label)
    dry_run = typing.cast(bool, args.dry_run)
    debug = typing.cast(bool, args.debug)

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(name)s: %(message)s",
    )

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

    if (
        run(
            "gh auth status",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    ):
        logger.critical("Please run `gh auth login`")
        return 1

    if (
        run("git diff --quiet").returncode != 0
        or run("git diff --quiet --cached").returncode != 0
    ):
        logger.critical("clean changes before running this command")
        return 1

    return mergeback(
        source_branch,
        target_branch,
        mergeback_pr_label,
        dry_run,
    )


def mergeback(
    source_branch: str,
    target_branch: str,
    mergeback_pr_label: str | None,
    dry_run: bool,
) -> int:
    logger.info(
        "Making sure we have the full commit history of both branches (no shallow clones)."
    )
    is_shallow_repository = (
        run(
            "git rev-parse --is-shallow-repository",
            check=True,
            capture_output=True,
        ).stdout.strip()
        == "true"
    )

    if not dry_run:
        # Not run on dry run so that we can maintain the illusion that the target branch is updated on a second call.
        git_fetch_args = [
            *shlex.split("git fetch --force --quiet origin"),
            f"refs/heads/{source_branch}:refs/remotes/origin/{source_branch}",
            f"refs/heads/{target_branch}:refs/remotes/origin/{target_branch}",
        ]
        if is_shallow_repository:
            git_fetch_args.append("--unshallow")
        _ = run(*git_fetch_args, check=True)

    if (
        run(
            "git merge-base --is-ancestor",
            f"origin/{source_branch}",
            f"origin/{target_branch}",
        ).returncode
        == 0
    ):
        logger.info(
            "Source branch %r is already part of the history of target branch %r",
            source_branch,
            target_branch,
        )
        return 0

    source_commit = run(
        "git rev-list -n1 --abbrev-commit --abbrev=8",
        f"origin/{source_branch}",
        check=True,
        capture_output=True,
    ).stdout.strip()
    mergeback_branch = f"mergeback/{target_branch}-{source_commit}"

    logger.info(
        "Creating initial mergeback %s branch based on target branch %s",
        mergeback_branch,
        target_branch,
    )
    _ = run(
        "git checkout --no-track --quiet",
        f"-B{mergeback_branch}",
        f"origin/{target_branch}",
        check=True,
    )

    logger.info("Attempting to merge source branch %s", source_branch)
    merge_result = run(
        "git merge --no-ff",
        f"origin/{source_branch}",
        f"-mAutomerging {source_branch} into {target_branch}",
        stdout=subprocess.DEVNULL,
    )

    if merge_result.returncode == 0:
        logger.info("Successfully merged code without merge conflict")

        return push_branch_and_create_pr(
            source_branch,
            target_branch,
            mergeback_branch,
            mergeback_pr_label,
            dry_run,
            body=f"Mergeback of hotfixes from {source_branch} to {target_branch}. No merge conflicts.",
        )

    logger.info("Encountered merge conflict.")
    logger.info("Resetting %s to source branch %s.", mergeback_branch, source_branch)
    _ = run("git merge --abort", check=True)
    _ = run("git reset --hard --quiet", f"origin/{source_branch}", check=True)

    return push_branch_and_create_pr(
        source_branch,
        target_branch,
        mergeback_branch,
        mergeback_pr_label,
        dry_run,
        body=f"Mergeback of hotfixes from {source_branch} to {target_branch}. This PR contains merge conflicts.",
    )


def push_branch_and_create_pr(
    source_branch: str,
    target_branch: str,
    mergeback_branch: str,
    mergeback_pr_label: str | None,
    dry_run: bool,
    body: str,
) -> int:
    logger.info("Pushing %s.", mergeback_branch)
    if not dry_run:
        _ = run(*shlex.split("git push origin --force --quiet"), mergeback_branch, check=True)

    logger.info("Creating pull request.")
    gh_pr_create_args = [
        *shlex.split("gh pr create"),
        f"--title=Mergeback from '{source_branch}' to '{target_branch}'",
        f"--body={body}",
        f"--head={mergeback_branch}",
        f"--base={target_branch}",
    ]
    if mergeback_pr_label:
        gh_pr_create_args.append(f"--label={mergeback_pr_label}")
    if not dry_run:
        completed_process = run(*gh_pr_create_args, check=True)
        pr_url = completed_process.stdout.strip()
        _ = run("gh pr merge --merge --auto --delete-branch", pr_url, check=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""\
After hotfixes are applied to the main and test branches, this script should
merge those hotfixes back to the upstream branches. For the main branch, the
upstream branch is the test branch, and for the test branch it is the dev
branch.

If the script encounters a merge conflict or if the command specified in
`--validate-merge-command=` fails after the merge, the script will create a
GitHub pull request with the label specified in `--mergeback-pr-label=`.

`--dry-run` is intended for local testing.
"""


import argparse
import os
import sys
import typing
import asyncio
import logging
import subprocess
import shutil


logger = logging.getLogger(os.path.basename(__file__))


async def main() -> int:
    logging.basicConfig(level=logging.INFO)
    argument_parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = argument_parser.add_argument("--validate-merge-command", help="Shell command to run after a successfull merge to validate that the merged code.")
    _ = argument_parser.add_argument("--mergeback-pr-label", help="GitHub label to attach to pull requests that will be created if the code cannot be safely merged.")
    _ = argument_parser.add_argument("--dry-run", action='store_true', default=False, help="Do not fetch, push or create pull requests.")
    _ = argument_parser.add_argument("source_branch", help="Branch which has received updates that we wish to merge back to the target branch.")
    _ = argument_parser.add_argument("target_branch", help="Branch to which we wish to merge changes.")
    
    args = argument_parser.parse_args(sys.argv[1:])

    validate_merge_command = typing.cast(str | None, args.validate_merge_command)
    mergeback_pr_label = typing.cast(str | None, args.mergeback_pr_label)
    dry_run = typing.cast(bool, args.dry_run)
    source_branch = typing.cast(str, args.source_branch)
    target_branch = typing.cast(str, args.target_branch)

    git_path = shutil.which("git")
    if git_path is None:
        logger.critical("git not in PATH")
        return 1

    gh_path = shutil.which("gh")
    if gh_path is None:
        logger.critical("gh (GitHub CLI) not in PATH")
        return 1

    gh_auth_status_process = await asyncio.subprocess.create_subprocess_exec(gh_path, "auth", "status", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git_diff_process = await asyncio.subprocess.create_subprocess_exec(git_path, "diff", "--quiet", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git_diff_cached_process = await asyncio.subprocess.create_subprocess_exec(git_path, "diff", "--quiet", "--cached", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git_is_shallow_repository_process = await asyncio.subprocess.create_subprocess_exec(git_path, "rev-parse", "--is-shallow-repository", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    _ = await asyncio.gather(
        gh_auth_status_process.communicate(),
        git_diff_process.communicate(),
        git_diff_cached_process.communicate(),
        git_is_shallow_repository_process.communicate(),
    )

    if not dry_run:
        if gh_auth_status_process.returncode != 0:
            logger.critical("Please run `gh auth login`")
            return 1

    if git_diff_process.returncode != 0 or git_diff_cached_process.returncode != 0:
        logger.critical("clean changes before running this command")
        return 1

    is_shallow_repository = (
        await git_is_shallow_repository_process.stdout.read()
        if git_is_shallow_repository_process.stdout is not None
        else b""
    ).decode().strip() == "true"

    git_fetch_process = await asyncio.subprocess.create_subprocess_exec(
        git_path, "fetch", "origin",
        f"refs/heads/{source_branch}:refs/remotes/origin{source_branch}",
        f"refs/heads/{target_branch}:refs/remotes/origin{target_branch}",
        "--force",
        *(["--unshallow"] if is_shallow_repository else []),
        stderr=subprocess.PIPE
    )
    _ = await git_fetch_process.communicate()
    if git_fetch_process.returncode != 0:
        stderr = (
            await git_fetch_process.stderr.read()
            if git_fetch_process.stderr is not None
            else b""
        ).decode().strip()
        logger.critical(f"`git fetch` failed: {stderr}")
        return 1

    git_merge_base_process = await asyncio.subprocess.create_subprocess_exec(
        git_path, "merge-base", "--is-ancestor", f"origin/{source_branch}", f"origin/{target_branch}",
    )
    _ = await git_merge_base_process.communicate()
    if git_merge_base_process.returncode == 0:
        logger.info(f"source branch {source_branch} is already part of the history of target branch {target_branch}")
        return 0

    logger.info("")
        
    return 0
            
if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
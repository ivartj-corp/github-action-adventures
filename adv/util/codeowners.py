from typing import Generator
import re
import glob
from functools import lru_cache


class CodeOwners:
    _assignments: list[tuple[str, set[str]]]

    def __init__(self, s: str) -> None:
        self._assignments = list(parse_codeowners(s))
        self._regex = {}

    @lru_cache()
    @staticmethod
    def _glob2regex(path_pattern: str) -> re.Pattern:
        root_anchored = False
        directory = False
        while path_pattern.startswith("/"):
            path_pattern = path_pattern.removeprefix("/")
            root_anchored = True
        if path_pattern.endswith("/"):
            directory = True
        s = glob.translate(path_pattern, recursive=True, include_hidden=True)
        if root_anchored:
            s = f"^{s}"
        if directory:
            s = s.replace(r"\z", "")
        return re.compile(s)

    def assignees(self, path: str) -> set[str]:
        for path_pattern, assignees in reversed(self._assignments):
            regex_pattern = CodeOwners._glob2regex(path_pattern)
            if regex_pattern.search(path) is not None:
                return assignees
        return set()


def parse_codeowners(s: str) -> Generator[tuple[str, set[str]]]:
    comment_pattern = re.compile(r"(^|\s*)#.*$")
    path_pattern = re.compile(r"([^\s\\]|\\ )+")
    for line in s.splitlines():
        line = comment_pattern.sub("", line)
        line.strip()
        if line == "":
            continue
        match = path_pattern.search(line)
        if match is not None:
            path = match.group(0).replace(r"\ ", " ")
            assignees_str = line[match.end() :].strip()
            if assignees_str == "":
                assignees = []
            else:
                assignees = assignees_str.split(" ")
            yield ((path, set(assignees)))

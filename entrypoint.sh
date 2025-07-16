#!/bin/sh -l
echo "Hello $1"
echo "time=$(date)" >> "$GITHUB_OUTPUT"
find /github/workspace -type f -print0 | xargs -0 rm

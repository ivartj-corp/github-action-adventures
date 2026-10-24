// parse-issue.mjs
//
// A simple command-line tool that reads a GitHub issue body and the issue
// form template it was created from, and prints the parsed result as JSON.
//
// Usage:
//   node parse-issue.mjs ISSUE-BODY-FILE ISSUE-FORM-TEMPLATE-FILE

import { readFileSync } from 'fs'
import { parseIssue } from '@github/issue-parser'

// process.argv looks like: [node, parse-issue.mjs, ISSUE-BODY-FILE, ISSUE-FORM-TEMPLATE-FILE]
const issueBodyFile = process.argv[2]
const issueFormTemplateFile = process.argv[3]

if (!issueBodyFile || !issueFormTemplateFile) {
  console.error('usage: node parse-issue.mjs ISSUE-BODY-FILE ISSUE-FORM-TEMPLATE-FILE')
  process.exit(1)
}

// Read both files as plain text.
const issueBody = readFileSync(issueBodyFile, 'utf8')
const issueFormTemplate = readFileSync(issueFormTemplateFile, 'utf8')

// Parse the issue body using the template, then print the result.
const parsedIssue = parseIssue(issueBody, issueFormTemplate)

console.log(JSON.stringify(parsedIssue, null, 2))

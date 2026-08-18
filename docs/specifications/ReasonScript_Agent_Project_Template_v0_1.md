# ReasonScript Agent Project Template v0.1

Specification ID: `reasonscript-agent-project-template/0.1`

Status: ACCEPTED

Target: ReasonScript v0.5.4.9

## Purpose

`reason init <project_name> --template agent` creates a standalone ReasonScript
project with tool-neutral instructions and a draft project specification that
Coding Agents can discover before changing code.

## Compatibility

- `reason init <project_name>` continues to select the `minimal` template.
- `reason init <project_name> --template minimal` is unchanged.
- Any template name other than `minimal` or `agent` is rejected with
  `UnsupportedTemplate`.

## Generated Agent Files

The `agent` template adds these files to the existing minimal project layout:

- `AGENTS.md`
- `SPECIFICATIONS/Project_Specification.md`

`AGENTS.md` is the tool-neutral Coding Agent authority. It defines the workflow,
required validation commands, artifact policy, Golden policy, compatibility
expectations, and completion-report requirements.

`Project_Specification.md` starts in `DRAFT` state. It contains explicit
sections for purpose, requirements, non-goals, compatibility, acceptance
criteria, validation, and remaining decisions. Placeholders must not be treated
as accepted requirements. A Coding Agent may proceed only for a scope explicitly
approved by the user or recorded in an accepted specification.

The initial project does not contain `agent_report.json`, because no development
task has yet been implemented or validated.

## Acceptance

- The default and explicit minimal templates remain byte-compatible.
- The agent template creates the complete minimal layout and both Agent files.
- The generated project name and normalized package identifier appear in the
  draft specification.
- A generated agent project passes `reason check`, `reason run`,
  `reason artifacts`, and `reason project-validate --json`.
- Unsupported templates remain rejected without creating a project directory.

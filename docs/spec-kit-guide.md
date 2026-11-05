# Use Spec Kit in Shugal Mela

## Installation scope

Spec Kit 1.3.0 is installed only for this project in `.venv-spec-kit/`.
The release source is pinned to commit `34a0d388eac671d656eb05b125ad3ed6056168ed`.
Its runtime dependencies are locked in `.tools/spec-kit/requirements.lock`.
The installation uses Python 3.12. Global CLI paths, user-level agent configuration,
and other projects were not changed. uv may use its ordinary shared download cache.

The Codex integration installs skills under `.agents/skills/speckit-*/SKILL.md`.
Runtime event handlers are disabled for this setup.
The official templates and Bash helpers are under `.specify/`.

From the project directory, run:

```bash
./scripts/specify version
./scripts/specify integration list
```

To recreate the executable environment, run:

```bash
./scripts/setup-spec-kit
```

This command installs dependencies into `.venv-spec-kit/`. It does not regenerate
the project files. Keep `.tools/`, `.agents/skills/`, `.specify/`, `docs/`, and `specs/`
in source control when you initialize a repository. Ignore the environment and local feature pointer.

## Find the project documents

- [Project guide](project-guide.md): product scope, architecture, proposed rules, and phases.
- [Constitution](../.specify/memory/constitution.md): constraints that every feature plan checks.
- [First feature specification](../specs/001-online-rooms-chat/spec.md): player-visible rooms and chat behavior.
- [First feature plan](../specs/001-online-rooms-chat/plan.md): backend and frontend design.
- [Protocol](../specs/001-online-rooms-chat/contracts/protocol.md): HTTP, WebSocket, and error contracts.
- [First feature tasks](../specs/001-online-rooms-chat/tasks.md): implementation checklist.
- [First feature quickstart](../specs/001-online-rooms-chat/quickstart.md): planned local and remote verification.

Feature 001 has planning artifacts only. All of its application tasks remain unchecked.

## Invoke the Codex skills

Open this project in Codex. If the newly installed skills are missing from the picker,
start a new Codex session in the same project so it discovers `.agents/skills/`.
The CLI installation and helpers work independently of skill discovery in this running chat.

These are agent chat commands, not terminal commands:

```text
$speckit-constitution
$speckit-specify
$speckit-clarify
$speckit-plan
$speckit-tasks
$speckit-analyze
$speckit-implement
$speckit-converge
```

Codex uses a dollar prefix and hyphenated skill names. Other integrations may expose
the same workflow with different syntax. The constitution and first feature artifacts already
exist, so begin by reading them rather than creating another copy of feature 001.

For the current feature, a useful next prompt is:

```text
$speckit-analyze Check specs/001-online-rooms-chat against the constitution.
Check requirement coverage, protocol consistency, and task dependencies.
The application is not implemented yet.
```

When ready to build, use:

```text
$speckit-implement Implement only the setup and shared foundation sections of
specs/001-online-rooms-chat/tasks.md. Explain the HTTP and WebSocket behavior
and verify those tasks before marking them complete.
```

The scope limit in that prompt is deliberate. Omit it only when you want the whole feature implemented.

## Select a feature without Git

This folder was not a Git repository at setup time. Spec Kit can use a feature name
and its local `.specify/feature.json` pointer without Git. No repository or commit was created.

For an explicit prerequisite check from the project root, run:

```bash
SPECIFY_FEATURE=001-online-rooms-chat \
  .specify/scripts/bash/check-prerequisites.sh \
  --json --require-spec --require-tasks --include-tasks
```

This validates artifact presence and selection. It does not validate requirements
or prove that the application works.
If you later initialize Git, use a feature branch with the matching directory name,
or continue to set `SPECIFY_FEATURE` explicitly while selecting a feature.

## Specify the next feature

After feature 001 passes its remote check, ask the agent to create the Ludo rules feature:

```text
$speckit-specify Create the next feature for a deterministic Ludo rules engine.
Use phase 4 and the proposed rule defaults in docs/project-guide.md.
Include complete-match behavior, illegal actions, and focused rule verification.
Keep networking and the browser outside this feature.
```

Then clarify material ambiguities, plan the design, generate tasks, and analyze consistency:

```text
$speckit-clarify
$speckit-plan Use a pure Python rules module, immutable transition results,
server-supplied dice outcomes, and pytest. Keep transport and storage separate.
$speckit-tasks
$speckit-analyze
```

Review the resulting files before starting implementation. Repeat this sequence for
online gameplay, reconnection, persistence, voice, and the second game.
The CLI initializes the toolkit. The agent skills create and work through feature artifacts.

## Reproduce or upgrade the toolkit

The original initialization command, for reference, was:

```bash
./scripts/specify init --here --force --non-interactive \
  --integration codex --integration-options='--skills --events false' --script sh
```

The `--force` option permits template overwrites. Re-running initialization is not
part of normal development. Back up or commit project documents before an intentional refresh.

For an intentional CLI upgrade, edit `.tools/spec-kit/requirements.in` to the reviewed
release commit, regenerate the lockfile, and reinstall:

```bash
uv pip compile .tools/spec-kit/requirements.in \
  --output-file .tools/spec-kit/requirements.lock \
  --python .venv-spec-kit/bin/python --no-header --quiet
./scripts/setup-spec-kit
```

Updating the CLI does not automatically update installed skills or templates.
Follow the upstream upgrade guide and review any changes to `.agents/` and `.specify/` separately.

## Official references

- [Spec Kit 1.3.0 release](https://github.com/github/spec-kit/releases/tag/v1.3.0)
- [Installation guide](https://github.github.io/spec-kit/installation.html)
- [Codex integration and skill invocation](https://github.github.io/spec-kit/integrations/codex.html)
- [Upgrade guide](https://github.github.io/spec-kit/upgrade.html)

# Task Management

This project uses two layers of task management.

## GitHub

GitHub is the public collaboration surface:

- public issues,
- pull requests,
- release planning,
- contributor discussion,
- bug reports and feature requests.

Public roadmap parent issue:

- <https://github.com/BigSwanNZ/video-to-artifact-agent/issues/9>

## Paperclip

Paperclip is the internal agent control plane:

- company goal,
- project workspace,
- agent assignment,
- task hierarchy,
- execution comments,
- cost and run tracking.

Initial Paperclip mapping:

| Paperclip | GitHub |
| --- | --- |
| COD-1 Launch OSS MVP | GitHub #9 |
| COD-2 Define evidence and build-spec schemas | GitHub #1 |
| COD-3 Implement mac-mlx MiniCPM-V 4.6 runtime adapter | GitHub #2 |
| COD-4 Build agent-neutral CLI contract | GitHub #3 |
| COD-5 Add subtitle and ASR ingestion with coverage gates | GitHub #4 |
| COD-6 Create Excel builder demo with formula and visual verification | GitHub #5 |
| COD-7 Design mobile and non-Mac MiniCPM-V runtime matrix | GitHub #6 |
| COD-8 Build benchmark suite for video-to-artifact quality | GitHub #7 |
| COD-9 Add MCP and HTTP adapters for non-Codex agents | GitHub #8 |

Paperclip and GitHub do not conflict. Paperclip manages agent execution and
private coordination; GitHub manages public code collaboration.


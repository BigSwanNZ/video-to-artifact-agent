# Acknowledgements

This project stands on several open model, runtime, and agent projects. The
repository does not vendor these components unless explicitly stated; users must
follow each upstream project's license and model terms.

## Agent Interfaces

- [MoonshotAI/kimi-code](https://github.com/MoonshotAI/kimi-code): Kimi Code CLI
  is acknowledged as an agent-surface reference for terminal agents, video input,
  MCP configuration, and ACP-style editor integration. `video-to-artifact-agent`
  does not depend on Kimi Code, but its contracts are designed so Kimi Code or a
  similar host can call the same workflow.

## Apple Silicon Runtime

- [Apple MLX](https://github.com/ml-explore/mlx): MLX provides the Apple Silicon
  array framework used by the local Mac runtime path.
- [Blaizzy/mlx-vlm](https://github.com/Blaizzy/mlx-vlm): `mlx-vlm` provides the
  local VLM command surface used by `mac-mlx`, including `python -m
  mlx_vlm.generate --video` on the validated route.
- oMLX: the maintainer-machine route used the installed oMLX application bundle
  as a practical distribution of a compatible Python and MLX/VLM runtime. oMLX
  is treated as an external runtime provider, not as code owned by this project.

## MiniCPM-V 4.6

- [openbmb/MiniCPM-V-4.6](https://huggingface.co/openbmb/MiniCPM-V-4.6): the
  upstream MiniCPM-V 4.6 model family used as the model reference.
- [mlx-community/MiniCPM-V-4.6-4bit](https://huggingface.co/mlx-community/MiniCPM-V-4.6-4bit):
  the MLX 4-bit conversion used by the local Mac smoke route.

## Project Scope

Acknowledgement does not imply endorsement by the upstream projects. This
project's value is the agent-neutral evidence contract, runtime adapter layer,
artifact builders, and verification workflow around these components.

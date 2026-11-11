# Global CLAUDE.md

## Workflow

- Default to a full cutover to the new behavior when making behavior changes. Do not introduce versioned behavior branches, legacy compatibility paths, dual-mode operation, or replay-preservation gates unless I explicitly request them. If a cutover requires migration, draining or restarting active workflows, or another operational step, identify that requirement directly rather than adding compatibility behavior implicitly.
- Before wrapping up any implementation task, always run lint check and tests from the root workspace directory of the project. Do not skip this step.
- You are operating in an environment where ast-grep is installed. For any code search that requires understanding of syntax or code structure, you should default to using ast-grep --lang [language] -p '<pattern>'. Adjust the --lang flag as needed for the specific programming language. Avoid using text-only search tools unless a plain-text search is explicitly requested.
- if you need to explore codebase for any reason, try to use Chunkhound first

## Subagent models

Subagents default to Sonnet (`CLAUDE_CODE_SUBAGENT_MODEL=sonnet`). When spawning one with the Agent tool, choose the model by task:

- `model: "haiku"`: narrow, well-specified, read-only work whose answer is easy to check: file/symbol lookups, grep-style sweeps, fetching and summarizing a web page or doc, listing or counting things, extracting fields from logs or JSON, and simple mechanical edits where the exact change is already spelled out.
- Default (Sonnet), no override: implementation, debugging, test writing, plan or code review, multi-step investigations, anything that needs judgment about this codebase.
- `model: "opus"`: only for hard design or root-cause work where a Sonnet pass already fell short, or when the user asks.

When unsure between Haiku and Sonnet, pick Sonnet.


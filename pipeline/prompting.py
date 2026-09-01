from __future__ import annotations

from config.config import MAX_DRIVER_CHARS, PROMPT_CONTEXT_RADIUS
from .utils import read_full_text, read_text_snippet, resolve_existing_path, trim_text

PYTHON_CODE_MODES = {"python_code", "python_codegen_v1"}
SEED_BASE64_MODES = {"seed_base64", "base64_json_v1"}


CALLCHAIN_PROMPT_TEMPLATE = """You are helping generate one fuzzing seed.

{response_instructions}

Task metadata:
- language: {language}
- project: {project}
- target symbol: {target_symbol}
- target line: {target_line_spec}

Call chain:
{call_chain_block}

Target source snippet:
{source_snippet}

Execution harness ({harness_label}):
{harness_snippet}

Goal:
- Generate one binary seed that is plausible for this fuzz target.
- The seed does not need to be perfect.
- Prefer a compact input that is syntactically valid for the target format.
"""

SINGLEFILE_PROMPT_TEMPLATE = """You are helping generate one fuzzing seed.

{response_instructions}

Task metadata:
- language: {language}
- project: {project}
- target symbol: {target_symbol}
- target line: {target_line_spec}

Relevant file context:
{file_context}

Execution harness ({harness_label}):
{harness_snippet}

Goal:
- Generate one binary seed that is plausible for this fuzz target.
- The seed should be compatible with the execution harness.
- Use the target file context to infer the expected input structure.
"""

AGENTCONTEXT_PROMPT_TEMPLATE = """You are helping generate one fuzzing seed.

{response_instructions}

Task metadata:
- language: {language}
- project: {project}
- target symbol: {target_symbol}
- target line: {target_line_spec}

Repository context prepared for the target:
{agent_context}

Execution harness ({harness_label}):
{harness_snippet}

Goal:
- Generate one binary seed that is plausible for this fuzz target.
- Use the repository context to infer the right structure and trigger path.
"""


def _resolve_source_snippet(target: dict, radius: int) -> str:
    source_snippet = target.get("target_source_snippet")
    if source_snippet:
        return source_snippet
    source_path, checked = resolve_existing_path(target.get("target_source_path"))
    if source_path is None:
        raise FileNotFoundError(
            f"Unable to resolve target source for {target['id']}. Checked: {checked}"
        )
    return read_text_snippet(source_path, int(target["target_line"]), radius)


def _resolve_harness(target: dict) -> tuple[str, str]:
    harness_label = target.get("harness_label")
    if not harness_label:
        harness_label = "test file snippet" if target["language"] == "python" else "fuzz driver snippet"

    harness_text = target.get("harness_snippet")
    if harness_text:
        return harness_label, harness_text

    inline_text = target.get("test_script_snippet") or target.get("driver_snippet")
    if inline_text:
        return harness_label, inline_text

    harness_path, checked = resolve_existing_path(
        target.get("test_script_path"),
        target.get("driver_path"),
    )
    if harness_path is None:
        raise FileNotFoundError(
            f"Unable to resolve execution harness for {target['id']}. Checked: {checked}"
        )
    return harness_label, read_full_text(harness_path)


def _format_call_chain(target: dict) -> str:
    call_chain = target.get("call_chain") or []
    if isinstance(call_chain, list):
        return "\n".join(f"- {item}" for item in call_chain) if call_chain else "- <not provided>"
    return str(call_chain)


def _resolve_single_file_context(target: dict) -> str:
    if target.get("single_file_snippet"):
        return target["single_file_snippet"]
    return _resolve_source_snippet(target, max(PROMPT_CONTEXT_RADIUS, 80))


def _resolve_agent_context(target: dict) -> str:
    if target.get("agent_context_snippet"):
        return target["agent_context_snippet"]
    if target.get("single_file_snippet"):
        return target["single_file_snippet"]
    return _resolve_source_snippet(target, max(PROMPT_CONTEXT_RADIUS, 80))


def normalize_llm_output_mode(llm_output_mode: str | None) -> str:
    if not llm_output_mode:
        return "seed_base64"
    if llm_output_mode in PYTHON_CODE_MODES:
        return "python_code"
    if llm_output_mode in SEED_BASE64_MODES:
        return "seed_base64"
    raise ValueError(f"Unsupported llm_output_mode: {llm_output_mode}")


def _response_instructions(target: dict, llm_output_mode: str) -> str:
    llm_output_mode = normalize_llm_output_mode(llm_output_mode)
    if llm_output_mode == "python_code":
        return (
            "Return ONLY a single Python code block in exactly this form:\n"
            "```python\n"
            "<your code>\n"
            "```\n\n"
            "Do not include explanations.\n"
            "Instead of returning the seed bytes directly, write a Python 3 script that generates the raw fuzz input bytes.\n"
            "The variable `output_file` is already defined for you before your code runs.\n"
            "Your code must open `output_file` in binary mode and write the generated bytes to it.\n"
            "You may import Python modules that are available in the configured artifact environment.\n"
            "Prefer a compact, deterministic seed that is syntactically plausible for the target format."
        )
    return (
        "Return ONLY a JSON object in exactly this form:\n"
        "{\"seed_base64\":\"<base64 bytes>\"}\n\n"
        "Do not include markdown.\n"
        "Do not include explanations."
    )


def _decorate_template_for_harness(template: str, harness_snippet: str) -> str:
    if "ConsumeUnicodeNoSurrogates" not in harness_snippet:
        return template
    return (
        template
        + "\n**IMPORTANT**: ConsumeUnicodeNoSurrogates() requires an encoding selector byte. "
        + "The input bytes must include an encoding selector (typically 0x01 for UTF-8) before the string data."
    )


def build_prompt(
    target: dict,
    prompt_style: str = "callchain",
    llm_output_mode: str = "seed_base64",
) -> str:
    harness_label, harness_text = _resolve_harness(target)
    resolved_output_mode = normalize_llm_output_mode(target.get("llm_output_mode", llm_output_mode))
    response_instructions = _response_instructions(target, resolved_output_mode)
    common = {
        "language": target["language"],
        "project": target["project"],
        "target_symbol": target.get("target_symbol", "<unknown>"),
        "target_line_spec": target["target_line_spec"],
        "harness_label": harness_label,
        "harness_snippet": trim_text(harness_text, MAX_DRIVER_CHARS),
        "response_instructions": response_instructions,
    }

    if prompt_style == "callchain":
        template = _decorate_template_for_harness(
            CALLCHAIN_PROMPT_TEMPLATE,
            common["harness_snippet"],
        )
        return template.format(
            call_chain_block=_format_call_chain(target),
            source_snippet=_resolve_source_snippet(target, PROMPT_CONTEXT_RADIUS),
            **common,
        )
    if prompt_style == "singlefile":
        template = _decorate_template_for_harness(
            SINGLEFILE_PROMPT_TEMPLATE,
            common["harness_snippet"],
        )
        return template.format(
            file_context=_resolve_single_file_context(target),
            **common,
        )
    if prompt_style == "agentcontext":
        template = _decorate_template_for_harness(
            AGENTCONTEXT_PROMPT_TEMPLATE,
            common["harness_snippet"],
        )
        return template.format(
            agent_context=_resolve_agent_context(target),
            **common,
        )
    raise ValueError(f"Unsupported prompt style: {prompt_style}")

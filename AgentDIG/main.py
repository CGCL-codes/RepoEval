import json
import subprocess
import argparse

LANG_ALIASES = {
    "python": "python",
    "java": "java",
    "cpp": "cpp",
    "c_cpp": "cpp",
}

BUILD_PATH_LANG = {
    "python": "python",
    "java": "java",
    "cpp": "c_cpp",
    "c_cpp": "c_cpp",
}

OUTPUT_FORMAT = [
     {
        "attempt_number": "the attempt number (1, 2, or 3)",
        "py_script_path": "the file path of the generated Python script for this attempt",
        "bin_file_path": "the file path of the generated binary input for this attempt",
        "success": "a boolean indicating whether the target line was covered in this attempt"
     }
]



PROMPT_NEW = """Task Description: Generate directed test inputs for the {lang} project {project}.
The path {test_script_path} contains a test script that takes a binary input, specifically targeted at covering line {line} in file {file_name} of repo {repo_path}. Your task is to generate directed test inputs which follows the call chain {call_chain} to cover the target line with a maximum of 3 attempts.
TERMINATION CONDITIONS: You are allowed a maximum of 3 attempts for this generate-test-verify cycle. You must immediately terminate the task under either of the following conditions:
1. The target line {line} in {file_name} is successfully covered in any attempt.
2. All 3 attempts have been executed and the target line remains uncovered.
FINAL OUTPUT REQUIREMENT: Upon termination, you must generate the result with a JSON file The JSON format is {output_format}. The generated JSON file and all the immedidate results of each attempt should be saved in {repo_path}/dig_results/ with the prefix {project}{id}_. 
ATTENTION: Use {skill_name} to help you deal with the task.
"""


build_sh_path = {
    "java": {
        "jsoup": "../oss-fuzz/projects/jsoup/build.sh",
        "jedis": "../oss-fuzz/projects/jedis/build.sh",
        "async-http-client": "../oss-fuzz/projects/async-http-client/build.sh",
        "metadata-extractor": "../oss-fuzz/projects/metadata-extractor/build.sh",
    },
    "c_cpp": {
        "jansson": "../oss-fuzz/projects/jansson/build.sh",
        "cpp-httplib": "../oss-fuzz/projects/cpp-httplib/build.sh",
        "sqlite3": "../oss-fuzz/projects/sqlite3/build.sh",
        "exiv2": "../oss-fuzz/projects/exiv2/build.sh",
    }
}




def run_agent_input(lang, input, test_script_path, repo_path, project, id, call_chain):
    line = input["target_line"]
    file_name = input["target_file"]
    print(f"Processing target: {file_name}:{line}", flush=True)

    skill_name = ""
    if LANG_ALIASES.get(lang) == "java":
        skill_name = "java-directed-test-skill"
    elif LANG_ALIASES.get(lang) == "cpp":
        skill_name = "cpp-directed-test-skill"
    else:
        skill_name = "python-directed-test-skill"
    prompt = PROMPT_NEW.format(lang=lang,test_script_path=test_script_path, line=line, file_name=file_name, repo_path=repo_path, project=project, id=id, output_format=json.dumps(OUTPUT_FORMAT, indent=4), call_chain=call_chain, skill_name=skill_name)
    

    prompt = prompt.replace("\n", "\\n")  # Escape newlines for command line
    prompt = prompt.replace('"', '\\"')  # Escape double quotes for command line
    if LANG_ALIASES.get(lang) in ["java", "cpp"]:
        build_path = build_sh_path[BUILD_PATH_LANG.get(lang, lang)][project]
        prompt += f" **Build Script Path**: {build_path}.\n"
    test_script_code = open(test_script_path, 'r').read()
    if "ConsumeUnicodeNoSurrogates" in test_script_code:
            prompt += "**IMPORTANT**: ConsumeUnicodeNoSurrogates() requires an encoding selector byte."
            prompt += "The input bytes must include an encoding selector (typically 0x01 for UTF-8) before the string data."
    command_str = f'opencode run "{prompt}" -m deepseek/deepseek-chat'
    print(f"Running command: {command_str}")
    output = subprocess.run(command_str, shell=True, capture_output=True, text=True) 
    if output.returncode != 0:
        print(f"Error running command: {output.stderr}")
        return output.stdout + output.stderr if output.stderr else output.stdout
    else:
        return output.stdout + output.stderr if output.stderr else output.stdout



def match_target(input_dataset, lang, project, idx):
    norm_lang = LANG_ALIASES.get(lang, lang)
    candidate_ids = {
        f"{lang}-{project}-{idx}",
        f"{norm_lang}-{project}-{idx}",
    }
    for it in input_dataset:
        if str(it.get("id")) in candidate_ids:
            return it, str(it.get("id"))
    for it in input_dataset:
        if (
            str(it.get("id")) == str(idx)
            and it.get("project") == project
            and LANG_ALIASES.get(it.get("language"), it.get("language")) == norm_lang
        ):
            return it, f"{norm_lang}-{project}-{idx}"
    return None, f"{norm_lang}-{project}-{idx}"


def main(lang, project, idx, dataset_path):
    dataset = json.load(open(dataset_path, 'r'))
    input_dataset = dataset["targets"]

    matched, data_id = match_target(input_dataset, lang, project, idx)
    if matched is None:
        available = [
            f"id={it.get('id')} (language={it.get('language')}, project={it.get('project')})"
            for it in input_dataset
        ]
        raise SystemExit(
            f"No target matched id '{data_id}' (or plain index {idx}) for "
            f"lang={lang}, project={project} in {dataset_path}.\n"
            f"Available targets:\n  " + "\n  ".join(available) + "\n"
        )

    print(f"Processing {data_id} (matched id {matched['id']})...")
    if LANG_ALIASES.get(lang) == "python":
        test_script_path = matched["test_script_path"]
    else:
        test_script_path = matched["driver_path"]
    repo_path = matched["target_source_path"]
    call_chain = matched["call_chain"]
    output = run_agent_input(lang, matched, test_script_path, repo_path, project, idx, call_chain)
    print(f"Output for {data_id}:\n{output}")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the directed test generation agent.')
    parser.add_argument('--lang', type=str, required=True, help='Programming language (e.g., java, c_cpp)')
    parser.add_argument('--project', type=str, required=True, help='Project name (e.g., jsoup, jansson)')
    parser.add_argument('--idx', type=int, required=True, help='Index of the input data to process')
    parser.add_argument('--dataset_path', type=str, required=True, help='Path to the input dataset JSON file')
    
    args = parser.parse_args()
    main(args.lang, args.project, args.idx, args.dataset_path)
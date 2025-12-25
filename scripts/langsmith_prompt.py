"""LangSmith Prompt Hub demo script.

Upload prompts to LangSmith Hub and pull them for use.

Usage:
    export LANGCHAIN_API_KEY="ls_..."

    # Push prompt to hub
    uv run python scripts/langsmith_prompt.py --push

    # Pull and test prompt
    uv run python scripts/langsmith_prompt.py --pull

    # Both
    uv run python scripts/langsmith_prompt.py
"""

import argparse
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client

PROMPT_NAME = "beneissue-triage"


def load_local_prompt() -> str:
    """Load triage prompt from local file."""
    prompt_path = Path("src/beneissue/prompts/triage.md")
    return prompt_path.read_text()


def push_prompt(client: Client) -> None:
    """Push prompt to LangSmith Hub."""
    prompt_text = load_local_prompt()

    # Create a ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        ("human", "Title: {title}\n\nBody: {body}"),
    ])

    # Push to hub
    url = client.push_prompt(PROMPT_NAME, object=prompt)
    print(f"Pushed prompt: {url}")


def pull_prompt(client: Client) -> None:
    """Pull prompt from LangSmith Hub and test it."""
    try:
        prompt = client.pull_prompt(PROMPT_NAME)
        print(f"Pulled prompt: {PROMPT_NAME}")
        print(f"Type: {type(prompt)}")

        # Test with sample input
        sample = {
            "readme_content": "# Calculator\nA simple calculator app.",
            "existing_issues": "No existing issues.",
            "title": "Bug: division by zero",
            "body": "The divide function crashes.",
        }

        messages = prompt.invoke(sample)
        print("\n--- Sample output ---")
        for msg in messages.messages:
            print(f"[{msg.type}]: {msg.content[:200]}...")

    except Exception as e:
        print(f"Failed to pull prompt: {e}")
        print("Run with --push first to upload the prompt.")


def main():
    parser = argparse.ArgumentParser(description="LangSmith Prompt Hub demo")
    parser.add_argument("--push", action="store_true", help="Push prompt to hub")
    parser.add_argument("--pull", action="store_true", help="Pull prompt from hub")
    args = parser.parse_args()

    client = Client()

    # If neither specified, run both
    do_push = args.push or (not args.push and not args.pull)
    do_pull = args.pull or (not args.push and not args.pull)

    if do_push:
        push_prompt(client)

    if do_pull:
        pull_prompt(client)


if __name__ == "__main__":
    main()

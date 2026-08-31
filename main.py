"""Bedtime stories for ages 5 to 10.

    python main.py
    python main.py "a story about Alice and her best friend Bob, who is a cat"
    python main.py "a story about space" --show-work
    python main.py "a story about a dragon" --speak

Writes a few versions of the story, throws out the bad ones with cheap string
checks, then lets the judge compare whatever survives. Each module opens with
the finding that shaped it; the block diagram and the write-up are in
README.md.

Before submitting the assignment, describe here in a few sentences what you
would have built next if you spent 2 more hours on this project:

    An eval harness. Everything I know about this system came from scratch
    scripts I ran once and deleted, so I'd keep thirty or so fixed requests
    (vague, violent, empty, not in English), run them nightly, and log every
    draft with the reason it got rejected. Without that, anyone editing a
    prompt is guessing, same as I was before I started measuring.

    Then real numbers on the ending check, which has only ever been tried on
    five cases I picked myself and got 4 of them right. And the drafts are
    written one after another when they could go at the same time, which is
    most of the thirty second wait.
"""

import argparse
import os
import shutil
import subprocess
import sys
import textwrap

from pipeline import NoSafeStory, Result, apply_feedback, tell_story

WIDTH = 76

# `say` defaults to 175, which is a news reader. Read aloud to a child at
# bedtime that is much too brisk, and it is also the number the printed
# reading time is based on.
WORDS_PER_MINUTE = 150


def load_env():
    """Read .env if there is one, so `python main.py` works without exporting."""
    if not os.path.exists(".env") or os.getenv("OPENAI_API_KEY"):
        return
    with open(".env") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def show(result: Result):
    print("\n" + "=" * WIDTH)
    print(result.title.upper().center(WIDTH))
    print("=" * WIDTH + "\n")
    for para in result.text.split("\n"):
        if para.strip():
            print(textwrap.fill(para.strip(), WIDTH))
            print()
    print("-" * WIDTH)
    minutes = result.word_count / WORDS_PER_MINUTE
    print(f"{result.word_count} words, about {minutes:.0f} minutes to read aloud. "
          f"Chosen from {result.drafts_kept} drafts ({result.drafts_written} written).")


def speak(result: Result):
    """Read the story out loud, which is how a bedtime story is meant to arrive.

    Leans on the macOS `say` binary rather than a TTS API, so it costs nothing
    and works with no key. Reading it aloud is also the fastest way to hear
    the faults the checks are looking for: a moral tacked onto the end sounds
    much worse than it reads.
    """
    if not shutil.which("say"):
        print("(--speak needs the macOS `say` command, skipping)")
        return
    print("(reading aloud, ctrl-c to stop)")
    try:
        subprocess.run(["say", "-r", str(WORDS_PER_MINUTE),
                        f"{result.title}. {result.text}"], check=False)
    except KeyboardInterrupt:
        print("\n(stopped)")


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def main():
    parser = argparse.ArgumentParser(description="Tell a bedtime story for ages 5-10.")
    parser.add_argument("request", nargs="?", help="what the story should be about")
    parser.add_argument("--show-work", action="store_true",
                        help="show drafts being thrown out and the judge choosing")
    parser.add_argument("--once", action="store_true", help="one story, then exit")
    parser.add_argument("--speak", action="store_true",
                        help="read the story out loud (macOS)")
    args = parser.parse_args()

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY=sk-...")

    request = args.request or ask("What kind of story do you want to hear? ")
    if not request:
        print("No request, no story. Goodnight!")
        return

    report = (lambda m: print(f"  {m}", flush=True)) if args.show_work else (lambda _: None)

    try:
        result = tell_story(request, report)
    except NoSafeStory:
        sys.exit("\nEvery version of that one came out too upsetting for bedtime. "
                 "Ask me for a different story and I'll try again.")
    except Exception as exc:
        sys.exit(f"\nSomething went wrong talking to OpenAI: {exc}")

    show(result)
    if args.speak:
        speak(result)

    while not args.once:
        change = ask("\nAnything you'd change? (press enter to keep it) ")
        if not change:
            break
        result = apply_feedback(result, change, report)
        show(result)
        if args.speak:
            speak(result)

    print("\nSweet dreams.\n")


if __name__ == "__main__":
    main()

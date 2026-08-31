"""Wires the pieces together: understand, write several, filter, choose.

This module owns the order things happen in and nothing else. It has no
opinion on what makes a story good (checks.py and judge.py do) or on how to
write one (storyteller.py does).
"""

from checks import check, ends_on_a_lesson, harm_words
from intake import Brief, understand
from judge import pick_best
from storyteller import make_title, revise_story, write_story

DRAFTS = 3          # candidates written per story
MAX_ATTEMPTS = 5    # hard cap on generation calls, in case the checks keep failing


class NoSafeStory(Exception):
    """Every draft had upsetting content in it, so there is nothing to read."""


class Result:
    def __init__(self, brief, story, drafts_written, drafts_kept):
        self.brief = brief
        self.story = story
        self.drafts_written = drafts_written
        self.drafts_kept = drafts_kept
        self.title, self.text = split_title(story)
        if not self.title:
            self.title = make_title(self.text)

    @property
    def word_count(self):
        return len(self.text.split())


def split_title(story: str):
    """Split the reply into (title, body). An empty title means it had none."""
    cleaned = story.strip()
    parts = cleaned.split("\n", 1)
    first = parts[0].strip().strip("#*").strip().strip('"')
    if len(parts) == 2 and len(first.split()) <= 10 and not first.endswith((".", "!", "?")):
        return first, parts[1].strip()
    return "", cleaned


def tell_story(request: str, report=lambda _: None) -> Result:
    report("thinking about what you asked for...")
    brief = understand(request)

    if not brief.child_safe and brief.softened_request:
        report(f"changing that a little: {brief.concern}")

    kind = brief.category.replace("_", " ")
    article = "an" if kind[:1] in "aeiou" else "a"
    report(f"writing {DRAFTS} versions of {article} {kind} story...")

    kept, rejected, written = [], [], 0
    while len(kept) < DRAFTS and written < MAX_ATTEMPTS:
        written += 1
        draft = write_story(brief)
        reasons = check(draft, brief)
        if not reasons and ends_on_a_lesson(draft):
            reasons = ["ends by spelling out the lesson"]
        if reasons:
            report(f"threw version {written} away: {reasons[0]}")
            rejected.append((written, draft, reasons))
        else:
            report(f"kept version {written}")
            kept.append((written, draft))

    if not kept:
        # Nothing came back clean, so fall back to the least bad draft rather
        # than writing yet another unchecked one. But only the cosmetic
        # failures are eligible. Running short or keeping the characters quiet
        # makes for a dull story; a death in it is not something to read to a
        # five year old because the alternative was silence.
        harmless = [item for item in rejected if not harm_words(item[1])]
        if not harmless:
            raise NoSafeStory(request)
        number, draft, reasons = min(harmless, key=lambda item: len(item[2]))
        report(f"no clean version, reading version {number} ({reasons[0]})")
        kept = [(number, draft)]

    number, story = pick_best(kept, report)
    report(f"reading version {number}")
    return Result(brief, story, written, len(kept))


def apply_feedback(result: Result, feedback: str, report=lambda _: None) -> Result:
    """One revision pass driven by what the listener asked for.

    Revision happens here and nowhere else. When the model invented its own
    criticism it produced word swaps that left the real problem untouched. An
    instruction from an actual person is specific enough to act on.

    A revision has to clear the same bar a fresh draft does. If neither try
    manages it the story the listener already has is returned unchanged, since
    not getting the change you asked for beats being handed something that
    failed the checks.
    """
    def good_enough(story):
        return not check(story, result.brief) and not ends_on_a_lesson(story)

    report("making that change...")
    revised = revise_story(result.story, feedback, result.brief)
    written = 1

    if not good_enough(revised):
        report("that introduced a problem, trying once more")
        second = revise_story(result.story, feedback, result.brief)
        written += 1
        if good_enough(second):
            revised = second
        else:
            report("could not make that change safely, keeping the story as it was")
            revised = result.story

    return Result(result.brief, revised, result.drafts_written + written,
                  result.drafts_kept)

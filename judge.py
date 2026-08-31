"""The LLM judge. It picks between drafts. It does not score them or fix them.

Both of the obvious designs were tried first and neither worked on this model.

Scoring gave no signal. Three clearly different drafts all came back at
exactly 4.50 out of 5, two of them with the same complaint word for word.

Critique and patch was worse. Told to fix a story with a sick pet in it, the
model changed "tragedy" to "challenge" and left the pet sick. Told a story
stated its lesson, it swapped "proving that" for "showing that" in the same
sentence. Three rounds moved a bad story from 3.17 to 3.50, fixed nothing
structural, and added a new fault that broke the fourth wall.

Comparison works. Given a known-bad draft next to a good one it picked the
good one every time, in both orders.
"""

from llm import call_json

COMPARE_SYSTEM = """You are the toughest children's picture book editor in
publishing. You are given two drafts of a bedtime story for ages 5 to 10.
Choose the one you would actually read to a child tonight.

What decides it:
- Does it hold a young child's attention, or is it a list of events?
- Do the characters talk like people?
- Does the young hero solve their own problem?
- Is a worry raised and then properly settled?
- Does it end calm enough for sleep?
- Does it avoid stating its lesson out loud?
- Does it sound good read aloud?

Do not favour the longer draft. Do not favour decorated language. Purple,
over-written prose is a fault, not a strength.

Reply with ONLY a JSON object:
{"winner": "A" or "B", "why": "one sentence naming the deciding difference"}"""


def compare_once(story_a: str, story_b: str):
    """Ask which of two drafts is better. Returns ("A"/"B"/None, reason)."""
    verdict = call_json(
        f"DRAFT A:\n{story_a}\n\n{'-' * 40}\n\nDRAFT B:\n{story_b}",
        system=COMPARE_SYSTEM,
        max_tokens=300,
    )
    if not verdict or verdict.get("winner") not in ("A", "B"):
        return None, ""
    return verdict["winner"], str(verdict.get("why", "")).strip()


def better_of(champion: str, challenger: str):
    """Does the challenger beat the champion? Returns (bool, reason).

    Compared both ways round, and the challenger has to win both. Asked one
    way only, the model picks whichever draft it saw first about two thirds of
    the time. Demanding agreement removes that, at the cost of no result when
    the drafts are close, which is fine because then either would do.
    """
    first, why = compare_once(champion, challenger)
    second, _ = compare_once(challenger, champion)
    challenger_wins = (first == "B" and second == "A")
    return challenger_wins, (why if challenger_wins else "")


def pick_best(drafts, report):
    """Knock-out between drafts: 2 calls per challenger, none for a single draft.

    Takes and returns (version_number, text) so progress messages refer to the
    same version numbers the rejections do.
    """
    champion = drafts[0]
    for number, text in drafts[1:]:
        challenger_wins, why = better_of(champion[1], text)
        if challenger_wins:
            report(f"the judge prefers version {number}" + (f": {why}" if why else ""))
            champion = (number, text)
        else:
            report(f"version {number} did not beat version {champion[0]}")
    return champion

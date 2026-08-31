"""Throwing away drafts that are not worth reading.

These run before the judge because they are free and because they were right
twice when the model was wrong. It gave a story with a sick pet and no
dialogue five out of five for safety and engagement. It also said a story
ending "proving that sometimes, the best friends come in the most unexpected
of packages" did not state a lesson.

The model never sees these rules. When a revision prompt was told which words
were being looked for, it renamed them and left the problem alone: "tragedy"
became "challenge" while the pet stayed sick.
"""

import re

from intake import Brief
from llm import call_json
from storyteller import WORDS

# Last paragraph only. Scanning the whole story threw away good drafts for an
# "and so," in the middle of a scene and still missed the ones that really did
# end on a lesson.
#
# Only patterns that are almost never innocent go here, since they reject a
# draft for free. "and so," is left out on purpose: it caused every false
# rejection I measured, and the model check below gets it right.
MORALISING = ("learned that", "proving that", "the moral", "teaching us",
              "showing that", "remember,", "that's the magic",
              "is all about", "what mattered most")
HARM = ("fell ill", "got sick", "was sick", "tragedy", "died", "death",
        "passed away", "mock", "coward", "nightmare", "injured")

MORAL_SYSTEM = ("You check the endings of children's bedtime stories. "
                "You reply with one JSON object and no other text.")

MORAL_PROMPT = """This is the last paragraph of a bedtime story for children
aged 5 to 10.

Does it state the story's lesson or message out loud, instead of simply
ending the story?

Stating the lesson out loud looks like:
  "And so they learned that sharing is the best thing of all."
  "Remember, bravery and friendship can overcome even the darkest of times."
  "...knew that as long as they had each other, every adventure would be grand."

Simply ending looks like:
  "Goodnight, Mom," Tommy whispered, drifting off to sleep, feeling safe.
  And with that, Mia drifted off to sleep, dreaming of the stars.
  And so, hand in paw, they curled up in the grass and closed their eyes.

A paragraph can begin with "And so" and still just be an ending. What matters
is whether it tells the reader what to take away.

LAST PARAGRAPH:
{paragraph}

Return JSON: {{"states_lesson": true or false}}"""


def last_paragraph(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return paragraphs[-1] if paragraphs else ""


def check(text: str, brief: Brief):
    """Return a list of reasons to reject this draft. Empty list means keep it."""
    low = text.lower()
    ending = last_paragraph(text).lower()
    words = len(text.split())
    dialogue = len(re.findall(r'"[^"]{3,}"', text))
    target_low, target_high = WORDS.get(brief.length, WORDS["medium"])

    reasons = []
    found_harm = [w for w in HARM if w in low]
    found_moral = [p for p in MORALISING if p in ending]
    if found_harm:
        reasons.append(f"upsetting content: {', '.join(found_harm)}")
    if found_moral:
        reasons.append(f"states its lesson at the end: {', '.join(found_moral)}")
    if dialogue < 6:
        reasons.append(f"only {dialogue} lines of dialogue")
    if not target_low - 100 <= words <= target_high + 200:
        reasons.append(f"{words} words, wanted {target_low}-{target_high}")
    return reasons


def ends_on_a_lesson(text: str) -> bool:
    """One small model call, asked about one paragraph.

    The full six-part rubric could not spot a stated moral, but this single
    question mostly can. It runs only on drafts that already passed the free
    checks, so a bad draft never costs a call.
    """
    ending = last_paragraph(text)
    if not ending:
        return False
    data = call_json(MORAL_PROMPT.format(paragraph=ending),
                     system=MORAL_SYSTEM, max_tokens=100)
    return bool(data and data.get("states_lesson") is True)

"""Writing the story.

This prompt is where the quality actually comes from. Against the raw
skeleton it took the Alice story from 0 to 15 lines of dialogue and cleared
every problem the baseline had (lonely opening, sick pet, moral stated in the
last line) in a single call. Everything else here is a filter on top of it.

Each category gets its own tone, shape and ending instead of one generic
prompt. A sleepy story and a silly one should not be written the same way.
"""

from intake import Brief
from llm import call_model

RECIPES = {
    "adventure": ("brave and exciting but never frightening",
                  "a clear goal, three tries to reach it, the third works",
                  "home again, tired and proud"),
    "animal_friends": ("cozy and affectionate",
                       "two friends want different things and find a way to agree",
                       "curled up together somewhere soft"),
    "silly": ("giggly and absurd",
              "one ridiculous problem that gets worse three times, then pops",
              "everyone laughing, the mess mostly tidied"),
    "calming": ("slow, soft and drowsy",
                "a gentle wandering journey where nothing goes badly wrong",
                "drifting off to sleep, safe and warm"),
    "discovery": ("curious and full of wonder",
                  "a question, a hunt for the answer, a surprising true fact",
                  "the wonder of it carried off to bed"),
    "feelings": ("gentle and understanding",
                 "a worry grows, is named out loud, and is made smaller",
                 "tucked in beside whoever helped, the worry now small"),
    "fantasy": ("magical and a little grand",
                "an ordinary child crosses into a magic place, helps, comes back",
                "back in bed with one small proof it was real"),
}

WORDS = {"short": (300, 450), "medium": (400, 600), "long": (550, 800)}

STORYTELLER = """You are a warm bedtime storyteller for children aged 5 to 10.
You are reading aloud to one sleepy child.

Rules:
- Write in scenes. Never summarise time passing ("days turned into weeks").
- Characters talk. Include at least eight lines of real dialogue.
- Never state the lesson out loud. No "and so they learned that..." ending.
- Use words a 5 to 10 year old knows.
- The young hero solves the problem themselves. Grown-ups may comfort, but
  must not hand over the answer.
- A character may feel scared, sad or worried. That is what makes a story.
  What matters is that the story settles the feeling before it ends.
- No illness, death, injury, or teasing that goes unanswered.
- End calm and sleepy, on something a child can see or hear: a face, an
  object, a sound, someone closing their eyes. Never end on what anyone
  learned, knew, realised or understood.
- Title on the first line, then the story. No headings, no notes."""

WRITE_PROMPT = """Write a bedtime story.

REQUEST: {request}
{details}WHAT HAPPENS: {hook}

Tone: {tone}
Shape: {shape}
Ending: {ending}
Length: {low} to {high} words."""

REVISE_PROMPT = """Revise this bedtime story. The listener asked for one
change. Make that change and leave everything else exactly as it is: the
characters, the voice, the ending.

WHAT THEY ASKED FOR: {feedback}

STORY:
{story}

Return the whole revised story: title on the first line, then the prose."""


def write_story(brief: Brief) -> str:
    tone, shape, ending = RECIPES.get(brief.category, RECIPES["adventure"])
    low, high = WORDS.get(brief.length, WORDS["medium"])

    details = ""
    if brief.characters:
        details += f"Characters, spelled exactly like this: {', '.join(brief.characters)}\n"
    if brief.setting:
        details += f"Setting: {brief.setting}\n"
    if brief.themes:
        details += f"Themes: {', '.join(brief.themes)}\n"

    return call_model(
        WRITE_PROMPT.format(request=brief.story_request, details=details,
                            hook=brief.hook or "you decide", tone=tone,
                            shape=shape, ending=ending, low=low, high=high),
        system=STORYTELLER,
        max_tokens=int(high * 1.8) + 200,
        temperature=0.9,  # the draft is where the imagination should live
    )


TITLE_PROMPT = """Give this children's bedtime story a short, inviting title.
Six words at most. Reply with the title and nothing else: no quotes, no
explanation, no full stop.

STORY:
{story}"""


def make_title(story: str) -> str:
    """Name a story that arrived without a title.

    The storyteller is asked for one on the first line and usually gives one,
    but every so often it opens straight into "Once upon a time". Without this
    the headline reads "A Bedtime Story", which is nobody's idea of a title.
    """
    title = call_model(TITLE_PROMPT.format(story=story[:1500]),
                       max_tokens=20, temperature=0.7)
    title = title.strip().strip('"').strip(".").strip()
    return title if 0 < len(title.split()) <= 10 else "A Bedtime Story"


def revise_story(story: str, feedback: str, brief: Brief) -> str:
    low, high = WORDS.get(brief.length, WORDS["medium"])
    return call_model(
        REVISE_PROMPT.format(feedback=feedback, story=story),
        system=STORYTELLER,
        max_tokens=int(high * 1.8) + 200,
        temperature=0.6,  # editing, not reinventing
    )

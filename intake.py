"""Turn a free-form request into something specific enough to write from.

Two jobs. Enrichment first: the vaguest request I tested, "tell me a story
about space", gave the worst story of the lot and had two of its three drafts
thrown out, where a specific request had none. Vague input is the thing to
fix, and it has to be fixed before anyone writes anything.

Then screening, which happens in code here rather than in the model. The
reason why is written next to RISKY.
"""

import re

from llm import call_json, call_model

CATEGORIES = ("adventure", "animal_friends", "silly", "calming", "discovery",
              "feelings", "fantasy")
LENGTHS = ("short", "medium", "long")

INTAKE_SYSTEM = ("You sort bedtime story requests from children and their "
                 "parents. You reply with one JSON object and no other text.")

INTAKE_PROMPT = """Read this bedtime story request.

REQUEST: {request}

Return JSON with exactly these keys:
  "category": one of {categories}. Choose by what the story is really for:
      discovery for space, dinosaurs, the sea, how things work;
      adventure for quests, journeys and treasure;
      animal_friends for pets and talking animals;
      feelings for worries, first days, being shy or scared;
      calming when they want something slow and sleepy;
      silly for jokes and nonsense; fantasy for magic and dragons
  "characters": names mentioned, exactly as spelled (empty list if none)
  "setting": short phrase, or "" if not given
  "themes": 1-3 themes worth building the story around
  "length": one of {lengths}; "medium" unless the request says otherwise
  "hook": if the request is vague, invent one specific problem for the story
      to be about, in one sentence. If the request is already specific,
      repeat its own idea back in one sentence.
  "child_safe": true if this suits children aged 5-10
  "concern": one short sentence on why not, if child_safe is false
  "softened_request": if child_safe is false, rewrite the request keeping what
      the child was excited about and dropping what is unsuitable; else ""

Most requests are fine. Mark child_safe false for real violence, death,
horror, romance or adult topics. A monster or a bad guy is not a problem."""

SOFTEN_PROMPT = """A child asked for this bedtime story, and it is not
suitable for a five year old at bedtime.

REQUEST: {request}
THE PROBLEM: it mentions {found}

Rewrite it as a request for a story that keeps whatever the child was
actually excited about and drops what is unsuitable. One sentence, no
explanation, no apology.

Your rewrite must not contain the words war, soldier, army, fighting, weapon,
gun, killing, dying or death. Replace what they were asking for entirely. Do
not just make it sound gentler.

For example, "a war where soldiers fight and die" becomes "two kingdoms who
stop arguing and become friends", and "my grandma who died" becomes "a girl
who visits her grandma's garden and remembers her stories"."""

# Used when the model cannot produce a clean rewrite. Bland, but a child who
# asked for something unsuitable still gets a story.
SAFE_FALLBACK = ("a story about a brave child who helps someone in trouble "
                 "and makes a new friend")

# Suitability is decided here, not by the model. Asked to screen "a war where
# soldiers fight and die", it listed war, soldiers and dying as problems and
# then set child_safe to true anyway. It also found "romance" in a story about
# a girl and her cat. Its judgement is not usable, but its rewriting is, so
# that is all it gets asked for.
# A request is one short sentence, which is where word matching is at its most
# reliable. "fight" is left out on purpose: a pillow fight is fine.
RISKY = ("war", "soldier", "soldiers", "army", "gun", "guns", "kill", "killed",
         "killing", "murder", "blood", "weapon", "bomb", "dead", "died",
         "dying", "death", "passed away", "drown", "drowned", "suicide",
         "gore", "zombie", "zombies")


class Brief:
    def __init__(self, request, **kw):
        self.request = request
        self.category = kw.get("category", "adventure")
        self.characters = kw.get("characters", [])
        self.setting = kw.get("setting", "")
        self.themes = kw.get("themes", [])
        self.length = kw.get("length", "medium")
        self.hook = kw.get("hook", "")
        self.child_safe = kw.get("child_safe", True)
        self.concern = kw.get("concern", "")
        self.softened_request = kw.get("softened_request", "")

    @property
    def story_request(self):
        if not self.child_safe and self.softened_request:
            return self.softened_request
        return self.request


def risky_words(request: str):
    low = request.lower()
    return [w for w in RISKY if re.search(rf"\b{re.escape(w)}\b", low)]


def clean_rewrite(reply: str) -> str:
    """Pull the rewritten request out of the reply.

    It sometimes restates the original first and labels its answer, as in
    "a story about my grandma who passed away.\n\nREWRITE: a girl who visits
    her grandma's garden", so the last line is the one worth having.
    """
    lines = [line.strip() for line in reply.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return re.sub(r"^[A-Za-z ]{3,12}:\s*", "", lines[-1]).strip().strip('"')


def soften(request: str, found) -> str:
    """Rewrite an unsuitable request, then check the rewrite is actually clean.

    Left unchecked, "a war where soldiers fight and die" came back as
    "soldiers who bravely protect their kingdom from a sorcerer's army". Still
    soldiers, still an army. So the rewrite has to pass the same word list as
    the original or it does not count.
    """
    for _ in range(2):
        reply = call_model(
            SOFTEN_PROMPT.format(request=request, found=", ".join(found)),
            max_tokens=120,
            temperature=0.3,  # a rewrite should be careful, not creative
        )
        if cleaned := clean_rewrite(reply):
            if not risky_words(cleaned):
                return cleaned
    return SAFE_FALLBACK


def as_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def classify(request: str) -> dict:
    return call_json(
        INTAKE_PROMPT.format(request=request,
                             categories=", ".join(CATEGORIES),
                             lengths=", ".join(LENGTHS)),
        system=INTAKE_SYSTEM,
        max_tokens=400,
    ) or {}


def understand(request: str) -> Brief:
    found = risky_words(request)
    data = classify(request)

    # Unsafe if either the word check or the model says so. The word check is
    # the one that is trusted to fire; the model only ever adds to it.
    child_safe = data.get("child_safe", True) is not False and not found
    softened = str(data.get("softened_request") or "").strip()
    concern = str(data.get("concern") or "").strip()

    if not child_safe:
        if found:
            concern = f"it asks for {', '.join(found)}"
        # The model's own suggested rewrite is held to the same word list as
        # anything else it produces.
        if not softened or risky_words(softened):
            softened = soften(request, found or [concern or "unsuitable content"])
        # Classify the softened request in its own right. Reusing the original
        # request's category and hook gave the worst story of the whole test
        # run: a war request softened into two arguing kingdoms was still
        # being written as an "adventure" with no hook to hang it on.
        data = classify(softened) or data

    category = str(data.get("category", "")).strip().lower()
    length = str(data.get("length", "")).strip().lower()

    # The hook is written straight into the storyteller's prompt, so it gets
    # the same screening. Asked to invent one for two kingdoms who stop
    # arguing, the model came back with "on the brink of war".
    hook = str(data.get("hook") or "").strip()
    if risky_words(hook):
        hook = ""

    return Brief(
        request,
        category=category if category in CATEGORIES else "adventure",
        characters=as_list(data.get("characters")),
        setting=str(data.get("setting") or "").strip(),
        themes=as_list(data.get("themes")),
        length=length if length in LENGTHS else "medium",
        hook=hook,
        child_safe=child_safe,
        concern=concern,
        softened_request=softened,
    )

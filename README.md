# Bedtime stories for ages 5 to 10

My submission for the Hippocratic AI coding assignment. The original brief is in [ASSIGNMENT.md](ASSIGNMENT.md).

Short version: the model writes several versions of the story, some cheap string checks throw out the bad ones, and an LLM judge picks a winner by comparing the survivors against each other instead of scoring them. It is `gpt-3.5-turbo` the whole way through, at different temperatures depending on the job.

Most of what is below came out of running things rather than reasoning about them. A couple of those runs killed designs I had already half built, and I have written those up too, because the failures turned out to be more useful than the successes.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export OPENAI_API_KEY=sk-...            # or put it in a .env file, which is gitignored

.venv/bin/python main.py
.venv/bin/python main.py "a story about Alice and her best friend Bob, who is a cat"
.venv/bin/python main.py "a story about space" --show-work
.venv/bin/python main.py "a story about a dragon" --speak
```

`--show-work` prints the drafts getting thrown away and the judge picking between what is left. It is the quickest way to see whether any of this is actually doing anything. `--once` skips the feedback prompt and exits after one story.

`--speak` reads the winner out loud through the macOS `say` voice, at 150 words a minute instead of its default 175, which is a newsreader's pace rather than a bedtime one. A story printed to a terminal is the one format the intended listener cannot use, so this felt worth the twelve lines. It also changes what you notice, because a moral tacked onto the last line sounds much worse aloud than it looks on the page, which makes it the quickest way to hear the faults the checks are hunting for. The footer gives reading time next to the word count for the same reason, minutes being the honest unit for something meant to be heard. It shells out to a system binary rather than to a TTS API, so it adds no dependency and leaves `gpt-3.5-turbo` as the only model in the project. It is opt-in and off by default.

The dependency is pinned to `openai==0.28.1`, because `openai.ChatCompletion.create` was removed in openai 1.0 and the skeleton uses it. Pinning meant I could leave the `call_model` you gave me essentially as it was, and the model is untouched.

## Block diagram

```
   "tell me a story about space"
             |
             v
   +-------------------------------------------+
   | intake.py                                 |
   |                                           |
   |   classify() [model] + risky_words()      |
   |   category / characters / setting /       |
   |   themes / length / hook                  |
   |   unsafe if either the model or the       |
   |   word list says so                       |
   |        |                                  |
   |        +-- clean ---------------------+   |
   |        |                              |   |
   |        +-- blocked                    |   |
   |              |                        |   |
   |              v                        |   |
   |          soften() [model], up to 2    |   |
   |          tries until the rewrite is   |   |
   |          clean too, then classify()   |   |
   |          the rewrite from scratch     |   |
   |          (its hook gets screened      |   |
   |          as well)                     |   |
   |              |                        |   |
   |              +------------------------+   |
   |                        |                  |
   +-------------------------------------------+
             |
             |  Brief
             v
   recipe table, no model
   category -> tone, shape, ending;  length -> word target
             |
             v
   +-------------------------------------------+
   | storyteller.py + checks.py    x3, max 5   |
   |                                           |
   |   write_story() [model, temp 0.9]         |
   |        |                                  |
   |        v                                  |
   |   check()   free, no model                |
   |     harm words                            |
   |     moral in the last paragraph           |
   |     at least 6 lines of dialogue          |
   |     length in range                       |
   |        |                                  |
   |        v   only if it got this far        |
   |   ends_on_a_lesson() [model, 1 question]  |
   |        |                                  |
   |        v                                  |
   |   keep it, or bin it and write another    |
   |                                           |
   |   if nothing survives all 5 attempts, the |
   |   least bad draft is read instead, but    |
   |   only if it failed on length or dialogue |
   |   rather than on content. if every draft  |
   |   had something upsetting in it, nothing  |
   |   is read at all                          |
   +-------------------------------------------+
             |
             |  1 to 3 drafts
             v
   +-------------------------------------------+
   | judge.py                                  |
   |   knock-out, champion vs each challenger  |
   |   every pair run both ways round, 2 calls |
   |   a challenger has to win both to take    |
   |   the title                               |
   |   (a single draft skips this entirely)    |
   +-------------------------------------------+
             |
             |  winner
             v
   title off line 1, or make_title() if it forgot one
             |
             v
        READ ALOUD
   (--speak sends it to the system voice)
             |
             v
   "make it sillier" -> revise_story() [temp 0.6]
                        re-checked afterwards, one retry
                        if the revision broke something,
                        and the original is kept if both
                        tries fail, then back to READ ALOUD
```

Somewhere between 9 and 14 model calls, and 25 to 35 seconds, for one story.

## Design notes

### The prompt

The skeleton hands your words straight to the model. Its Alice story opens with "Alice had always been a bit of a loner", contains zero lines of dialogue, reaches "But one day, tragedy struck. Bob fell ill" by the middle, and signs off by stating its moral outright. All three of the baseline stories I captured had that same shape. They were also reaching for words like "confidante", "partner in crime" and "an anomaly that seemed to defy the laws of physics", which is nobody's five-year-old, and the endings wound the child up rather than down.

One system prompt fixed most of it in a single call. Dialogue went from 0 to 15 lines, the moralising and the illness both vanished, and the story finished with a mother tucking the child into bed. That prompt is doing more work than everything else in this repo put together, and the rest of it is really a set of filters sitting on top.

### Vague requests

"Tell me a story about space" was the worst of the three baselines by a distance. An adult astronaut, no child in it anywhere, nothing at stake. The specific request, Alice and her cat Bob, gave the best one. That gap never really closed either: later on, with the checks in place, the space request had two of its three drafts thrown out where the Alice request had none.

So intake does not only classify. When there is nothing specific in the request to grab onto, it invents a `hook`, one sentence saying what actually happens, and that goes into the storyteller prompt.

### The judge

The first thing I built was the obvious design, which is to score a story against a rubric, feed the criticism back, rewrite, repeat. Then I measured it, and it does not work on this model.

Scoring gave me nothing to select on. Asked to grade the original Alice story, the one with the sick pet and no dialogue at all, a judge I had explicitly told to be strict came back with safety 5, engagement 5, an empty list of fixes, and the phrase "a heartwarming tale". Forcing it to quote evidence out of the text before it was allowed to score did help, and that story dropped to 2.50 against 3.67 for a good one. But as soon as I handed it three drafts that were genuinely comparable, all three came back at exactly 4.50, two of them with the same complaint attached word for word.

The revision half was worse. Told to fix the sick pet, it changed "tragedy" to "challenge" and left the pet sick. Told the story stated its lesson, it changed "proving that" to "showing that" in the same sentence. Three rounds of that moved a bad story from 3.17 to 3.50 without touching anything structural, and somewhere along the way it introduced a new fault where the narrator started addressing the listener as a character. It was also fairly obviously learning to dodge whichever wording I happened to be checking for, which is a problem in its own right.

Comparison is a much easier question, and it answers that one fine. Put a known-bad draft next to a good one and it picked the good one every time, in both orders. Between two drafts that are close it is roughly a coin flip, which I do not mind, because if they are that close either will do. What I want from it is that the dud never reaches the child.

One thing worth knowing: asked one way round only, it picks whichever draft it saw first 67% of the time. So every pair gets asked both ways, and a challenger only takes the title if it wins both.

### The checks

String matching beat the model twice on plain questions of fact, which is why these run first. The model gave a story containing a sick pet 5 out of 5 for safety, while a regex found "fell ill" and "tragedy" instantly. It also told me a story ending on "proving that sometimes, the best friends come in the most unexpected of packages" did not state a lesson. These checks are free, they are instant, and unlike the model they cannot be talked round.

The model never gets told what they look for. The one time I did tell a revision prompt which words I was checking, it renamed them and left the problem sitting where it was, which is optimising against the check rather than against the fault.

One check I measured and then did not ship: Flesch-Kincaid reading level, to catch the adult vocabulary the baseline kept reaching for. On three stories it looked like a clean win, with the pipeline sitting at 6.06 to 6.59 and the skeleton at 6.67 to 10.49. Widening the sample to eight killed it. Good stories ran from 5.57 all the way to 9.23, and skeleton stories came in as low as 7.03, so the two ranges sit on top of each other and there is no threshold that divides them. The pipeline's high scorers were all space and dinosaurs, where the longest words are "prehistoric" and "exploration", which is exactly the vocabulary a child who asked about dinosaurs already has. Flesch-Kincaid counts syllables, and a child's vocabulary is not syllable length, so it was really measuring the topic. Worth noting that at n=3 I would have shipped it.

They do not get me all the way, though. My first version scanned the whole story for moralising phrases, and it threw out good drafts over an "and so," in the middle of a scene while still missing morals sitting in the final line. Now the scan looks at the last paragraph only, holds nothing but phrases that are almost never innocent, and hands anything subtler to one small model call asking a single yes or no question about that one paragraph. Narrow questions it can handle. Six-part rubrics it cannot.

### Safety

Asked to screen "a story about a war where soldiers fight and die", the model listed war, soldiers and dying as the problems and then set `child_safe: true` in the same response. It also found "romance" in a story about a girl and her cat. So I stopped relying on it to make the call. A word list decides now, and the model's opinion can only add to that, never overrule it. Blunt, but a request is one short sentence, which is about the friendliest case plain string matching ever gets. The model still does the rewriting, which it is genuinely good at.

The rewrite then has to pass the same list. Left to itself it turned "a war where soldiers fight and die" into "soldiers who bravely protect their kingdom from a sorcerer's army", which is still soldiers and still an army. The hook gets screened for the same reason. Asked to invent one for two kingdoms who stop arguing, it offered "on the brink of war".

An unsuitable request is redirected rather than refused. Zombies eating people becomes monsters having a picnic, and a grandmother who died becomes grandma's favourite recipe bringing everyone together. Telling a six-year-old at bedtime that you cannot help with that is the wrong way to fail when there is a good story to be had instead. A refusal only happens at the far end, if every draft written from the softened request still comes back with something upsetting in it, and that case is below.

The story gets screened on the way out too, not just on the way in. The two vocabularies used to be separate, which left a hole: a request for a story about Bob the cat passes intake cleanly, and then "give Bob a gun and send him to war" arrives through the feedback loop and goes straight to the model without ever meeting the intake screen. The revision is now checked against the violent words as well, so it fails the checks, and the listener keeps the story they already had.

That check is not simply the intake list reused. "army" has ants in it and "dead" has leaves, and six test stories turned up "war" twice, both times as tug of war at a school sports day. A false match costs more here than at intake, because five false rejections in a row now means no story at all, so the story-side list holds only the words that are never innocent, with tug of war carved out by name.

### Revision

There is exactly one place a story gets revised, and that is when a person asks for a change. "Make it sillier and give Bob a funny voice" is specific enough that the model does the right thing with it. Criticism the model invents about its own work is not specific, and it does not, which is most of what the judge section above is about.

A revision has to clear the same bar a fresh draft does, and it gets one retry. If neither attempt clears it, the listener keeps the story they already had. Not getting the change you asked for is a smaller failure than being handed something the checks rejected.

### Failing closed

The pipeline would rather read nothing than read something it has already judged unsafe. If all five drafts get thrown out, it falls back to the least bad one, but only from the drafts whose problems were cosmetic. Running short or keeping the characters too quiet makes for a dull story and a dull story is still worth reading. A draft rejected for illness or death is not eligible no matter how few other complaints it had, and if every draft has something like that in it the answer is that there is no story tonight and the child can ask for a different one.

This was not the original behaviour. The first version picked whichever rejected draft had the fewest complaints, which meant a single "upsetting content: died" could beat two harmless notes about length, and a story with a death in it would be read to a five year old because it was technically the tidiest failure. Counting complaints is not the same as weighing them.

## The files

| file | what it does |
| --- | --- |
| `main.py` | command line, printing, the feedback loop |
| `pipeline.py` | the order things happen in |
| `intake.py` | request to brief, and the safety screen |
| `storyteller.py` | category recipes and the prompt that does the real work |
| `checks.py` | free string checks, plus the one narrow model check |
| `judge.py` | picks between drafts by comparison |
| `llm.py` | the only place that calls OpenAI |

Each module opens with whatever finding shaped it.

## Known limitations

Softened requests still give weaker stories than clean ones. Blanking a hook because it contains a blocked word leaves the storyteller with less to work with, and the rewritten premises come out more abstract than whatever the child actually asked for. I do not have a good answer for this yet.

The ending check has partial recall. It got 4 out of 5 on the cases I validated against, so a mild moral does occasionally reach the reader.

The judge confirms the first draft far more often than it changes anything. That is correct when the drafts genuinely tie, but it does mean its 4 calls frequently buy nothing at all.

Drafts are written one after another. Doing them concurrently would cut most of the wait, and it is the first thing I would change.

`--speak` is macOS only. It checks for the `say` binary first and prints a note rather than failing, so nothing breaks anywhere else, but on Linux or Windows the story stays on the page and that part of the idea only arrives through this document. Shelling out to a system voice is what keeps it free and dependency free; not being portable is the price of that.

## How I tested

Everything above came from scripts run against the real API rather than from reading the output and forming an impression: a baseline capture, four experiments on prompting and judging, a discrimination test for the judge, a full run of the revise loop, a best-of-N test, a pairwise test with the positions swapped, and a spread across five kinds of request including some deliberately unsuitable ones. Those were scratch files and they are not part of the submission.

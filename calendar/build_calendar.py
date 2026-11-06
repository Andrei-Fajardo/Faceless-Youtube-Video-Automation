"""Builds calendar/calendar.json and calendar/calendar.md: 30 days (Mon 2 Nov 2026 - Tue 1 Dec 2026), one Short a day and one long-form every Sunday.
POOL holds every planned topic; SCHEDULE (further down) picks which ones go in this month, the rest become the backlog. Edit and re-run:  python calendar/build_calendar.py
Fields per item: title, rule (the ONE idea the script is built on) or hint (what to verify), risk (handle with care), fam (the mechanism the video explains).
No-redundancy gate: every fam must be unique across the whole calendar, the reserve and the videos already made, and no two titles may be near-duplicates.
The build stops with a list of clashes if the gate fails. When you add a topic, give it a new fam; if you cannot, the topic is a repeat.
"""
import json, datetime, pathlib, re, difflib, sys
ROOT = pathlib.Path(__file__).resolve().parent
START = datetime.date(2026, 11, 2)
W, O = "whatif", "odd"
# day, theme, long What If (title, rule, risk, fam), [short, short, short]; a short is (kind, title, rule or hint, risk, fam)
POOL = [
 (2, "Sleep", ("What If You Slept 20 Hours Every Day?", "extra sleep gives no extra rest; waking life shrinks to four hours", "", "sleep: too much"),
  [(W, "What If You Needed Zero Sleep?", "the body stops asking for sleep, the brain still needs it (script drafted)", "", "sleep: none needed"),
   (W, "What If You Could Fall Asleep Instantly?", "falling asleep is a staged handover; instant sleep skips the part that keeps you safe; verify sleep onset stages", "medical adjacent: no advice, sensitive to people with narcolepsy", "sleep: onset"),
   (O, "The Tiny Hole In An Airplane Window", "breather hole: pressure equalising and fog; verify with Boeing or the FAA", "", "odd: airplane breather hole")]),
 (3, "Memory", ("What If You Never Forgot A Face?", "faces yes, names no; super-recognizers are real", "", "memory: face recognition"),
  [(W, "What If Your Memory Was 100x Stronger?", "you cannot choose what stays (script drafted)", "", "memory: total recall"),
   (W, "What If You Could Forget On Purpose?", "trying not to think of something brings it back; forgetting is not a delete key; verify the suppression studies", "", "memory: deliberate forgetting"),
   (O, "Why Phone Numbers Come In Chunks", "memory span and chunking; verify Miller and Cowan", "", "odd: phone number chunks")]),
 (4, "Speed", ("What If You Could Jump 10x Higher?", "your legs launch you, the landing is the problem", "", "motion: jump height"),
  [(W, "What If You Could Read 10x Faster?", "eyes speed up, understanding and memory do not", "", "speed: reading"),
   (W, "What If Your Reflexes Were 100x Faster?", "nerves and muscles cannot keep up with the brain", "", "speed: reflexes"),
   (O, "The Crosswalk Button That May Do Nothing", "verify which crossing buttons are disabled and by whom", "", "odd: crosswalk button")]),
 (5, "Breath and heart", ("What If You Could Hold Your Breath One Hour?", "carbon dioxide, not oxygen, forces the next breath; warn about blackout", "dangerous activity: frame as a warning", "breath: holding"),
  [(W, "What If Breathing Was Not Automatic?", "a real rare condition (congenital central hypoventilation): the body forgets to breathe in sleep; verify", "medical: real patients, no advice", "breath: automatic control"),
   (W, "What If Your Heart Beat 10x Faster?", "the chambers need time to fill", "", "heart: rate"),
   (O, "The Bumps On The F And J Keys", "homing bumps for touch typing; verify the origin", "", "odd: F and J bumps")]),
 (6, "Sight", ("What If Your Eyesight Was 100x Sharper?", "optics and light set the limit, not the retina", "", "sight: sharpness"),
  [(W, "What If You Had Perfect Night Vision?", "rods give sharp dim vision but no colour", "", "sight: night vision"),
   (W, "What If You Could See Heat Like A Snake?", "pit organs and infrared; what warm things look like", "", "sight: infrared"),
   (O, "Why All Your Cards Are The Same Size", "ISO/IEC 7810 ID-1, 85.6 by 54 mm; verify the history before telling any origin story", "", "odd: card size")]),
 (7, "Hearing, smell, taste", ("What If Your Hearing Was 50x Better?", "you would hear your own blood and breath all day; verify the hearing thresholds", "", "hearing: sensitivity"),
  [(W, "What If Your Nose Was 100x Stronger?", "smell is wired to memory; the world floods in", "", "smell: memory link"),
   (W, "What If You Were A Supertaster?", "a real trait (more taste buds): bitter foods taste harsher; verify the share of people", "", "taste: supertaster"),
   (O, "Why Stop Signs Are Octagons", "verify the history of the shape", "", "odd: stop sign octagon")]),
 (8, "Touch and pain", ("What If You Felt Zero Pain?", "pain is a warning system; real rare conditions show the cost", "medical topic: no advice, sensitive to people with the condition", "touch: no pain"),
  [(W, "What If You Had No Fingerprints?", "a real rare condition (adermatoglyphia); what fingerprints do for grip and touch is debated, tell as debated", "real people: rare condition", "touch: fingerprints"),
   (W, "What If You Never Got Goosebumps?", "a leftover fur-raising reflex that does little on a hairless body; verify", "", "touch: goosebumps"),
   (O, "Why Ambulance Lettering Is Backwards", "mirror writing so drivers read it in the rear-view mirror; verify the origin", "", "odd: ambulance mirror lettering")]),
 (9, "Strength", ("What If Your Bones Were 10x Stronger?", "bones hold, tendons, joints and organs do not", "", "strength: bones"),
  [(W, "What If You Could Grip Like A Gecko?", "toe-pad adhesion works by tiny forces; at human weight the pads would need a huge area; verify the estimates", "", "strength: adhesion"),
   (W, "What If You Could Punch Like A Mantis Shrimp?", "speed and collapsing bubbles; a human arm cannot store that spring; verify", "", "strength: punch speed"),
   (O, "Why SOS Is Not An Abbreviation", "a Morse pattern, not initials; verify", "", "odd: SOS")]),
 (10, "Healing and body repair", ("What If Your Body Healed 10x Faster?", "scars, bones and cancer risk: fast healing is not free", "", "repair: healing speed"),
  [(W, "What If Your Immune System Was 10x Stronger?", "an over-eager immune system attacks you", "", "repair: immune strength"),
   (W, "What If Your Teeth Grew Back Forever?", "humans get two sets, sharks replace endlessly; what a third set would take; verify", "", "repair: tooth replacement"),
   (O, "Why Clocks Say AM And PM", "Latin ante and post meridiem; verify", "", "odd: AM and PM")]),
 (11, "Thinking", ("What If You Had 1,000 IQ?", "the IQ scale does not work that way; what changes and what does not", "", "mind: IQ scale"),
  [(W, "What If Your Brain Learned 10x Faster?", "learning needs sleep and repetition to stick", "", "mind: learning speed"),
   (W, "What If You Had No Inner Voice?", "people differ in how much they think in words; tell as varied, not as a disorder; verify", "", "mind: inner voice"),
   (O, "Why An Hour Has 60 Minutes", "Babylonian base 60; verify", "", "odd: sixty minutes")]),
 (12, "Days and time", ("What If Your Day Had 48 Hours?", "body clocks are set to about 24 hours; verify the long-day experiments", "", "time: body clock length"),
  [(W, "What If You Could Feel The Earth Spinning?", "you already move about 1,670 km/h at the equator; bodies feel changes in speed, not speed", "", "time: earth rotation"),
   (W, "What If You Had A Perfect Internal Stopwatch?", "people are poor at timing and drift with mood; verify", "", "time: interval timing"),
   (O, "Why There Are Seven Days In A Week", "Babylonian and planetary origins; verify", "", "odd: seven-day week")]),
 (13, "Emotions", ("What If Your Emotions Were 10x Stronger?", "feelings guide decisions; louder is not wiser", "mental-health adjacent: no advice", "emotion: intensity"),
  [(W, "What If You Could Never Feel Embarrassed?", "embarrassment is social glue; verify the research", "", "emotion: embarrassment"),
   (W, "What If You Had Zero Fear?", "fear protects; real rare cases exist", "sensitive: real patients", "emotion: fear"),
   (O, "Why A Baker's Dozen Is Thirteen", "medieval bread law; verify", "", "odd: baker's dozen")]),
 (14, "Food and energy", ("What If You Needed 10x Less Food?", "the brain uses a fifth of your energy", "", "energy: food need"),
  [(W, "What If You Could Digest Grass?", "cellulose needs fermenting microbes; how a cow's stomach does it", "", "energy: digesting cellulose"),
   (W, "What If You Could Drink Seawater?", "kidneys cannot make urine saltier than seawater; frame as physics, never as advice", "dangerous: no advice", "energy: salt and kidneys"),
   (O, "Why Bluetooth Is Named After A King", "Harald Bluetooth; verify", "", "odd: Bluetooth")]),
 (15, "Temperature", ("What If Your Body Ran 10 Degrees Colder?", "enzymes slow, thinking slows", "", "temp: body temperature"),
  [(W, "What If You Could Survive 100 Degrees?", "dry heat tolerance and sweat; sauna records", "", "temp: heat survival"),
   (W, "What If You Never Got A Fever?", "fever slows germs and speeds defences; verify", "medical adjacent: no advice", "temp: fever"),
   (O, "Why A Computer Mouse Is Called A Mouse", "Engelbart's team; verify", "", "odd: computer mouse name")]),
 (16, "Voice and hands", ("What If Your Voice Was 10x Louder?", "decibels are not linear; damage to others and yourself", "", "voice: loudness"),
  [(W, "What If Your Hands Were 10x More Precise?", "surgeons and shaking; limits of nerves", "", "hands: precision"),
   (W, "What If You Could Mimic Any Voice?", "the shape of your throat and mouth sets your sound; impressionists and lyrebirds; verify", "", "voice: mimicry"),
   (O, "The Moth Behind The Word Computer Bug", "Grace Hopper's moth and the older engineering term; tell it as nuanced", "", "odd: computer bug")]),
 (17, "Weight", ("What If You Weighed 10x Less?", "walking, throwing and falling on a light body", "", "weight: lighter"),
  [(W, "What If You Had A Tail?", "the tailbone is a real remnant; a tail would change balance; verify", "", "body plan: tail"),
   (W, "What If You Could Fall From Any Height?", "terminal velocity; why landing is the issue", "dangerous: frame as physics", "weight: terminal velocity"),
   (O, "Why Jeans Have Metal Rivets", "Jacob Davis and Levi Strauss, 1873; verify", "", "odd: jeans rivets")]),
 (18, "Size and shape", ("What If You Were 10 Times Taller?", "the square-cube law: bones cannot carry it", "", "size: square-cube law"),
  [(W, "What If Your Eyes Were On The Sides Of Your Head?", "horses see nearly all around but lose depth; verify", "", "sight: panoramic eyes"),
   (W, "What If You Had Four Arms?", "the brain maps limbs; extra-limb studies; verify", "", "body plan: extra arms"),
   (O, "Why Pen Caps Have A Hole", "the hole lets air through if a cap is swallowed; verify the standard", "", "odd: pen cap hole")]),
 (19, "Movement", ("What If You Could Run 100 Kilometers Per Hour?", "joints, heat and air resistance", "", "motion: running speed"),
  [(W, "What If You Could Fly By Flapping Your Arms?", "wing area and chest muscle; human-powered aircraft; verify", "", "motion: flapping flight"),
   (W, "What If You Could Walk On Water?", "basilisk lizards run across it; the speed needed is far beyond a human; verify", "", "motion: water running"),
   (O, "Why Post-it Notes Are Yellow", "3M's story; verify", "", "odd: Post-it yellow")]),
 (20, "Air and gravity", ("What If You Could Breathe Underwater?", "oxygen in water is scarce; pressure at depth", "", "air: dissolved oxygen"),
  [(W, "What If You Lived Without Gravity For A Year?", "real astronaut bone and muscle loss", "", "gravity: none for a year"),
   (W, "What If You Lived On The Top Of Everest?", "the thin air; Sherpa and Tibetan adaptations; verify", "", "air: altitude"),
   (O, "Why The Power Symbol Is A Circle And A Line", "0 and 1 combined; verify IEC", "", "odd: power symbol")]),
 (21, "Dreams and the mind", ("What If You Controlled Every Dream?", "lucid dreaming is real; control has limits", "", "dream: lucid control"),
  [(W, "What If Every Moment Felt Like Deja Vu?", "a real rare experience (deja vecu); verify", "medical adjacent: no advice", "memory: deja vu"),
   (W, "What If You Had A Second Brain In Your Gut?", "the gut's nerve network is real; avoid the popular exaggerations; verify", "", "body: gut nervous system"),
   (O, "Why Paper Is A4", "ISO 216 and the square-root-of-two ratio", "", "odd: A4 paper")]),
 (22, "Attention", ("What If Your Attention Span Was 10x Longer?", "what attention costs the brain", "", "attention: span"),
  [(W, "What If You Could Hear Only One Voice In A Crowd?", "the cocktail party effect; verify", "", "attention: selective hearing"),
   (W, "What If You Used 100 Percent Of Your Brain?", "the ten percent idea is a myth; tell the myth carefully", "", "mind: ten percent myth"),
   (O, "Why Keyboards Are Not In Alphabet Order", "QWERTY history; tell the myth carefully", "", "odd: QWERTY")]),
 (23, "People", ("What If You Could Read Faces Perfectly?", "micro-expressions are weaker evidence than people think", "", "people: reading faces"),
  [(W, "What If You Could Talk To Animals?", "honeybee dances, dolphin names; what is proven; verify", "", "people: animal communication"),
   (W, "What If You Spoke 10 Languages Instantly?", "knowing words is not understanding people", "", "people: languages"),
   (O, "Why Screws Turn Clockwise To Tighten", "right-handed mechanics; verify, tell as contested", "", "odd: clockwise screws")]),
 (24, "Stress and boredom", ("What If You Never Felt Stress?", "stress hormones help you in danger", "mental-health adjacent: no advice", "emotion: stress"),
  [(W, "What If You Never Yawned?", "why we yawn is debated (cooling, contagion); tell as debated", "", "body: yawning"),
   (W, "What If You Never Got Bored?", "boredom drives curiosity", "", "emotion: boredom"),
   (O, "Why Batteries Are Called AA", "sizing history; verify", "", "odd: AA batteries")]),
 (25, "Hair, nails, skin", ("What If Your Hair Grew 10x Faster?", "daily haircuts and heat loss", "", "skin: hair growth"),
  [(W, "What If Your Skin Changed Color Like An Octopus?", "chromatophores; what humans lack; verify", "", "skin: colour change"),
   (W, "What If You Could Shed Your Skin Like A Snake?", "you already shed the top layer of skin cells all day; verify", "", "skin: shedding"),
   (O, "Why USB Plugs Take Three Tries", "the design of the old connector and the fix", "", "odd: USB orientation")]),
 (26, "Balance and space", ("What If Your Balance Was 100x Better?", "the inner ear; limits of the rest of the body", "", "space: balance"),
  [(W, "What If You Never Got Lost Again?", "the brain's navigation cells; what you would lose", "", "space: navigation"),
   (W, "What If You Could Sense Magnetic Fields?", "birds do; humans are contested; tell as contested", "", "space: magnetic sense"),
   (O, "Where The @ Sign Came From", "verify the earliest uses", "", "odd: at sign")]),
 (27, "Blood and heart", ("What If You Had Two Hearts?", "octopus hearts; what a second heart would pump", "", "heart: second heart"),
  [(W, "What If Your Blood Never Clotted?", "clotting also saves your life", "medical topic: no advice", "blood: clotting"),
   (W, "What If Everyone Had The Same Blood Type?", "ABO types and Landsteiner, 1901; why transfusions need matching; verify", "", "blood: blood types"),
   (O, "What The Hash Sign Is Really Called", "octothorpe; verify", "", "odd: hash sign")]),
 (28, "Lifespan", ("What If You Lived To 200?", "cells, savings, relationships", "", "life: lifespan"),
  [(W, "What If You Remembered Being A Baby?", "childhood amnesia; why early memories do not stay; verify", "", "memory: childhood amnesia"),
   (W, "What If You Could Photosynthesize?", "skin area times sunlight gives a tiny fraction of your energy; do the sums from sources", "", "energy: photosynthesis"),
   (O, "Why We Say Hello On The Phone", "Edison and Bell; verify", "", "odd: hello")]),
 (29, "Sound", ("What If You Had Perfect Pitch?", "real, rare, and sometimes annoying", "", "sound: perfect pitch"),
  [(W, "What If You Could Hear Colors?", "synesthesia is real; what it feels like", "", "senses: synesthesia"),
   (W, "What If You Could Hear 10x Higher Notes?", "bats and dogs; what ultrasound sounds like", "", "hearing: ultrasound range"),
   (O, "Why The Red Light Is On Top", "traffic light history; verify", "", "odd: traffic light order")]),
 (30, "Finale", ("What If You Could See With Sound?", "echolocation is real and learnable; the brain repurposes its visual areas; verify", "", "senses: echolocation"),
  [(W, "What If Your Ears Could Move Like A Cat's?", "ear muscles are a human remnant; some people can wiggle them; verify", "", "body plan: moving ears"),
   (W, "What If You Could Always See Your Own Nose?", "it is always in view and your brain edits it out; verify", "", "sight: nose blindness"),
   (O, "Why SD Cards Have A Clipped Corner", "orientation and the standard; verify", "", "odd: SD card corner")]),
]
RESERVE = [  # same gate: every fam is unique across the calendar too
 (W, "What If You Could Tickle Yourself?", "the brain predicts its own touch and cancels it; verify", "", "touch: self-tickle"),
 (W, "What If You Were Ambidextrous?", "handedness and the brain; verify", "", "body: handedness"),
 (W, "What If You Could Smell Fear?", "chemical signals in sweat; what is and is not proven; tell as contested", "", "smell: fear signals"),
 (W, "What If Your Eyes Were Two Different Colors?", "heterochromia; what causes it; verify", "", "sight: eye colour"),
 (O, "Why Elevator Buttons Are Numbered Like That", "verify the standard", "", "odd: elevator buttons"),
 (O, "Why Hospital Scrubs Are Green Or Blue", "contrast and red fatigue; verify", "", "odd: scrub colour"),
 (O, "Why Clocks Run Clockwise", "sundials in the northern hemisphere; verify", "", "odd: clockwise clocks"),
 (O, "Why We Say 'Break A Leg'", "contested origins; tell as contested", "", "odd: break a leg"),
 (O, "Why Coins Have Ridged Edges", "anti-clipping edges; verify", "", "odd: coin edges"),
 (O, "Why Shirt Buttons Switch Sides", "men's and women's shirts; the origin is contested; tell as contested", "", "odd: shirt buttons"),
 (O, "Why Plugs Have One Wider Prong", "polarised plugs and safety; verify", "", "odd: polarised plug"),
 (O, "Why A Foot Has Twelve Inches", "units and base twelve; verify", "", "odd: twelve inches"),
]
MADE = {  # already produced: title -> (folder, fam, format)
 "What If One Nap Felt Like A Week?": ("finished/what-if/one-nap-a-week", "time: nap time distortion", W),
 "Your Phone And Calculator Disagree": ("finished/odd-detail-js/the-keypad", "odd: keypad layouts", O),
 "What If You Saw 100x More Colors?": ("finished/what-if/seeing-100x-colors", "sight: more colours", W),
 "What If Half Your Brain Never Slept?": ("finished/what-if/half-brain-never-slept", "sleep: half-brain (dolphin)", W),
}
# The month plan is sized to the ElevenLabs free plan (30,000 characters a month; 26,634 were left on 1 Nov): one Short every day (3 already made)
# and one long every Sunday (half-brain already made). New voice need: 3 longs x ~1,550 + 27 Shorts x at most 650 = about 22,200 characters,
# which leaves about 4,400 for retakes. Topics were picked for the widest appeal (everyday curiosity, survival, body limits, objects people use daily).
# Posting slots (Manila time, see the posting calendar): Shorts 3:00 AM daily, long-form Sunday 11:00 PM.
SCHEDULE = [  # day 1 .. 30 (Mon 2 Nov .. Tue 1 Dec): (Short title, long title or None). A long is only allowed on a Sunday.
 ("What If One Nap Felt Like A Week?", None),
 ("Your Phone And Calculator Disagree", None),
 ("What If You Saw 100x More Colors?", None),
 ("What If You Needed Zero Sleep?", None),
 ("The Tiny Hole In An Airplane Window", None),
 ("What If You Could Jump 10x Higher?", None),
 ("What If Your Memory Was 100x Stronger?", "What If Half Your Brain Never Slept?"),
 ("The Crosswalk Button That May Do Nothing", None),
 ("What If You Could Hold Your Breath One Hour?", None),
 ("Why USB Plugs Take Three Tries", None),
 ("What If You Felt Zero Pain?", None),
 ("What If You Could Fall From Any Height?", None),
 ("Why Ambulance Lettering Is Backwards", None),
 ("What If You Could Talk To Animals?", "What If You Lived To 200?"),
 ("What If You Lived Without Gravity For A Year?", None),
 ("Why Pen Caps Have A Hole", None),
 ("What If You Could Read 10x Faster?", None),
 ("What If Your Reflexes Were 100x Faster?", None),
 ("Why Keyboards Are Not In Alphabet Order", None),
 ("What If You Could Run 100 Kilometers Per Hour?", None),
 ("What If You Used 100 Percent Of Your Brain?", "What If You Had 1,000 IQ?"),
 ("Why Stop Signs Are Octagons", None),
 ("What If You Never Forgot A Face?", None),
 ("What If You Had Zero Fear?", None),
 ("Why Bluetooth Is Named After A King", None),
 ("What If You Could Survive 100 Degrees?", None),
 ("Where The @ Sign Came From", None),
 ("What If You Could Fly By Flapping Your Arms?", "What If You Could Breathe Underwater?"),
 ("Why We Say Hello On The Phone", None),
 ("What If You Could See Heat Like A Snake?", None),
]
def slug(t): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t.lower())).strip("-")[:48]
def core(t):   # the subject of a title, without the shared template wording ("Was 100x Stronger")
    t = re.sub(r"^(what if (you|your)|why|the|where|what)\s+", "", t.lower().replace("'", ""))
    return re.sub(r"\b(was|were|is|are|could|had|felt|grew|ran|\d[\d,]*x?|times|stronger|better|faster|sharper|louder|longer|higher|more|less|10|100|50)\b", " ", t).replace("  ", " ").strip(" ?")

# every topic ever planned: title -> (format, rule, risk, fam)
pool = {}
for _, _, lng, shorts in POOL:
    pool[lng[0]] = (W, lng[1], lng[2], lng[3])
    for fmt, title, rule, risk, fam in shorts: pool[title] = (fmt, rule, risk, fam)
used = [t for pair in SCHEDULE for t in pair if t]
bad = [t for t in used if t not in pool and t not in MADE]
if bad: sys.exit("STOP: scheduled titles that are in neither the pool nor the made list: " + "; ".join(bad))
BACKLOG = [t for t in pool if t not in used]   # planned, not scheduled this month: later months, or swap-ins

# ---- the no-redundancy gate (made, scheduled, backlog and reserve all count) ----
fam_of = lambda t: MADE[t][1] if t in MADE else pool[t][3]
entries = [(f"D{n:02d}", t, fam_of(t)) for n, pair in enumerate(SCHEDULE, 1) for t in pair if t]
entries += [(f"B{i + 1:02d}", t, pool[t][3]) for i, t in enumerate(BACKLOG)]
entries += [(f"R{i + 1:02d}", r[1], r[4]) for i, r in enumerate(RESERVE)]
problems, seen = [], {}
if len(set(used)) != len(used): problems.append("a title is scheduled twice")
for i, t, f in entries:
    if f in seen: problems.append(f"same family '{f}': {seen[f]} and {i} ({t})")
    seen[f] = i
for a in range(len(entries)):
    for b in range(a + 1, len(entries)):
        r = difflib.SequenceMatcher(None, core(entries[a][1]), core(entries[b][1])).ratio()
        if r >= 0.8 or slug(entries[a][1]) == slug(entries[b][1]): problems.append(f"near-duplicate titles ({r:.2f}): {entries[a][0]} '{entries[a][1]}' and {entries[b][0]} '{entries[b][1]}'")
if problems: sys.exit("STOP: redundancy found:\n  " + "\n  ".join(problems))

def item(id_, kind, title, slot):
    if title in MADE: path, fam, fmt = MADE[title]; rule, risk, made = "", "", path
    else: fmt, rule, risk, fam = pool[title]; made = None
    d = {"id": id_, "kind": kind, "format": fmt, "title": title, "rule": rule, "risk": risk, "family": fam, "slug": made.split("/")[-1] if made else slug(title), "slot": slot, "status": "made" if made else "todo"}
    if made: d["path"] = made
    return d
days = []
for n, (short, lng) in enumerate(SCHEDULE, 1):
    date = START + datetime.timedelta(days=n - 1)
    if lng and date.weekday() != 6: sys.exit(f"STOP: a long is scheduled on day {n} which is a {date.strftime('%A')}, not a Sunday")
    items = ([item(f"D{n:02d}-L", "long", lng, "Sun 11:00 PM Manila")] if lng else []) + [item(f"D{n:02d}-S1", "short", short, "3:00 AM Manila")]
    days.append({"day": n, "date": date.isoformat(), "weekday": date.strftime("%a"), "theme": "Long-form day and a Short" if lng else "Short", "items": items})
def extra(prefix, titles, status):
    out = []
    for i, t in enumerate(titles, 1):
        fmt, rule, risk, fam = pool[t] if t in pool else (None, "", "", "")
        out.append({"id": f"{prefix}{i:02d}", "kind": "short", "format": fmt, "title": t, "rule": rule, "risk": risk, "family": fam, "slug": slug(t), "status": status})
    return out
backlog = extra("B", BACKLOG, "backlog")
reserve = [{"id": f"R{i + 1:02d}", "kind": "short", "format": f, "title": t, "rule": r, "risk": k, "family": fam, "slug": slug(t), "status": "reserve"} for i, (f, t, r, k, fam) in enumerate(RESERVE)]
json.dump({"start": START.isoformat(), "days": days, "reserve": reserve, "backlog": backlog}, open(ROOT / "calendar.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
n_long = sum(1 for d in days for i in d["items"] if i["kind"] == "long"); n_short = sum(1 for d in days for i in d["items"] if i["kind"] == "short")
n_new_long = sum(1 for d in days for i in d["items"] if i["kind"] == "long" and i["status"] == "todo"); n_new_short = sum(1 for d in days for i in d["items"] if i["kind"] == "short" and i["status"] == "todo")
need = n_new_long * 1550 + n_new_short * 650
md = ["# Curio production and posting calendar (30 days: 1 Short a day, 1 long-form every Sunday)", "",
      "Produce any item with `/produce <day>` (that day's long and Short), `/produce <day> long`, `/produce <day> short 1`, or `/produce next`.",
      "Posting slots (Manila time): Short at 3:00 AM every day; long-form on Sunday at 11:00 PM. Schedule each upload the day before in YouTube Studio. Nothing is uploaded for you.", "",
      f"**Sized to the voice budget.** The ElevenLabs free plan allows 30,000 characters a month and 26,634 were left on 1 Nov. This plan has {n_long} long-form and {n_short} Shorts; {n_new_long} longs (about 1,550 characters each) and {n_new_short} new Shorts (keep each to 650 characters or fewer) need about {need:,} characters, leaving about {26634 - need:,} for retakes. Check `python tools/produce.py budget` before each item.",
      f"**No-redundancy gate.** All {len(entries) + len(MADE)} topics (made, scheduled, backlog and reserve) have a different family (the mechanism each one explains) and no two titles are near-duplicates; `python calendar/build_calendar.py` fails otherwise.",
      "Topics were picked for the widest appeal first: everyday curiosity, survival, the limits of the body, and objects people use daily. `B##` is the backlog for later months, `R##` are reserves if research fails; swap one in with `python tools/produce.py swap <id> <B##|R##>`.", "",
      "| Day | Date | Long-form (Sun 11 PM) | Short (3 AM) | Format | Risk |", "|---|---|---|---|---|---|"]
for d in days:
    sh = next(i for i in d["items"] if i["kind"] == "short"); lg = next((i for i in d["items"] if i["kind"] == "long"), None)
    mark = lambda i: f"{i['title']}" + (" (made)" if i["status"] == "made" else "")
    risk = "; ".join(f"{i['id']}: {i['risk']}" for i in d["items"] if i["risk"])
    md.append(f"| {d['day']} | {d['weekday']} {d['date'][5:]} | {mark(lg) if lg else ''} | {mark(sh)} | {'What If' if sh['format'] == 'whatif' else 'Odd Detail'} | {risk} |")
md += ["", "## The idea behind each item", "", "| Item | Title | Premise (the one rule) or what to verify | Risk |", "|---|---|---|---|"]
for d in days:
    for i in d["items"]:
        if i["status"] != "made": md.append(f"| {i['id']} | {i['title']} | {i['rule']} | {i['risk']} |")
md += ["", "## Backlog (later months)", "", "| Item | Title | Premise | Risk |", "|---|---|---|---|"] + [f"| {r['id']} | {r['title']} | {r['rule']} | {r['risk']} |" for r in backlog]
md += ["", "## Reserve (swap in if research fails)", "", "| Item | Title | Note | Risk |", "|---|---|---|---|"] + [f"| {r['id']} | {r['title']} | {r['rule']} | {r['risk']} |" for r in reserve]
open(ROOT / "calendar.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
sp = ROOT / "status.json"
if not sp.exists(): json.dump({i["id"]: {"status": "made", "path": i["path"]} for d in days for i in d["items"] if i["status"] == "made"}, open(sp, "w", encoding="utf-8"), indent=1)
print(len(days), "days,", n_long, "longs,", n_short, "Shorts,", len(backlog), "backlog,", len(reserve), f"reserve; new voice need about {need} of 26,634 characters; redundancy gate passed over", len(entries) + len(MADE), "topics")

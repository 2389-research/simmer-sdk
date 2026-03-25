You extract hobby entities from miniature painting video transcripts into JSON.

TYPE TAXONOMY — CLOSED SET (the ONLY valid types are these 14, do NOT invent new types):
- technique: painting methods ("non-metallic metal", "wet blend", "edge highlight", "glazing", "outlining", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "feathering", "loaded brush", "two-brush blend", "slapchop", "sketch style")
- paint: specific paint products ("rhinox hide", "mephiston red", "nuln oil", "agrax earthshade", "skeleton horde", "leadbelcher")
- brand: manufacturers ("vallejo", "citadel", "army painter", "ak interactive", "scale75", "monument hobbies", "kimera")
- tool: physical instruments ("airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "sponge", "brush")
- material: supplies and mediums ("contrast paint", "oil paint", "texture paste", "primer", "varnish", "flow improver", "matte medium", "speed paint", "ink")
- model: miniature kits ("hive tyrant", "intercessor", "imperial knight", "plague marine")
- faction: army names ("stormcast eternals", "death guard", "tyranids", "space marines")
- game_system: game names ("warhammer 40k", "age of sigmar", "kill team")
- color: compound color references NOT tied to a product ("dark brown", "warm gold", "cold gold", "cool blue", "off-white", "orange", "black")
- concept: painting theory and abstract ideas ("color temperature", "contrast", "focal point", "light placement", "reflection placement", "color theory", "value sketch", "saturation", "hue shifting", "panel lining")
- body_area: parts of a miniature ("face", "cloak", "pauldron", "base", "sword blade", "skin", "armor trim")
- aesthetic: visual style, look, OR difficulty level ("grimdark", "parade ready", "tabletop standard", "display quality", "high contrast", "eavy metal", "intermediate", "advanced", "beginner")
- person: named painters or YouTubers ("trovarion", "squidmar", "miniac", "dana howl", "darren latham")
- topic: tutorial subject or theme ("nmm gold", "painting faces", "basing", "weathering vehicles", "osl lighting", "display piece", "batch painting")

If an entity does not clearly fit one of these 14 types, DROP it.

EXTRACTION RULES:
1. Extract every hobby-relevant entity. Multi-word concepts are ONE entity: "warm gold", "cold gold", "non-metallic metal", "edge highlight", "wet palette", "skin tone" — never split them.
2. Extract discourse-level entities — GOAL, CONTEXT, DIFFICULTY, AESTHETIC. Common words ARE entities when they name a hobby concept:

KEEP vs DROP (learn from these):
- "intermediate" → KEEP as {{"name": "intermediate", "type": "aesthetic"}} — names a difficulty level
- "somewhat difficult" → DROP — paraphrase, not a named level
- "high contrast" → KEEP as {{"name": "high contrast", "type": "aesthetic"}} — names a visual style
- "very contrasted" → DROP — description, not a named style
- "display piece" → KEEP as {{"name": "display piece", "type": "topic"}} — names a project category
- "really nice model" → DROP — opinion, not a category
- "color temperature" → KEEP as {{"name": "color temperature", "type": "concept"}} — names a painting theory concept
- "the colors look warm" → DROP — casual observation
- "warm gold" / "cold gold" → KEEP as color — compound color terms used in NMM
- "orange" → KEEP as {{"name": "orange", "type": "color"}} — names a specific color
- "gold" alone, "yellow" alone, "white" alone, "warm" alone, "cold" alone → DROP — too generic
- "glazing" mentioned in passing ("a quick glazing pass") → KEEP as {{"name": "glazing", "type": "technique"}} — it names a method even briefly
- "outlining" → KEEP as {{"name": "outlining", "type": "technique"}} — it names a method

3. No duplicates. Each entity appears only ONCE.

DO NOT extract:
- Studio/filming/personal anecdotes, YouTube/Patreon/social media references
- Non-hobby objects (furniture, pets, food)
- Standalone generic words: "painting", "color", "gold", "yellow", "white", "warm", "cold"
- Sentence fragments: "broad side of the brush", "darkest spot", "darkest areas", "upper edges"

WORKED EXAMPLE 1:
Transcript: "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold on the pauldron. Grab an old brush and some orange for the midtones. This is a grimdark style approach."
Output:
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}, {{"name": "nmm gold", "type": "topic"}}, {{"name": "pauldron", "type": "body_area"}}, {{"name": "brush", "type": "tool"}}, {{"name": "orange", "type": "color"}}, {{"name": "grimdark", "type": "aesthetic"}}]}}

WORKED EXAMPLE 2:
Transcript: "For the skin tone I'm focusing on color temperature, keeping the shadows cool and the highlights warm. This reflection placement technique is something trovar ian does really well. I'd add some glazing on the warm gold areas. This is definitely an intermediate level display piece with high contrast."
Output:
{{"entities": [{{"name": "skin tone", "type": "body_area"}}, {{"name": "color temperature", "type": "concept"}}, {{"name": "reflection placement", "type": "concept"}}, {{"name": "trovarion", "type": "person"}}, {{"name": "glazing", "type": "technique"}}, {{"name": "warm gold", "type": "color"}}, {{"name": "intermediate", "type": "aesthetic"}}, {{"name": "display piece", "type": "topic"}}, {{"name": "high contrast", "type": "aesthetic"}}]}}

CAPTION CORRECTION — scan every entity and apply before output:
"mephisto red" or "mefist on red" → "mephiston red"
"chris baron" or "trova ryan" or "trovar ian" → "trovarion"
"rhine oxide" or "rhino hide" or "rhino ox hide" → "rhinox hide"
"nonmetallic metal" or "non metallic metal" → "non-metallic metal"
"nolan oil" or "nolin oil" → "nuln oil"
"agra x earth shade" or "agrax earth" → "agrax earthshade"
"wraith bone" or "rate bone" → "wraithbone"
"mac rag blue" or "macrag" → "macragge blue"
"led belcher" or "lead belcher" → "leadbelcher"
"retributor armor" or "retributor" → "retributor armour"
"corrects white" → "corax white"
"a bad on black" → "abaddon black"
"mini ac" → "miniac"
"squid mar" or "squid more" → "squidmar"
"zenit all" or "zenith all" → "zenithal"
If a word sounds like a known hobby term, use the known spelling.

Return ONLY valid JSON, no other text:
{{"entities": [{{"name": "entity name lowercase", "type": "type_from_taxonomy"}}, ...]}}

Transcript:
{chunk_text}
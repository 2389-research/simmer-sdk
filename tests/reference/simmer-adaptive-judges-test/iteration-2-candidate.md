You extract hobby entities from miniature painting video transcripts into JSON.

TYPE TAXONOMY (assign exactly one to each entity):
- technique: painting methods ("non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "feathering", "loaded brush", "two-brush blend", "slapchop", "sketch style")
- paint: specific paint products ("rhinox hide", "mephiston red", "nuln oil", "agrax earthshade", "skeleton horde", "leadbelcher")
- brand: manufacturers ("vallejo", "citadel", "army painter", "ak interactive", "scale75", "monument hobbies", "kimera")
- tool: physical instruments ("airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "sponge")
- material: supplies and mediums ("contrast paint", "oil paint", "texture paste", "primer", "varnish", "flow improver", "matte medium", "speed paint", "ink")
- model: miniature kits ("hive tyrant", "intercessor", "imperial knight", "plague marine")
- faction: army names ("stormcast eternals", "death guard", "tyranids", "space marines")
- game_system: game names ("warhammer 40k", "age of sigmar", "kill team")
- color: color references NOT tied to a product name ("dark brown", "warm gold", "cool blue", "off-white")
- concept: painting theory and abstract ideas ("color temperature", "contrast", "focal point", "light placement", "reflection placement", "color theory", "value sketch", "saturation", "hue shifting", "panel lining")
- body_area: parts of a miniature ("face", "cloak", "pauldron", "base", "sword blade", "skin", "armor trim")
- aesthetic: visual style or look ("grimdark", "parade ready", "tabletop standard", "display quality", "high contrast", "eavy metal")
- person: named painters or YouTubers ("trovarion", "squidmar", "miniac", "dana howl", "darren latham")
- topic: tutorial subject or theme ("nmm gold", "painting faces", "basing", "weathering vehicles", "osl lighting", "display piece")

EXTRACTION RULES:
1. Extract every hobby-relevant entity from the transcript. Each entity MUST have a valid type from the taxonomy above. If you cannot assign a type, DROP it.
2. Multi-word concepts are ONE entity: "warm gold", "non-metallic metal", "edge highlight", "wet palette", "batch painting", "skin tone" — never split them.
3. Extract discourse-level entities — things describing the GOAL, CONTEXT, DIFFICULTY, or AESTHETIC of what's being painted. Examples:
   - "This is more of an intermediate technique" → {{"name": "intermediate", "type": "aesthetic"}}
   - "We're going for high contrast here" → {{"name": "high contrast", "type": "aesthetic"}}
   - "Color temperature is key for skin" → {{"name": "color temperature", "type": "concept"}}
   - "This is a display piece" → {{"name": "display piece", "type": "topic"}}
   - "I'll place reflections on the upper curve" → {{"name": "reflection placement", "type": "concept"}}
4. No duplicates — each entity appears only ONCE.

DO NOT extract:
- Studio/filming/personal anecdotes, YouTube/Patreon/social media references
- Non-hobby objects (furniture, pets, food)
- Generic single words: "painting" alone, "color" alone, "brush" alone
- Sentence fragments or descriptive phrases that aren't hobby terms ("broad side of the brush", "darkest spot", "upper edges")

WORKED EXAMPLE 1:
Transcript: "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold on the pauldron. This is a grimdark style approach."
Output:
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}, {{"name": "nmm gold", "type": "topic"}}, {{"name": "pauldron", "type": "body_area"}}, {{"name": "grimdark", "type": "aesthetic"}}]}}

WORKED EXAMPLE 2:
Transcript: "For the skin tone I'm focusing on color temperature, keeping the shadows cool and the highlights warm. This reflection placement technique is something trovar ian does really well. This is definitely an intermediate level display piece with high contrast."
Output:
{{"entities": [{{"name": "skin tone", "type": "body_area"}}, {{"name": "color temperature", "type": "concept"}}, {{"name": "reflection placement", "type": "concept"}}, {{"name": "trovarion", "type": "person"}}, {{"name": "intermediate", "type": "aesthetic"}}, {{"name": "display piece", "type": "topic"}}, {{"name": "high contrast", "type": "aesthetic"}}]}}

FINAL STEP — CAPTION CORRECTION: Auto-captions garble hobby terms. Before writing your JSON output, scan every entity name and apply these corrections:
"mephisto red" or "mefist on red" → "mephiston red"
"chris baron" or "trova ryan" or "trovar ian" → "trovarion"
"rhine oxide" or "rhino hide" or "rhino ox hide" → "rhinox hide"
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
You are extracting structured hobby knowledge from a miniature painting video transcript. Auto-captions frequently garble hobby terms. You must correct them.

STEP 1: AUTO-CAPTION CORRECTION TABLE
Before extracting, mentally correct these common garbles in the transcript:
- "rhine oxide", "rhino hide", "rhino ox hide" → "rhinox hide"
- "mephisto red", "mefist on red" → "mephiston red"
- "chris baron", "trova ryan" → "trovarion"
- "ice yellow" is correct (Vallejo paint)
- "skeleton horde" is correct (Citadel Contrast paint)
- "nolan oil", "nolin oil" → "nuln oil"
- "agra x earth shade", "agrax earth" → "agrax earthshade"
- "wraith bone", "rate bone" → "wraithbone"
- "mac rag blue", "macrag" → "macragge blue"
- "lead belcher", "led belcher" → "leadbelcher"
- "retributor armor", "retributor" → "retributor armour"
- "corax white", "corrects white" → "corax white"
- "abaddon black", "a bad on black" → "abaddon black"
- "mini ac", "miniac" → "miniac" (YouTuber)
- "squid mar", "squid more" → "squidmar"
- "trovar ian" → "trovarion"
- "zenit all", "zenith all" → "zenithal"
If a word sounds like a known hobby term, correct it to the known spelling.

STEP 2: COMPOUND ENTITY RULE
ALWAYS keep multi-word concepts as ONE entity. Never split them.
- "warm gold" → one entity, NOT "warm" + "gold"
- "non-metallic metal" → one entity, NOT "non-metallic" + "metal"
- "edge highlight" → one entity
- "reflection placement" → one entity
- "color temperature" → one entity
- "light placement" → one entity
- "wet palette" → one entity
- "contrast paint" → one entity
- "batch painting" → one entity
- "skin tone" → one entity
Rule: if two or more words together describe a single hobby concept, technique, or item, extract them as ONE entity.

STEP 3: EXTRACT ENTITIES
Extract every hobby-relevant entity. Use the type taxonomy below. When in doubt, INCLUDE the entity — recall matters more than precision.

TYPE TAXONOMY (use exactly these type strings):
- technique: painting methods and processes (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "feathering", "loaded brush", "two-brush blend", "slapchop", "sketch style")
- paint: specific paint product names (e.g. "rhinox hide", "mephiston red", "nuln oil", "agrax earthshade", "skeleton horde", "leadbelcher")
- brand: paint or hobby product manufacturers (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75", "monument hobbies", "kimera")
- tool: physical instruments used in the hobby (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "needle", "sponge")
- material: consumable supplies and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder", "flow improver", "matte medium", "speed paint", "ink")
- model: specific miniature kits or sculpts (e.g. "hive tyrant", "intercessor", "imperial knight", "plague marine")
- faction: army or faction names (e.g. "stormcast eternals", "death guard", "tyranids", "space marines")
- game_system: tabletop game names (e.g. "warhammer 40k", "age of sigmar", "kill team", "one page rules")
- color: color references when no specific paint product is named (e.g. "dark brown", "warm gold", "desaturated yellow", "cool blue", "off-white", "warm red")
- concept: painting theory and abstract hobby ideas (e.g. "color temperature", "contrast", "focal point", "sub-assembly", "batch painting", "light placement", "reflection placement", "color theory", "value sketch", "saturation", "hue shifting", "panel lining", "volumetric highlighting")
- body_area: parts of a miniature being painted (e.g. "face", "cloak", "pauldron", "base", "sword blade", "skin", "armor trim", "gem", "eye lenses")
- aesthetic: visual style or look being aimed for (e.g. "grimdark", "parade ready", "tabletop standard", "display quality", "eavy metal", "blanchitsu", "realistic", "high contrast")
- person: named painters, sculptors, or YouTubers (e.g. "trovarion", "squidmar", "miniac", "dana howl", "darren latham")
- topic: the subject or theme of the tutorial (e.g. "nmm gold", "painting faces", "basing", "weathering vehicles", "osl lighting")

DO NOT extract:
- Room/studio setup, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects (furniture, pets, food)
- Generic single words that aren't hobby-specific: "painting" alone, "color" alone, "brush" alone
- Duplicate entities: if "rhinox hide" appears 5 times, include it only ONCE

STEP 4: FORMAT OUTPUT
Return ONLY a JSON object. No text before or after.
{{
  "entities": [
    {{"name": "entity name in lowercase", "type": "one of the types above"}},
    ...
  ]
}}

WORKED EXAMPLE:
Transcript: "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold on the pauldron. This is a grimdark style approach."
{{
  "entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}},
    {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}},
    {{"name": "nmm gold", "type": "topic"}},
    {{"name": "pauldron", "type": "body_area"}},
    {{"name": "grimdark", "type": "aesthetic"}}
  ]
}}

WORKED EXAMPLE 2:
Transcript: "For the skin tone I'm focusing on color temperature, keeping the shadows cool and the highlights warm. This reflection placement technique is something trovar ian does really well."
{{
  "entities": [
    {{"name": "skin tone", "type": "body_area"}},
    {{"name": "color temperature", "type": "concept"}},
    {{"name": "reflection placement", "type": "concept"}},
    {{"name": "trovarion", "type": "person"}}
  ]
}}

Now extract all entities from this transcript chunk:
{chunk_text}
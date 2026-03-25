You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

EXTRACT these kinds of things:
- Painting techniques (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash")
- Specific paint names (e.g. "rhinox hide", "mephiston red", "ice yellow", "skeleton horde") — auto-captions often garble these, extract as heard
- Paint brands (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75")
- Tools (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp")
- Materials and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder")
- Miniature models and kits (e.g. "hive tyrant", "intercessor", "imperial knight")
- Factions and armies (e.g. "stormcast eternals", "death guard", "tyranids"); game systems (e.g. "warhammer 40k", "age of sigmar", "kill team")
- Color references when no specific paint is named (e.g. "dark brown", "warm gold", "desaturated yellow")
- Painting theory and concepts (e.g. "zenithal lighting", "color temperature", "hue shifting", "focal point", "volumetric highlighting")
- Hobby workflow concepts (e.g. "sub-assembly", "batch painting"); people mentioned by name (painters, sculptors, YouTubers)

DO NOT extract:
- Room/studio setup, filming equipment, personal anecdotes, YouTube/Patreon/social media references
- Non-hobby objects mentioned in passing (furniture, pets, food)
- Generic words that aren't hobby-specific ("painting", "color", "brush" alone without context)

Return a JSON object:
{{
  "entities": [
    {{"name": "entity name lowercase", "type": "technique|paint|brand|tool|material|model|faction|game_system|color|concept|person"}},
    ...
  ]
}}

Example — transcript: "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold"
{{"entities": [
    {{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}}, {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}}
]}}

Example — transcript: "the butterfly wings need a warm glaze of mephiston red over the feathers, keep the cold shadows desaturated"
{{"entities": [
    {{"name": "glazing", "type": "technique"}}, {{"name": "mephiston red", "type": "paint"}},
    {{"name": "desaturated", "type": "concept"}}
]}}
Note: "butterfly", "wings", "feathers" are the mini's subject — not hobby knowledge. "warm" and "cold" alone are not entities.

Return ONLY the JSON object. No explanation, no reasoning, no markdown fencing.

Transcript chunk:
{chunk_text}

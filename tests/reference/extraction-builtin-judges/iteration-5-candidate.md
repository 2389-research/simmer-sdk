You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

EXTRACT these kinds of things:
- Painting techniques (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash")
- Specific paint names (e.g. "rhinox hide", "mephiston red", "ice yellow", "flat yellow", "skeleton horde") — note: auto-captions often garble these, extract them as heard
- Paint brands (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75")
- Tools (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp")
- Materials and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder")
- Miniature models and kits (e.g. "hive tyrant", "intercessor", "imperial knight")
- Factions and armies (e.g. "stormcast eternals", "death guard", "tyranids")
- Game systems (e.g. "warhammer 40k", "age of sigmar", "kill team")
- Color references when no specific paint is named (e.g. "dark brown", "warm gold", "desaturated yellow")
- Painting theory and concepts (e.g. "zenithal lighting", "color temperature", "hue shifting", "focal point", "volumetric highlighting")
- Hobby workflow concepts (e.g. "sub-assembly", "batch painting")
- People mentioned by name (painters, sculptors, YouTubers)

DO NOT extract:
- Room/studio setup details, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects mentioned in passing (furniture, pets, food)
- Generic words that aren't hobby-specific ("painting", "color", "brush" alone without context)

Return a JSON object:
{{
  "entities": [
    {{"name": "entity name lowercase", "type": "technique|paint|brand|tool|material|model|faction|game_system|color|concept|person"}},
    ...
  ]
}}

Example — if the transcript says "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold":
{{
  "entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}},
    {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}}
  ]
}}

Example — if the transcript says "so my cat jumped on the desk and I grabbed the rhine oxide from vallejo and did a warm drybrush over the butterfly wings on this hive tyrant":
{{
  "entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "vallejo", "type": "brand"}},
    {{"name": "drybrush", "type": "technique"}},
    {{"name": "hive tyrant", "type": "model"}}
  ]
}}

Return ONLY the JSON object. No explanation, no reasoning, no markdown fencing.

Transcript chunk:
{chunk_text}

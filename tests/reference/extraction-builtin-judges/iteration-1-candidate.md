You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

Output each entity exactly once, in singular form. Merge spelling variants and plurals into one canonical entry (e.g., "edge highlight" not "edge highlights"; "wash" not "washes").

EXTRACT these kinds of things:
- Painting techniques (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "feathering", "loaded brush", "sketch style")
- Specific paint names (e.g. "rhinox hide", "mephiston red", "ice yellow", "flat yellow", "skeleton horde") — note: auto-captions often garble these, extract them as heard
- Paint brands (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75")
- Tools (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "palette knife", "makeup brush")
- Materials and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder", "flow improver", "retarder", "medium")
- Miniature models and kits (e.g. "hive tyrant", "intercessor", "imperial knight")
- Factions and armies (e.g. "stormcast eternals", "death guard", "tyranids")
- Game systems (e.g. "warhammer 40k", "age of sigmar", "kill team")
- Color references when no specific paint is named (e.g. "dark brown", "warm gold", "desaturated yellow") — standalone adjectives like "warm" or "cold" must be part of a compound color term; do not extract bare adjectives alone
- Painting theory and concepts (see dedicated block below)
- People mentioned by name (painters, sculptors, YouTubers)

PAINTING THEORY AND CONCEPTS — extract these when discussed:
These are abstract ideas about how and why painting choices work. Look for:
- Light and shadow theory (e.g. "zenithal lighting", "object source lighting", "shadow placement", "specular highlight", "ambient occlusion")
- Color theory (e.g. "color temperature", "complementary color", "saturation", "hue shifting", "color harmony", "warm-cool contrast")
- Composition and visual design (e.g. "focal point", "visual hierarchy", "contrast", "readability", "silhouette")
- Workflow concepts (e.g. "sub-assembly", "batch painting", "speed painting", "display piece", "tabletop standard", "competition painting")
- Surface and finish (e.g. "smooth blend", "texture", "freehand", "volumetric highlighting", "color modulation")

DO NOT extract:
- The subject being painted (e.g. "butterfly", "feather", "dragon wing", "face", "cloak", "sword blade") — only extract the hobby techniques, paints, and tools used ON the subject
- Standalone adjectives that are not part of a compound hobby term (e.g. do not extract "warm" alone, "cold" alone, "bright" alone — only as part of "warm gold", "cold blue", "bright highlight")
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

Example 1 — if the transcript says "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold":
{{
  "entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}},
    {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}}
  ]
}}

Example 2 — if the transcript says "I'm thinking about where the light hits this model, so I'll put my specular highlights up top and use hue shifting in the shadows, going from a warm brown to a cooler purple. Grab your size 1 brush and let's glaze this on":
{{
  "entities": [
    {{"name": "specular highlight", "type": "concept"}},
    {{"name": "hue shifting", "type": "concept"}},
    {{"name": "shadow placement", "type": "concept"}},
    {{"name": "warm brown", "type": "color"}},
    {{"name": "cool purple", "type": "color"}},
    {{"name": "size 1 brush", "type": "tool"}},
    {{"name": "glazing", "type": "technique"}}
  ]
}}

Transcript chunk:
{chunk_text}

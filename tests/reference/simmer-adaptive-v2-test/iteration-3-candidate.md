You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

EXTRACT these kinds of things:
- Painting techniques (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash")
- Specific paint names (e.g. "rhinox hide", "mephiston red", "ice yellow", "flat yellow", "skeleton horde") — auto-captions often garble these, correct garbled names to their real spelling
- Paint brands (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75")
- Tools (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp")
- Materials and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder")
- Miniature models and kits (e.g. "hive tyrant", "intercessor", "imperial knight")
- Factions and armies (e.g. "stormcast eternals", "death guard", "tyranids")
- Game systems (e.g. "warhammer 40k", "age of sigmar", "kill team")
- Color references when no specific paint is named (e.g. "dark brown", "warm gold", "desaturated yellow")
- Hobby concepts (e.g. "color temperature", "focal point", "sub-assembly", "batch painting")
- People mentioned by name (painters, sculptors, YouTubers)
- Body areas on a miniature (e.g. "cloak", "face", "shoulder pad", "base")
- Aesthetics and visual styles (e.g. "grimdark", "clean studio style")
- Skill levels (e.g. "beginner", "advanced")

DO NOT extract:
- Room/studio setup details, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects mentioned in passing (furniture, pets, food)
- Generic words that aren't hobby-specific ("painting", "color", "brush" alone without context)

Return a JSON object:
{{"entities": [{{"name": "entity name lowercase", "type": "technique|paint|brand|tool|material|model|faction|game_system|color|concept|person|body_area|aesthetic|skill_level|topic"}}, ...]}}

Example 1 — transcript says "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold":
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}]}}

Example 2 — transcript says "Duncan Rhodes talks about color temperature a lot — he always starts with the face before moving to the cloak, which is great advice for beginners":
{{"entities": [{{"name": "duncan rhodes", "type": "person"}}, {{"name": "color temperature", "type": "concept"}}, {{"name": "face", "type": "body_area"}}, {{"name": "cloak", "type": "body_area"}}, {{"name": "beginner", "type": "skill_level"}}]}}

Example 3 — transcript says "make sure you thin your paints and don't forget to shake your bottles":
{{"entities": [{{"name": "thin your paints", "type": "technique"}}]}}

Transcript chunk:
{chunk_text}

You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

EXTRACT these kinds of things:
- Painting techniques (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "feathering", "loaded brush", "slapchop")
- Specific paint names (e.g. "rhinox hide", "mephiston red", "mournfang brown", "abaddon black", "ice yellow", "flat yellow", "skeleton horde", "agrax earthshade", "nuln oil", "retributor armour", "leadbelcher")
- Paint brands (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75", "kimera", "pro acryl")
- Tools (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "masking tape")
- Materials and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder", "flow improver", "lahmian medium")
- Miniature models and kits (e.g. "hive tyrant", "intercessor", "imperial knight", "plague marine")
- Factions and armies (e.g. "stormcast eternals", "death guard", "tyranids", "space marines")
- Game systems (e.g. "warhammer 40k", "age of sigmar", "kill team")
- Color references when no specific paint is named (e.g. "dark brown", "warm gold", "cold gold", "desaturated yellow", "off-white")
- Body areas of miniatures (e.g. "recesses", "raised edges", "face", "cloak", "shoulder pad", "trim", "base rim", "weapon", "feather")
- Aesthetic styles (e.g. "grimdark", "display quality", "tabletop standard", "blanchitsu", "eavy metal", "clean style", "display piece")
- Theory and concepts (e.g. "color temperature", "contrast", "focal point", "sub-assembly", "batch painting", "value sketch", "hue shifting", "color harmony", "saturation", "underpainting", "reflection placement", "high contrast")
- People mentioned by name (painters, sculptors, YouTubers)

Return a JSON object:
{{"entities": [{{"name": "entity name lowercase", "type": "technique|paint|brand|tool|material|model|faction|game_system|color|body_area|aesthetic|concept|person"}}, ...]}}

Example 1 — "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold":
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "warm dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}]}}

Example 2 — "For this display piece I'm thinking about color temperature and where to place reflections, keeping high contrast on the focal point":
{{"entities": [{{"name": "display piece", "type": "aesthetic"}}, {{"name": "color temperature", "type": "concept"}}, {{"name": "reflection placement", "type": "concept"}}, {{"name": "high contrast", "type": "concept"}}, {{"name": "focal point", "type": "concept"}}]}}

Example 3 — "I learned this from watching chris baron, he does a cold gold on the weapon using ice yellow from vallejo":
{{"entities": [{{"name": "trovarion", "type": "person"}}, {{"name": "cold gold", "type": "color"}}, {{"name": "weapon", "type": "body_area"}}, {{"name": "ice yellow", "type": "paint"}}, {{"name": "vallejo", "type": "brand"}}]}}

Example 4 — "I'll glaze some warm gold into the feather edges then drybrush the raised areas for this grimdark look":
{{"entities": [{{"name": "glazing", "type": "technique"}}, {{"name": "warm gold", "type": "color"}}, {{"name": "feather", "type": "body_area"}}, {{"name": "raised edges", "type": "body_area"}}, {{"name": "drybrush", "type": "technique"}}, {{"name": "grimdark", "type": "aesthetic"}}]}}

Transcript chunk:
{chunk_text}

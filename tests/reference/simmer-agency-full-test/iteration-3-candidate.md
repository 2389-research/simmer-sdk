You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

IMPORTANT: Compound names are SINGLE entities. Extract "warm gold" not "warm"+"gold". Extract "rhinox hide" not "rhinox"+"hide". Extract "non-metallic metal" not "nonmetallic"+"metal". Extract "dark brown" not "dark"+"brown".

NEVER extract these words as standalone entities: warm, cold, gold, brown, edges, layers, whites, yellow, reflection, reflections, hue, guide, brushstrokes

EXTRACT these kinds of things:
- Painting techniques (e.g. "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "feathering", "loaded brush", "slapchop")
- Specific paint names (e.g. "rhinox hide", "mephiston red", "mournfang brown", "abaddon black", "ice yellow", "flat yellow", "skeleton horde", "agrax earthshade", "nuln oil", "retributor armour", "leadbelcher")
- Paint brands (e.g. "vallejo", "citadel", "army painter", "ak interactive", "scale75", "kimera", "pro acryl")
- Tools (e.g. "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "masking tape")
- Materials and mediums (e.g. "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder", "flow improver", "lahmian medium")
- Miniature models and kits (e.g. "hive tyrant", "intercessor", "imperial knight", "plague marine")
- Factions and armies (e.g. "stormcast eternals", "death guard", "tyranids", "space marines")
- Game systems (e.g. "warhammer 40k", "age of sigmar", "kill team")
- Color references when used as a compound description (e.g. "dark brown", "warm gold", "cold gold", "desaturated yellow", "off-white")
- Body areas of miniatures (e.g. "recesses", "raised edges", "face", "cloak", "shoulder pad", "trim", "base rim")
- Aesthetic styles (e.g. "grimdark", "display quality", "tabletop standard", "blanchitsu", "eavy metal", "display piece")
- Theory and concepts (e.g. "color temperature", "contrast", "focal point", "sub-assembly", "batch painting", "value sketch", "hue shifting", "color harmony", "saturation", "underpainting", "reflection placement", "high contrast")
- People mentioned by name (painters, sculptors, YouTubers e.g. "trovarion")

DO NOT extract:
- Room/studio setup, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects (furniture, pets, food)
- Generic words alone ("painting", "color", "brush" without qualifier)

Return a JSON object:
{{"entities": [{{"name": "entity name lowercase", "type": "technique|paint|brand|tool|material|model|faction|game_system|color|body_area|aesthetic|concept|person"}}, ...]}}

Example — if the transcript says "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold":
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}]}}

Transcript chunk:
{chunk_text}

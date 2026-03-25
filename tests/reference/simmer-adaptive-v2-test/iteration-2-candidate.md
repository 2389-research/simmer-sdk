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
- Hobby concepts (e.g. "color temperature", "focal point", "sub-assembly", "batch painting", "light source placement")
- People mentioned by name (painters, sculptors, YouTubers) — type: person
- Body areas being painted (e.g. "cloak", "pauldron", "base", "face") — type: body_area
- Aesthetic styles or goals (e.g. "gritty realism", "studio quality", "display piece") — type: aesthetic
- Skill levels referenced (e.g. "beginner", "advanced", "competition level") — type: skill_level
- Tutorial topics or subjects (e.g. "nmm gold tutorial", "speed painting guide") — type: topic

DO NOT extract:
- Room/studio setup details, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects mentioned in passing (furniture, pets, food)
- Generic words that aren't hobby-specific ("painting", "color", "brush" alone without context)

NOISE GATE — never extract these bare words alone: gold, guide, edges, yellow, white, contrast, transition, reflection, reflections, stroked, leaves
SEARCHABLE TAG TEST — before adding any entity, ask: "would a hobbyist type this into a search bar?" If no, skip it. Phrases like "darkest areas", "broad side of the brush", "upper edges" fail this test and must NOT be extracted.

CORRECTION TABLE — check every paint-sounding name against this table and use the corrected form:
| Heard as              | Use instead        |
|-----------------------|--------------------|
| rinox hide / rynox    | rhinox hide        |
| mephiston / mefiston  | mephiston red      |
| trovarian / trovarion | trovarion          |
| contrast paint brand  | citadel (brand)    |
| skeleton hoard        | skeleton horde     |
| iyanden / eyanden     | iyanden yellow     |

Return a JSON object:
{{"entities": [{{"name": "entity name lowercase", "type": "technique|paint|brand|tool|material|model|faction|game_system|color|concept|person|body_area|aesthetic|skill_level|topic"}}, ...]}}

Example — if the transcript says "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold":
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}]}}

Transcript chunk:
{chunk_text}

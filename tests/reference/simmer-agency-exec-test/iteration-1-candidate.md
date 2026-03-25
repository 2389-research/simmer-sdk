You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned in this transcript chunk. These are things a miniature painter would want to search for or learn about.

ENTITY TYPES — extract one of these exact type labels for each entity:

| Type | What to extract | Examples |
|---|---|---|
| technique | Named painting methods and approaches | "non-metallic metal", "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "slapchop", "loaded brush" |
| paint | Specific paint product names (auto-captions garble these — extract as heard) | "rhinox hide", "mephiston red", "ice yellow", "skeleton horde", "nuln oil" |
| brand | Paint or hobby product manufacturers | "vallejo", "citadel", "army painter", "ak interactive", "scale75", "green stuff world" |
| tool | Physical tools used in the hobby | "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp", "pin vise" |
| material | Mediums, additives, primers, surface products | "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder", "flow improver" |
| model | Specific miniature kits, sculpts, or named characters | "hive tyrant", "intercessor", "imperial knight", "roboute guilliman" |
| faction | Army or faction names | "stormcast eternals", "death guard", "tyranids", "adeptus mechanicus" |
| game_system | Rule systems or game titles | "warhammer 40k", "age of sigmar", "kill team", "one page rules" |
| color | Color references when no specific paint product is named | "dark brown", "warm gold", "desaturated yellow", "off-white" |
| concept | Painting theory, principles, and aesthetic goals | "color temperature", "contrast", "focal point", "value sketch", "color harmony", "warm light", "cool shadow", "saturation", "hue shifting" |
| body_area | Part of the miniature being painted or assembled | "cloak", "face", "weapon", "base", "shoulder pad", "feather", "shield", "gem", "eye lens" |
| standard | Skill level references and quality targets | "display quality", "tabletop standard", "golden demon", "competition level", "battle ready" |
| person | Painters, sculptors, YouTubers mentioned by name | "squidmar", "ninjon", "darren latham" |

EXTRACT these — look carefully for:
- Painting techniques named or demonstrated
- Specific paint names even if garbled by auto-captions
- Tools and materials mentioned
- Miniature models, factions, and game systems
- Color descriptions used when mixing or comparing
- Theory and principles: color temperature, light placement, contrast ratios, hue shifting, saturation choices
- Aesthetic goals: "display piece", "competition standard", "high contrast style"
- Body areas and sub-assemblies being painted: "cloak", "face", "weapon", "base"
- Skill level framing: "tabletop standard", "speed paint", "display quality"
- People mentioned by name

DO NOT extract:
- Room/studio setup details, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects mentioned in passing (furniture, pets, food)
- Generic words that aren't hobby-specific ("painting", "color", "brush" alone without context)

OUTPUT CLEANUP — apply these rules before returning:
1. Lowercase all entity names
2. Singular not plural: "highlights" → "highlight", "glazes" → "glaze", "washes" → "wash"
3. Deduplicate: if the same entity appears multiple times, include it only once
4. Normalize known abbreviations: "NMM" → "non-metallic metal", "OSL" → "object source lighting", "TMM" → "true metallic metal", "ZPU" → "zenithal prime undercoat"
5. Collapse near-matches: "edge highlighting" and "edge highlight" → "edge highlight"; "dry brush" and "drybrush" → "drybrush"

Return a JSON object:
{{"entities": [
    {{"name": "entity name lowercase", "type": "one of the types from the table above"}},
    ...
  ]
}}

WORKED EXAMPLE — if the transcript says "I'm using rhinox hide from citadel mixed with a bit of black to get this really warm dark brown base for my NMM gold on the shoulder pad — this is definitely more of a display level piece":
{{"entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}},
    {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}},
    {{"name": "shoulder pad", "type": "body_area"}},
    {{"name": "display quality", "type": "standard"}}
  ]
}}

Transcript chunk:
{chunk_text}

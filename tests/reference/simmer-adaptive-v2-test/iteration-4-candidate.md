Extract hobby entities from this miniature painting video transcript chunk.

STEP 1 — MANDATORY CORRECTIONS: Before extracting, mentally find-and-replace these auto-caption errors:
- "rhino side" or "rhino hide" or "rhine oxide" → "rhinox hide"
- "mephisto red" → "mephiston red"
- "chris baron" or "chris barren" → "trovarion"
- "squid mar" or "squid more" → "squidmar"
- "mini ac" → "miniac"
- "duncan roads" → "duncan rhodes"
- "mour fang brown" → "mournfang brown"
- "death cla brown" → "death claw brown"
- "valo" → "vallejo"

STEP 2 — EXTRACT ENTITIES: Only extract entities actually spoken in this transcript.

RULES:
1. Names: 1–3 words max. Must appear in (or be corrected from) the transcript.
2. Singularize nouns ("skeletons"→"skeleton"). Keep -ing endings ("feathering").
3. Standard forms: "non-metallic metal", "drybrush", "basecoat", "zenithal prime".
4. NEVER extract: standalone colors (red, black, white, gold), generic words (paint, army, edge, time, water, step, guide, contrast, finish), social media refs, non-hobby items, type labels.
5. REJECT 4+ word names.
6. Infer paint brands: any Citadel paint → also extract "citadel"; any Vallejo paint → also extract "vallejo".
7. Extract painting theory concepts (color temperature, value contrast, focal point, hue shifting, light placement) as type "concept" — these are high value.

ENTITY TYPES:
| type | what counts |
|------|-------------|
| technique | wet blend, edge highlight, glazing, drybrush, non-metallic metal, zenithal prime, oil wash, stippling, layering, basecoat, wash, highlight, airbrushing, blending |
| paint | specific product names (after corrections) |
| paint_brand | vallejo, citadel, army painter, ak interactive, scale75 |
| color | 2+ word color phrases only: dark brown, warm gold, cold blue |
| tool | airbrush, wet palette, hobby knife, brush (with size) |
| material | contrast paint, oil paint, texture paste, primer, varnish, ink, pigment powder, green stuff |
| model | specific miniature kit or model names |
| faction | black templar, tyranid, stormcast eternal, death guard, space marine |
| game_system | warhammer 40k, age of sigmar, kill team |
| concept | color temperature, value contrast, focal point, hue shifting, light placement, color reflection |
| person | content creator or painter names (apply Step 1 corrections) |

EXAMPLE:
Transcript: "[01:22] so chris baron here is going to show us how he does this wet blend on the gold using ice yellow from vallejo"
Output: {{"entities": [{{"name": "trovarion", "type": "person"}}, {{"name": "wet blend", "type": "technique"}}, {{"name": "ice yellow", "type": "paint"}}, {{"name": "vallejo", "type": "paint_brand"}}]}}

BEFORE RETURNING — remove anything not hobby-specific. If in doubt, leave it out.

Return ONLY valid JSON:
{{"entities": [{{"name": "...", "type": "..."}}, ...]}}

Transcript chunk:
{chunk_text}

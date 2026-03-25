Extract hobby entities from this miniature painting video transcript chunk.

STEP 1 — MANDATORY CORRECTIONS: Before extracting, mentally find-and-replace these auto-caption errors in the transcript:
- "chris baron" or "chris barren" → "trovarion"
- "squid mar" or "squid more" → "squidmar"
- "mini ac" → "miniac"
- "duncan roads" → "duncan rhodes"
- "nin john" → "ninjon"
- "lucas" → "lukas"
- "rhine oxide" or "rhino hide" or "rino hide" → "rhinox hide"
- "mephisto red" → "mephiston red"
- "death cla brown" → "death claw brown"
- "dect tan" → "deck tan"
- "mour fang brown" or "m fang brown" → "mournfang brown"
- "valo" → "vallejo"
Apply these corrections to entity names in your output. Keep all other paint names as heard.

STEP 2 — EXTRACT ENTITIES: Only extract entities actually spoken in the transcript. Do NOT invent entities from the examples below.

RULES:
1. Entity names: 1-3 words max. Every entity MUST appear in (or be corrected from) the transcript below.
2. Singularize nouns ("skeletons"→"skeleton", "black templars"→"black templar"). Keep -ing endings.
3. Standard forms: "non-metallic metal" (hyphenated), "drybrush" (one word), "basecoat" (one word).
4. NEVER extract these: standalone colors (red, black, white, gold, yellow), generic words (paint, army, edge, reflection, time, water, step, guide, person, contrast, finish, win, push, jump), clothing, emotions, body parts, social media, non-hobby items, or type labels.
5. REJECT 4+ word names. REJECT made-up fantasy names not in transcript.
6. "highlight" = valid technique. "edge" alone or "reflection" alone = invalid.
7. Infer paint brands from products: If you extract ANY Citadel paint → also extract "citadel" as paint_brand. If you extract ANY Vallejo paint → also extract "vallejo" as paint_brand.
8. Extract the host/presenter as type "person" (apply corrections from Step 1).
9. Look for painting theory concepts: color temperature, value contrast, reflection placement, focal point, hue shifting, light placement, color reflection, highlight placement. Extract as type "concept".

ENTITY TYPES (use these as the "type" field):
| type | what counts |
|------|------------|
| technique | wet blend, edge highlight, glazing, drybrush, non-metallic metal, zenithal prime... |
| paint | specific product names as heard (after corrections) |
| paint_brand | vallejo, citadel, army painter, ak interactive, scale75... |
| color | 2+ word color phrases: dark brown, warm gold, cold gold, orange brown... |
| tool | airbrush, wet palette, hobby knife... |
| medium | contrast paint, oil paint, texture paste, primer, varnish... |
| model | specific miniature kit/model names |
| faction | black templar, tyranids, stormcast eternal... |
| game_system | warhammer 40k, age of sigmar, kill team... |
| body_area | carapace, cloak, base, face, weapon, armor, tabard, sword, feather... |
| aesthetic | grimdark, weathered, high contrast, tabletop standard, display piece... |
| skill_level | beginner friendly, intermediate, advanced, competition level... |
| topic | speed painting, army project, batch painting... |
| assembly | kitbashing, converting, 3d printing, gap filling... |
| basing | texture paint, cork rock, tufts... |
| person | content creator names |
| award | best in show, golden demon... |
| concept | color temperature, value contrast, reflection placement, hue shifting, focal point... |

EXAMPLE 1 — transcript: "I'm using rhinox hide from citadel mixed with black for a warm dark brown base on the NMM gold"
{{"entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "paint_brand"}},
    {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}}
  ]
}}

EXAMPLE 2 — transcript: "Squidmar really nails color temperature on his display pieces — notice how the warm highlights shift toward yellow on the face, and the reflections on the sword are placed at the sharpest edges"
{{"entities": [
    {{"name": "squidmar", "type": "person"}},
    {{"name": "color temperature", "type": "concept"}},
    {{"name": "display piece", "type": "aesthetic"}},
    {{"name": "hue shifting", "type": "concept"}},
    {{"name": "face", "type": "body_area"}},
    {{"name": "reflection placement", "type": "concept"}},
    {{"name": "sword", "type": "body_area"}},
    {{"name": "edge highlight", "type": "technique"}}
  ]
}}

BEFORE RETURNING — review your list and remove anything that is not a painting technique, specific paint product, tool, miniature model, game term, or hobby concept. If in doubt, leave it out.

Return a JSON object:
{{"entities": [{{"name": "entity name lowercase", "type": "type_from_table_above"}}, ...]}}

Transcript chunk:
{chunk_text}
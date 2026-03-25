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
2. PAINTING THEORY — actively look for these concepts and extract as type "concept": color temperature, value contrast, reflection placement, focal point, hue shifting, light placement, color reflection, highlight placement. These are IMPORTANT and easy to miss.
3. Singularize nouns ("skeletons"→"skeleton", "black templars"→"black templar"). Exception: "tyranids" stays plural. Keep -ing endings ("feathering", "highlighting").
4. Standard forms: "non-metallic metal" (hyphenated), "drybrush" (one word), "basecoat" (one word), "zenithal prime".
5. STOP-LIST — NEVER extract these EXACT single words by themselves: red, black, white, gold, yellow, paint, army, edge, reflection, time, water, step, guide, person, contrast, finish, win, push, jump, socks, jackets, sweatpants, underwear, flannels, excitement, pride, hyper, legs, groin, torso, patreon, subscriber. HOWEVER multi-word phrases containing these words ARE valid — e.g., "high contrast" is valid, "reflection placement" is valid, "gold nmm" is valid, "edge highlight" is valid. Only block the exact single word alone.
6. REJECT 4+ word names. REJECT made-up fantasy names not in transcript. REJECT non-hobby items (dollar shave club), type labels (technique, faction, model, game_system), generic verbs (painting, looking).
7. "highlight" = valid technique. "edge" alone or "reflection" alone = invalid. "orange" = valid color.
8. Infer paint brands from products: If you extract ANY Citadel paint → also extract "citadel" as paint_brand. If you extract ANY Vallejo paint → also extract "vallejo" as paint_brand.
9. Extract the host/presenter as type "person" (apply corrections from Step 1).

ENTITY TYPES (use these as the "type" field):
| type | what counts |
|------|------------|
| technique | wet blend, edge highlight, glazing, drybrush, non-metallic metal, zenithal prime, oil wash, stippling, feathering, layering, basecoat, osl, wash, highlighting, airbrushing, varnishing, ink blending, highlight, gap filling, converting, kitbashing, outlining, base sculpting, blending |
| paint | specific product names as heard (after corrections) |
| paint_brand | vallejo, citadel, army painter, ak interactive, scale75, green stuff world, kimera |
| color | named color phrases: dark brown, warm gold, cold gold, orange brown, green gray, ivory, warm gray, orange |
| tool | airbrush, wet palette, hobby knife, sanding strip, silicon sculpting tool, q-tip, brush |
| medium | contrast paint, oil paint, texture paste, primer, varnish, matte varnish, ink, thinner, pigment powder, epoxy, plaster, green stuff, black ink, brown ink, purple ink |
| model | specific miniature kit/model names (nagash, fell bat, vampire lord) |
| faction | black templar, tyranids, stormcast eternal, soulblight gravelord, blood angel, space marine |
| game_system | warhammer 40k, age of sigmar, kill team, 40k |
| aesthetic | grimdark, weathered, high contrast, tabletop standard, display piece, parade ready |
| skill_level | beginner friendly, intermediate, advanced, competition level |
| body_area | carapace, cloak, base, face, weapon, armor, tabard, shoulder pad, skin, backpack |
| assembly | kitbashing, converting, 3d printing, gap filling, sub-assembly, magnetizing, sculpting |
| basing | texture paint, cork rock, tufts, rust pigment, pigment powder |
| topic | speed painting, army project, army painting, batch painting, 24-hour painting challenge, competition prep |
| person | content creator names (trovarion, squidmar, lukas, miniac, etc.) |
| award | best in show, golden demon, everchosen, grand champion |
| concept | color temperature, value contrast, reflection placement, focal point, hue shifting, light placement, color reflection, highlight placement |

EXAMPLE:
Transcript: "[01:22] so chris baron here is going to show us how he does this wet blend on the gold using ice yellow and flat yellow from vallejo"
Output: {"entities": [{"name": "trovarion", "type": "person"}, {"name": "wet blend", "type": "technique"}, {"name": "ice yellow", "type": "paint"}, {"name": "flat yellow", "type": "paint"}, {"name": "vallejo", "type": "paint_brand"}]}

BEFORE RETURNING — review your list and remove anything that is not a painting technique, specific paint product, tool, miniature model, game term, or hobby concept. If in doubt, leave it out.

Return ONLY valid JSON, no other text:
{"entities": [{"name": "...", "type": "..."}, ...]}

Transcript chunk:
{chunk_text}
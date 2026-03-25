Extract hobby entities from this miniature painting video transcript chunk.

STEP 1 — CORRECTIONS: Before extracting, fix these auto-caption errors in entity names:
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

STEP 2 — EXTRACT THEORY CONCEPTS FIRST: Scan for painting theory — color temperature, value contrast, reflection placement, focal point, hue shifting, light placement, highlight placement. Extract each as type "concept". These are high priority.

STEP 3 — EXTRACT ALL OTHER ENTITIES using the type table below.

RULES (follow all 5):
1. Only extract entities actually spoken in the transcript. Do NOT invent entities.
2. Entity names: 1-3 words, lowercase. REJECT 4+ word names.
3. NEVER extract standalone single-word colors (red, black, white, gold, yellow, green, blue, purple, brown, orange, silver). DO extract multi-word color phrases (warm gold, cold gold, dark brown, orange brown).
4. NEVER extract generic non-hobby words (paint, army, edge, time, water, step, guide, person, win, push, jump), clothing, emotions, body parts, social media platforms, or sponsors.
5. If you extract ANY Citadel paint → also extract "citadel" as paint_brand. If ANY Vallejo paint → also extract "vallejo" as paint_brand. Extract the host/presenter as type "person".

ENTITY TYPES (use these as the "type" field):
| type | what counts |
|------|------------|
| technique | wet blend, edge highlight, glazing, drybrush, non-metallic metal, zenithal prime, oil wash, stippling, feathering, layering, basecoat, osl, wash, highlighting, airbrushing, varnishing, ink blending, highlight, gap filling, converting, kitbashing, outlining, base sculpting, blending |
| paint | specific product names as heard (after corrections) |
| paint_brand | vallejo, citadel, army painter, ak interactive, scale75, green stuff world, kimera |
| color | 2+ word color phrases: dark brown, warm gold, cold gold, orange brown, green gray, ivory, warm gray |
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

Return ONLY valid JSON, no other text:
{"entities": [{"name": "...", "type": "..."}, ...]}

Transcript chunk:
{chunk_text}

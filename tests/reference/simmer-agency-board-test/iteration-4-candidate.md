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
- "nonmetallic" or "non metallic metal" → "non-metallic metal"
- "outline" (verb/noun) → "outlining" (technique name)
Apply these corrections to entity names in your output. Keep all other paint names as heard.

STEP 2 — EXTRACT ENTITIES: Only extract entities actually spoken in the transcript. Do NOT invent entities from the examples below.

RULES:
1. Entity names: 1-3 words max. Every entity MUST appear in (or be corrected from) the transcript below.
2. Singularize nouns ("skeletons"→"skeleton", "black templars"→"black templar"). Exception: "tyranids" stays plural. Keep -ing endings ("feathering", "highlighting").
3. Standard forms: "non-metallic metal" (hyphenated), "drybrush" (one word), "basecoat" (one word), "zenithal prime".
4. BRAND INFERENCE (IMPORTANT — always do this): If you extract ANY Citadel paint (rhinox hide, mephiston red, abaddon black, mournfang brown, bugmans glow, death claw brown, etc.) → you MUST also extract "citadel" as paint_brand. If you extract ANY Vallejo paint → you MUST also extract "vallejo" as paint_brand.
5. Extract the host/presenter as type "person" (apply corrections from Step 1).

ENTITY TYPES (use these as the "type" field):
| type | what counts |
|------|------------|
| technique | wet blend, edge highlight, glazing, drybrush, non-metallic metal, zenithal prime, oil wash, stippling, feathering, layering, basecoat, osl, wash, highlighting, airbrushing, varnishing, ink blending, highlight, gap filling, converting, kitbashing, outlining, base sculpting, blending |
| paint | specific product names as heard (after corrections) |
| paint_brand | vallejo, citadel, army painter, ak interactive, scale75, green stuff world, kimera |
| color | standalone or multi-word color terms when used as hobby color references: dark brown, warm gold, cold gold, orange, orange brown, green gray, ivory, warm gray, black, gold |
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

EXAMPLE 1 (paints + person + technique):
Transcript: "[01:22] so chris baron here is going to show us how he does this wet blend on the gold using ice yellow and flat yellow from vallejo"
Output: {"entities": [{"name": "trovarion", "type": "person"}, {"name": "wet blend", "type": "technique"}, {"name": "ice yellow", "type": "paint"}, {"name": "flat yellow", "type": "paint"}, {"name": "vallejo", "type": "paint_brand"}]}

EXAMPLE 2 (colors + body areas + brand inference):
Transcript: "[08:30] I'm doing the power weapon in cold gold and orange tones, starting from a rhinox hide base and building up — you get this really warm feel"
Output: {"entities": [{"name": "weapon", "type": "body_area"}, {"name": "cold gold", "type": "color"}, {"name": "orange", "type": "color"}, {"name": "rhinox hide", "type": "paint"}, {"name": "citadel", "type": "paint_brand"}]}

EXAMPLE 3 (concepts + aesthetics + body areas):
Transcript: "[05:10] the key to good non-metallic metal on the shoulder pad is understanding color temperature and reflection placement so you get that high contrast display piece look on the armor"
Output: {"entities": [{"name": "non-metallic metal", "type": "technique"}, {"name": "shoulder pad", "type": "body_area"}, {"name": "color temperature", "type": "concept"}, {"name": "reflection placement", "type": "concept"}, {"name": "high contrast", "type": "aesthetic"}, {"name": "display piece", "type": "aesthetic"}, {"name": "armor", "type": "body_area"}]}

EXAMPLE 4 (colors + models + factions):
Transcript: "[12:45] for the tyranids carapace I'm starting with a dark brown basecoat and then building up to warm gold highlights on the hive tyrant"
Output: {"entities": [{"name": "tyranids", "type": "faction"}, {"name": "carapace", "type": "body_area"}, {"name": "dark brown", "type": "color"}, {"name": "basecoat", "type": "technique"}, {"name": "warm gold", "type": "color"}, {"name": "highlight", "type": "technique"}, {"name": "hive tyrant", "type": "model"}]}

BEFORE RETURNING — review your list and remove anything that is not a painting technique, specific paint product, tool, miniature model, game term, or hobby concept. If in doubt, leave it out.

Return ONLY valid JSON, no other text:
{"entities": [{"name": "...", "type": "..."}, ...]}

Transcript chunk:
{chunk_text}
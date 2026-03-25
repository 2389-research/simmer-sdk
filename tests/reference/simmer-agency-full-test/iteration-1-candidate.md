Extract hobby entities from this miniature painting video transcript chunk.

STEP 1 — FIX CAPTION ERRORS: Auto-captions garble names. Fix these before extracting:
| heard in transcript | correct name |
|---|---|
| chris baron, chris barren | trovarion |
| squid mar, squid more | squidmar |
| mini ac | miniac |
| duncan roads | duncan rhodes |
| nin john | ninjon |
| lucas | lukas |
| rhine oxide, rhino hide, rino hide, rhino side | rhinox hide |
| mephisto red | mephiston red |
| death cla brown, death clown brown | death claw brown |
| dect tan | deck tan |
| mour fang brown, m fang brown | mournfang brown |
| valo, vjo | vallejo |
| soul black grave, soul black gravelord | soulblight gravelord |
| vangorian lord | vargheist lord |
| kayman | kayman green |
| sandry | sandry dust |

STEP 2 — EXTRACT ENTITIES: Find every hobby entity spoken in the transcript. Use corrected names from Step 1.

ENTITY TYPES — use exactly one of these as the "type" field:
| type | examples |
|---|---|
| technique | wet blend, edge highlight, glazing, drybrush, non-metallic metal, zenithal prime, oil wash, stippling, feathering, layering, basecoat, osl, wash, highlighting, airbrushing, varnishing, ink blending, highlight, gap filling, outlining, blending, color reflection, highlight placement, reflection placement, base sculpting |
| paint | specific product names: rhinox hide, mephiston red, ice yellow, flat yellow, orange brown, green gray, deck tan, sandry dust, steel legion drab, mournfang brown, death claw brown, wild rider red, scarlet blood, dark sea blue, kayman green, grunge brown, sunny skintone, skeleton horde, vermilion, ivory |
| paint_brand | vallejo, citadel, army painter, ak interactive, scale75, green stuff world, kimera |
| color | 2+ word color descriptions: dark brown, warm gold, cold gold, orange brown, warm gray, desaturated yellow |
| tool | airbrush, wet palette, hobby knife, sanding strip, silicon sculpting tool, q-tip, brush |
| medium | contrast paint, oil paint, texture paste, primer, varnish, matte varnish, ink, thinner, pigment powder, epoxy, plaster, green stuff, black ink, brown ink, purple ink |
| model | specific miniature names: nagash, fell bat, vampire lord, vargheist lord, imperial knight, hive tyrant |
| faction | black templar, tyranids, stormcast eternal, soulblight gravelord, blood angel, space marine, death guard |
| game_system | warhammer 40k, 40k, age of sigmar, kill team |
| body_area | carapace, cloak, base, face, weapon, armor, tabard, shoulder pad, skin, backpack, feather |
| aesthetic | grimdark, weathered, high contrast, tabletop standard, display piece, parade ready, competition level |
| assembly | kitbashing, converting, 3d printing, gap filling, sub-assembly, magnetizing, sculpting |
| basing | texture paint, cork rock, tufts, rust pigment |
| topic | speed painting, army project, army painting, batch painting, 24-hour painting challenge, competition prep |
| concept | color temperature, value contrast, focal point, hue shifting, light placement |
| award | best in show, golden demon, everchosen, grand champion |
| person | content creators: trovarion, squidmar, lukas, miniac, duncan rhodes, ninjon |

RULES:
1. Only extract entities actually spoken in the transcript. Do NOT invent entities from the examples above.
2. Use singular forms: "skeletons" -> "skeleton", "black templars" -> "black templar". Keep -ing endings ("feathering").
3. Use standard forms: "non-metallic metal" (hyphenated), "drybrush" (one word), "basecoat" (one word).
4. Entity names: 1-3 words max. All lowercase.
5. DO NOT extract: standalone single colors (red, black, white, gold, yellow), generic words (paint, army, edge, reflection, time, water, step, guide, contrast, finish), body parts (legs, groin, torso), clothing, emotions, social media references.
6. If you extract a Citadel paint (rhinox hide, mephiston red, mournfang brown, steel legion drab, death claw brown, wild rider red) -> also extract "citadel" as paint_brand. If you extract a Vallejo paint (ice yellow, deck tan, flat yellow, orange brown, sandry dust, green gray, kayman green) -> also extract "vallejo" as paint_brand.
7. Look for THEORY CONCEPTS — these are important and often missed. When the speaker discusses HOW light works on surfaces, WHERE to place highlights, or WHY colors look warm/cold, extract the concept: color temperature, value contrast, reflection placement, highlight placement, color reflection, focal point, hue shifting, light placement.

EXAMPLE:
Transcript: "[01:22] so chris baron here is going to show us how he does this wet blend on the gold using ice yellow and flat yellow from vallejo"
Output: {{"entities": [{{"name": "trovarion", "type": "person"}}, {{"name": "wet blend", "type": "technique"}}, {{"name": "ice yellow", "type": "paint"}}, {{"name": "flat yellow", "type": "paint"}}, {{"name": "vallejo", "type": "paint_brand"}}]}}

Return ONLY valid JSON:
{{"entities": [{{"name": "...", "type": "..."}}, ...]}}

Transcript chunk:
{chunk_text}
You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned. These are things a miniature painter would want to search for or learn about.

AUTO-CAPTION CORRECTION TABLE — if you hear these garbled forms, output the canonical name:
| Heard (garbled)         | Extract as (canonical)     |
|-------------------------|----------------------------|
| rhino side / rhine oxide / rhinox | rhinox hide        |
| mephisto red / mephiston / mephist red | mephiston red |
| agrax / agrax earthshade / agrak | agrax earthshade   |
| nuln oil / null oil / nun oil  | nuln oil               |
| reikland / reiklands / reikland flesh | reikland fleshshade |
| abaddon / abbadon black | abaddon black              |
| lahmian / lahm medium   | lahmian medium             |
| ard coat / hard coat    | 'ardcoat                   |
| technical paint / texture paint | texture paste      |
| vallejo / val / valhejo | vallejo                    |
| scale 75 / scale seventy | scale75                   |
| duncan / dunc           | duncan rhodes              |
| minimax / mini max      | miniac                     |
| goobertown / goober town | goobertown hobbies        |

TYPE TAXONOMY — use exactly one of these types per entity:

| Type         | What it covers                                         | Examples                                                      |
|--------------|--------------------------------------------------------|---------------------------------------------------------------|
| technique    | How paint is applied or a method used                  | wet blend, edge highlight, glazing, zenithal prime, stippling, oil wash, layering, drybrush |
| paint        | A specific named paint                                 | rhinox hide, mephiston red, skeleton horde, ice yellow, flat yellow |
| brand        | A paint or hobby product company                       | vallejo, citadel, army painter, ak interactive, scale75       |
| tool         | A physical instrument used                             | airbrush, wet palette, size 2 brush, hobby knife, magnifying lamp |
| material     | A medium, primer, or product category                  | contrast paint, oil paint, primer, varnish, pigment powder, texture paste |
| model        | A specific miniature kit or sculpt                     | hive tyrant, intercessor, imperial knight                     |
| faction      | An army or faction within a game                       | stormcast eternals, death guard, tyranids                     |
| game_system  | A tabletop game                                        | warhammer 40k, age of sigmar, kill team                       |
| color        | A color description when no specific paint is named    | dark brown, warm gold, desaturated yellow, cool shadow        |
| concept      | Painting theory or abstract hobby idea — PRIORITIZE THESE | color temperature, reflected light, focal point, sub-assembly, batch painting, value contrast, color harmony, highlight placement, ambient occlusion, shadow shape, color saturation, transition smoothness |
| body_area    | A region of a miniature being painted                  | cloak, armour, face, base, weapon, shoulder pad, skin         |
| aesthetic    | A visual style or finish goal                          | grimdark, heroic scale, realistic, OSL (object source lighting), comic style |
| skill_level  | A painter skill or experience level                    | beginner, intermediate, advanced, competition level           |
| assembly     | A physical build or prep step                          | sub-assembly, conversion, pinning, gap filling, mold line removal |
| person       | A named individual (painter, sculptor, YouTuber)       | duncan rhodes, miniac, goobertown hobbies, sodrazin            |

EXTRACT THESE — binary checklist:
[ ] Every named technique the speaker demonstrates or mentions
[ ] Every specific paint name spoken (apply correction table above)
[ ] Every brand name mentioned
[ ] Every tool mentioned by name
[ ] Every material or medium mentioned
[ ] Every model or kit mentioned
[ ] Every faction or game system mentioned
[ ] Every color description used when no paint name is given
[ ] Every painting theory concept (color temperature, light placement, contrast — even if mentioned briefly)
[ ] Every body area discussed in context of painting decisions
[ ] Every visual style or aesthetic goal mentioned
[ ] Every named person mentioned

DO NOT EXTRACT:
- Room/studio setup, filming equipment, personal anecdotes
- YouTube/Patreon/social media references
- Non-hobby objects (furniture, pets, food)
- Bare generic words with no hobby context ("painting", "brush", "color" used as filler)

Return a JSON object:
{{"entities": [{{"name": "entity name lowercase", "type": "<type from taxonomy>"}}, ...]}}

Example — transcript says "I'm using rhinox hide from citadel mixed with black to get a warm dark brown base for my NMM gold, focusing on where zenithal light hits the cloak":
{{"entities": [{{"name": "rhinox hide", "type": "paint"}}, {{"name": "citadel", "type": "brand"}}, {{"name": "black", "type": "color"}}, {{"name": "warm dark brown", "type": "color"}}, {{"name": "non-metallic metal", "type": "technique"}}, {{"name": "zenithal prime", "type": "technique"}}, {{"name": "highlight placement", "type": "concept"}}, {{"name": "cloak", "type": "body_area"}}]}}

Transcript chunk:
{chunk_text}

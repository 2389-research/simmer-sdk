You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned. These are things a miniature painter would search for or learn about.

ENTITY TYPES (use exactly one): technique, paint, brand, tool, material, model, faction, game_system, color, concept, body_area, aesthetic, skill_level, topic, person

EXAMPLES by type:
- technique: "wet blend", "edge highlight", "glazing", "zenithal prime", "drybrush", "layering", "stippling", "oil wash", "non-metallic metal", "feathering"
- paint: "rhinox hide", "mephiston red", "ice yellow", "skeleton horde"
- brand: "vallejo", "citadel", "army painter", "ak interactive", "scale75"
- tool: "airbrush", "wet palette", "size 2 brush", "hobby knife", "magnifying lamp"
- material: "contrast paint", "oil paint", "texture paste", "primer", "varnish", "pigment powder", "medium"
- model: "hive tyrant", "intercessor", "imperial knight"
- faction: "stormcast eternals", "death guard", "tyranids"
- game_system: "warhammer 40k", "age of sigmar", "kill team"
- color: "dark brown", "warm gold", "desaturated yellow" (use ONLY when no specific paint name is given)
- concept: "color temperature", "contrast", "focal point", "reflection placement", "light placement", "hue shifting", "value sketch", "shadow mapping"
- body_area: "face", "shoulder pad", "cloak", "base rim"
- aesthetic: "grimdark", "display quality", "parade ready"
- skill_level: "beginner", "tabletop standard", "competition level"
- topic: "batch painting", "sub-assembly", "army building", "speed painting"
- person: painters, sculptors, YouTubers mentioned by name

HARD NEGATIVES — do NOT extract these:
- Bare adjectives alone: "warm", "cold", "desaturated", "bright" — only extract if paired with a noun ("warm gold" YES, "warm" NO)
- Generic words without context: "painting", "color", "brush", "paint" alone — only extract specific names ("size 2 brush" YES, "brush" NO)
- Non-hobby things: studio setup, filming gear, social media, Patreon, furniture, pets, food
- Auto-caption garble that isn't a real entity

PAINT NAME CORRECTIONS (auto-captions garble these — fix on output):
- mephisto red → mephiston red
- rhino side / rhine oxide / rhynox → rhinox hide
- skeleton hoard → skeleton horde
- macro crag → macragge
- agrax earth shade → agrax earthshade
- nuland oil / new land → nuln oil

Return a JSON object:
{{"entities": [
    {{"name": "entity name lowercase", "type": "one of the types above"}},
    ...
  ]
}}

Example — transcript says "I'm using rhinox hide from citadel mixed with black for a warm dark brown base on the NMM gold, great for beginners":
{{"entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}},
    {{"name": "dark brown", "type": "color"}},
    {{"name": "non-metallic metal", "type": "technique"}},
    {{"name": "beginner", "type": "skill_level"}}
  ]
}}

Transcript chunk:
{chunk_text}

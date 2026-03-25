You are extracting structured hobby knowledge from a miniature painting video transcript.

Extract every hobby-relevant entity mentioned. These are things a miniature painter would search for or learn about.

ENTITY TYPES: technique, paint, brand, tool, material, model, faction, game_system, color, concept, body_area, aesthetic, skill_level, topic, person

---

EXAMPLE 1 — transcript: "I'm using rhinox hide from citadel mixed with black for a warm dark brown base on the NMM gold"
{{"entities": [
    {{"name": "rhinox hide", "type": "paint"}},
    {{"name": "citadel", "type": "brand"}},
    {{"name": "black", "type": "color"}},
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

EXAMPLE 3 — transcript: "for the feathers on this stormcast I'm glazing vallejo ice yellow over a zenithal prime — gives you that high contrast look with smooth transitions"
{{"entities": [
    {{"name": "feather", "type": "body_area"}},
    {{"name": "stormcast eternals", "type": "faction"}},
    {{"name": "glazing", "type": "technique"}},
    {{"name": "vallejo", "type": "brand"}},
    {{"name": "ice yellow", "type": "paint"}},
    {{"name": "zenithal prime", "type": "technique"}},
    {{"name": "high contrast", "type": "aesthetic"}},
    {{"name": "smooth transitions", "type": "concept"}}
  ]
}}

EXAMPLE 4 — transcript: "if you're just starting out, batch painting death guard with contrast paints on a wet palette is a great tabletop standard workflow — skeleton horde over a white primer does all the work"
{{"entities": [
    {{"name": "batch painting", "type": "topic"}},
    {{"name": "death guard", "type": "faction"}},
    {{"name": "contrast paint", "type": "material"}},
    {{"name": "wet palette", "type": "tool"}},
    {{"name": "tabletop standard", "type": "skill_level"}},
    {{"name": "skeleton horde", "type": "paint"}},
    {{"name": "white primer", "type": "material"}}
  ]
}}

---

Return a JSON object with the same format as above.

Transcript chunk:
{chunk_text}

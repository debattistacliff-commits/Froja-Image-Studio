/** Groups for the Styles & Artists slider, so 164 styles are easy to browse. */
export const STYLE_GROUPS: { id: string; label: string; match: RegExp }[] = [
  { id: "all", label: "All", match: /./ },
  { id: "masters", label: "Old Masters", match: /renaissance|michelangelo|leonardo|raphael|baroque|caravaggio|rembrandt|vermeer|botticelli|titian|turner|goya|bosch|bruegel|dore|piranesi|john martin|moreau/i },
  { id: "modern", label: "Modern Art", match: /impressionism|monet|van gogh|art nouveau|klimt|mucha|kandinsky|escher|rackham|surrealism|william morris|beksinski|watercolor|charcoal|gouache/i },
  { id: "asia", label: "Japan & China", match: /hokusai|hiroshige|kuniyoshi|yoshitoshi|sesshu|jakuchu|korin|shoen|yumeji|fan kuan|guo xi|ma yuan|zeduan|bada|qi baishi|xu beihong|wu guanzhong|chinese|wuxia|manhua|yokai/i },
  { id: "manga", label: "Manga & Anime", match: /manga|anime|tezuka|ishinomori|matsumoto|toriyama|miura|mizuki|umezz|monkey punch|taniguchi|cel |comedy action|cel animation/i },
  { id: "design", label: "Design & Architecture", match: /loewy|dreyfuss|bel geddes|fuller|eames|saarinen|panton|colombo|sottsass|castiglioni|scarpa|frank lloyd|gaudi|corbusier|hadid|harley earl|exner|bauhaus|streamline|brutalist|biomorphic|metabolism|constructivist|architectural|product illustration|industrial/i },
  { id: "craft", label: "Sculpture & Craft", match: /marble|bronze|wood|tapestry|mosaic|stained glass|bas-relief|sculpture|clay|stop motion|cut paper|designer toy|maquette|relic/i },
  { id: "fantasy", label: "Fantasy & Sci-Fi", match: /fantasy|eldritch|biomechanical|volcanic|giger|syd mead|ron cobb|mcquarrie|ken adam|moebius|frazetta|pulp|retro futur|cyberpunk|steampunk|alien|celestial|mythic|legendary|epic cover|antihero|ritual|armour|nordic|procedural|ink fantasy|concept art/i },
  { id: "looks", label: "Looks", match: /photoreal|cinematic|depthstage|jellybean|3d animation|minimal|graphic novel|golden age comic|isometric|storybook/i },
];

export function styleSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
}

export function inStyleGroup(group: string, name: string): boolean {
  const found = STYLE_GROUPS.find((g) => g.id === group);
  return !found || found.match.test(name);
}

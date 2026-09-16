# Authentication icons

Exact Figma SVG exports from Re:hear XR (`t15qxZbFhezXWMyay2REVH`):

- `2684:31782`: person, mail, lock, visibility, checkbox-unchecked, chevron-down.
- `2684:31921`: checkbox-checked (blue), check-success (green).
- `2323:39081`: logout. This export is white; render through a CSS mask with `currentColor` on light surfaces.

The terms chevron export points down. AgreementBox rotates it -90deg to point right, as in Figma.
Do not substitute navigation `home.svg`: it is a white home glyph and is invisible on white forms.
The password visibility control uses the original eye glyph and exposes its toggled state with `aria-pressed` and its action label.

Practice mapping is in `../practice.ts`. The Figma practice design intentionally shares a flag glyph and varies the color by exercise. Existing report-v3 `metric-flag-blue.svg` and `metric-flag-purple.svg` filenames are inverted relative to the SVG fills; the mapping uses their actual colors without changing report rendering.

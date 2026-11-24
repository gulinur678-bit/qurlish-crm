from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
html=(root/'index.html').read_text()
js=(root/'app.js').read_text()
css=(root/'styles.css').read_text()
assert all((root/p).is_file() for p in ['README.md','DESIGN.md','docs/ux-review.md','index.html','styles.css','app.js'])
assert 'Xonadon tanlash' in html and 'id="lead-dialog"' in html
assert 'role="group"' in html and 'aria-live' in html
assert "Array.from({length:7}" in js and 'buildingNames' in js and '[1,2,3]' in js
assert 'fetch(' not in js and 'localStorage' not in js
assert 'prefers-reduced-motion' in css and ':focus-visible' in css
assert len(re.findall(r'<section\b',html))>=5
print('PASS: 7 static structural checks; no actual E2E/backend tests performed')

"""
A temporary fix for https://github.com/pydicom/pydicom/issues/1965
while waiting for upstream sphinx_rtd_theme to fix/remove their
dependency on jQuery.
"""
from pathlib import Path
import re


search_html = Path("./_build/html/search.html")
assert search_html.exists()

with open(search_html) as fp:
    html = fp.read()

pat = r"(<script>\s+jQuery.+searchindex\.js.+\s+<\/script>)"
repl = r'<script src="searchindex.js" defer></script>'
# re.findall(pat, html)
html_fixed = re.sub(pat, repl, html)

with open(search_html, "w") as fp:
    fp.write(html_fixed)

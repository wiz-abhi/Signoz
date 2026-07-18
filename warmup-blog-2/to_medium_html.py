"""Render the blog markdown to a standalone HTML file for pasting into Medium.

Medium's editor only accepts rich text. Open the generated file in a browser,
select all, copy, and paste into a new Medium story: headings, bold, links,
lists and images come across, and each fenced block lands as a code block.
"""
import os

import markdown

here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "signoz-funnels-blog.md")
out = os.path.join(here, "signoz-funnels-blog.medium.html")

text = open(src, encoding="utf-8").read()
body = markdown.markdown(text, extensions=["fenced_code", "tables"])

# Medium keeps <pre> as a code block; give it a readable face while copying.
html = f"""<!doctype html>
<meta charset="utf-8">
<title>Paste into Medium</title>
<style>
  body {{ max-width: 740px; margin: 40px auto; padding: 0 20px;
         font: 19px/1.7 Georgia, "Times New Roman", serif; color: #111; }}
  h1 {{ font-size: 40px; line-height: 1.2; }}
  h2 {{ font-size: 28px; margin-top: 2em; }}
  pre {{ background: #f6f6f6; padding: 16px; overflow-x: auto;
        font: 14px/1.5 "SF Mono", Consolas, monospace; }}
  code {{ font-family: "SF Mono", Consolas, monospace; font-size: 0.85em; }}
  img {{ max-width: 100%; height: auto; }}
  table {{ border-collapse: collapse; }}
  td, th {{ border: 1px solid #ddd; padding: 6px 10px; }}
  hr {{ margin: 3em 0; }}
</style>
{body}
"""

open(out, "w", encoding="utf-8").write(html)
print("wrote:", out)
print("images:", body.count("<img"))
print("code blocks:", body.count("<pre>"))

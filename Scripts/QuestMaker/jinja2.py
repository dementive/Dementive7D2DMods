# Minimal stand-in for the jinja2 features QuestMaker uses ({% if x != "" %} / {% if x %} blocks and {{x}}).
import re
class Template:
    def __init__(self, src):
        self.src = src
    def render(self, **kw):
        def cond(m):
            expr, body = m.group(1).strip(), m.group(2)
            ne = re.match(r'(\w+)\s*!=\s*""$', expr)
            ok = kw.get(ne.group(1), "") != "" if ne else bool(kw.get(expr))
            return body if ok else ""
        out = re.sub(r'{%\s*if (.*?)%}(.*?){%\s*endif\s*%}', cond, self.src, flags=re.S)
        return re.sub(r'{{\s*(\w+)\s*}}', lambda m: str(kw.get(m.group(1), "")), out)

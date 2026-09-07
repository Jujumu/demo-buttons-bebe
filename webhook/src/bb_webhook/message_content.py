"""Read retained Gorgias content without following archived body URLs."""
from html.parser import HTMLParser
import re

class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        elif not self.hidden and tag in ('p','div','br','li','tr','blockquote'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.hidden:self.hidden-=1
        elif not self.hidden and tag in ('p','div','li','tr','blockquote'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def message_text(message):
    """Prefer retained stripped text/HTML, then full bodies, then legacy text."""
    for key in ('stripped_text','stripped_html','body_text','body_html','text'):
        value=message.get(key)
        if not isinstance(value,str) or not value.strip():continue
        if key.endswith('_html'):
            parser=_VisibleText();parser.feed(value);parser.close()
            value=re.sub(r'\n[ \t]*\n+', '\n\n',''.join(parser.parts))
        if value.strip():return value.strip()
    return ''

import re

class Parser(object):

    def __init__(self, text):
        self.text = text
        self.pos = 0

    def lex_lit(self, lit):
        if self.pos + len(lit) > len(self.text):
            return None
        if self.text[self.pos:self.pos + len(lit)] == lit:
            self.pos += len(lit)
            return lit
        return None

    def lex_regex(self, pat):
        mat = re.match(pat, self.text[self.pos:])
        if mat:
            self.pos += len(mat.group(0))
            return mat
        else:
            return None

    def lex_re(self, pat):
        mat = self.lex_regex(pat)
        return mat.group(0) if mat else None

class DbParser(Parser):
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def lex_word(self):
        return self.lex_re(r'[A-Za-z0-9][A-Za-z0-9\-]*')

    def lex_line(self):
        self.lex_ws()
        return self.lex_re(r'[\r\n \t]+')

    def lex_ws(self):
        return self.lex_re(r'[ \t]+')

    def parse_binds(s):
        if not s.lex_lit('('):
            return

        first = True
        s.lex_ws()
        while not s.lex_lit(')'):
            if not first:
                comma = s.lex_lit(',')
                assert comma, "Expected ',' between binds"
                s.lex_ws()
            bind = s.lex_word()
            assert bind, "Expected bind"
            yield bind
            s.lex_ws()
            first = False

    def parse_tag(s):
        sign = s.lex_re(r'[-+]')
        assert sign, "Expected sign"
        
        tag = s.lex_re(r'[A-Za-z0-9][A-Za-z0-9\-]+!?')
        assert tag, "Expected tag name"

        binds = tuple(s.parse_binds())
            
        return (sign == '+', tag, binds)

    def parse_patterns(s):
        while True:
            s.lex_ws()
            entity = s.lex_word()
            if not entity:
                return

            while not s.lex_line():
                s.lex_ws()
                tag = s.parse_tag()
                assert tag, "Expected tag"

                yield (entity, tag)

    def parse_rule(s):
        s.lex_line()
        head = s.lex_lit('#')
        assert head, "Expected '#'"
        s.lex_ws()
        
        name = s.lex_word()
        assert name, "Expected rule name"

        s.lex_line()

        ma_desc = s.lex_regex(r'>[ \t]*(.*)[\r\n]')
        assert ma_desc, "Expected rule description"
        desc = ma_desc.group(1)

        s.lex_line()
        pre = tuple(s.parse_patterns())
        s.lex_line()

        arrow = s.lex_lit('->')
        assert arrow, "Expected '->'"

        s.lex_line()
        post = tuple(s.parse_patterns())
        s.lex_line()

        return (name, desc, pre, post)

    def parse_rules(s):
        while s.pos < len(s.text):
            yield s.parse_rule()

    def parse_entities(s):
        s.lex_line()
        patterns = tuple(s.parse_patterns())
        names = set(p[0] for p in patterns)
        tags = { n: (i, []) for i,n in enumerate(names) }

        for p in patterns:
            if p[1][0]:
                tags[p[0]][1].append(p[1][1:])
        
        return tags

def parse_rules(s):
    p = DbParser(s)
    return list(p.parse_rules())

def parse_entities(s):
    p = DbParser(s)
    return p.parse_entities()


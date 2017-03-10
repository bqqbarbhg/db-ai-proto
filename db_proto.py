from collections import namedtuple, defaultdict, OrderedDict
import itertools

import db_parse

Entity = namedtuple('Entity', 'id name tags notags')
Tag = namedtuple('Tag', 'tag binds')
Pattern = namedtuple('Pattern', 'sign entity tag')

def tag_match(entity, tag, entities):
    """Returns whether a matching tag is found in a entity, the list of
    entities is required for tags with binds such as `+hold(object)`
    """

    for t in entity.tags:
        if t.tag != tag.tag:
            continue
        if any(entities[bp].id != bt for bt, bp in zip(t.binds, tag.binds)):
            continue
        return True
    return False

def pattern_match(pat, entities):
    """Returns whether a set of entities matches the pattern"""

    return tag_match(entities[pat.entity], pat.tag, entities) == pat.sign

def swizzle_tuple(lst, indices):
    """Swizzle a list into a tuple by selecting items using indices"""

    if indices:
        return tuple(lst[i] for i in indices)
    else:
        return tuple(lst)

def unswizzle_tuple(original, lst, indices):
    """Unswizzle a list into a tuple by replacing elements of the original
    list with new ones using indices
    """

    if indices:
        copy = list(original)
        for e,i in zip(lst, indices):
            copy[i] = e
        return tuple(copy)
    else:
        return tuple(lst)

class Rule(object):

    def __init__(self, name, desc, names, pre, post):
        self.name = name
        self.desc = desc
        self.names = names
        self.num = len(names)
        self.pre = pre
        self.post = post

    def forward(self, entity_list, swizzle=None):
        """Applies the rule forwards to entities, which is what the simulation
        would do. Checks for preconditions first and if the rule is applicable
        it updates the entities to reflect the postconditions.
        Returns modified entities if rule is applicable, None if not.

        swizzle: Optional list of indices for which entities to apply the rule for
        """

        if len(swizzle) < self.num if swizzle else len(entities) < self.num:
            raise IndexError("Not enough entities provided for rule '{}'".format(self.name))

        entities = swizzle_tuple(entity_list, swizzle)

        tags = [set(e.tags) for e in entities]

        if not all(pattern_match(p, entities) for p in self.pre):
            return None

        for pat in self.post:
            binds = tuple(entities[b].id for b in pat.tag.binds)
            if pat.sign:
                tags[pat.entity].add(Tag(pat.tag.tag, binds))
            else:
                rem = set(t for t in tags[pat.entity] if t.tag == pat.tag.tag)
                tags[pat.entity] -= rem

        new_entities = tuple(Entity(e.id, e.name, tuple(t), ()) for e,t in zip(entities, tags))
        asd = unswizzle_tuple(entity_list, new_entities, swizzle)
        return asd

    def backward(self, entity_list, swizzle=None):
        """Applies the rule backwards to entities, which returns entities that
        satisfy the preconditions. Also removes tags from the entities that
        are obtained from the postconditions.
        Returns modified entities, cannot fail.

        swizzle: Optional list of indices for which entities to apply the rule for
        """

        if len(swizzle) < self.num if swizzle else len(entities) < self.num:
            raise IndexError("Not enough entities provided for rule '{}'".format(self.name))

        entities = swizzle_tuple(entity_list, swizzle)

        tags = [set(e.tags) for e in entities]
        notags = [set(e.notags) for e in entities]

        for pat in self.post:
            binds = tuple(entities[b].id for b in pat.tag.binds)
            if pat.sign:
                tags[pat.entity].discard(Tag(pat.tag.tag, binds))
            else:
                notags[pat.entity].discard(Tag(pat.tag.tag, binds))

        for pat in self.pre:
            binds = tuple(entities[b].id for b in pat.tag.binds)
            if pat.sign:
                tags[pat.entity].add(Tag(pat.tag.tag, binds))
            else:
                notags[pat.entity].add(Tag(pat.tag.tag, binds))

        new_entities = tuple(Entity(e.id, e.name, tuple(t), tuple(nt)) for e,t,nt in zip(entities, tags, notags))
        return unswizzle_tuple(entity_list, new_entities, swizzle)

    def format_desc(self, entity_list, swizzle=None):
        """Returns a description of the rule application for entities"""

        entities = swizzle_tuple(entity_list, swizzle)
        namemap = { n: e.name for n,e in zip(self.names, entities) }
        return self.desc.format(**namemap)

    def format_rule(self):
        """Pretty prints the rule using the format of `parse_rules`
        
        swizzle: Optional list of indices for which entities to apply the rule for
        """

        def fmt_tag(sign, tag):
            if tag.binds:
                binds = ','.join(self.names[b] for b in tag.binds)
                return '{}{}({})'.format('-+'[sign], tag.tag, binds)
            else:
                return '{}{}'.format('-+'[sign], tag.tag)

        def fmt_patterns(pats):
            tags = defaultdict(list)
            for pat in pats:
                tags[self.names[pat.entity]].append(fmt_tag(pat.sign, pat.tag))
            return '\n'.join('{} {}'.format(n, ' '.join(tags[n])) for n in self.names if tags[n])

        return '\n'.join((
                '# {}'.format(self.name),
                '> {}'.format(self.desc),
                '',
                fmt_patterns(self.pre),
                '->',
                fmt_patterns(self.post)))

def parse_rules(s):
    """Parse rules from a string, for example:

        dwarf +dwarf +hold(weapon)
        other +dwarf
        wepaon +weapon
        ->
        other +hurt!
    """

    def create_rule(name, desc, pre, post):
        names = list(OrderedDict.fromkeys(p[0] for p in pre + post))

        def create_pattern(pat):
            entity, sign, tag, binds = pat[0], pat[1][0], pat[1][1], pat[1][2]
            tg = Tag(tag, tuple(names.index(b) for b in binds))
            return Pattern(sign, names.index(entity), tg)

        pre, post = ([create_pattern(p) for p in pats] for pats in (pre, post))
        return Rule(name, desc, names, pre, post)

    return [create_rule(*r) for r in db_parse.parse_rules(s)]

def parse_entities(s):
    """Parse entities from a string, for example:

        Urist +dwarf +hold(Sword)
        Sword +weapon
    """

    def create_entity(ents, name, index, tags):
        tg = tuple(Tag(t[0], tuple(ents[b][0] for b in t[1])) for t in tags)
        return Entity(index, name, tg, ())

    ents = db_parse.parse_entities(s)
    return [create_entity(ents, k, *v) for k,v in ents.items()]

def format_entities(entities):
    """Pretty-prints entities using the format of `parse_entities`"""

    names = { e.id: e.name for e in entities }

    def fmt_tag(sign, tag):
        if tag.binds:
            binds = ','.join(names[b] for b in tag.binds)
            return '{}{}({})'.format('-+'[sign], tag.tag, binds)
        else:
            return '{}{}'.format('-+'[sign], tag.tag)

    def fmt_entity(entity):
        tags = ' '.join(itertools.chain(
            (fmt_tag(True, t) for t in entity.tags),
            (fmt_tag(False, t) for t in entity.notags)))
        return '{} {}'.format(entity.name, tags)
    
    return '\n'.join(fmt_entity(e) for e in entities)


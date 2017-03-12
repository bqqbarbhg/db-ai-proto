from collections import namedtuple, defaultdict, OrderedDict, Counter
import itertools
import heapq

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
        self.action = '!' in name

    def forward(self, entity_list, swizzle=None):
        """Applies the rule forwards to entities, which is what the simulation
        would do. Checks for preconditions first and if the rule is applicable
        it updates the entities to reflect the postconditions.
        Returns modified entities if rule is applicable, None if not.

        swizzle: Optional list of indices for which entities to apply the rule for
        """

        if len(swizzle) < self.num if swizzle else len(entity_list) < self.num:
            raise IndexError("Not enough entities provided for rule '{}'".format(self.name))

        entities = swizzle_tuple(entity_list, swizzle)

        tags = [set(t for t in e.tags if '!' not in t.tag) for e in entities]

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
        Returns modified entities or None if impossible.

        swizzle: Optional list of indices for which entities to apply the rule for
        """

        if len(swizzle) < self.num if swizzle else len(entity_list) < self.num:
            raise IndexError("Not enough entities provided for rule '{}'".format(self.name))

        entities = swizzle_tuple(entity_list, swizzle)

        tags = [set(e.tags) for e in entities]
        notags = [set(e.notags) for e in entities]

        # Remove provided postconditions
        for pat in self.post:
            binds = tuple(entities[b].id for b in pat.tag.binds)
            if pat.sign:
                tags[pat.entity].discard(Tag(pat.tag.tag, binds))
            else:
                notags[pat.entity].discard(Tag(pat.tag.tag, binds))

        # Add required precondition tags
        for pat in self.pre:
            binds = tuple(entities[b].id for b in pat.tag.binds)
            if pat.sign:
                tags[pat.entity].add(Tag(pat.tag.tag, binds))
            else:
                notags[pat.entity].add(Tag(pat.tag.tag, binds))

        # If there are multiples of some tag then this production is invalid
        for ts in tags:
            tagcount = Counter(t.tag for t in ts)
            if ts and tagcount.most_common(1)[0][1] > 1:
                return None

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

AiRule = namedtuple('AiRule', 'rule swizzle')
AiChain = namedtuple('AiChain', 'start rules')

def format_ai_rule(ai_rule):
    """Pretty prints AI rule in form of 'rule-name(0,1,2)'"""

    swizzle = ','.join(str(s) for s in ai_rule.swizzle)
    return '{}({})'.format(ai_rule.rule.name, swizzle)

def ai_search(rules, root_rule, num_entities, max_depth):
    """Search for chains of rules to reach a state where a root rule can be
    applied

    rules: Rules to combine
    root_rule: All the rule chains will lead to this rule
    num_entities: For how many entities to search the solution for
    max_depth: Maximum depth of the chain

    Returns a generator of possible rule chains yielding results lazily,
    querying all the rules may take an unreasonable time so there is an
    attempt to return the most relevant and plausible ones first.
    """

    return ai_search_greedy(rules, root_rule, num_entities, max_depth)

def check_chain(entities, ai_chain):
    """Check whether an AI chain is actually applicable"""

    if not entities:
        return False

    es = entities
    for r, s in ai_chain:
        es = r.forward(es, swizzle=s)
        if not es:
            return False
    return True


def ai_search_dumb(rules, root_rule, num_entities, max_depth):
    """See ai_search for the interface.

    Probably the dumbest and most straightforward implementation of this
    function. Just try all combinations of increasing length.
    """

    indices = list(range(num_entities))

    def dumb_step(entities, chain, depth):

        # Yield current result (also the first)
        yield AiChain(entities, chain)

        # Reached the end
        if depth >= max_depth:
            return

        # Try each rule in order
        for rule in rules:
            # Well, at least make sure we have enough entities to apply
            if num_entities < rule.num:
                continue

            # Iterate through all permutations of the entities
            for permutation in itertools.permutations(indices, rule.num):

                # Action rules require the actor to be the first entity
                if rule.action and permutation[0] != 0:
                    continue

                # Try to simulate the rule backwards
                enext = rule.backward(entities, swizzle=permutation)
                if not enext:
                    continue

                cnext = [AiRule(rule, permutation)] + chain

                # Check that the chain can be actually applied
                if check_chain(enext, cnext):
                    # If the loop went through without breaking the chain
                    # is valid
                    for c in dumb_step(enext, cnext, depth + 1):
                        yield c

    start_entities = [Entity(i, 'e_{}'.format(i), (), ()) for i in range(num_entities)]

    # Always apply the root rule
    start_entities = root_rule.backward(start_entities)

    for chain in dumb_step(start_entities, [AiRule(root_rule, indices[:root_rule.num])], 0):
        yield chain

def ai_search_greedy(rules, root_rule, num_entities, max_depth):
    """See ai_search for the interface.

    Some kind of greedy search.
    """

    indices = list(range(num_entities))

    Node = namedtuple('Node', 'score entities chain')

    start_entities = [Entity(i, 'e_{}'.format(i), (), ()) for i in range(num_entities)]
    work = [Node(0, start_entities, [AiRule(root_rule, list(range(root_rule.num)))])]

    # WIP
    # rules_for_tag = defaultdict(set)
    # for rule in rules:
    #     for post in rule.post:

    while work:
        node = heapq.heappop(work)
        rule = node.chain[0]
        entities = rule.rule.backward(node.entities, swizzle=rule.swizzle)

        if not check_chain(entities, node.chain):
            continue

        yield AiChain(entities, node.chain)

        if len(node.chain) <= max_depth:
            for rule in rules:
                if num_entities < rule.num:
                    continue
                for permutation in itertools.permutations(indices, rule.num):
                    if rule.action and permutation[0] != 0:
                        continue

                    ai_rule = AiRule(rule, permutation)
                    heapq.heappush(work, Node(1, entities, [ai_rule] + node.chain))


import db_proto as db
import itertools
import re

weaponhit = r'''

# weapon-hit!
> {dwarf} hits {thing} with {weapon}
    dwarf +dwarf +hold(weapon)
    weapon +weapon
    ->
    thing +hurt!

# pick-up!
> {dwarf} picks up {thing}
    dwarf +dwarf -hold
    thing +holdable
    ->
    dwarf +hold(thing)

# drop!
> {dwarf} drops {thing}
    dwarf +dwarf +hold(thing)
    thing +holdable
    ->
    dwarf -hold
    thing +fall!

# light-weapon!
> {dwarf} lights {item} on fire from {fire}
    dwarf +dwarf +hold(item)
    item +holdable +flammable
    fire +fire
    ->
    item +fire +weapon

# make-fire!
> {dwarf} sets {thing} on fire
    dwarf +dwarf
    thing +flammable
    ->
    thing +fire

# fall-break
> {object} breaks as it falls
    object +fall!
    ->
    object +break!

# glass-break
> {glass} breaks into shards
    glass +glass +break!
    ->
    glass +weapon

'''

rules = db.parse_rules(weaponhit)
best_chains = []

src = db.ai_search(rules, rules[0], num_entities=4, max_depth=5)
for chain in src:
    if any(any('!' in t.tag for t in e.tags) for e in chain.start):
        continue
    total_tags = sum(len(set(t.tag for t in e.tags + e.notags)) for e in chain.start)
    best_chains.append((float(total_tags) + float(len(chain.rules)) * 0.5, chain))

def is_unseen(seen, entities):
    for s in seen:
        for es, en in zip(s, entities):
            if set(es.tags) - set(en.tags) or set(es.notags) - set(en.notags):
                break
        else:
            return False
    return True

def filter_chains(chains):
    seen = []
    for score, chain in sorted(best_chains):
        if is_unseen(seen, chain.start):
            seen.append(chain.start)
            yield score, chain

for score, chain in itertools.islice(filter_chains(best_chains), 50):
    desc = ' -> '.join(db.format_ai_rule(r) for r in chain.rules) 
    print '[{}]: {}'.format(score, desc)


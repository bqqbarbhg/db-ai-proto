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
seen = set()

src = db.ai_search(rules, rules[0], num_entities=3, max_depth=5)
for chain in src:
    if any(any('!' in t.tag for t in e.tags) for e in chain.start):
        continue
    total_tags = sum(len(set(t.tag for t in e.tags + e.notags)) for e in chain.start)
    best_chains.append((float(total_tags) + float(len(chain.rules)) * 0.5, chain))

for score, chain in itertools.islice(sorted(best_chains), 100):
    if chain.start in seen:
        continue
    seen.add(chain.start)

    desc = ' -> '.join(db.format_ai_rule(r) for r in chain.rules) 
    print '[{}]: {}'.format(score, desc)


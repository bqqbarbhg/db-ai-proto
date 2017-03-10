import db_proto as db

weaponhit = r'''
# weapon-hit
> {dwarf} hits {thing} with {weapon}
dwarf +dwarf +hold(weapon)
weapon +weapon
->
thing +hurt!

# pick-up
> {dwarf} picks up {thing}
dwarf +dwarf -hold
thing +holdable
->
dwarf +hold(thing)

# drop
> {dwarf} drops {thing}
dwarf +dwarf +hold(thing)
thing +holdable
->
dwarf -hold
'''

rules = db.parse_rules(weaponhit)

es = [db.Entity(i, 'e_{}'.format(i), (), ()) for i in range(4)]
es = rules[0].backward(es, swizzle=[0, 1, 2])
es = rules[1].backward(es, swizzle=[0, 1])
es = rules[2].backward(es, swizzle=[0, 3])

rs = rules[2].forward(es, swizzle=[0, 3])
rs = rules[1].forward(rs, swizzle=[0, 1])
rs = rules[0].forward(rs, swizzle=[0, 1, 2])

print db.format_entities(es)
print '->'
print db.format_entities(rs)

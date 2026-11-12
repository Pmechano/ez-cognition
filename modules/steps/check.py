"""Rules for `steps` that the schema cannot express."""


def check(record):
    problems = []
    seen = set()
    for index, step in enumerate(record.get("steps", [])):
        if step["id"] in seen:
            problems.append('steps[%d].id: "%s" is used by an earlier step' % (index, step["id"]))
        seen.add(step["id"])
    return problems

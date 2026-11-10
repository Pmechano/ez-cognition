"""Rules for `steps` that the schema cannot express."""


def check(task):
    problems = []
    seen = set()
    for index, step in enumerate(task.get("steps", [])):
        if step["id"] in seen:
            problems.append('steps[%d].id: "%s" is used by an earlier step' % (index, step["id"]))
        seen.add(step["id"])
    return problems

"""Rules for `steps` that the schema cannot express."""


def check(record):
    problems = []
    seen = set()
    submit = record.get("submit")
    deliverables = submit.get("deliverables") if isinstance(submit, dict) else None
    known = {d.get("id") for d in deliverables if isinstance(d, dict)} if isinstance(deliverables, list) else set()
    for index, step in enumerate(record.get("steps", [])):
        if step["id"] in seen:
            problems.append('steps[%d].id: "%s" is used by an earlier step' % (index, step["id"]))
        seen.add(step["id"])
        for used in step.get("for", []):
            if used not in known:
                problems.append('steps[%d].for: "%s" is not an id in submit.deliverables' % (index, used))
    return problems

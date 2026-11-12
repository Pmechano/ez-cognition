"""Rules for `submit` that the schema cannot express."""


def check(record):
    problems = []
    submit = record.get("submit")
    if not isinstance(submit, dict):
        return problems
    items = submit.get("deliverables", [])
    ids = [item["id"] for item in items]
    for index, item in enumerate(items):
        if item["id"] in ids[:index]:
            problems.append('submit.deliverables[%d].id: "%s" is used by an earlier deliverable' % (index, item["id"]))
    return problems

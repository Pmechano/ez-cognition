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
        for used in item.get("uses", []):
            if used == item["id"]:
                problems.append("submit.deliverables[%d].uses: a deliverable cannot use itself" % index)
            elif used not in ids:
                problems.append('submit.deliverables[%d].uses: "%s" is not a deliverable id' % (index, used))
    return problems

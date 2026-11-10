"""Rules for `project` that the schema cannot express."""


def check(record):
    problems = []
    project = record.get("project")
    if not isinstance(project, dict):
        return problems
    items = project.get("deliverables", [])
    ids = [item["id"] for item in items]
    for index, item in enumerate(items):
        if item["id"] in ids[:index]:
            problems.append('project.deliverables[%d].id: "%s" is used by an earlier deliverable' % (index, item["id"]))
        for used in item.get("uses", []):
            if used == item["id"]:
                problems.append("project.deliverables[%d].uses: a deliverable cannot use itself" % index)
            elif used not in ids:
                problems.append('project.deliverables[%d].uses: "%s" is not a deliverable id' % (index, used))
    return problems

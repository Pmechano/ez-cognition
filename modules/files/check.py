"""Rules for `files` that the schema cannot express."""


def check(record):
    problems = []
    steps = record.get("steps")
    ids = {step.get("id") for step in steps if isinstance(step, dict)} if isinstance(steps, list) else set()
    seen = set()
    for index, item in enumerate(record.get("files", [])):
        path = item["path"]
        if path in seen:
            problems.append('files[%d].path: "%s" is already in the list' % (index, path))
        seen.add(path)
        if "step" in item and item["step"] not in ids:
            problems.append('files[%d].step: no step has the id "%s"' % (index, item["step"]))
    return problems

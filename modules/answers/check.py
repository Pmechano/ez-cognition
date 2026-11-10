"""Rules for `answers` that the schema cannot express."""


def check(task):
    problems = []
    steps = task.get("steps")
    ids = {step.get("id") for step in steps if isinstance(step, dict)} if isinstance(steps, list) else set()
    for key, answer in task.get("answers", {}).items():
        if key not in ids:
            problems.append('answers.%s: no step has the id "%s"' % (key, key))
        seen = set()
        for index, direction in enumerate(answer.get("directions", [])):
            pair = (direction["who"], direction["id"])
            if pair in seen:
                problems.append("answers.%s.directions[%d]: %s / %s is already in this step"
                                % (key, index, pair[0], pair[1]))
            seen.add(pair)
    return problems

# ez-cognition agent guide

You work in a student group project. Each member works with their own agent. ez-cognition is a page that helps each member understand the project: what the task asks, step by step, and how the group answers each step. You write the records. The page shows them. Follow this guide in every work session.

## Words

- **Task**: one thing that the group hands in or presents. One task has one page. Two assignments are two tasks.
- **Step**: one thing that the task asks the group to do or to show. The steps come from the course materials, not from the group's plan.
- **Answer**: how the group does one step.
- **Framework**: the answers to all the steps of a task. The leader drafts it. All members work inside it.
- **Direction**: something that one member explores inside the framework. A direction is not an owned part of the work. The member chooses it. Two members can explore the same step.
- **Task record**: the file `cognition-data/<task-id>.json`. It contains the task, its steps and the framework, in key points.

## Commands

`<plugin>` is the directory of this guide. Run the commands from the project root. They need Python 3.9 or later and no packages. If `python` is not found, use `python3`.

```
python <plugin>/ezc.py open
python <plugin>/ezc.py check
python <plugin>/ezc.py init
python <plugin>/ezc.py stop
```

- `open` adds this project to the page, starts the local server if it does not run, and shows the page in the user's browser. It prints the address, the state of each task record, the user's name and the git branch. If the page is already open, the page changes to this project, and `open` does not open a second page.
- `check` validates the task records. It prints the problems, or `OK`.
- `init` is for the leader's setup.
- `stop` stops the server now, for all projects. Usually you do not need it: the server stops by itself approximately one minute after the user closes the page.

One server and one page show all the projects on the computer. Projects in WSL are included. The address is `http://127.0.0.1:27180/`. If the system refuses this port, the server uses one of the next ports, and `open` prints it. Do not start a server in another way.

The page refreshes by itself when a task record changes. The page never calls a model. When the user has a question about the page, the user asks you.

## Set up the project (leader only)

Do the setup on `main`.

1. Put the original course materials in `docs/`. Examples: the assignment, the rubric, the syllabus. Do not edit them. If some materials are not in the repo, ask the leader for them.
2. Run `init`. It creates `cognition-data/` and adds one line to `AGENTS.md`, so that each member's agent finds this guide.
3. Write one task record for each task (see "The task record"). Read all of `docs/` first. The steps and the task requirements come only from official course materials.
4. Draft the framework with the leader: propose an answer for each step, and change it until the leader agrees. A step can stay without an answer.
5. Run `check`, then `open`. The setup is done when the leader has read the page and agrees with it.
6. Commit and push. If `collab-guide.md` applies, send a `framework` message.

## Start of each session

1. Run `open`. If it prints that the user has no name, ask the user to write a name in the settings panel of the page. Do not write it yourself.
2. Read the task records. For the exact wording of a requirement, read the source file.
3. Read the Slack channel as `collab-guide.md` tells you.
4. Ask what the user wants to do, if you do not know.

## Explore a direction (members)

The member chooses what to explore. Do not assign a direction to the user, and do not divide the work into owned parts.

1. Update `main`. Create the branch `<name>/<direction-id>` from it. If the branch exists, merge `main` into it.
2. Add the direction to `directions` of the step that it belongs to: `id`, `who` (the user's name) and `explores`. Commit this change early, so that the other members see it.
3. When the user finds something, write `found`: one or two sentences, and where the work is.
4. Merge into `main` through a pull request, or in the way that the team agreed.

Rules for the task record:

- Write only the user's own direction entries.
- A finding can show that the framework must change. Do not change `answer`, `detail`, `steps` or `logistics` yourself. Tell the user. The leader decides. After the change is in `main`, send a `framework` message.
- If git reports a conflict in a task record, keep the entries of both sides.
- Run `check` after each change. Do not commit a task record that has problems.

## The task record

One file for each task: `cognition-data/<task-id>.json`. The task id is the file name. Ids are lowercase ASCII letters, digits and `-`. Do not change an id after the record is in `main`: answers, branch names, Slack messages and the user's marks use it.

```json
{
  "title": "期末报告",
  "goal": "用一份 8 页以内的报告说明：共享单车的调度问题主要出在早高峰。",
  "sources": ["docs/assignment.pdf"],
  "logistics": {
    "summary": "12 月 20 日截止，不超过 8 页，占总成绩 40%",
    "items": [
      { "label": "截止", "value": "2026-12-20", "note": "迟交每天扣 5%。", "from": "docs/assignment.pdf" }
    ]
  },
  "steps": [
    {
      "id": "method",
      "title": "说明方法",
      "ask": "说明用了什么数据和方法，让读者能重复这项分析。",
      "detail": ["评分表的“方法”一项看这一步。"],
      "from": "docs/assignment.pdf"
    }
  ],
  "answers": {
    "method": {
      "answer": "用 2025 年全年的骑行记录，按站点和小时统计缺车次数。",
      "detail": ["缺车的定义：一个站点连续 10 分钟没有可用的车。"],
      "directions": [
        {
          "id": "weather",
          "who": "zez",
          "explores": "下雨天的缺车规律是否不同。",
          "found": "雨天早高峰的缺车次数少一半。图在 `analysis/weather.ipynb`。"
        }
      ]
    }
  }
}
```

| Key                              | Content                                                                                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`                        | The name of the task, as the members say it.                                                                                                                              |
| `goal`                         | One sentence: what the group makes and what it must show.                                                                                                                 |
| `sources`                      | The source files. The reader goes there for details.                                                                                                                      |
| `logistics.summary`            | One line that a member must not miss: the date, the form, the weight.                                                                                                     |
| `logistics.items`              | The requirements around the work: the deadline, what to hand in, the form, the grading, the rules. `label` and `value` are short. `note` and `from` are optional. |
| `steps`                        | What the task asks, in order. `ask` is one or two sentences. `detail` and `from` are optional.                                                                      |
| `answers.<step-id>.answer`     | The group's answer to that step, in one or two sentences.                                                                                                                 |
| `answers.<step-id>.detail`     | Optional key points of the answer.                                                                                                                                        |
| `answers.<step-id>.directions` | What members explore in that step. `found` is optional.                                                                                                                 |

All keys except `title` and `goal` are optional. `check` reports a key that it does not know.

The page is for understanding, not for reference. Write the record so:

- Write key points. Do not copy the source text. Exact details stay in the source files, and `from` names the file.
- Put the conclusion first. The first line of each part must make sense alone: a closed row of the page shows only `title` and `answer`.
- Use the words of the course and of the members, not code names.
- The only markup is `` `code` ``.
- Write in the user's language.

## Questions

The user can ask you about the project. Answer with the framework in mind: say which step the answer is about.

The task record is a transcription and can contain errors. If a question needs the exact wording of a requirement, read the source file.

## Scope

- Do not change the files of ez-cognition.
- Do not write in `cognition-data/.local/`. It contains the user's personal state, and git ignores it. The only exception is the file that `collab-guide.md` names.
- Do not write in `~/.ez-cognition/`. It contains the state of the one server: the list of projects and the look of the page. Only `open` and the page write it.
- The marks "我已认知" on the page belong to the user. They are voluntary. Do not ask the user to set them, and do not test the user.
- Do not compare the members, and do not count their work.

## Writing style

Text for people must be easy to read. This includes the task record, summaries and answers. Use the rules of ASD-STE100 (Simplified Technical English):

- One sentence gives one instruction or one fact.
- Use one word for one thing. Do not change to a synonym.
- Put the conclusion first.
- Use the active voice. Put conditions before actions.
- Use lists for complex content. Do not write long sentences.
- In Chinese: do not use empty verbs like "进行" or "实施". Do not chain many "的".

A Chinese summary of the rules is in `ASD-STE100.md`. Read it when you need more detail.

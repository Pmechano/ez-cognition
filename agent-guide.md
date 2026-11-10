# ez-cognition agent guide

You work in a student group project. Each member works with their own agent. ez-cognition is a page that helps each member understand three things: the project (what the group hands in), the task (what the work actually does), and our solution (how the group does each step). You write the record. The page shows it. Follow this guide in every work session.

## Words

- **Project**: the course work that the group hands in. It has deliverables, dates and grading.
- **Deliverable**: one thing that the group hands in or presents. Examples: a proposal, a report with code, a poster, a talk, a peer review. One project usually has several deliverables. They belong together: a later deliverable uses the work of an earlier one.
- **Task**: what the work actually does. Examples: "predict the activity of a person from phone sensor signals", "find defects in product images when only a few normal images are available", "argue that a chat model refuses a dangerous request but a robot model does it". All deliverables of a project show the same task.
- **Step**: one thing that the work must do or show. The steps come from the course materials, not from the group's plan.
- **Answer**: how the group does one step. All the answers together are our solution.
- **Framework**: the answers to all the steps. The leader drafts it. All members work inside it.
- **Direction**: something that one member explores inside the framework. A direction is not an owned part of the work. The member chooses it. Two members can explore the same step.
- **Record**: the file `cognition-data/<id>.json`. It contains the project, the task, the steps and the framework. One assignment has one record, also when it has many deliverables. Make a second record only for a second assignment with a different task.

## Commands

`<plugin>` is the directory of this guide. Run the commands from the project root. They need Python 3.9 or later and no packages. If `python` is not found, use `python3`.

```
python <plugin>/ezc.py open
python <plugin>/ezc.py check
python <plugin>/ezc.py init
python <plugin>/ezc.py stop
```

- `open` adds this project to the page, starts the local server if it does not run, and shows the page in the user's browser. It prints the address, the state of each record, the user's name and the git branch. If the page is already open, the page changes to this project, and `open` does not open a second page.
- `check` validates the records. It prints the problems, or `OK`.
- `init` is for the leader's setup.
- `stop` stops the server now, for all projects. Usually you do not need it: the server stops by itself approximately one minute after the user closes the page.

One server and one page show all the projects on the computer. Projects in WSL are included. The address is `http://127.0.0.1:27180/`. If the system refuses this port, the server uses one of the next ports, and `open` prints it. Do not start a server in another way.

The page refreshes by itself when a record changes. The page never calls a model. When the user has a question about the page, the user asks you.

## Set up the project (leader only)

Do the setup on `main`.

1. Put the original course materials in `docs/`. Examples: the assignment, the rubric, the syllabus, the feedback of the teaching assistant. Do not edit them. If some materials are not in the repo, ask the leader for them.
2. Run `init`. It creates `cognition-data/` and adds one line to `AGENTS.md`, so that each member's agent finds this guide.
3. Read all of `docs/`. Then write the record (see "The record"). The project, the task and the steps come only from the course materials, from what the leader tells you, and from the official descriptions of the public datasets, methods and papers that the materials name (see "Describe the task").
4. Draft the framework with the leader: propose an answer for each step, and change it until the leader agrees. A step can stay without an answer.
5. Read the page as a member who knows nothing about the course (see "Write for the page"). Fix each sentence that this member cannot understand.
6. Run `check`, then `open`. The setup is done when the leader has read the page and agrees with it.
7. Commit and push. If `collab-guide.md` applies, send a `framework` message.

## Start of each session

1. Run `open`. If it prints that the user has no name, ask the user to write a name in the settings panel of the page. Do not write it yourself.
2. Read the record. For the exact wording of a requirement, read the source file.
3. Read the Slack channel as `collab-guide.md` tells you.
4. Ask what the user wants to do, if you do not know.

## Explore a direction (members)

The member chooses what to explore. Do not assign a direction to the user, and do not divide the work into owned parts.

1. Update `main`. Create the branch `<name>/<direction-id>` from it. If the branch exists, merge `main` into it.
2. Add the direction to `directions` of the step that it belongs to: `id`, `who` (the user's name) and `explores`. Commit this change early, so that the other members see it.
3. When the user finds something, write `found`: what the user found, and where the work is.
4. Merge into `main` through a pull request, or in the way that the team agreed.

Rules for the record:

- Write only the user's own direction entries.
- A finding can show that the framework must change. Do not change `project`, `task`, `steps`, `answer` or `detail` yourself. Tell the user. The leader decides. After the change is in `main`, send a `framework` message.
- If git reports a conflict in a record, keep the entries of both sides.
- Run `check` after each change. Do not commit a record that has problems.

## The record

One file for each assignment: `cognition-data/<id>.json`. The id is the file name. Ids are lowercase ASCII letters, digits and `-`. Do not change an id after the record is in `main`: branch names, Slack messages and the user's marks use it.

The page shows the parts in this order: the title and the goal, the project, the task, then the steps with our solution.

```json
{
  "title": "共享单车调度小组项目",
  "goal": "我们要用一学期的骑行记录说明：共享单车的缺车问题主要出在工作日早高峰的少数站点，并给出一个调度建议。",
  "sources": ["docs/assignment.pdf", "docs/rubric.pdf"],
  "project": {
    "summary": "先交提案，再交报告和代码（12 月 20 日），最后做海报展示；报告占总成绩 40%",
    "about": "这是数据分析课的小组项目。全组围绕同一个问题做一次完整的数据分析，再用三种形式交出来：提案说明打算做什么，报告和代码给出完整的分析，海报在展示会上向同学讲清结论。",
    "deliverables": [
      { "id": "proposal", "title": "提案", "what": "一页纸：研究问题、数据来源、打算用的方法。", "done": true, "from": "docs/assignment.pdf" },
      { "id": "report", "title": "报告和代码", "what": "8 页以内的报告，加上能重新跑出全部图表的代码。", "due": "2026-12-20", "uses": ["proposal"], "from": "docs/assignment.pdf" },
      { "id": "poster", "title": "海报展示", "what": "一张海报，现场讲 5 分钟。内容来自报告的主要结论。", "due": "2026-12-22", "uses": ["report"] }
    ],
    "items": [
      { "label": "评分", "value": "报告 40%，代码 20%，海报 20%，组内互评 20%。", "from": "docs/rubric.pdf" }
    ]
  },
  "task": {
    "summary": "从骑行记录里找出什么时候、在哪些站点会没车可借，并检验一个简单的调度办法能不能减少这种情况。",
    "questions": [
      { "ask": "我们要做什么？", "answer": "共享单车有时会出现“站点没车可借”。我们要从全年的骑行记录里找出这种情况集中在什么时间、哪些站点，再用同样的数据检验：如果每天早上提前往这些站点补车，缺车会少多少。" },
      { "ask": "举个例子", "answer": "周一早上 8 点，大学城站的车在 10 分钟内被借光，之后 25 分钟里有 14 个人来借车没借到。我们把这样一段“连续 10 分钟没车”记为一次缺车。全年的缺车记录就是我们分析的对象。" }
    ],
    "terms": [
      { "term": "缺车", "means": "一个站点连续 10 分钟没有可借的车。这是我们自己定的标准，报告里要写明。" }
    ]
  },
  "steps": [
    {
      "id": "method",
      "title": "说明方法",
      "ask": "说明用了什么数据和方法，让读者能重复这项分析。",
      "detail": ["评分表的“方法”一项看这一步。"],
      "for": ["report"],
      "from": "docs/assignment.pdf"
    }
  ],
  "answers": {
    "method": {
      "answer": "我们用 2025 年全年的骑行记录，按站点和小时统计缺车次数，因为缺车只在一部分时段出现，按天统计会把它平均掉。",
      "detail": ["数据来自城市开放数据平台，约 1,200 万条骑行记录，每条有借车站点、还车站点和时间。"],
      "directions": [
        {
          "id": "weather",
          "who": "zez",
          "explores": "下雨天的缺车规律是否不同。",
          "found": "雨天早高峰的缺车次数少一半，因为骑车的人少了。图在 `analysis/weather.ipynb`。"
        }
      ]
    }
  }
}
```

| Key | Content |
|---|---|
| `title` | The name of the project, as the members say it. |
| `goal` | One or two sentences: what the group makes, and what it must show. |
| `sources` | The source files. |
| `project.summary` | One line that a member must not miss: the next date, the deliverables, the weight. |
| `project.about` | What this course project is, in a short paragraph. |
| `project.deliverables` | Everything that the group hands in or presents, in time order. `what` says what it is and what it contains. `due` is the date. `done` is `true` when it is handed in. `uses` names the earlier deliverables whose work it uses; the page shows them as "基于：". `note` and `from` are optional. |
| `project.items` | Other requirements: the grading, the team, the rules, the form. |
| `task.summary` | One sentence: what the work does. The closed panel shows it. |
| `task.questions` | The questions that explain the task, and their answers (see "Describe the task"). `detail` and `from` are optional. |
| `task.terms` | Each word that a member must know to read the page, and its meaning. |
| `steps` | What the work must do or show, in order. `ask` says what the step asks. `for` names the deliverables that show this step. `detail` and `from` are optional. |
| `answers.<step-id>.answer` | How the group does that step. The first sentence must make sense alone: the closed row shows it. |
| `answers.<step-id>.detail` | More about the answer: the reasons, the settings, what is not decided. |
| `answers.<step-id>.directions` | What members explore in that step. `found` is optional. |

All keys except `title` and `goal` are optional. `check` reports a key that it does not know.

## Describe the task

A member must understand the task before the steps make sense. Answer these questions in `task.questions`, in this order. They come from the Heilmeier Catechism, a set of questions for explaining a research project to a person outside the field. Write the question in the user's language as `ask`. Leave out a question that does not apply. You can add a question.

1. What are we trying to do? Say it without special words.
2. One example from start to end. Show one real case: what goes in, what happens, what comes out. For a prediction task, show one input and its output, with real sizes and values. For a talk or an argument, show the scene or the case that the talk starts from.
3. Why does it matter? What do people do today, and what is missing?
4. What do we work with? The data, the material or the tools: where they come from, how large they are, what one item looks like.
5. How do we know that it worked? What we measure, and what we compare with.
6. What is hard, and what can go wrong?

Then put in `task.terms` each word that the answers or the steps use and that a member may not know: the names of datasets, methods, measures and course rules, and all abbreviations.

The course materials often only name a public dataset, method or paper. A member cannot understand the task from a name. Read the official description (the page of the dataset, the paper, the documentation of the tool) and give the facts that a member needs: what one item is, how large it is, which classes or parts it has, how it was made. Put that source in `from`. Do not write these facts from memory. If you cannot read the source, say which facts are missing.

## Write for the page

The reader is a member who reads only this page. The member did not read the course materials, the code or your chat with the user. After reading, the member must be able to explain the project, the task and our solution to another person.

- Write full sentences in plain language, as you explain to a classmate. A list of key words is not enough.
- Explain each special word where it first appears, or put it in `task.terms`.
- Give the reason for a decision. "We use X" is not enough; say why.
- When a sentence is abstract, add a concrete example.
- Put the conclusion first. The first sentence of each part must make sense alone.
- Say what is not decided yet, and what it depends on.
- Do not copy the source text, and do not put in every detail. `from` names the source, and agents read it there.
- The only markup is `` `code` ``.
- Write in the user's language.

Before you finish, read the page from top to bottom as this member. Mark each sentence that uses a word or an idea that the page did not explain before. Fix it.

## Questions

The user can ask you about the project. Answer with the framework in mind: say which step the answer is about.

The record is a transcription and can contain errors. If a question needs the exact wording of a requirement, read the source file.

## Scope

- Do not change the files of ez-cognition.
- Do not write in `cognition-data/.local/`. It contains the user's personal state, and git ignores it. The only exception is the file that `collab-guide.md` names.
- Do not write in `~/.ez-cognition/`. It contains the state of the one server: the list of projects and the look of the page. Only `open` and the page write it.
- The marks "我已认知" on the page belong to the user. They are voluntary. Do not ask the user to set them, and do not test the user.
- Do not compare the members, and do not count their work.

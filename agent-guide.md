# ez-cognition agent guide

You work in a student group project. Each member works with their own agent. ez-cognition is a page that helps each member understand the task (what the work actually does), our solution (how the group does each step, and how far it is), and the submit requirements (what to hand in, and when). You write the record. The page shows it. Follow this guide in every work session.

## Words

- **Task**: what the work actually does, as the course describes it. Examples: "predict the activity of a person from phone sensor signals", "find defects in product images when only a few normal images are available".
- **Step**: one thing that the work must do or show. The steps come from the course materials, not from the group's plan.
- **Answer**: how the group does one step. All the answers together are our solution.
- **Framework**: the answers to all the steps. The leader drafts it. All members work inside it.
- **Direction**: something that one member explores inside the framework. The member chooses it. Two members can explore the same step.
- **Deliverable**: one thing that the group hands in or presents: a proposal, a report, code, a poster, a talk. One assignment usually has several deliverables. They belong together.
- **Record**: the file `cognition-data/<id>.json`. It contains the task, the steps, the framework and the submit requirements. One assignment has one record, also when it has many deliverables.

## Commands

`<plugin>` is the directory of this guide. Run the commands from the project root. They need Python 3.9 or later and no packages. If `python` is not found, use `python3`.

```
python <plugin>/ezc.py open
python <plugin>/ezc.py check
python <plugin>/ezc.py init
python <plugin>/ezc.py stop
```

- `open` adds this project to the page, starts the local server if it does not run, and shows the page in the user's browser. It prints the address, the state of each record, the user's name and the git branch. If the page is already open, the page changes to this project, and `open` does not open a second page.
- `check` validates the records and the images. It prints the problems, or `OK`.
- `init` is for the leader's setup.
- `stop` stops the server now, for all projects. Usually you do not need it: the server stops by itself approximately one minute after the user closes the page.

One server and one page show all the projects on the computer. Projects in WSL are included. The address is `http://127.0.0.1:22267/`. If the system refuses this port, the server uses one of the next ports, and `open` prints it. Do not start a server in another way.

The page refreshes by itself when a record changes. The page never calls a model. When the user has a question about the page, the user asks you.

## Set up the project (leader only)

Do the setup on `main`.

1. Put the original course materials in `docs/`. Examples: the assignment, the rubric, the syllabus, the feedback of the teaching assistant. Do not edit them. If some materials are not in the repo, ask the leader for them.
2. Run `init`. It creates `cognition-data/` and adds one line to `AGENTS.md`, so that each member's agent finds this guide.
3. Read all of `docs/`. Then write the record (see "The record"). The content comes only from the course materials, from what the leader tells you, and from the official descriptions of the public datasets, methods and papers that the materials name.
4. Draft the framework with the leader: propose an answer for each step, and change it until the leader agrees. The group aims for the top band of the rubric. A step can stay without an answer.
5. Run `check`, then `open`. The setup is done when the leader has read the page and agrees with it.
6. Commit and push. If `collab-guide.md` applies, send a `framework` message.

## Start of each session

1. Run `open`. If it prints that the user has no name, ask the user to write a name in the settings panel of the page. Do not write it yourself.
2. Read the record. For the exact wording of a requirement, read the source file.
3. Read the Slack channel as `collab-guide.md` tells you.
4. Ask what the user wants to do, if you do not know.

## Explore a direction (members)

The member chooses what to explore. Do not assign a direction to the user.

1. Update `main`. Create the branch `<name>/<direction-id>` from it. If the branch exists, merge `main` into it.
2. Add the direction to `directions` of the step that it belongs to: `id`, `who` (the user's name), `explores` and `state`. Commit this change early, so that the other members see who explores what.
3. Keep `state` true: `doing` while the user works on it, `done` when it is finished. When the user finds something, write `found`: what the user found, and where the work is. If a picture shows it best (a plot, an example output), add it to `media/` and put it in `found`.
4. Merge into `main` through a pull request, or in the way that the team agreed. Tell the other agents on Slack as `collab-guide.md` says.

Rules for the record:

- Write only the user's own direction entries.
- A finding can show that the framework must change. Do not change `task`, `steps`, `answer`, `detail` or `submit` yourself. Tell the user. The leader decides. After the change is in `main`, send a `framework` message.
- The leader's agent keeps the `state` of each answer true.
- If git reports a conflict in a record, keep the entries of both sides.
- Run `check` after each change. Do not commit a record that has problems.

## The record

One file for each assignment: `cognition-data/<id>.json`. The id is the file name. Ids are lowercase ASCII letters, digits and `-`. Do not change an id after the record is in `main`: branch names, Slack messages and the user's marks use it.

The page shows the parts in this order: the title and the goal, the task, our solution, and the submit requirements at the bottom.

```json
{
  "title": "共享单车调度小组项目",
  "goal": "用一学期的骑行记录说明：共享单车的**缺车**主要出在工作日早高峰的少数站点，并给出一个调度建议。",
  "sources": ["docs/assignment.pdf", "docs/rubric.pdf"],
  "terms": [
    { "term": "缺车", "means": "一个站点连续 10 分钟没有可借的车。这是我们自己定的标准。" },
    { "term": "MAE", "means": "平均绝对误差（Mean Absolute Error）：预测值和真实值之差的绝对值的平均。越小越好。" }
  ],
  "task": {
    "summary": "从骑行记录里找出什么时候、在哪些站点会没车可借，并预测下一小时的需求。",
    "cards": [
      {
        "title": "1. 背景与目标",
        "text": "共享单车经常出现**站点没车可借**。课程要求：\n\n- 找出缺车集中的时间和站点\n- 预测每个站点下一小时的借车数\n- 提出一个调度建议，并用数据检验它",
        "image": { "src": "media/empty-station.png", "alt": "周一 8:00 大学城站：10 分钟内车被借光" },
        "from": "docs/assignment.pdf"
      },
      {
        "title": "2. 数据与评测",
        "text": "数据是 2025 年全年的骑行记录（约 1,200 万条），每条有借车站点、还车站点和时间。\n\n| 指标 | 看什么 |\n|---|---|\n| MAE | 需求预测准不准 |\n| 缺车次数 | 调度建议是否有效 |\n\n$\\text{MAE} = \\frac{1}{n}\\sum_{i=1}^{n} |y_i - \\hat{y}_i|$"
      },
      {
        "title": "要点小结",
        "text": "- 先找规律，再预测，最后用同一份数据检验调度建议\n- 报告和海报讲的是同一件事"
      }
    ]
  },
  "steps": [
    {
      "id": "method",
      "title": "说明方法",
      "ask": "说明用了什么数据和方法，让读者能重复这项分析。",
      "rubric": "- 数据来源、预处理和方法**都写清楚**\n- 另一个人能按说明重新跑出结果",
      "for": ["report"],
      "from": "docs/rubric.pdf"
    }
  ],
  "answers": {
    "method": {
      "answer": "按站点和小时统计缺车次数，因为缺车只在一部分时段出现，按天统计会把它平均掉。",
      "detail": "- 缺车的定义见词语注释\n- 是否加入天气数据：**还没定**，取决于下雨天的规律是否不同",
      "image": { "src": "media/hourly.svg", "alt": "工作日每小时的缺车次数，8 点最高" },
      "state": "doing",
      "directions": [
        { "id": "weather", "who": "zez", "explores": "下雨天的缺车规律是否不同。", "found": "雨天早高峰的缺车次数少一半。图在 `analysis/weather.ipynb`。", "state": "done" }
      ]
    }
  },
  "submit": {
    "summary": "12 月 20 日交报告和代码，12 月 22 日海报展示",
    "deliverables": [
      { "id": "proposal", "title": "提案", "what": "一页：问题、数据、方法。", "done": true },
      { "id": "report", "title": "报告和代码", "what": "8 页以内的报告，加上能重跑全部图表的代码。", "due": "12-20 23:59", "uses": ["proposal"] },
      { "id": "poster", "title": "海报展示", "what": "一张海报，现场讲 5 分钟。", "due": "12-22 14:00", "uses": ["report"] }
    ],
    "items": [
      { "label": "评分", "value": "报告 40%，代码 20%，海报 20%，组内互评 20%。", "from": "docs/rubric.pdf" },
      { "label": "迟交", "value": "每晚一天扣 10%。" }
    ]
  }
}
```

| Key | Content |
|---|---|
| `title` | The name of the assignment, as the members say it. |
| `goal` | One or two sentences: what the group makes, and what it must show. |
| `sources` | The source files. The page does not show them. |
| `terms` | Each word that a member may not know, and its meaning. The page shows a note when the member points at the word. |
| `task.summary` | One sentence: what the work does. The closed panel shows it. |
| `task.cards` | The task as a study note (see "Write the task"). Each card has a `title`, a Markdown `text`, and an optional `image`. |
| `steps` | What the work must do or show, in order. `ask` says what the step asks. `rubric` says what the top band of the rubric asks for this step. `for` names the deliverables that show the step. |
| `answers.<step-id>.answer` | How the group does that step, in one or two sentences. The closed row shows its first line. |
| `answers.<step-id>.detail` | More: the reasons, the settings, what is not decided and what it depends on. |
| `answers.<step-id>.image` | A picture of the answer: a diagram, a plot, an example output. |
| `answers.<step-id>.state` | `todo`, `doing` or `done`. |
| `answers.<step-id>.directions` | Who explores what in that step: `id`, `who`, `explores`, `found`, `state`. |
| `submit.summary` | One line: the next deadlines and what is due. |
| `submit.deliverables` | Each deliverable, in time order. `due` is the deadline (short: `12-11 23:59`). `what` is one short line. `done` is `true` when it is handed in. `uses` names the earlier deliverables it builds on. |
| `submit.items` | Grading, late rules and other rules, one short line each. |

All keys except `title` and `goal` are optional. `from` is optional on cards, terms, steps, deliverables and items: it names the source for the agents, and the page does not show it. `check` reports a key that it does not know.

## Write the task

Write `task.cards` as a study note of the course's own task description:

- Follow the source's own heading order. One card for each part of the source. Do not add parts that the source does not have.
- Explain; do not transcribe. Use lists and tables for definitions, procedures and comparisons.
- At the first use of a technical word, give its English original, for example `受试者留一（Leave-One-Subject-Out, LOSO）`. Put the words that a member may not know in `terms` too.
- The course materials often only name a public dataset, method or paper. Read its official description and put the facts that a member needs in `terms` or in a card: what one item is, how large it is, which classes it has. Do not write such facts from memory.
- End with a card "要点小结": the few things that a member must remember.

## Images

A card shows its text on the left and its image on the right. An image often explains more than a paragraph. Add one where it helps:

- a real item of the data (one input image, one signal window as a plot);
- a figure from the course materials or from the paper of the method;
- a diagram that you draw as an SVG file (a pipeline, the steps of the method);
- a plot of a result, when the result exists.

Put the image files in `cognition-data/media/` and write the path as `media/<file>`. Allowed: PNG, JPG, GIF, WebP and SVG. Keep each file small (under 500 KB). `alt` says what the image shows, in one line: the page shows it under the image. Do not draw data or results that do not exist. `check` reports an image that is missing.

## Write for the page

The page should be as clear as a good README.

- Use Markdown: `**bold**` for the key facts, lists, tables, `` `code` ``, links and math in `$...$`. Use headings (`###`) only inside a long card.
- Short is better. One idea per card. The first sentence says the conclusion.
- Write full sentences in plain language, as you explain to a classmate.
- Say what is not decided yet, and what it depends on.
- Do not copy the source text, and do not put in every detail. The page does not show sources; agents read the details in `docs/`.
- Write in the user's language.

## Questions

The user can ask you about the project. Answer with the framework in mind: say which step the answer is about.

The record is a transcription and can contain errors. If a question needs the exact wording of a requirement, read the source file.

## Scope

- Do not change the files of ez-cognition.
- Do not write in `cognition-data/.local/`. It contains the user's personal state, and git ignores it. The only exception is the file that `collab-guide.md` names.
- Do not write in `~/.ez-cognition/`. It contains the state of the one server: the list of projects and the look of the page. Only `open` and the page write it.
- The marks "我已认知" on the page belong to the user. They are voluntary. Do not ask the user to set them, and do not test the user.
- The page shows who explores what. Do not compare the members, and do not count their work.

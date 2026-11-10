# ez-cognition

小组项目里，每个人都和自己的 agent 一起干活。活干得很快，但人很容易不知道整个项目在做什么。ez-cognition 是一个本地网页，帮你理解项目：**任务要求什么，一步一步是什么，我们组每一步打算怎么回答。**

它是帮你理解的工具，不是监督工具：

- 没有打卡、排名和工作量对比。“我已认知”是你自己愿意才点的标记，没有测验。
- 没有常驻的东西。你关掉网页大约一分钟后，本地服务自己退出。
- 网页不调用任何模型。有问题就问你自己的 agent。
- 网页是用来理解的，不是用来查资料的：先说结论，先看整体再看局部。细节留在原始材料里，由 agent 去读。

## 页面上有什么

一个任务一页。一页从上到下是几个可以展开和收起的栏目：

| 栏目 | 内容 |
|---|---|
| 任务要求 | 什么时候交、交什么、什么形式、怎么评分。 |
| 任务步骤 | 任务要求我们做的事，一步一行。每一行右边是我们的回答，一句话。 |
| 我们的回答 | 展开一步就能看到：组长起草的回答，和组员正在这一步里探索的方向。 |
| 设置 | 你的名字、主题、动效。只存在你自己的电脑上。 |

协作的方式是：组长先把框架打好（每一步的回答），然后每个人在框架里自由探索一个方向。方向不是分给谁的一块活。

## 怎么用

需要 Python 3.9 或更新的版本，不需要安装任何包。

组长：

1. 把 ez-cognition 放进项目，例如作为 git submodule：`git submodule add <ez-cognition 的仓库地址> ez-cognition`。
2. 对你的 agent 说：“读 `ez-cognition/agent-guide.md`，帮我做组长的初始化。”
3. agent 会读课程材料、写任务记录、和你一起起草框架，然后打开网页给你看。你同意了才算完成。

组员：

1. 拉取项目（带上 submodule）。
2. 对你的 agent 说：“打开 ez-cognition。”
3. 在网页的“设置”里写上你的名字。

任务记录变了，网页会自己刷新，变了的那一行会亮一下。

## 文件在哪里

```
你的项目/
  cognition-data/
    talk.json        一个任务一个文件，由 agent 写，提交到 git
    report.json
    .local/          你个人的状态，git 忽略
  ez-cognition/      本仓库，agent 不改它
```

## 一切皆插件

核心很小：一个本地服务、一个页面外壳、一个注册表。它不知道什么是“任务步骤”。页面上的每个栏目都是 `modules/` 里的一个文件夹，主题是 `themes/` 里的一个 CSS 文件。删掉任何一个栏目，核心照样运行。

```
core/                页面外壳、注册表、折叠、个人状态、自动刷新
modules/<名字>/
  module.js          在注册表里登记这个栏目
  module.css         可选
  schema.json        可选：这个栏目用到的任务记录字段
  check.py           可选：schema 表达不了的检查
themes/<名字>.css    一组颜色和字体变量
ez_cognition/        本地服务和命令（只用 Python 标准库）
```

加一个栏目：新建 `modules/<名字>/module.js`，从 `/core/core.js` 引入 `registry`，登记一个 `panel`。栏目也可以定义自己的扩展点：`steps` 定义了 `step-part`，`answers` 就是往每一步里加内容的插件。

## 开发

```
python -m unittest discover -s tests -t .
python ezc.py --root <一个项目> serve
```

给 agent 看的规则在 [agent-guide.md](agent-guide.md)（英文）和 [collab-guide.md](collab-guide.md)（Slack 协作）。

ez-cognition 是 [ezgoggles](https://github.com/Pmechano/ezgoggles)（终端界面版）的重写。

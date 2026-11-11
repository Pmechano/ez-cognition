# ez-cognition

小组项目里，每个人都和自己的 agent 一起干活。活干得很快，但人很容易不知道整个项目在做什么。ez-cognition 是一个本地网页，帮你理解三件事：**任务到底在做什么，我们组每一步打算怎么做、做到哪了，以及要交什么、什么时候交。**

它是帮你理解的工具，不是监督工具：

- 没有打卡、排名和工作量对比。“我已认知”是你自己愿意才点的标记，没有测验。
- 本地服务常驻，你随时打开 `http://127.0.0.1:22267/` 都能看；不开机自启，agent 下次运行 `open` 时会把它打开。
- 网页不调用任何模型。有问题就问你自己的 agent。
- 网页是用来理解的，不是用来查资料的：假设你只读这个网页，也能把项目讲给别人听。先说结论，先看整体再看局部；原文细节留在课程材料里，由 agent 去读。

## 页面上有什么

一个作业一页（提案、报告、海报这些交付物都在同一页里）。一页从上到下是几个可以展开和收起的栏目：

页面像一个 wiki：左边是边栏，有项目切换、多级目录（带进度）和左下角的设置；右边是全部展开的内容。每个位置有自己的链接，可以直接发给组员。

| 栏目 | 内容 |
|---|---|
| 任务 | 课程任务描述的中文翻译总结：按原文一节一张卡片，图片放在正文里，最后是要点小结。 |
| 我们的方案 | 一步一行，带进度（未开始 / 进行中 / 已完成）。展开一步能看到：这一步要做的、拿高分要做到什么、组长起草的方案、谁在探索什么。 |
| 提交要求 | 截止时间、要交什么、交了没有；评分和迟交规则。 |

文字按 Markdown 显示（加粗、列表、表格、公式）。专有名词下面有虚线，鼠标指上去（手机上点一下）会弹出解释。

agent 需要、人不需要的细节（参数、路径、命令）写在隐藏的“agent 附注”里，在设置里打开“显示 agent 附注”就能看到。
| 设置 | 你在这个项目里的名字；外观（跟随系统、深色、浅色）和动效。只存在你自己的电脑上。 |

协作的方式是：组长先把框架打好（每一步的回答），然后每个人在框架里自由探索一个方向。方向不是分给谁的一块活。

## 怎么用

需要 Python 3.9 或更新的版本，不需要安装任何包。

组长：

1. 把 ez-cognition 作为 git submodule 放进项目，用公开地址：`git submodule add https://github.com/Pmechano/ez-cognition.git ez-cognition`。不要用本地路径，否则组员拉不下来。
2. 对你的 agent 说：“读 `ez-cognition/agent-guide.md`，帮我做组长的初始化。”
3. agent 会读课程材料、写记录、和你一起起草框架，然后打开网页给你看。你同意了才算完成。

组员：

1. 拉取项目时带上 submodule：`git clone --recurse-submodules <项目地址>`。已经拉过的，运行 `git submodule update --init`。
2. 对你的 agent 说：“打开 ez-cognition。”
3. 在网页的“设置”里写上你的名字。

记录变了，网页会自己刷新，变了的那一行会亮一下。

一台电脑上只有一个服务、一个页面：`http://127.0.0.1:22267/`。你的所有项目都在这个页面上，在顶上切换；WSL 里的项目也一样。哪个 agent 运行 `open`，页面就切到它的项目。

## 文件在哪里

```
你的项目/
  cognition-data/
    final.json       一个作业一个文件（记录），由 agent 写，提交到 git
    media/           记录用到的图片
    .local/          你在这个项目里的个人状态（名字、展开了什么、我已认知），git 忽略
  ez-cognition/      本仓库，agent 不改它
  human.md           只有人写的笔记：想法、决定、对 agent 的纠正；agent 只读，以它为准
  handbook.md        给全组 agent 的手册：当前有效的说明，每次 push 前更新
  journal.md         agent 干活时的随手记，追加式
  handbook.local.md  只给自己 agent 的手册，git 忽略

~/.ez-cognition/     这台电脑上唯一的服务：项目列表、页面外观、服务的状态和日志
```

## 一切皆插件

核心很小：一个本地服务、一个页面外壳、一个注册表。它不知道什么是“任务步骤”。页面上的每个栏目都是 `modules/` 里的一个文件夹，主题是 `themes/` 里的一个 CSS 文件。删掉任何一个栏目，核心照样运行。

```
core/                页面外壳、注册表、折叠、个人状态、自动刷新、Markdown 渲染（md.js）
  vendor/temml/      公式渲染库 Temml 0.14.0（MIT），只在页面有公式时加载
modules/<名字>/
  module.js          在注册表里登记这个栏目
  module.css         可选
  schema.json        可选：这个栏目用到的记录字段
  check.py           可选：schema 表达不了的检查
themes/<名字>.css    一组颜色和字体变量
ez_cognition/        本地服务和命令（只用 Python 标准库）
```

加一个栏目：新建 `modules/<名字>/module.js`，从 `/core/core.js` 引入 `registry`，登记一个 `panel`。栏目也可以定义自己的扩展点：`steps` 定义了 `step-part`，`answers` 就是往每一步里加内容的插件。

## 开发

```
python -m unittest discover -s tests -t .
python ezc.py serve      # 在这个终端里运行服务，显示 ~/.ez-cognition/projects.json 里的所有项目
```

给 agent 看的规则在 [agent-guide.md](agent-guide.md)（英文）和 [collab-guide.md](collab-guide.md)（Slack 协作）。

ez-cognition 是 [ezgoggles](https://github.com/Pmechano/ezgoggles)（终端界面版）的重写。

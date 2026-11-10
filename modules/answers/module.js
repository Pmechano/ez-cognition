// Step part: how the group answers each step.
// Data: task.answers = { "<step id>": { answer, detail?: [..], directions?: [..] } }
//       direction = { id, who, explores, found? }
//
// `answer` and `detail` are the framework: the shared answer that the leader
// drafts. `directions` are what members explore freely inside it. A direction
// is not an owned part of the work, so this part shows no owner and no counts.

import { registry, h, rich, points, t, user } from "/core/core.js";

const of = (step, task) => task.answers?.[step.id] ?? null;

registry.add("step-part", {
  id: "answers",
  order: 10,
  title: () => t("answers.title", "我们的回答"),
  data: of,
  summary: (step, task) => of(step, task)?.answer ?? null,
  render(step, task, el) {
    const mine = of(step, task);
    el.append(h("div", { class: "label" }, "// ", t("answers.title", "我们的回答")));
    if (!mine) {
      el.append(h("p", { class: "dim" }, t("answers.none", "还没有回答。组长起草框架后，它会出现在这里。")));
      return;
    }
    el.append(h("p", { class: "bright" }, rich(mine.answer)));
    if (mine.detail?.length) el.append(points(mine.detail));

    const directions = mine.directions ?? [];
    if (!directions.length) return;
    const me = user().name;
    el.append(h("div", { class: "label directions-label" }, "// ", t("answers.directions", "正在探索的方向")));
    for (const direction of directions) {
      el.append(
        h(
          "div",
          { class: "direction" },
          h(
            "div",
            null,
            h("span", { class: me && direction.who === me ? "bright" : null }, direction.who),
            h("span", { class: "dim" }, ` / ${direction.id}`),
          ),
          h("div", { class: "direction-body" }, h("span", { class: "dim" }, t("answers.explores", "探索：")), rich(direction.explores)),
          h(
            "div",
            { class: "direction-body" },
            h("span", { class: "dim" }, t("answers.found", "发现：")),
            direction.found ? rich(direction.found) : h("span", { class: "dim" }, t("answers.nofound", "还没有")),
          ),
        ),
      );
    }
  },
});

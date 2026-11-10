// Panel: the personal settings of the user. The server writes them to
// cognition-data/.local/user.json, which git ignores.

import { registry, h, t, user, saveUser, manifest } from "/core/core.js";

const NAME = /^[a-z0-9][a-z0-9-]{0,29}$/;

registry.add("panel", {
  id: "settings",
  order: 900,
  open: false,
  title: () => t("settings.title", "设置"),
  summary: () => user().name || t("settings.noname", "还没有名字"),
  render(task, el) {
    const me = user();
    const hint = h("span", { class: "dim" });
    const input = h("input", {
      type: "text",
      value: me.name,
      maxlength: "30",
      spellcheck: "false",
      autocomplete: "off",
      "aria-label": t("settings.name", "名字"),
    });
    const say = (text, hot) => {
      hint.className = hot ? "hot" : "dim";
      hint.textContent = text;
    };
    const keep = () => {
      const name = input.value.trim();
      if (name === user().name) return;
      if (name !== "" && !NAME.test(name)) {
        say(t("settings.name.bad", "只能用小写英文字母、数字和 -"), true);
        return;
      }
      saveUser({ name });
      say(t("settings.saved", "已保存"), false);
      const summary = el.closest(".panel")?.querySelector(".panel-summary");
      if (summary) summary.textContent = name || t("settings.noname", "还没有名字");
    };
    input.addEventListener("change", keep);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") input.blur();
    });
    say(t("settings.name.why", "分支名和方向记录用它。小写英文字母、数字和 -"), false);

    const rows = [
      h("label", { class: "set-row" }, h("span", { class: "dim" }, t("settings.name", "名字")), h("span", null, input, " ", hint)),
    ];

    const themes = manifest().themes;
    if (themes.length > 1) {
      const select = h(
        "select",
        { "aria-label": t("settings.theme", "主题"), onchange: (event) => saveUser({ theme: event.target.value }) },
        themes.map((name) => h("option", { value: name, selected: name === me.theme }, name)),
      );
      rows.push(h("label", { class: "set-row" }, h("span", { class: "dim" }, t("settings.theme", "主题")), select));
    }

    const motion = h(
      "button",
      {
        type: "button",
        class: "set-toggle",
        onclick: () => {
          saveUser({ motion: !user().motion });
          motion.firstChild.textContent = user().motion ? "[x] " : "[ ] ";
        },
      },
      me.motion ? "[x] " : "[ ] ",
      t("settings.motion.on", "刷新后，标出变了的那一行"),
    );
    rows.push(h("div", { class: "set-row" }, h("span", { class: "dim" }, t("settings.motion", "动效")), motion));

    el.append(h("div", { class: "set" }, rows));
  },
});

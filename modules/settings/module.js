// The settings of the user, in the window of the gear at the bottom left.
// The name belongs to this project (cognition-data/.local/user.json, which
// git ignores). The look is the same in all projects (~/.ez-cognition/user.json).

import { registry, h, t, user, saveUser, manifest } from "/core/core.js";

const NAME = /^[a-z0-9][a-z0-9-]{0,29}$/;
const SCHEME = { dark: "深色", light: "浅色" };

function toggle(key, label) {
  const button = h(
    "button",
    {
      type: "button",
      class: "set-toggle",
      role: "switch",
      "aria-checked": String(Boolean(user()[key])),
      onclick: () => saveUser({ [key]: !user()[key] }, true),
    },
    h("span", { class: user()[key] ? "switch-on" : "switch-off" }, user()[key] ? "开" : "关"),
    " ",
    label,
  );
  return button;
}

registry.add("panel", {
  id: "settings",
  slot: "settings",
  title: () => t("settings.title", "设置"),
  render(task, el) {
    const me = user();
    const hint = h("div", { class: "set-hint dim" });
    const input = h("input", {
      type: "text",
      value: me.name,
      maxlength: "30",
      spellcheck: "false",
      autocomplete: "off",
      placeholder: t("settings.name.placeholder", "例如 zez"),
      "aria-label": t("settings.name", "名字"),
    });
    const say = (text, hot) => {
      hint.className = hot ? "set-hint hot" : "set-hint dim";
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
    };
    input.addEventListener("change", keep);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") input.blur();
    });
    say(t("settings.name.why", "只在这个项目里用：分支名和方向记录用它"), false);

    const rows = [
      h("label", { class: "set-row" }, h("span", { class: "set-label" }, t("settings.name", "名字")), input, hint),
    ];

    const themes = manifest().themes;
    if (themes.length > 1) {
      const label = (theme) => `${t(`settings.scheme.${theme.scheme}`, SCHEME[theme.scheme] ?? theme.scheme)} · ${theme.name}`;
      const options = [{ value: "auto", text: t("settings.theme.auto", "跟随系统") }].concat(
        themes.map((theme) => ({ value: theme.name, text: label(theme) })),
      );
      rows.push(
        h(
          "label",
          { class: "set-row" },
          h("span", { class: "set-label" }, t("settings.theme", "外观")),
          h(
            "select",
            { onchange: (event) => saveUser({ theme: event.target.value }) },
            options.map((o) => h("option", { value: o.value, selected: o.value === me.theme }, o.text)),
          ),
        ),
      );
    }

    rows.push(
      h("div", { class: "set-row" }, toggle("motion", t("settings.motion", "动效：标出刷新后变了的地方"))),
      h("div", { class: "set-row" }, toggle("notes", t("settings.notes", "显示 agent 附注"))),
    );
    el.append(h("div", { class: "set" }, h("div", { class: "set-head" }, t("settings.title", "设置")), rows));
  },
});

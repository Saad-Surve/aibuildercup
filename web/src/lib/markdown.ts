/**
 * Shared Markdown rendering.
 *
 * `markdown-it` (CommonMark) with `shiki` syntax highlighting for fenced code blocks. Shiki runs
 * through its synchronous JavaScript engine so the same renderer can be used from the draft
 * editor's synchronous `innerHTML` path as well as from React components.
 *
 * Raw HTML is disabled (`html: false`), so model output cannot inject markup. Links are validated
 * by markdown-it, which rejects `javascript:` URLs.
 */
import MarkdownIt from "markdown-it";
import { createHighlighterCoreSync } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";
import bash from "shiki/langs/bash.mjs";
import css from "shiki/langs/css.mjs";
import html from "shiki/langs/html.mjs";
import javascript from "shiki/langs/javascript.mjs";
import json from "shiki/langs/json.mjs";
import jsx from "shiki/langs/jsx.mjs";
import markdown from "shiki/langs/markdown.mjs";
import python from "shiki/langs/python.mjs";
import shell from "shiki/langs/shell.mjs";
import tsx from "shiki/langs/tsx.mjs";
import typescript from "shiki/langs/typescript.mjs";
import yaml from "shiki/langs/yaml.mjs";
import githubDark from "shiki/themes/github-dark.mjs";
import githubLight from "shiki/themes/github-light.mjs";

/** Languages bundled for highlighting. Add here if a new fence language shows up often. */
function createHighlighter() {
  return createHighlighterCoreSync({
    themes: [githubLight, githubDark],
    langs: [
      bash,
      css,
      html,
      javascript,
      json,
      jsx,
      markdown,
      python,
      shell,
      tsx,
      typescript,
      yaml,
    ],
    engine: createJavaScriptRegexEngine(),
  });
}

let highlighter: ReturnType<typeof createHighlighter> | undefined;
const loadedLanguages = new Set([
  "bash",
  "css",
  "html",
  "javascript",
  "json",
  "jsx",
  "markdown",
  "python",
  "shell",
  "tsx",
  "typescript",
  "yaml",
]);

const LANG_ALIASES: Record<string, string> = {
  bash: "bash",
  sh: "shell",
  shell: "shell",
  zsh: "shell",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  ts: "typescript",
  py: "python",
  yml: "yaml",
  md: "markdown",
};

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Highlight a fenced code block. The `<pre>` is tagged with `data-language` so the draft editor
 * can round-trip the fence language when it serializes the DOM back to Markdown.
 */
export function highlightCode(code: string, language = ""): string {
  const requested =
    (language || "").trim().split(/\s+/)[0]?.toLowerCase() ?? "";
  const resolved = LANG_ALIASES[requested] ?? requested;
  const dataLang = requested ? ` data-language="${escapeHtml(requested)}"` : "";
  if (!loadedLanguages.has(resolved)) {
    return `<pre class="shiki"${dataLang}><code>${escapeHtml(code)}</code></pre>`;
  }
  // Ordinary prose never needs to compile grammars or initialize the regex engine.
  highlighter ??= createHighlighter();
  const rendered = highlighter.codeToHtml(code, {
    lang: resolved,
    themes: { light: "github-light", dark: "github-dark" },
    defaultColor: false,
  });
  // Inject the fence language onto the <pre> (shiki omits it from the output).
  return requested
    ? rendered.replace(/^<pre/, `<pre data-language="${escapeHtml(requested)}"`)
    : rendered;
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight: (code, language) => highlightCode(code, language),
});

/** Render Markdown to safe HTML. Raw HTML is escaped. */
export function renderMarkdown(source: string): string {
  return md.render(source ?? "");
}

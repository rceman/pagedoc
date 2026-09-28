"""Built-in M1 reference theme.

This is intentionally minimal: enough to demonstrate the fixed page
shell, prose/mono typography, and every v1 component surface. Real
geometry/layout intelligence arrives in M2.
"""

DEFAULT_CSS = """\
:root {
  --pd-page-width: 980px;
  --pd-bg: #ffffff;
  --pd-page-bg: #ffffff;
  --pd-ink: #1a1a1a;
  --pd-muted: #555555;
  --pd-line: #cccccc;
  --pd-surface: #f6f6f6;
  --pd-accent: #204ecf;
  --pd-warning: #8a5200;
  --pd-mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  --pd-prose: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 0; background: var(--pd-bg); color: var(--pd-ink);
  font-family: var(--pd-prose); font-size: 15px; line-height: 1.5; }
.pd-document { display: flex; flex-direction: column; align-items: center; gap: 32px; }
.pd-page { width: var(--pd-page-width); min-height: 1200px; background: var(--pd-page-bg);
  border: 1px solid var(--pd-line); box-shadow: 0 1px 4px rgba(0,0,0,0.12); }
.pd-page-header { padding: 28px 40px 12px; border-bottom: 2px solid var(--pd-ink); }
.pd-page-group { margin: 0; font-size: 12px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--pd-muted); }
.pd-page-title { margin: 4px 0 0; font-size: 24px; }
.pd-page-content { padding: 24px 40px 40px; }
.pd-page-content > * { margin: 0 0 16px; }
.pd-page-content > *:last-child { margin-bottom: 0; }
h1, h2, h3, h4, h5, h6 { margin: 0.6em 0 0.4em; line-height: 1.25; }
p { margin: 0 0 0.8em; }
table { border-collapse: collapse; margin: 0 0 1em; font-size: 14px; }
th, td { border: 1px solid var(--pd-line); padding: 6px 12px; text-align: left; }
th { background: var(--pd-surface); }
code { font-family: var(--pd-mono); font-size: 0.92em; background: var(--pd-surface);
  padding: 1px 4px; border-radius: 3px; }
pre.pd-code, .pd-request-body, .pd-response-body { font-family: var(--pd-mono);
  font-size: 13px; line-height: 1.45; background: var(--pd-surface);
  border: 1px solid var(--pd-line); border-radius: 4px; padding: 12px 14px;
  margin: 0; overflow-x: auto; white-space: pre; }
pre.pd-code code, .pd-request-body code, .pd-response-body code {
  background: none; padding: 0; }
blockquote { margin: 0 0 1em; padding: 0 0 0 14px; border-left: 3px solid var(--pd-line);
  color: var(--pd-muted); }
a { color: var(--pd-accent); }
hr { border: none; border-top: 1px solid var(--pd-line); margin: 1em 0; }
.pd-request, .pd-response { margin: 0 0 16px; }
.pd-request figcaption, .pd-response figcaption, .pd-media figcaption {
  font-size: 12px; font-weight: 600; letter-spacing: 0.04em; color: var(--pd-muted);
  margin-bottom: 4px; }
.pd-response-status { display: inline-block; margin-left: 8px; padding: 0 8px;
  border: 1px solid var(--pd-line); border-radius: 10px; font-family: var(--pd-mono);
  font-size: 11px; background: var(--pd-surface); }
.pd-response-status::before { content: "status "; }
.pd-browser { margin: 0 0 16px; border: 1px solid var(--pd-line); border-radius: 6px;
  overflow: hidden; }
.pd-browser-title { font-size: 12px; padding: 4px 12px; background: var(--pd-surface);
  border-bottom: 1px solid var(--pd-line); color: var(--pd-muted); }
.pd-browser-bar { display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  font-family: var(--pd-mono); font-size: 13px; }
.pd-browser-secure { color: #0a6b2d; border: 1px solid #0a6b2d; border-radius: 10px;
  padding: 0 8px; font-size: 11px; font-family: var(--pd-prose); }
.pd-browser-insecure { color: var(--pd-muted); border: 1px solid var(--pd-line);
  border-radius: 10px; padding: 0 8px; font-size: 11px; font-family: var(--pd-prose); }
.pd-browser-status { margin-left: auto; color: var(--pd-muted); font-size: 11px;
  font-family: var(--pd-prose); }
.pd-url-scheme { color: var(--pd-muted); }
.pd-url-host { font-weight: 600; }
.pd-url-path, .pd-url-query, .pd-url-fragment, .pd-url-port, .pd-url-userinfo,
.pd-url-delim { color: var(--pd-muted); }
.pd-note, .pd-result { border: 1px solid var(--pd-line); border-left: 4px solid var(--pd-accent);
  border-radius: 4px; padding: 12px 16px; margin: 0 0 16px; background: var(--pd-surface); }
.pd-note--tone-warning { border-left-color: var(--pd-warning); }
.pd-result { border-left-color: #0a6b2d; }
.pd-note-title, .pd-result-title, .pd-flow-title { font-weight: 700; margin: 0 0 6px; }
.pd-note > :last-child, .pd-result > :last-child { margin-bottom: 0; }
.pd-row { display: flex; gap: 16px; align-items: flex-start; margin: 0 0 16px; }
.pd-row--align-stretch { align-items: stretch; }
.pd-row-cell { min-width: 0; }
.pd-row-cell > *:last-child { margin-bottom: 0; }
.pd-row--split-equal .pd-row-cell { flex: 1 1 0; }
.pd-row--split-wide-left .pd-row-cell:first-child { flex: 2 1 0; }
.pd-row--split-wide-left .pd-row-cell:last-child { flex: 1 1 0; }
.pd-row--split-wide-right .pd-row-cell:first-child { flex: 1 1 0; }
.pd-row--split-wide-right .pd-row-cell:last-child { flex: 2 1 0; }
.pd-compare { margin: 0 0 16px; border: 1px solid var(--pd-line); border-radius: 4px; }
.pd-compare-sides { display: flex; gap: 0; }
.pd-compare--layout-vertical .pd-compare-sides { flex-direction: column; }
.pd-compare-side { flex: 1 1 0; min-width: 0; padding: 12px 16px; }
.pd-compare-side + .pd-compare-side { border-left: 1px solid var(--pd-line); }
.pd-compare--layout-vertical .pd-compare-side + .pd-compare-side {
  border-left: none; border-top: 1px solid var(--pd-line); }
.pd-compare-label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--pd-muted); margin: 0 0 8px; }
.pd-compare-side > :last-child { margin-bottom: 0; }
.pd-flow { margin: 0 0 16px; }
.pd-flow-steps { display: flex; gap: 12px; list-style: none; margin: 0; padding: 0; }
.pd-flow--layout-vertical .pd-flow-steps { flex-direction: column; }
.pd-step { flex: 1 1 0; min-width: 0; border: 1px solid var(--pd-line);
  border-radius: 4px; padding: 10px 14px; position: relative; }
.pd-flow--layout-horizontal .pd-step + .pd-step { margin-left: 8px; }
.pd-flow--layout-horizontal .pd-step + .pd-step::before {
  content: "\\2192"; position: absolute; left: -14px; top: 10px; color: var(--pd-muted); }
.pd-step-label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--pd-muted); margin: 0 0 6px; }
.pd-step > :last-child { margin-bottom: 0; }
.pd-media { margin: 0 0 16px; }
.pd-media-img { display: block; max-width: 100%; border: 1px solid var(--pd-line);
  border-radius: 4px; }
.pd-media--fit-cover .pd-media-img { width: 100%; object-fit: cover; }
.pd-media--fit-contain .pd-media-img { object-fit: contain; }
.pd-media-title { font-weight: 600; }
.pd-md-image-remote { font-family: var(--pd-mono); font-size: 0.92em;
  color: var(--pd-muted); }
"""

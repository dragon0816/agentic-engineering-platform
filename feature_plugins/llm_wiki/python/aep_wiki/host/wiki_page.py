"""The LLM Wiki maintenance page: its CSS, Knowledge pane and script.

The `知識庫維護` tab of Knowledge (docs/phases/KNOWLEDGE_K1.md, knowledge
repositories R4b): the three guided steps on a sandbox or a wiki repository,
the repositories and their versions. Moved out of `web_page.py` unchanged
(docs/phases/FEATURE_PLUGIN_WIKI_PROPOSAL_DRAFT_20261118.md, owner 2026-11-18
D2); the feature fills the page slots with them, ahead of BI (`page_order`).
The shell keeps what Reviews, memory and BI share with it: `kpRun`,
`kpStatus`, `kpWithProgress`, `kpButton`, `askableLoad`, `stepperSet` and
their CSS, and three Wiki rules (`.kp-nav button`, `.kp-repos`, `.kp-doc`)
that later shell rules override where they are: moved, they would win and the
page would change.
"""

WIKI_CSS = r"""
.kp-banner { border: 1px solid #c9d8f5; background: #eef3fb; border-radius: 8px;
  padding: 8px 12px; margin: 8px 0; }
.kp-list button { margin: 2px 6px 2px 0; }
.kp-check { display: inline-block; margin: 2px 14px 2px 0; }
/* The steps, the status and the progress stay on top while the page scrolls (owner
   2026-10-14); kpStage scrolls a new step title to just below them. */
.kp-top { position: sticky; top: 0; z-index: 6; background: var(--bg); padding-bottom: 2px; }
.kp-advanced summary { cursor: pointer; font-weight: 600; }
#kp-assist-input { width: 100%; }
.kp-turn { margin: 6px 0; padding: 6px 8px; border-radius: 6px; }
.kp-running { border: 1px dashed var(--accent, #2b6cb0); }
.kp-steps { margin: 4px 0 0 18px; padding: 0; }
.kp-steps .kp-now { font-weight: 600; }
.kp-steps .kp-later { opacity: 0.55; }
.kp-tabs { display: flex; gap: 4px; margin: 6px 0; }
.kp-tabs [role="tab"][aria-selected="true"] { background: var(--accent, #2b6cb0); color: #fff; }
.kp-panes { display: flex; height: 70vh; min-height: 360px; gap: 0; }
.kp-pane { position: relative; display: flex; flex-direction: column; min-width: 0;
  border: 1px solid var(--line, #ddd); border-radius: 6px; background: var(--panel, #fff);
  padding-top: 0; max-width: none; }  /* a <section>: drop the page's section padding */
.kp-pane > header { padding: 6px 48px 6px 10px; font-weight: 600; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; border-bottom: 1px solid var(--line, #ddd); }
.kp-pane-body { flex: 1; overflow: auto; position: relative; min-height: 0; }
.kp-split { flex: 0 0 8px; cursor: col-resize; touch-action: none; }
.kp-split:hover { background: var(--accent-soft, #dbe8f7); }
/* Top right, in the pane's header row, clear of the scrollbar arrows (owner 2026-10-14). */
.kp-max { position: absolute; right: 8px; top: 4px; z-index: 3; padding: 2px 8px; opacity: 0.8; }
.kp-pane.kp-maxed { position: fixed; inset: 16px; z-index: 60; flex-basis: auto !important;
  box-shadow: 0 8px 30px rgba(0,0,0,0.25); }
.kp-filebody { display: flex; flex-direction: column; overflow: hidden; }
.kp-md-view { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.kp-block { display: flex; flex-direction: column; flex: 1 1 0; min-height: 0;
  border-bottom: 1px solid var(--line, #ddd); }
.kp-block.kp-collapsed { flex: 0 0 auto; }
.kp-block.kp-collapsed .kp-block-body { display: none; }
.kp-block.kp-collapsed .kp-chev { display: inline-block; transform: rotate(-90deg); }
.kp-block-head { text-align: left; border: 0; border-bottom: 1px solid var(--line, #ddd);
  background: var(--panel, #fff); padding: 6px 10px; font-weight: 600; cursor: pointer; }
.kp-block-body { flex: 1; min-height: 0; overflow: auto; position: relative; }
.kp-diffrows, .kp-code, #kp-rule-text, .kp-gutter { font-family: ui-monospace, Consolas, monospace;
  font-size: 13px; line-height: 20px; }
.kp-drow { display: flex; white-space: pre; min-height: 20px; }
.kp-ln { flex: 0 0 3.2em; text-align: right; padding-right: 6px; color: #888;
  user-select: none; border-right: 1px solid var(--line, #ddd); }
.kp-txt { padding-left: 8px; }
.kp-hunk { color: #888; background: var(--accent-soft, #eef3fb); }
.kp-none { padding: 8px 12px; }
.kp-cur { display: flex; overflow: hidden; }
.kp-gutter { flex: 0 0 6.4em; overflow: hidden; padding: 8px 0 48px; }
.kp-gline { display: flex; height: 20px; white-space: pre; }
.kp-code { padding: 8px; margin: 0; white-space: pre; tab-size: 4; }
.kp-code > div { min-height: 20px; }
.kp-editwrap { position: relative; flex: 1; overflow: hidden; }
.kp-backdrop { position: absolute; inset: 0; overflow: hidden; color: transparent;
  pointer-events: none; padding-bottom: 48px; padding-right: 48px; }
/* The backdrop only shades lines: its text never shows (a green .kp-add line drew a second
   copy under the textarea), and the extra padding lets it and the gutter scroll as far as
   the textarea, whose scrollbars add to its range (owner 2026-10-14: doubled lines). */
.kp-backdrop > div { color: transparent; width: max-content; min-width: 100%; }
#kp-rule-text { position: absolute; inset: 0; width: 100%; height: 100%; box-sizing: border-box;
  border: 0; resize: none; background: transparent; overflow: auto; color: inherit;
  padding: 8px; margin: 0; white-space: pre; tab-size: 4; }
#kp-after-preview { padding: 8px 12px; overflow: auto; flex: 1; }
.kp-ai { display: flex; flex-direction: column; gap: 6px; padding: 8px;
  overflow: hidden; }
.kp-ai #kp-assist-log { flex: 1; overflow: auto; max-height: none; min-height: 0; }
.kp-ai #kp-assist-input { width: 100%; box-sizing: border-box; }
.kp-nav { display: flex; justify-content: space-between; gap: 8px; margin: 16px 0 4px;
  padding-top: 12px; border-top: 1px solid var(--line, #ddd); }
.kp-sandbox-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px;
  flex-wrap: wrap; padding: 8px 12px; margin-bottom: 8px; border: 1px solid var(--line, #ddd);
  border-radius: 8px; background: var(--soft, #f4f6fa); }
#kp-sandboxes button { min-height: 44px; padding: 6px 14px; margin: 4px 6px 4px 0; }
.kp-grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.kp-form label { display: block; font-size: 13px; margin: 10px 0 4px; }
.kp-form select, .kp-form input { width: 100%; box-sizing: border-box; min-height: 36px; }
.kp-form button { margin-top: 8px; min-height: 44px; }
.kp-repos .kp-list button { min-height: 44px; }
.kp-ver h4 { margin: 14px 0 4px; font-size: 14px; }
.kp-ver input { width: 100%; box-sizing: border-box; min-height: 36px; }
.kp-ver ul { margin: 4px 0; padding-left: 20px; }
.kp-ver li { margin: 6px 0; }
.kp-ver .kp-ver-pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px; margin: 4px 0; }
.kp-ver .kp-ver-pair > div { border: 1px solid var(--line, #d0d4da); border-radius: 6px;
  padding: 6px 8px; overflow-wrap: anywhere; }
.kp-ver .kp-ver-ask { display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  margin: 6px 0; }
.kp-ver .kp-ver-ask input { flex: 1 1 220px; width: auto; }
.kp-ver .kp-warn { color: var(--warn, #9a5b00); }
#kp-repo-settings input { width: 100%; box-sizing: border-box; min-height: 36px; }
#kp-repo-settings label { display: block; font-size: 13px; margin: 10px 0 4px; }
.kp-coverage { padding: 8px 10px; border-radius: 6px; background: #e6f4ea; color: #137333; }
.kp-coverage.kp-low { background: #fef7e0; color: #8a5a00; }
.kp-q-editor textarea { width: 100%; box-sizing: border-box; font-family: ui-monospace, Consolas,
  monospace; font-size: 13px; }
.kp-ingest { display: flex; gap: 12px; align-items: stretch; height: 70vh; min-height: 380px; }
.kp-ingest-main { flex: 2 1 0; min-width: 0; display: flex; flex-direction: column;
  border: 1px solid var(--line, #ddd); border-radius: 6px; background: var(--panel, #fff); }
.kp-ingest-head { display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-bottom: 1px solid var(--line, #ddd); }
.kp-ingest-head strong { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
#kp-plan:empty { display: none; }
#kp-plan { padding: 6px 10px; border-bottom: 1px solid var(--line, #ddd); max-height: 40%;
  overflow: auto; }
.kp-ingest-side { flex: 1 1 0; min-width: 220px; display: flex; flex-direction: column; }
.kp-filelist { position: relative; flex: 1; overflow: auto; border: 1px solid var(--line, #ddd);
  border-radius: 6px; background: var(--panel, #fff); outline: none; }
.kp-filelist:focus { box-shadow: 0 0 0 2px var(--accent-soft, #c9d8f5); }
.kp-file { display: flex; align-items: center; gap: 6px; padding: 3px 8px; cursor: pointer;
  white-space: nowrap; }
.kp-file span { overflow: hidden; text-overflow: ellipsis; }
.kp-file:hover { background: var(--soft, #f4f6fa); }
.kp-file.kp-focus { background: var(--accent-soft, #dbe8f7); }
.kp-file.kp-new span { color: #137333; font-weight: 600; }
.kp-add { background: #e6f4ea; color: #137333; }
.kp-del { background: #fce8e6; color: #a50e0e; }
.kp-same { opacity: 0.7; }
pre.kp-added { background: var(--ok-bg, #e8f5e9); white-space: pre-wrap; padding: 8px; }
pre.kp-removed { background: var(--bad-bg, #fdecea); white-space: pre-wrap; padding: 8px; }
"""

WIKI_PANE_HTML = r"""
    <div id="kn-pane-pipeline" role="tabpanel" aria-label="知識庫維護">
    <div id="kp-disabled" class="empty" hidden>The Knowledge pipeline is not configured on
      this machine (host.json <code>knowledge_pipeline</code>).</div>
    <div class="kp-top">
      <nav id="kp-stepper" class="kp-stepper" aria-label="Maintenance steps">
        <ol>
          <li><button type="button" data-stage="pull"><span class="kp-step-n">1</span>
            <span><strong>Pull data</strong><small>pull, add files, convert</small></span>
          </button></li>
          <li><button type="button" data-stage="ingest"><span class="kp-step-n">2</span>
            <span><strong>Ingest data</strong><small>edit skills, ingest</small></span>
          </button></li>
          <li><button type="button" data-stage="test"><span class="kp-step-n">3</span>
            <span><strong>Testing data</strong><small>questions, test, push</small></span>
          </button></li>
        </ol>
      </nav>
      <div id="kp-status" class="section-status" role="status" aria-live="polite"><span
        id="kp-status-text"></span> <span id="kp-status-time" class="note"></span></div>
      <div id="kp-progress" class="kp-progress" hidden>
        <progress id="kp-progress-bar" max="1"></progress>
        <span id="kp-progress-text" class="note"></span></div>
    </div>
    <div id="kp-main">
      <div id="kp-start">
        <h2 class="kp-stage-title" tabindex="-1">Step 1 of 3 &middot; Pull data</h2>
        <p class="note">Continue a sandbox, or start one for the folder you maintain.</p>
        <div class="kp-grid2">
          <div class="card"><h3>Continue a sandbox</h3>
            <div id="kp-sandboxes" class="kp-list">reading&hellip;</div></div>
          <form id="kp-new" class="card kp-form"><h3>Start a new sandbox</h3>
            <label for="kp-base">Project vault</label>
            <select id="kp-base"></select>
            <label for="kp-scope">Folder you maintain</label>
            <select id="kp-scope" required></select>
            <label for="kp-label">Sandbox name</label>
            <input id="kp-label" required maxlength="80" placeholder="e.g. VNA trial">
            <p class="note">The vault is copied into your sandbox and the folder's originals are
              pulled, so you can convert them next.</p>
            <button class="go" type="submit">Create sandbox and pull</button>
          </form>
        </div>
        <div class="card kp-repos" lang="zh-Hant"><h3>知識庫（有版本紀錄）</h3>
          <p class="note">每個改動都寫目的並 commit，push 給大家，發佈後 Agent
            才讀到；歷史裡可以改回任何版本。之後 sandbox 會被知識庫取代。</p>
          <div id="kp-repos" class="kp-list">reading&hellip;</div>
          <div id="kp-askable" aria-live="polite"></div>
          <details class="kp-repo-new"><summary>新增知識庫</summary>
            <form id="kp-repo-form" class="kp-form">
              <label for="kp-repo-mode">方式</label>
              <select id="kp-repo-mode">
                <option value="import">匯入既有 wiki 資料夾的副本</option>
                <option value="create">建立空的知識庫</option>
                <option value="join">加入別人分享的知識庫資料夾</option>
              </select>
              <div id="kp-repo-source-box">
                <label for="kp-repo-source">要匯入的 wiki 資料夾（只會讀，不會改）</label>
                <input id="kp-repo-source" maxlength="400"
                  placeholder="例如 C:\Users\me\Documents\my-wiki">
              </div>
              <label for="kp-repo-path" id="kp-repo-path-l">
                放知識庫的資料夾（例如 OneDrive 上的共用資料夾）</label>
              <input id="kp-repo-path" required maxlength="400">
              <div id="kp-repo-title-box">
                <label for="kp-repo-title">名稱</label>
                <input id="kp-repo-title" maxlength="80" placeholder="例如 RS 產品知識">
              </div>
              <button class="go" type="submit">新增</button>
            </form>
          </details>
        </div>
      </div>
      <div id="kp-box" hidden>
        <div class="kp-sandbox-bar">
          <div><strong id="kp-title"></strong>
            <span class="note">&middot; folder <span id="kp-scope-name"></span></span></div>
          <div class="kp-actions">
            <button id="kp-switch" type="button">Switch sandbox</button>
            <button id="kp-discard" type="button">Discard sandbox</button></div>
        </div>
        <div class="kp-banner" id="kp-review" hidden></div>
        <section class="kp-stage" data-stage="pull" aria-labelledby="kp-stage-pull">
          <h2 class="kp-stage-title" id="kp-stage-pull" tabindex="-1">Step 1 of 3 &middot; Pull
            data</h2>
          <p class="note">Bring this folder's originals into the sandbox, add files from this
            computer if needed, then convert everything to Raw.</p>
          <div class="card" id="kp-repo-settings" lang="zh-Hant" hidden><h3>這台電腦的資料夾</h3>
            <p class="note">只存在這台電腦：「拉資料」從收件資料夾拉原始檔，
              測試題目放在題目資料夾。</p>
            <label for="kp-intake">收件資料夾</label>
            <input id="kp-intake" maxlength="400"
              placeholder="例如 OneDrive 上大家放原始檔的資料夾">
            <label for="kp-questions">題目資料夾</label>
            <input id="kp-questions" maxlength="400">
            <div class="kp-actions"><button id="kp-repo-save" type="button">儲存</button>
              <span class="note" id="kp-repo-saved" role="status"></span></div></div>
          <div class="card"><h3 id="kp-pull-h">From the project vault</h3>
            <p class="note" id="kp-pull-note">Originals not yet ingested are copied into the
              sandbox. Ingested ones are already here as Raw, so they are not pulled again.</p>
            <div id="kp-pull-folders" class="kp-list"></div>
            <div class="kp-actions"><button id="kp-pull" type="button">Pull</button>
              <span class="note" id="kp-pull-result"></span></div></div>
          <div class="card"><h3>From this computer</h3>
            <div class="kp-actions">
              <label for="kp-category">Folder</label>
              <select id="kp-category"></select>
              <input id="kp-files" type="file" multiple aria-label="Files to add">
              <button id="kp-upload" type="button">Add files</button>
            </div>
            <div id="kp-drop"></div></div>
          <div class="card"><h3>Convert</h3>
            <p class="note">Turns every original waiting in the sandbox into a Raw document.
              Pictures are described by the model, so a deck can take minutes; it runs in the
              background and you can keep working.</p>
          <div class="kp-actions">
            <button id="kp-preview" type="button">Preview convert</button>
            <button class="go" id="kp-convert" type="button">Convert</button>
            <button id="kp-convert-stop" type="button" hidden>Stop</button>
          </div>
          <p class="note">Convert asks the model to describe every picture, so a deck can take
            minutes. It runs in the background: you can keep working and come back.</p>
          <div id="kp-convert-progress" class="kp-progress" hidden>
            <progress id="kp-convert-bar" max="1"></progress>
            <span id="kp-convert-text" class="note"></span></div>
          <div id="kp-converted"></div>
          </div>
          <div class="kp-nav"><span></span>
            <button class="go" type="button" data-go="ingest">Next: Ingest data &rarr;</button>
          </div>
        </section>
        <section class="kp-stage" data-stage="ingest" aria-labelledby="kp-stage-ingest" hidden>
          <h2 class="kp-stage-title" id="kp-stage-ingest" tabindex="-1">Step 2 of 3 &middot;
            Ingest data</h2>
          <p class="note">Adjust how this folder's data becomes wiki pages, then ingest the Raw
            documents with those rules.</p>
          <div class="card"><h3>Skills for this folder</h3>
            <p class="note">Edit or add the skills of this folder; the AI session can help.
              The vault-wide CLAUDE.md and more general layers are read only here. Changes stay
              in the sandbox until you push.</p>
            <div id="kp-rules" class="kp-list"></div>
          <div id="kp-rule-editor" hidden>
            <p><strong id="kp-rule-path"></strong>
              <span class="note" id="kp-rule-dirty"></span></p>
            <div class="kp-tabs" role="tablist">
              <button type="button" role="tab" data-tab="preview">Preview</button>
              <button type="button" role="tab" data-tab="md" aria-selected="true">Markdown</button>
            </div>
            <div class="kp-panes" id="kp-panes">
              <section class="kp-pane" id="kp-pane-file">
                <div class="kp-pane-body kp-filebody">
                  <div id="kp-md-view" class="kp-md-view">
                    <div class="kp-block" id="kp-block-prev">
                      <button class="kp-block-head" type="button" data-block="kp-block-prev"
                              aria-expanded="true"><span class="kp-chev">&#x2304;</span>
                        Previous file <span class="note" id="kp-diff-summary"></span></button>
                      <div class="kp-block-body" id="kp-prev-body">
                        <div id="kp-prev" class="kp-diffrows"></div></div>
                    </div>
                    <div class="kp-block" id="kp-block-cur">
                      <button class="kp-block-head" type="button" data-block="kp-block-cur"
                              aria-expanded="true"><span class="kp-chev">&#x2304;</span>
                        Current file <span class="note">editable</span></button>
                      <div class="kp-block-body kp-cur" id="kp-cur-body">
                        <div class="kp-gutter" id="kp-cur-gutter" aria-hidden="true"></div>
                        <div class="kp-editwrap">
                          <div id="kp-after-backdrop" class="kp-code kp-backdrop"
                               aria-hidden="true"></div>
                          <textarea id="kp-rule-text" spellcheck="false" wrap="off"
                                    aria-label="Rule file text"></textarea>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div id="kp-after-preview" class="kp-markdown" hidden></div>
                </div>
                <button class="kp-max" type="button" data-pane="kp-pane-file"
                        title="Maximize" aria-label="Maximize the file">&#x2922;</button>
              </section>
              <div class="kp-split" data-left="kp-pane-file" data-right="kp-pane-ai"
                   role="separator" aria-orientation="vertical" title="Drag to resize"></div>
              <section class="kp-pane" id="kp-pane-ai">
                <header>AI session <span class="note">proposals go to Current file</span></header>
                <div class="kp-pane-body kp-ai">
                  <div id="kp-assist-log"></div>
                  <textarea id="kp-assist-input" rows="4"
                            placeholder="e.g. every market claim must carry a date"
                            aria-label="Message to the Skill assistant"></textarea>
                  <div class="kp-actions">
                    <button class="go" id="kp-assist-send" type="button">Send</button>
                    <button id="kp-assist-reset" type="button">New conversation</button>
                  </div>
                </div>
                <button class="kp-max" type="button" data-pane="kp-pane-ai"
                        title="Maximize" aria-label="Maximize AI session">&#x2922;</button>
              </section>
            </div>
            <div class="kp-actions">
              <button class="go" id="kp-rule-save" type="button">Save</button>
              <button id="kp-rule-revert" type="button">Revert to saved</button>
              <button id="kp-rule-close" type="button">Close</button>
            </div></div>
          </div>
        <div class="card" id="kp-viewer" hidden><h3 id="kp-viewer-title">Preview</h3>
          <div class="kp-actions"><button id="kp-viewer-close" type="button">Close</button></div>
          <div id="kp-viewer-body" class="kp-markdown"></div></div>
          <div class="card"><h3>Ingest</h3>
            <p class="note">Click a document to read it. Tick the ones to ingest; documents a
              convert just made are ticked and shown in green. Keys in the list: &uarr;&darr;
              move, Shift+&uarr;&darr; tick a range, Space ticks one.</p>
          <div class="kp-ingest">
            <section class="kp-ingest-main">
              <div class="kp-ingest-head"><strong id="kp-doc-title">Choose a Raw document on
                the right.</strong>
                <button class="go" id="kp-plan-one" type="button" hidden>Plan ingest</button>
                <button id="kp-doc-back" type="button" hidden>Back to the document</button></div>
              <div id="kp-plan"></div>
              <div id="kp-doc" class="kp-markdown kp-doc"></div>
            </section>
            <section class="kp-ingest-side">
              <div class="kp-actions">
                <label class="kp-check"><input type="checkbox" id="kp-raw-all"
                  aria-label="Tick or untick every listed document"> All</label>
                <select id="kp-raw-folder" aria-label="Raw folder to list"></select>
              </div>
              <div id="kp-raw" class="kp-filelist" tabindex="0" role="listbox"
                   aria-multiselectable="true" aria-label="Raw documents"></div>
              <p class="note" id="kp-raw-count"></p>
            </section>
          </div>
          <div class="kp-actions">
            <button class="go" id="kp-reingest" type="button">Ingest ticked</button>
            <button id="kp-reingest-stop" type="button" hidden>Stop</button></div>
          <div class="note" id="kp-reingest-state"></div>
          <div id="kp-reingest-result"></div>
          </div>
          <div class="kp-nav">
            <button type="button" data-go="pull">&larr; Back: Pull data</button>
            <button class="go" type="button" data-go="test">Next: Testing data &rarr;</button>
          </div>
        </section>
        <section class="kp-stage" data-stage="test" aria-labelledby="kp-stage-test" hidden>
          <h2 class="kp-stage-title" id="kp-stage-test" tabindex="-1">Step 3 of 3 &middot;
            Testing data</h2>
          <p class="note">Make sure the questions cover this folder, test the sandbox against
            the project vault, and push when the result is good.</p>
          <div class="card"><h3>Questions</h3>
            <p id="kp-q-coverage" class="kp-coverage" role="status"></p>
            <div class="kp-actions">
              <button class="go" id="kp-q-new" type="button">New question</button></div>
            <div id="kp-q-list"></div>
            <div id="kp-q-editor" class="kp-q-editor" hidden>
              <label for="kp-q-text"><strong id="kp-q-path"></strong></label>
              <textarea id="kp-q-text" rows="14" spellcheck="false"></textarea>
              <p class="note">The heading is the question. Under <code>必須提到:</code> list the
                terms a good answer must mention, under <code>不可以說:</code> what it must not
                say, one per line starting with <code>- </code>. A question without terms is
                not graded.</p>
              <div class="kp-actions">
                <button class="go" id="kp-q-save" type="button">Save question</button>
                <button id="kp-q-cancel" type="button">Close</button></div>
            </div>
          </div>
          <div class="card"><h3>Test</h3>
            <p class="note">Each ticked question set is asked against this sandbox and against
              the project vault, and graded by its terms.</p>
          <div id="kp-bench-sets" class="kp-list"></div>
          <div class="kp-actions">
            <button class="go" id="kp-bench" type="button">Run test</button>
            <span class="note" id="kp-bench-state"></span></div>
          <div id="kp-bench-result"></div>
          </div>
          <div class="card kp-ver" id="kp-ver" lang="zh-Hant" hidden><h3>版本</h3>
            <p class="note" id="kp-ver-reads"></p>
            <p class="note" id="kp-ver-state"></p>
            <h4>還沒給大家的改動</h4>
            <div id="kp-ver-pending"></div>
            <label for="kp-ver-purpose">
              這次改動的目的（commit 一定要寫，之後在歷史裡看得到）</label>
            <input id="kp-ver-purpose" maxlength="500" placeholder="例如：加入 Tester Y 的規格">
            <div class="kp-actions">
              <button class="go" id="kp-ver-commit" type="button">Commit</button>
              <button id="kp-ver-push" type="button">Push 給大家</button>
              <button id="kp-ver-discard" type="button">捨棄還沒 commit 的改動</button></div>
            <p class="note">Push 前可以先跑上面的「Run test」：跑過的內容如果有
              題目退步，push 會被擋下；沒跑過的照樣送出，但會註明沒有測試。</p>
            <div id="kp-ver-result" role="status" aria-live="polite"></div>
            <div id="kp-ver-conflicts" role="alert"></div>
            <h4>歷史與發佈</h4>
            <div id="kp-ver-history"></div>
          </div>
          <div class="card" id="kp-push-card"><h3>Push to the vault</h3>
            <p class="note">Check conflicts and choose a side for each. Push merges into the
              project vault as it is now, tests the merged result with the ticked sets, and
              writes only when no question regresses and the score is not lower.</p>
          <div class="kp-actions">
            <button id="kp-merge-preview" type="button">Check conflicts</button>
            <button class="go" id="kp-push" type="button">Push</button>
            <button id="kp-refresh-agent" type="button">Refresh the Agent's Knowledge</button>
            <span class="note" id="kp-push-state"></span></div>
          <div id="kp-merge-result"></div>
          <div id="kp-push-result"></div>
          </div>
          <details class="card kp-advanced"><summary>Advanced</summary>
            <h3>Lint</h3>
            <div class="kp-actions"><button id="kp-lint" type="button">Run lint</button></div>
            <div id="kp-lint-result"></div>
          <h3>Legacy Raw</h3>
          <div class="kp-actions"><button id="kp-adopt" type="button">Adopt legacy Raw</button>
            <span class="note" id="kp-adopt-result"></span></div>
          <div id="kp-candidate">
          <h3>Local candidate</h3>
          <p class="note">Merge into a local candidate and publish it as the Agent's version
            without pushing to the project vault.</p>
          <div class="kp-actions">
            <button id="kp-merge" type="button">Merge into a candidate</button>
            <button id="kp-publish" type="button" disabled>Publish candidate</button>
          </div></div>
          <h3>Layered index</h3>
          <p class="note">Bilingual summaries and category indexes for ingest planning on a
            large wiki; queries do not use them.</p>
          <div class="kp-actions">
            <button id="kp-enrich" type="button">Write bilingual summaries</button>
            <button id="kp-index" type="button">Build layered index</button>
          </div><div id="kp-index-result" class="note"></div></details>
          <div class="kp-nav">
            <button type="button" data-go="ingest">&larr; Back: Ingest data</button><span></span>
          </div>
        </section>
      </div>
    </div>
    </div>
"""

WIKI_JS = r"""
let kpSandbox = null;

async function pipeline(step, args) {
  const reply = await call("/api/knowledge/pipeline/call", {step, arguments: args || {}});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  return reply.data;
}

async function loadKnowledge() {
  const info = await call("/api/knowledge/pipeline");
  el("kp-disabled").hidden = info.enabled; el("kp-main").hidden = !info.enabled;
  el("kp-stepper").hidden = !info.enabled;
  if (!info.enabled) return;
  // Before the steps' own reads: a person without the pipeline's grants still sees this.
  askableLoad().catch((failure) => { el("kp-askable").textContent = failure.message; });
  const base = el("kp-base"); base.replaceChildren();
  for (const vault of info.vaults || info.bases.map((name) => ({name}))) {
    const option = document.createElement("option"); option.value = vault.name;
    option.append(text(vault.name + (vault.project ? " — project vault (the Agent's "
      + vault.asset + ")" : " — test vault"))); base.append(option);
  }
  await kpLoadScopes();
  const listed = await pipeline("sandbox-list");
  const box = el("kp-sandboxes"); box.replaceChildren();
  if (!listed.sandboxes.length) box.append(text("No sandbox yet."));
  for (const item of listed.sandboxes) {
    box.append(kpButton(item.label + " · " + (item.scope || "whole vault") + " ("
      + item.base_name + ")",
      () => kpRun("Opening", () => kpOpen(item))));
  }
  kpRepoPrefix = info.repo_prefix || "repo.";
  const repos = el("kp-repos"); repos.replaceChildren();
  if (!(info.repos || []).length) repos.append(text("還沒有知識庫。"));
  for (const repo of info.repos || []) {
    const item = kpRepoItem(repo);
    repos.append(kpButton(item.label + (repo.reachable ? "" : "（讀不到共用資料夾）"),
      () => kpRun("Opening", () => kpOpen(item))));
  }
  const open = kpSandbox && (kpSandbox.repo
    ? (info.repos || []).some((r) => r.id === kpSandbox.repo)
    : listed.sandboxes.some((s) => s.sandbox_id === kpSandbox.sandbox_id));
  if (!open) kpSandbox = null;
  if (!kpSandbox) kpStage("pull", false);
}

// -- Wiki knowledge repositories (knowledge repositories R4b) -----------------------
// A repository opens like a sandbox under the id `repo.<id>`: every step runs on
// its working folder and what a step writes becomes a change to commit. Its
// 「版本」 area replaces push, refresh and the candidate in step 3.
let kpRepoPrefix = "repo.";

function kpRepoItem(repo) {
  const id = kpRepoPrefix + repo.id;
  return {sandbox_id: id, base_name: id, label: repo.title || repo.id, scope: null,
          repo: repo.id};
}

function kpRepoMode() {
  const mode = el("kp-repo-mode").value;
  el("kp-repo-source-box").hidden = mode !== "import";
  el("kp-repo-title-box").hidden = mode === "join";
  el("kp-repo-path-l").textContent = mode === "join"
    ? "知識庫資料夾（別人分享給你、裡面有 repo.json 的資料夾）"
    : "放知識庫的資料夾（例如 OneDrive 上的共用資料夾）";
}
el("kp-repo-mode").addEventListener("change", kpRepoMode);
kpRepoMode();

async function kpRepoCall(path, body) {
  // The repository routes answer {ok: false, message} in words; show those.
  let reply;
  try { reply = await call("/api/knowledge/repos" + path, body); }
  catch (failure) {
    throw new Error((failure.payload && failure.payload.message) || failure.message);
  }
  if (reply && reply.ok === false) throw new Error(reply.message || reply.code);
  return reply;
}

function kpRepoPath(action) {
  return "/" + encodeURIComponent(kpSandbox.repo) + "/" + action;
}

el("kp-repo-form").addEventListener("submit", (event) => {
  event.preventDefault();
  kpRun("新增知識庫", async () => {
    const mode = el("kp-repo-mode").value, path = el("kp-repo-path").value.trim();
    const body = mode === "join" ? {path}
      : {path, title: el("kp-repo-title").value.trim(),
         ...(mode === "import" ? {source: el("kp-repo-source").value.trim()} : {})};
    if (mode === "create" && !body.title) throw new Error("請填名稱");
    const made = await kpRepoCall(mode === "create" ? "" : "/" + mode, body);
    for (const id of ["kp-repo-source", "kp-repo-path", "kp-repo-title"]) el(id).value = "";
    await loadKnowledge();
    await kpOpen(kpRepoItem({id: made.repo.id, title: made.repo.title}));
  });
});

async function kpRepoSettings() {
  const chosen = (await kpRepoCall(kpRepoPath("settings"))).settings;
  el("kp-intake").value = chosen.intake || ""; el("kp-questions").value = chosen.questions || "";
  el("kp-repo-saved").textContent = "";
}
el("kp-repo-save").addEventListener("click", () => kpRun("儲存資料夾", async () => {
  await kpRepoCall(kpRepoPath("settings"), {intake: el("kp-intake").value.trim(),
                                            questions: el("kp-questions").value.trim()});
  await kpOpen(kpSandbox);
  el("kp-repo-saved").textContent = "已儲存。";
}));

function kpVerValue(value) {
  if (value === null || value === undefined) return "（沒有）";
  let shown;
  if (typeof value !== "object") shown = String(value);
  else if ("heading" in value || "body" in value) {
    shown = [value.heading, value.body].filter(Boolean).join(" ");
  } else if ("text" in value) shown = value.text;
  else if ("file" in value) shown = value.file;
  else if ("revision" in value) shown = "第 " + value.revision + " 版";
  else shown = JSON.stringify(value);
  shown = String(shown).replace(/\s+/g, " ").trim();
  if (!shown) return "（空）";
  return shown.length > 160 ? shown.slice(0, 160) + "\u2026" : shown;
}

function kpVerChanges(changes) {
  const list = bh("ul", "");
  for (const change of changes.slice(0, 50)) {
    list.append(bh("li", "", bh("strong", "", change.label || change.unit), "：",
      kpVerValue(change.before), " \u2192 ", kpVerValue(change.after)));
  }
  if (changes.length > 50) list.append(bh("li", "note", "還有 " + (changes.length - 50) + " 項"));
  return list;
}

function kpVerAsk(where, label, value, go, run) {
  // One inline question (a purpose, a tag name) under the row that asked it.
  where.querySelector(".kp-ver-ask")?.remove();
  const input = document.createElement("input");
  input.maxLength = 500; input.value = value || ""; input.setAttribute("aria-label", label);
  const row = bh("div", "kp-ver-ask", bh("span", "", label), input);
  const ok = kpButton(go, () => kpRun(go, async () => {
    const answer = input.value.trim();
    if (!answer) { input.focus(); return; }
    await run(answer);
  }));
  ok.className = "go";
  row.append(ok, kpButton("取消", () => row.remove()));
  where.append(row); input.focus();
}

function kpVerSay(message, bad) {
  const box = el("kp-ver-result"); box.replaceChildren();
  if (message) box.append(bh("p", bad ? "kp-warn" : "note", message));
}

async function kpVerShow() {
  const [state, pending, history] = await Promise.all([kpRepoCall(kpRepoPath("status")),
    kpRepoCall(kpRepoPath("pending")), kpRepoCall(kpRepoPath("history?limit=30"))]);
  const reads = state.reads || {};
  el("kp-ver-reads").textContent = !state.reachable
    ? "現在讀不到共用資料夾（OneDrive 沒有同步或路徑不對）：可以繼續判讀，但不能 push。"
    : reads.tag ? "Agent 讀的是發佈版本「" + reads.tag
      + "」；之後 push 的內容要再發佈，Agent 才會讀到。"
    : "還沒有發佈過：Agent 讀的是大家已 push 的最新內容（不含你還沒 push 的改動）。";
  el("kp-ver-state").textContent = state.reachable ? "別人 push 了還沒套用的 " + state.behind
    + " 個・你還沒 push 的 commit " + state.ahead + " 個・還沒 commit 的改動 " + state.uncommitted
    + " 個・上次同步 " + (state.last_sync ? biTime(state.last_sync) : "\u2014") : "";
  const box = el("kp-ver-pending"); box.replaceChildren();
  const changes = pending.uncommitted || [], commits = pending.commits || [];
  const files = pending.files || [], uncommitted = changes.length + files.length;
  if (!uncommitted && !commits.length) {
    box.append(bh("p", "note", "沒有：大家看到的就是你的內容。"));
  }
  if (changes.length) {
    box.append(bh("p", "", "還沒 commit 的改動 " + changes.length + " 項："),
      kpVerChanges(changes));
  }
  if (files.length) {
    // Originals pulled or added, Raw, schema and skill files staged with them.
    const list = bh("ul", "");
    for (const path of files.slice(0, 20)) list.append(bh("li", "", path));
    if (files.length > 20) list.append(bh("li", "note", "還有 " + (files.length - 20) + " 個"));
    box.append(bh("p", "", "還沒 commit 的檔案 " + files.length + " 個："), list);
  }
  if (commits.length) {
    const list = bh("ul", "");
    for (const item of commits) {
      list.append(bh("li", "", bh("strong", "", item.purpose), "・" + biTime(item.created)
        + "（已 commit，還沒 push）"));
    }
    box.append(bh("p", "", "已 commit、還沒 push 的 " + commits.length + " 個："), list);
  }
  el("kp-ver-commit").disabled = !uncommitted;
  el("kp-ver-discard").disabled = !uncommitted;
  el("kp-ver-push").disabled = !commits.length || !state.reachable;
  kpVerHistory(history);
}

function kpVerHistory(history) {
  const box = el("kp-ver-history"); box.replaceChildren();
  const tags = history.tags || [], published = history.published;
  const byCommit = {};
  for (const tag of tags) (byCommit[tag.commit] = byCommit[tag.commit] || []).push(tag);
  const live = (tag) => Boolean(published && published.tag === tag.name);
  const list = bh("ul", "");
  (history.commits || []).forEach((commit, index) => {
    const row = bh("li", "");
    const badges = (byCommit[commit.id] || []).map((tag) =>
      biBadge("tag " + tag.name + (live(tag) ? "・發佈中" : ""), live(tag) ? "good" : ""));
    row.append(bh("div", "", bh("strong", "", commit.purpose), " ", ...badges),
      bh("div", "note", biTime(commit.created) + "・" + commit.author + "・" + commit.units
        + " 項" + (commit.kind === "revert" ? "・回復版本" : "") + "・" + commit.id.slice(0, 10)));
    const actions = bh("div", "kp-actions"), detail = bh("div", "");
    const look = kpButton("看改動", () => kpRun("讀取改動", async () => {
      if (detail.childNodes.length) { detail.replaceChildren(); return; }
      const reply = await kpRepoCall(kpRepoPath("diff?commit=" + encodeURIComponent(commit.id)));
      detail.replaceChildren(kpVerChanges(reply.changes || []));
    }));
    look.setAttribute("aria-label", "看「" + commit.purpose + "」的改動");
    actions.append(look);
    if (index > 0) {
      actions.append(kpButton("回到這個版本", () => kpVerAsk(row, "回復的目的",
        "回到「" + commit.purpose + "」的版本", "回復（成為新的 commit）", async (purpose) => {
          await kpRepoCall(kpRepoPath("revert"), {version: commit.id, purpose});
          kpVerSay("已回復成新的 commit；按「Push 給大家」送出。");
          await kpOpen(kpSandbox);
        })));
    }
    actions.append(kpButton("加 tag", () => kpVerAsk(row,
      "tag 名稱（小寫英數字與 . -，例如 2026q4）", "", "建立 tag", async (name) => {
        await kpRepoCall(kpRepoPath("tag"), {name, version: commit.id, purpose: commit.purpose});
        kpVerSay("已建立 tag「" + name + "」；要讓 Agent 讀它，請按「發佈 " + name + "」。");
        await kpVerShow();
      })));
    for (const tag of byCommit[commit.id] || []) {
      if (live(tag)) continue;
      actions.append(kpButton("發佈 " + tag.name, () => kpRun("發佈", async () => {
        if (!confirm("發佈 tag「" + tag.name + "」？發佈後 Agent 只讀這個版本的內容；"
          + "要撤回就再發佈另一個 tag。")) return;
        await kpRepoCall(kpRepoPath("publish"), {tag: tag.name, confirm: true});
        kpVerSay("已發佈「" + tag.name + "」：Agent 下一個問題就讀這個版本。");
        await kpVerShow();
      })));
    }
    row.append(actions, detail); list.append(row);
  });
  if (!(history.commits || []).length) list.append(bh("li", "note", "還沒有 commit。"));
  box.append(list);
}

function kpVerConflicts(conflicts) {
  // Push conflicts side by side: nothing was written until each is decided.
  const box = el("kp-ver-conflicts"); box.replaceChildren();
  if (!conflicts.length) return;
  const decided = {};
  box.append(bh("p", "kp-warn", "沒有送出：有 " + conflicts.length + " 個地方別人也改了。"
    + "每一項選一邊，再按「Push 給大家」。"));
  const list = bh("ul", "");
  for (const conflict of conflicts) {
    const label = conflict.label || conflict.unit;
    const mine = bh("div", "", bh("div", "note", "你的（" + conflict.purpose + "）"),
      kpVerValue(conflict.mine));
    const theirs = bh("div", "", bh("div", "note", "別人已 push 的"), kpVerValue(conflict.theirs));
    const choose = (choice) => kpRun("決定衝突", async () => {
      await kpRepoCall(kpRepoPath("resolve"), {unit: conflict.unit, choice});
      decided[conflict.unit] = choice;
      mine.classList.toggle("chosen", choice === "mine");
      theirs.classList.toggle("chosen", choice === "theirs");
      const left = conflicts.filter((c) => !decided[c.unit]).length;
      kpVerSay(left ? "已決定；還有 " + left + " 項。" : "全部決定了，按「Push 給大家」送出。");
    });
    const useMine = kpButton("用我的", () => choose("mine"));
    useMine.setAttribute("aria-label", "用我的：" + label);
    const useTheirs = kpButton("用別人的", () => choose("theirs"));
    useTheirs.setAttribute("aria-label", "用別人的：" + label);
    list.append(bh("li", "", bh("strong", "", label), bh("div", "kp-ver-pair", mine, theirs),
      bh("div", "kp-actions", useMine, useTheirs)));
  }
  box.append(list);
}

el("kp-ver-commit").addEventListener("click", () => kpRun("Commit", async () => {
  const input = el("kp-ver-purpose"), purpose = input.value.trim();
  if (!purpose) { kpVerSay("請先寫這次改動的目的。", true); input.focus(); return; }
  await kpRepoCall(kpRepoPath("commit"), {purpose});
  input.value = ""; kpVerSay("已 commit；按「Push 給大家」才會送出。");
  await kpVerShow();
}));
el("kp-ver-push").addEventListener("click", () => kpRun("Push", async () => {
  const reply = await kpRepoCall(kpRepoPath("push"), {});
  kpVerConflicts(reply.status === "conflicts" ? reply.conflicts || [] : []);
  const notes = (reply.notes || []).join("；");
  if (reply.status === "pushed") {
    kpVerSay("已 push " + (reply.commits || []).length
      + " 個 commit；要讓 Agent 讀到，請加 tag 並發佈。"
      + (notes ? " " + notes : ""));
  } else if (reply.status === "blocked") {
    kpVerSay("沒有送出：" + (reply.blocking || []).join("；") + (notes ? " " + notes : ""), true);
  } else if (reply.status === "nothing") {
    kpVerSay("沒有要 push 的 commit。");
  }
  await kpOpen(kpSandbox);
}));
el("kp-ver-discard").addEventListener("click", () => {
  if (!confirm("捨棄這台電腦上還沒 commit 的改動？工作資料夾會回到最近的版本；"
      + "已 commit 的不受影響。")) {
    return;
  }
  kpRun("捨棄", async () => {
    await kpRepoCall(kpRepoPath("discard"), {});
    kpVerSay("已捨棄還沒 commit 的改動。");
    await kpOpen(kpSandbox);
  });
});

async function kpReviewBanner(item) {
  // A sandbox opened from an accepted review proposal (owner 2026-10-13).
  const box = el("kp-review"); box.replaceChildren(); box.hidden = true;
  const reply = await call("/api/knowledge/review-proposal?sandbox_id="
    + encodeURIComponent(item.sandbox_id));
  const proposal = reply.ok ? reply.proposal : null;
  if (!proposal) return;
  const head = document.createElement("p");
  head.append(text("Opened from review proposal " + proposal.proposal_id + " (" + proposal.cause
    + "): " + proposal.diagnosis));
  const body = document.createElement("div"); body.className = "rv-text";
  body.append(text(proposal.text));
  const open = kpButton(proposal.kind === "test_question"
    ? "Open the draft question " + proposal.path
    : "Open " + proposal.path + " with the proposal added", () => kpRun("Reading", async () => {
      const file = await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id,
                                                path: proposal.path});
      kpRulePath = proposal.path; el("kp-rule-editor").hidden = false;
      el("kp-rule-path").textContent = proposal.path; kpRuleSaved = file.text;
      const marker = "Review proposal (" + proposal.proposal_id + ")";
      el("kp-rule-text").value = proposal.kind === "rule_edit" && !file.text.includes(marker)
        ? file.text.replace(/\s*$/, "") + "\n\n## " + marker + "\n\n" + proposal.text
          + "\n\n> Why: " + proposal.diagnosis + "\n"
        : file.text;
      el("kp-rule-text").dispatchEvent(new Event("input")); kpTab("md");
      el("kp-rule-editor").scrollIntoView({block: "start"});
    }));
  open.className = "go";
  const note = document.createElement("p"); note.className = "note";
  note.append(text(proposal.kind === "test_question"
    ? "Fill in the must-mention terms (an expert's job; the review never invents them), "
      + "save, then benchmark and push."
    : "The proposal is added as an unsaved edit: compare it, edit it (the AI session can "
      + "help), save, then benchmark and push."));
  box.append(head, body, note, open); box.hidden = false;
}

// -- Three guided steps (owner 2026-10-14) ----------------------------------
let kpCurrentStage = "pull", kpRawTotal = 0;
const KP_STAGES = ["pull", "ingest", "test"];

function kpStage(name, focus = true) {
  const open = !!kpSandbox;
  const stage = open && KP_STAGES.includes(name) ? name : "pull";
  kpCurrentStage = stage;
  stepperSet(el("kp-stepper"), stage, {pull: true, ingest: open, test: open},
    "Open or create a sandbox first");
  el("kp-start").hidden = open; el("kp-box").hidden = !open;
  for (const section of document.querySelectorAll("#kp-main .kp-stage")) {
    section.hidden = section.dataset.stage !== stage;
  }
  if (open) {
    try { localStorage.setItem("kp-stage-" + kpSandbox.sandbox_id, stage); } catch (e) { /* */ }
  }
  if (focus) {
    const title = open ? document.querySelector('.kp-stage[data-stage="' + stage + '"] '
      + ".kp-stage-title") : document.querySelector("#kp-start .kp-stage-title");
    if (title) {  // screen readers hear the step; the page shows its top below the steps
      title.focus({preventScroll: true});
      const below = document.querySelector(".kp-top").getBoundingClientRect().height + 8;
      const top = title.getBoundingClientRect().top;
      if (top < below) window.scrollTo({top: Math.max(0, top + window.scrollY - below)});
    }
  }
}

function kpStoredStage(sandboxId) {
  try { return localStorage.getItem("kp-stage-" + sandboxId) || "pull"; }
  catch (e) { return "pull"; }
}

for (const button of document.querySelectorAll("#kp-stepper [data-stage]")) {
  button.addEventListener("click", () => kpStage(button.dataset.stage));
}
for (const button of document.querySelectorAll(".kp-nav [data-go]")) {
  button.addEventListener("click", () => kpStage(button.dataset.go));
}
el("kp-switch").addEventListener("click", () => {
  kpSandbox = null; kpStage("pull"); kpRun("Reading", loadKnowledge);
});

// -- Questions and their coverage (step 3) -----------------------------------
let kpQuestionPath = null, kpQuestionSets = null;

function kpQuestionsShow(sets) {
  kpQuestionSets = sets;
  const scope = kpSandbox.scope || "this sandbox";
  const scoped = sets.questions.filter((q) => sets.defaults.includes(q.set));
  const graded = scoped.filter((q) => q.must + q.must_not > 0).length;
  const target = Math.max(5, Math.ceil(kpRawTotal / 10));
  const box = el("kp-q-coverage");
  box.textContent = scope + ": " + scoped.length + " question(s) in its sets, " + graded
    + " graded, for " + kpRawTotal + " Raw document(s). " + (graded < target
      ? "Aim for at least " + target + " graded questions (about one per 10 documents, at "
        + "least 5) so a test can catch a regression."
      : "That is about one graded question per " + Math.max(1, Math.round(kpRawTotal
        / Math.max(graded, 1))) + " documents.");
  box.classList.toggle("kp-low", graded < target);
  const ordered = [...scoped, ...sets.questions.filter((q) => !sets.defaults.includes(q.set))];
  el("kp-q-list").replaceChildren(table(["Set", "Question", "Terms", ""], ordered, (q) => [
    q.set || "(general)", q.text,
    q.must + q.must_not ? q.must + " must, " + q.must_not + " must not" : "not graded",
    kpButton(q.editable ? "Edit" : "View", () => kpRun("Reading", () => kpQuestionOpen(
      q.path, q.editable)))]));
}

async function kpQuestionOpen(path, editable, text = null) {
  const body = text !== null ? text
    : (await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id, path})).text;
  kpQuestionPath = path; el("kp-q-editor").hidden = false;
  el("kp-q-path").textContent = path + (editable ? "" : " (another folder's set: read only)");
  el("kp-q-text").value = body; el("kp-q-text").readOnly = !editable;
  el("kp-q-save").hidden = !editable; el("kp-q-text").focus();
}

el("kp-q-new").addEventListener("click", () => {
  const scope = (kpSandbox.scope || "general").split("/")[0].toLowerCase();
  const set = (kpQuestionSets && kpQuestionSets.defaults[0]) || scope;
  const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
  kpQuestionOpen("checks/questions/" + set + "/q-" + stamp + ".md", true,
    "---\nname: q-" + stamp + "\nasked_by: \n---\n\n# Write the question here?\n\n"
    + "必須提到:\n  - \n\n不可以說:\n");
});
el("kp-q-save").addEventListener("click", () => kpRun("Saving the question", async () => {
  await pipeline("rule-write", {sandbox_id: kpSandbox.sandbox_id, path: kpQuestionPath,
                                text: el("kp-q-text").value});
  await kpLoadBench();
  kpStatus("Saved " + kpQuestionPath + ".");
}));
el("kp-q-cancel").addEventListener("click", () => { el("kp-q-editor").hidden = true; });

async function kpLoadScopes() {
  // A sandbox maintains one folder of the project vault (owner, 2026-10-13).
  const pick = el("kp-scope"); pick.replaceChildren();
  if (!el("kp-base").value) return;
  const folders = await pipeline("drop-folders", {base: el("kp-base").value});
  const first = document.createElement("option"); first.value = "";
  first.append(text("Folder to maintain\u2026")); pick.append(first);
  for (const folder of folders.folders) {
    const option = document.createElement("option"); option.value = folder.path;
    option.append(text(folder.path)); pick.append(option);
  }
}
el("kp-base").addEventListener("change", () => kpRun("Reading", kpLoadScopes));

async function kpOpen(item) {
  const switched = !kpSandbox || kpSandbox.sandbox_id !== item.sandbox_id;
  if (switched) {
    kpCurrentStage = kpStoredStage(item.sandbox_id); el("kp-q-editor").hidden = true;
    kpNewRaw = new Set(); kpFocus = null; kpAnchor = null;
    el("kp-doc").replaceChildren(); el("kp-plan").replaceChildren();
    el("kp-doc-title").textContent = "Choose a Raw document on the right.";
    el("kp-plan-one").hidden = true; el("kp-doc-back").hidden = true;
  }
  kpSandbox = item; el("kp-box").hidden = false;
  const repo = Boolean(item.repo);
  el("kp-title").textContent = item.label + " \u2014 "
    + (repo ? "知識庫 " + item.repo : item.sandbox_id);
  el("kp-discard").hidden = repo;
  el("kp-switch").textContent = repo ? "換一個" : "Switch sandbox";
  el("kp-repo-settings").hidden = !repo;
  el("kp-ver").hidden = !repo; el("kp-push-card").hidden = repo;
  el("kp-candidate").hidden = repo;
  el("kp-pull-h").textContent = repo ? "從收件資料夾" : "From the project vault";
  el("kp-pull-note").textContent = repo
    ? "還沒判讀過的原始檔會複製進來；已經判讀過的（內容相同）已經是 Raw，不會再拉。"
    : "Originals not yet ingested are copied into the sandbox. Ingested ones are already "
      + "here as Raw, so they are not pulled again.";
  if (repo) await kpRepoSettings();
  kpStatus("Opening the sandbox: its files (1/5)\u2026");
  const contents = await pipeline("sandbox-contents", {sandbox_id: item.sandbox_id});
  el("kp-drop").replaceChildren(table(["Original in drop"], contents.drop, (row) => [row]));
  const raw = el("kp-raw"); raw.replaceChildren();
  const rawRefs = item.scope ? contents.raw.filter((ref) =>
    ref.startsWith("raw/" + item.scope + "/")) : contents.raw;
  el("kp-scope-name").textContent = item.scope
    || (item.repo ? "整個知識庫" : "whole vault (older sandbox)");
  kpRawTotal = rawRefs.length;
  kpStage(kpCurrentStage, switched);
  await kpReviewBanner(item);
  const prefix = item.scope ? "raw/" + item.scope + "/" : "raw/";
  for (const ref of rawRefs) {
    const row = document.createElement("div"); row.className = "kp-file";
    row.dataset.ref = ref; row.setAttribute("role", "option"); row.title = ref;
    const tick = document.createElement("input"); tick.type = "checkbox";
    tick.className = "kp-raw-tick"; tick.value = ref; tick.setAttribute("aria-label", ref);
    tick.tabIndex = -1;
    const name = document.createElement("span");
    name.append(text(ref.startsWith(prefix) ? ref.slice(prefix.length) : ref));
    row.append(tick, name); raw.append(row);
  }
  if (!rawRefs.length) raw.append(text("No Raw documents yet: convert originals in step 1."));
  kpMarkNew();
  if (kpFocus && !rawRefs.includes(kpFocus)) kpFocus = null;
  kpShowFocus();
  const folders = new Set();
  for (const ref of rawRefs) {
    const parts = ref.split("/").slice(0, -1);
    for (let n = 2; n <= parts.length; n++) folders.add(parts.slice(0, n).join("/"));
  }
  const pick = el("kp-raw-folder"); pick.replaceChildren(); kpRawFilter();
  const top = item.scope ? "raw/" + item.scope : "raw";
  for (const folder of [top, ...[...folders].filter((f) => f !== top).sort()]) {
    const option = document.createElement("option"); option.value = folder;
    option.append(text(folder === top ? folder + " (all)" : folder)); pick.append(option);
  }
  kpRawCount();
  await kpReingestShow();
  await kpConvertShow();
  kpStatus("Opening the sandbox: rules (2/5)\u2026"); await kpLoadRules();
  kpStatus("Opening the sandbox: drop folders (3/5)\u2026"); await kpLoadPull();
  kpStatus("Opening the sandbox: question sets (4/5)\u2026"); await kpLoadBench();
  kpStatus("Opening the sandbox: push status (5/5)\u2026");
  if (item.repo) await kpVerShow(); else await kpPushShow();
  kpStatus("");
}

let kpPushTimer = null;
async function kpPushShow() {
  const reply = await call("/api/knowledge/push?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const push = reply.ok ? reply.push : null;
  const box = el("kp-push-result"); box.replaceChildren();
  if (!push) { el("kp-push-state").textContent = "Not pushed yet."; return; }
  const bench = push.benchmark || {};
  el("kp-push-state").textContent = push.push_id + ": " + push.status
    + (push.reason ? " \u2014 " + push.reason : "");
  const lines = [
    "Files: " + push.written.length + (push.proposals.length
      ? "; proposals (outside the scope): " + push.proposals.join(", ") : ""),
    "Benchmark: merged " + (bench.sandbox_score ?? "-") + " / project vault "
      + (bench.project_score ?? "-") + " of " + (bench.total ?? "-")
      + ((bench.regressions || []).length ? "; regressions: " + bench.regressions.join(", ") : ""),
    push.conflicts.length ? "Conflicts to choose: " + push.conflicts.join(", ") : "",
    push.backup ? "Backup: " + push.backup : "",
  ].filter(Boolean);
  const list = document.createElement("ul");
  for (const line of lines) {
    const li = document.createElement("li"); li.append(text(line)); list.append(li);
  }
  box.append(list);
  clearTimeout(kpPushTimer);
  if (["merging", "benchmarking", "writing"].includes(push.status)) {
    kpPushTimer = setTimeout(() => kpPushShow().catch(() => {}), 5000);
  }
}

function kpChecks(box, items, checked) {
  box.replaceChildren();
  for (const [value, label] of items) {
    const row = document.createElement("label"); row.className = "kp-check";
    const tick = document.createElement("input"); tick.type = "checkbox"; tick.value = value;
    tick.checked = checked.includes(value); row.append(tick, text(" " + label)); box.append(row);
  }
}

function kpTicked(box) {
  return [...box.querySelectorAll("input[type=checkbox]:checked")].map((t) => t.value);
}

async function kpLoadPull() {
  let folders;
  try { folders = await pipeline("drop-folders", {base: kpSandbox.base_name}); }
  catch (failure) {
    if (failure.code !== "intake_not_set") throw failure;
    folders = {folders: [], unset: true};
  }
  const pick = el("kp-category"); pick.replaceChildren();
  const categories = kpSandbox.scope ? [[kpSandbox.scope, kpSandbox.scope]]
    : [["", "(no category)"], ...folders.folders.filter((f) => !f.path.includes("/"))
      .map((f) => [f.path, f.path])];
  for (const [value, label] of categories) {
    const option = document.createElement("option"); option.value = value;
    option.append(text(label)); pick.append(option);
  }
  const scope = kpSandbox.scope;
  const inScope = folders.folders.filter((f) => !scope || f.path === scope
    || f.path.startsWith(scope + "/"));
  kpChecks(el("kp-pull-folders"), inScope.map((f) =>
    [f.path, f.path + " (" + f.files + " files)"]), scope ? [scope] : []);
  if (!inScope.length) {
    el("kp-pull-folders").append(text(folders.unset ? "還沒設定收件資料夾（在上面設定）；"
      + "也可以用下面的「Add files」從這台電腦加入。" : kpSandbox.repo ? "收件資料夾是空的。"
      : scope ? "The project vault's drop has no " + scope + " folder yet."
      : "The project vault's drop is empty."));
  }
}

async function kpLoadBench() {
  const sets = await pipeline("question-sets", {sandbox_id: kpSandbox.sandbox_id});
  kpQuestionsShow(sets);
  kpChecks(el("kp-bench-sets"), Object.entries(sets.sets).map(([name, n]) =>
    [name, (name || "(general)") + " \u2014 " + n + " questions"]), sets.defaults);
  if (sets.ungraded.length) {
    el("kp-bench-sets").append(text(" Not graded (no must-mention / must-not-say terms): "
      + sets.ungraded.join(", ")));
  }
  if (kpSandbox.repo && !Object.keys(sets.sets).length) {
    el("kp-bench-sets").append(text("沒有題目：在步驟 1 設定這台電腦的題目資料夾。"));
  }
  await kpBenchShow();
}

let kpBenchTimer = null;
async function kpBenchShow() {
  const reply = await call("/api/knowledge/benchmark?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const report = reply.ok ? reply.report : null;
  const box = el("kp-bench-result"); box.replaceChildren();
  if (!report) { el("kp-bench-state").textContent = "No benchmark run yet."; return; }
  el("kp-bench-state").textContent = report.status + ": " + report.results.length + " of "
    + report.total + " questions; sandbox " + report.sandbox_score + ", project vault "
    + report.project_score + (report.regressions.length ? "; REGRESSIONS: "
    + report.regressions.length : "") + (report.error ? "; error " + report.error : "");
  const rows = [...report.results].sort((a, b) =>
    Number(report.regressions.includes(b.path)) - Number(report.regressions.includes(a.path)));
  const mark = (side) => (side.grade.passed ? "pass" : "fail")
    + (side.grade.missing.length ? " \u2014 missing: " + side.grade.missing.join(", ") : "")
    + (side.grade.forbidden.length ? " \u2014 said: " + side.grade.forbidden.join(", ") : "");
  box.append(table(["Question", "Set", "Project vault", "Sandbox"], rows, (row) => [
    (report.regressions.includes(row.path) ? "\u26a0 regression: " : "") + row.question,
    row.set || "(general)", mark(row.project), mark(row.sandbox)]));
  clearTimeout(kpBenchTimer);
  if (report.status === "running") {
    kpBenchTimer = setTimeout(() => kpBenchShow().catch(() => {}), 5000);
  }
}

function kpViewer(title, content) {
  el("kp-viewer").hidden = false; el("kp-viewer-title").textContent = title;
  el("kp-viewer-body").replaceChildren(content);
  el("kp-viewer").scrollIntoView({behavior: "smooth", block: "start"});
}

async function kpShowFile(path) {
  const file = await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id, path});
  kpViewer(path, renderMarkdown(file.text));
}

function kpLineDiff(before, after) {
  // Lines added or removed, ignoring order: what a reviewer checks first.
  const old = new Set(before.split("\n").map((line) => line.trim()));
  const now = new Set(after.split("\n").map((line) => line.trim()));
  const box = document.createDocumentFragment();
  const added = after.split("\n").filter((line) => line.trim() && !old.has(line.trim()));
  const removed = before.split("\n").filter((line) => line.trim() && !now.has(line.trim()));
  for (const [label, lines, cls] of [["Added", added, "kp-added"],
                                     ["Removed", removed, "kp-removed"]]) {
    const head = document.createElement("p");
    head.append(text(label + " (" + lines.length + " lines)")); box.append(head);
    const pre = document.createElement("pre"); pre.className = cls;
    pre.append(text(lines.join("\n") || "(none)")); box.append(pre);
  }
  return box;
}

async function kpShowPlanPage(planId, path) {
  const page = await pipeline("plan-page", {sandbox_id: kpSandbox.sandbox_id,
                                            plan_id: planId, path});
  const box = document.createDocumentFragment();
  box.append(page.before ? kpLineDiff(page.before, page.after) : text("New page."));
  const full = document.createElement("details");
  const summary = document.createElement("summary");
  summary.append(text("The page after apply")); full.append(summary, renderMarkdown(page.after));
  box.append(full);
  el("kp-doc-title").textContent = path + " \u2014 planned change";
  el("kp-doc-back").hidden = false;
  el("kp-doc").replaceChildren(box); el("kp-doc").scrollTop = 0;
}

let kpRulePath = null;
async function kpLoadRules() {
  const rules = await pipeline("rule-files", {sandbox_id: kpSandbox.sandbox_id});
  const box = el("kp-rules"); box.replaceChildren();
  const roles = {ingest: "how its data becomes wiki pages", answer: "how its questions are "
    + "answered", schema: "the whole vault's schema"};
  const access = {edit: "", inherited: "general layer, read only", shared: "shared, read only"};
  box.append(table(["Rule file", "What it decides", ""], rules.rules, (rule) => [
    rule.path, roles[rule.kind] + (access[rule.access] ? " (" + access[rule.access] + ")" : ""),
    rule.access === "edit"
      ? kpButton("Edit", () => kpRun("Reading", async () => {
          const file = await pipeline("file-read",
                                      {sandbox_id: kpSandbox.sandbox_id, path: rule.path});
          kpRulePath = rule.path; el("kp-rule-editor").hidden = false;
          el("kp-rule-path").textContent = rule.path; el("kp-rule-text").value = file.text;
          kpRuleSaved = file.text; kpTab("md");
        }))
      : kpButton("View", () => kpRun("Reading", () => kpShowFile(rule.path)))]));
  const scope = rules.scope;
  const slug = (scope || "").split("/").pop().toLowerCase().replace(/[^a-z0-9._-]+/g, "-");
  const guide = await pipeline("skill-guide", {});
  const add = kpButton("New skill", () => {
    const suggested = scope && !rules.rules.some((r) => r.kind === "ingest"
      && r.access === "edit") ? "ingest-" + slug : (scope ? "ask-" + slug : "");
    const name = (prompt("Skill folder name: ingest-<name> for processing data, "
      + "ask-<name> for answering" + (scope ? "; it applies to raw/" + scope : ""),
      suggested) || "").trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(name)) return;
    const answering = name.startsWith("ask-");
    const category = scope || name.replace(/^(ingest|ask)-/, "");
    kpRulePath = "skills/" + name + "/SKILL.md"; el("kp-rule-editor").hidden = false;
    el("kp-rule-path").textContent = kpRulePath;
    kpRuleSaved = ""; kpTab("md");
    el("kp-rule-text").value = (answering ? guide.answer_template : guide.ingest_template)
      .replaceAll("ingest-<category>", name).replaceAll("ask-knowledge", name)
      .replaceAll("raw/<Category>", "raw/" + category)
      .replaceAll("raw/Knowledge", "raw/" + category)
      .replaceAll("<Category>", category);
  });
  const help = kpButton("Writing guide", () => kpViewer("Skill writing guide",
                                                        renderMarkdown(guide.guide)));
  box.append(add, help);
}

function kpFileBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error); reader.readAsDataURL(file);
  });
}

async function kpConvert(mode) {
  // A background run, one original at a time (owner 2026-10-13).
  const reply = await call("/api/knowledge/convert/start",
                           {sandbox_id: kpSandbox.sandbox_id, mode});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  await kpConvertShow();
}

let kpConvertTimer = null, kpConvertWatching = null;
async function kpConvertShow() {
  clearTimeout(kpConvertTimer);
  const reply = await call("/api/knowledge/convert?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const run = reply.ok ? reply.run : null;
  const box = el("kp-convert-progress"), bar = el("kp-convert-bar");
  const live = run && ["running", "stopping"].includes(run.status);
  box.hidden = !live; el("kp-convert-stop").hidden = !live;
  el("kp-preview").disabled = !!live; el("kp-convert").disabled = !!live;
  if (!run || run.sandbox_id !== kpSandbox.sandbox_id) {
    el("kp-converted").replaceChildren(); return;
  }
  const total = run.paths.length, done = run.items.length;
  if (live) {
    const step = run.progress || {};
    const pictures = step.phase === "describing" && step.total
      ? "; pictures " + step.done + " / " + step.total : "";
    bar.max = total; bar.value = done + (step.phase === "describing" && step.total
      ? step.done / step.total : 0);
    el("kp-convert-text").textContent = (run.mode === "apply" ? "Converting" : "Previewing")
      + " " + Math.min(done + 1, total) + " / " + total + pictures
      + (run.current ? " \u2014 " + run.current.replace(/^drop\//, "") : "")
      + (run.status === "stopping" ? " (stopping after this one)" : "");
  }
  const head = document.createElement("p");
  head.append(text((run.mode === "apply" ? "Convert" : "Preview") + ": " + run.status + ", "
    + done + " of " + total + " originals" + (run.error ? " \u2014 " + run.error : "")));
  el("kp-converted").replaceChildren(head, table(["Original", "Result", "Raw", "Pictures"],
    run.items, (row) => [row.path, row.status, row.raw_ref || "",
      row.described ? row.described + " described" : String(row.images)]));
  if (live) {
    kpConvertWatching = run.run_id;
    kpConvertTimer = setTimeout(() => kpConvertShow().catch(() => {}), 1500);
  } else if (run.mode === "apply" && kpConvertWatching === run.run_id) {
    kpConvertWatching = null;  // it just ended: the new Raw appears in step 2
    kpNewRaw = new Set(run.items.filter((i) => ["written", "drifted"].includes(i.status)
      && i.raw_ref).map((i) => i.raw_ref));
    await kpOpen(kpSandbox);
  }
}

el("kp-convert-stop").addEventListener("click", () => kpRun("Stopping", async () => {
  await call("/api/knowledge/convert/stop", {sandbox_id: kpSandbox.sandbox_id});
  await kpConvertShow();
}));

async function kpPlan(rawRef) {
  const plan = await pipeline("ingest-plan", {sandbox_id: kpSandbox.sandbox_id, raw_ref: rawRef});
  const box = el("kp-plan"); box.className = ""; box.replaceChildren();
  const head = document.createElement("p");
  head.append(text(rawRef + ": " + plan.status + (plan.summary ? " \u2014 " + plan.summary : "")
    + " (schema: " + plan.schema_source + (plan.skill ? ", rules: " + plan.skill : "") + ")"));
  box.append(head);
  if (plan.problems.length) box.append(text("Problems: " + plan.problems.join(", ")));
  box.append(table(["Page", "Change", "Characters", ""], plan.pages,
    (row) => [row.path, row.change, String(row.chars), plan.plan_id
      ? kpButton("Compare", () => kpRun("Reading",
          () => kpShowPlanPage(plan.plan_id, row.path))) : ""]));
  if (plan.contradictions.length) {
    const list = document.createElement("ul");
    for (const line of plan.contradictions) {
      const li = document.createElement("li"); li.append(text("\u26a0 " + line)); list.append(li);
    }
    box.append(list);
  }
  if (plan.plan_id) {
    box.append(kpButton("Apply to this sandbox", () => kpRun("Applying", async () => {
      const done = await pipeline("ingest-apply",
        {sandbox_id: kpSandbox.sandbox_id, plan_id: plan.plan_id});
      const note = document.createElement("p");
      note.append(text(done.status === "applied" ? "Applied: " + done.written.join(", ")
        : "Not applied: " + done.problems.join(", ")));
      box.append(note);
    })));
  }
}

// -- Re-ingest with the current rules (owner 2026-10-13) ----------------------
// Seconds one document took in the live runs; only for the estimate shown.
const KP_SECONDS_PER_DOC = 60;
const KP_REINGEST_LABELS = {applied: "applied", needs_review: "needs your review",
  failed: "failed", rejected: "not applied"};

function kpRawTicked() {
  return [...document.querySelectorAll("#kp-raw .kp-raw-tick:checked")].map((t) => t.value);
}

function kpRawCount() {
  const rows = kpRows(), ticked = rows.filter((r) => r.querySelector(".kp-raw-tick").checked);
  const all = el("kp-raw-all");
  all.checked = rows.length > 0 && ticked.length === rows.length;
  all.indeterminate = ticked.length > 0 && ticked.length < rows.length;
  const n = kpRawTicked().length;
  el("kp-raw-count").textContent = n ? n + " ticked, about "
    + Math.max(1, Math.round(n * KP_SECONDS_PER_DOC / 60)) + " min" : "";
}

function kpRawTick(refs) {
  const wanted = new Set(refs);
  for (const tick of document.querySelectorAll("#kp-raw .kp-raw-tick")) {
    if (wanted.has(tick.value)) tick.checked = true;
  }
  kpRawCount();
}

let kpReingestTimer = null;
async function kpReingestShow() {
  const reply = await call("/api/knowledge/reingest?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const run = reply.ok ? reply.run : null;
  const box = el("kp-reingest-result"); box.replaceChildren();
  const live = run && ["running", "stopping"].includes(run.status);
  el("kp-reingest-stop").hidden = !live; el("kp-reingest").disabled = !!live;
  clearTimeout(kpReingestTimer);
  if (!run) { el("kp-reingest-state").textContent = ""; return; }
  const counts = {};
  for (const item of run.items) counts[item.status] = (counts[item.status] || 0) + 1;
  el("kp-reingest-state").textContent = "Re-ingest " + run.run_id + ": " + run.status + ", "
    + run.items.length + " of " + run.raw_refs.length + " done"
    + (run.current ? "; now " + run.current : "")
    + (Object.keys(counts).length ? " (" + Object.entries(counts).map(([k, n]) =>
      (KP_REINGEST_LABELS[k] || k) + " " + n).join(", ") + ")" : "");
  if (!live && run.remaining.length) {
    box.append(kpButton("Continue with the " + run.remaining.length + " left",
      () => kpRun("Starting", () => kpReingestStart(run.remaining))));
  }
  const shown = run.items.filter((item) => item.status !== "applied");
  if (shown.length) {
    box.append(table(["Raw document", "Result", "Detail", ""], shown, (item) => [
      item.raw_ref, KP_REINGEST_LABELS[item.status] || item.status, item.detail,
      item.status === "needs_review" && item.plan_id
        ? kpButton("Review", () => kpReview(item)) : ""]));
  }
  if (live) kpReingestTimer = setTimeout(() => kpReingestShow().catch(() => {}), 5000);
}

async function kpReingestStart(refs) {
  const minutes = Math.max(1, Math.round(refs.length * KP_SECONDS_PER_DOC / 60));
  if (!confirm("Re-ingest " + refs.length + " Raw document(s) with this sandbox's current "
      + "rules? About " + minutes + " min; each one asks the model. Pages are written in "
      + "this sandbox only; plans the planner flags wait for your review.")) return;
  const reply = await call("/api/knowledge/reingest/start",
                           {sandbox_id: kpSandbox.sandbox_id, raw_refs: refs});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  setTimeout(() => kpReingestShow().catch(() => {}), 1000);
}

function kpReview(item) {
  // A flagged plan from a re-ingest run: compare its pages, then apply or leave it.
  const box = el("kp-plan"); box.className = ""; box.replaceChildren();
  const head = document.createElement("p");
  head.append(text(item.raw_ref + ": needs your review — " + item.detail));
  box.append(head);
  box.append(table(["Page", ""], item.pages, (path) => [path,
    kpButton("Compare", () => kpRun("Reading", () => kpShowPlanPage(item.plan_id, path)))]));
  if (item.contradictions.length) {
    const list = document.createElement("ul");
    for (const line of item.contradictions) {
      const li = document.createElement("li"); li.append(text("⚠ " + line)); list.append(li);
    }
    box.append(list);
  }
  box.append(kpButton("Apply to this sandbox", () => kpRun("Applying", async () => {
    const done = await pipeline("ingest-apply",
      {sandbox_id: kpSandbox.sandbox_id, plan_id: item.plan_id});
    const note = document.createElement("p");
    note.append(text(done.status === "applied" ? "Applied: " + done.written.join(", ")
      : "Not applied: " + done.problems.join(", ")));
    box.append(note);
  })));
  box.scrollIntoView({block: "nearest"});
}

// -- The Raw list (owner 2026-10-13): click to read, keys to move and tick ------
let kpFocus = null, kpAnchor = null, kpNewRaw = new Set(), kpDocTimer = null;

function kpRows() {
  return [...document.querySelectorAll("#kp-raw .kp-file")].filter((row) => !row.hidden);
}

function kpRawFilter() {
  const folder = (el("kp-raw-folder").value || "raw") + "/";
  for (const row of document.querySelectorAll("#kp-raw .kp-file")) {
    row.hidden = !row.dataset.ref.startsWith(folder);
  }
  kpRawCount();
}

function kpMarkNew() {
  for (const row of document.querySelectorAll("#kp-raw .kp-file")) {
    const fresh = kpNewRaw.has(row.dataset.ref);
    row.classList.toggle("kp-new", fresh);
    if (fresh) row.querySelector(".kp-raw-tick").checked = true;
  }
  kpRawCount();
}

function kpShowFocus() {
  for (const row of document.querySelectorAll("#kp-raw .kp-file")) {
    const on = row.dataset.ref === kpFocus;
    row.classList.toggle("kp-focus", on); row.setAttribute("aria-selected", String(on));
    if (on) {
      // Scroll the list only, never the page, so the document stays where it is.
      const list = el("kp-raw"), top = row.offsetTop;  // the list is position: relative
      if (top < list.scrollTop) list.scrollTop = top;
      else if (top + row.offsetHeight > list.scrollTop + list.clientHeight) {
        list.scrollTop = top + row.offsetHeight - list.clientHeight;
      }
    }
  }
}

function kpFocusOn(ref, show = true) {
  kpFocus = ref; kpShowFocus();
  if (!show) return;
  clearTimeout(kpDocTimer);  // holding an arrow key reads only where it stops
  kpDocTimer = setTimeout(() => kpDocShow(ref).catch((failure) => {
    el("kp-doc").replaceChildren(text("Not readable: " + (failure.code || failure.message)));
  }), 200);
}

async function kpDocShow(ref) {
  el("kp-doc-title").textContent = ref; el("kp-plan-one").hidden = false;
  el("kp-doc-back").hidden = true; el("kp-doc").replaceChildren(text("Reading\u2026"));
  const file = await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id, path: ref});
  if (kpFocus !== ref) return;
  el("kp-doc").replaceChildren(renderMarkdown(file.text)); el("kp-doc").scrollTop = 0;
}

function kpTickRange(from, to) {
  const rows = kpRows(), a = rows.findIndex((r) => r.dataset.ref === from);
  const b = rows.findIndex((r) => r.dataset.ref === to);
  if (a < 0 || b < 0) return;
  for (const row of rows.slice(Math.min(a, b), Math.max(a, b) + 1)) {
    row.querySelector(".kp-raw-tick").checked = true;
  }
  kpRawCount();
}

el("kp-raw").addEventListener("click", (event) => {
  const row = event.target.closest(".kp-file");
  if (!row) return;
  const ref = row.dataset.ref;
  if (event.target.classList.contains("kp-raw-tick")) {
    if (event.shiftKey && kpAnchor) kpTickRange(kpAnchor, ref);
    kpAnchor = ref; kpFocusOn(ref, false); kpRawCount(); return;
  }
  if (event.shiftKey && kpAnchor) { kpTickRange(kpAnchor, ref); kpFocusOn(ref); return; }
  kpAnchor = ref; kpFocusOn(ref); el("kp-raw").focus();
});

el("kp-raw").addEventListener("keydown", (event) => {
  const rows = kpRows();
  if (!rows.length) return;
  let at = rows.findIndex((r) => r.dataset.ref === kpFocus);
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    at = at < 0 ? 0 : Math.max(0, Math.min(rows.length - 1,
                                            at + (event.key === "ArrowDown" ? 1 : -1)));
    const ref = rows[at].dataset.ref;
    if (event.shiftKey) {
      if (!kpAnchor) kpAnchor = kpFocus || ref;
      kpTickRange(kpAnchor, ref);
    } else {
      kpAnchor = ref;
    }
    kpFocusOn(ref);
  } else if (event.key === " " && at >= 0) {
    event.preventDefault();
    const tick = rows[at].querySelector(".kp-raw-tick"); tick.checked = !tick.checked;
    kpAnchor = kpFocus; kpRawCount();
  } else if ((event.key === "a" || event.key === "A") && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    for (const row of rows) row.querySelector(".kp-raw-tick").checked = true;
    kpRawCount();
  }
});

el("kp-raw-all").addEventListener("change", () => {
  for (const row of kpRows()) row.querySelector(".kp-raw-tick").checked = el("kp-raw-all").checked;
  kpRawCount();
});
el("kp-raw-folder").addEventListener("change", kpRawFilter);
el("kp-plan-one").addEventListener("click", () => {
  if (kpFocus) kpRun("Planning ingest (this asks the model)", () => kpPlan(kpFocus));
});
el("kp-doc-back").addEventListener("click", () => { if (kpFocus) kpFocusOn(kpFocus); });
el("kp-reingest").addEventListener("click", () => kpRun("Starting the ingest", async () => {
  const refs = kpRawTicked();
  if (!refs.length) { kpStatus("Tick at least one Raw document.", true); return; }
  await kpReingestStart(refs);
}));
el("kp-reingest-stop").addEventListener("click", () => kpRun("Stopping", async () => {
  await call("/api/knowledge/reingest/stop", {sandbox_id: kpSandbox.sandbox_id});
  kpStatus("Stops after the document in progress.");
  await kpReingestShow();
}));

async function kpLint() {
  const report = await pipeline("lint", {sandbox_id: kpSandbox.sandbox_id});
  const box = el("kp-lint-result"); box.replaceChildren();
  box.append(text(report.pages + " pages, " + (report.clean ? "clean" : "findings") + ": "
    + Object.entries(report.counts).filter(([, n]) => n).map(([k, n]) => k + " " + n)
      .join(", ")));
  const list = document.createElement("ul");
  for (const line of report.findings) {
    const li = document.createElement("li"); li.append(text(line)); list.append(li);
  }
  box.append(list);
}

el("kp-refresh").addEventListener("click", () => kpRun("Reading", loadKnowledge));
el("kp-new").addEventListener("submit", (event) => {
  event.preventDefault();
  kpRun("Creating the sandbox (copying the base vault)", async () => {
    if (!el("kp-scope").value) { kpStatus("Choose the folder this sandbox maintains.", true);
      return; }
    const key = kpKey();
    const made = await kpWithProgress("Copying the project vault", key, () =>
      pipeline("sandbox-create", {base: el("kp-base").value, label: el("kp-label").value.trim(),
                                  scope: el("kp-scope").value, progress_key: key}));
    el("kp-label").value = ""; await loadKnowledge(); await kpOpen(made);
    kpStage("pull");
    if (kpTicked(el("kp-pull-folders")).length) el("kp-pull").click();  // pull the folder now
  });
});
el("kp-upload").addEventListener("click", () => kpRun("Adding to drop", async () => {
  for (const file of el("kp-files").files) {
    const folder = el("kp-category").value;
    await pipeline("drop-add", {sandbox_id: kpSandbox.sandbox_id,
      name: (folder ? folder + "/" : "") + file.name,
      data_base64: await kpFileBase64(file)});
  }
  el("kp-files").value = ""; await kpOpen(kpSandbox);
}));
el("kp-preview").addEventListener("click", () => kpRun("Previewing", () => kpConvert("dry_run")));
el("kp-convert").addEventListener("click", () => kpRun("Converting", () => kpConvert("apply")));
el("kp-lint").addEventListener("click", () => kpRun("Linting", kpLint));
el("kp-push").addEventListener("click", () => kpRun("Starting the push", async () => {
  const sets = kpTicked(el("kp-bench-sets"));
  if (!confirm("Push " + kpSandbox.label + " into the project vault? It is written only if the "
      + "benchmark (" + (sets.join(", ") || "no question sets") + ") shows no regression.")) return;
  const reply = await call("/api/knowledge/push/start", {sandbox_id: kpSandbox.sandbox_id, sets,
                                                         resolutions: kpResolutions()});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  setTimeout(() => kpPushShow().catch(() => {}), 1500);
}));
el("kp-refresh-agent").addEventListener("click", () => kpRun("Refreshing", async () => {
  if (!confirm("Stage the project vault " + kpSandbox.base_name + " as the Agent's next "
      + "Knowledge version? It answers from it after a restart.")) return;
  const reply = await call("/api/knowledge/refresh", {base: kpSandbox.base_name});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  el("kp-push-state").textContent = "Staged " + reply.data.version + " at "
    + reply.data.vault_root + ". Restart the Agent to answer from it.";
}));
el("kp-pull").addEventListener("click", () => kpRun("Pulling", async () => {
  const folders = kpTicked(el("kp-pull-folders"));
  if (!folders.length) { kpStatus("Choose at least one folder.", true); return; }
  const key = kpKey();
  const pulled = await kpWithProgress("Pulling originals", key, () =>
    pipeline("pull", {sandbox_id: kpSandbox.sandbox_id, folders, progress_key: key}));
  const parts = [pulled.copied.length + " new original(s) copied to drop (convert them below)"];
  if (pulled.already_in_sandbox.length) {
    parts.push(pulled.already_in_sandbox.length + " already in this sandbox's drop");
  }
  if (pulled.too_large.length) parts.push(pulled.too_large.length + " too large to pull");
  if (pulled.already_ingested.length) {
    parts.push(pulled.already_ingested.length + " already ingested: their Raw ("
      + pulled.already_raw.length + " document(s)) is already in this sandbox, so they are "
      + "not pulled again. To try changed rules on them, re-ingest them in step 2");
  }
  await kpOpen(kpSandbox);
  const box = el("kp-pull-result"); box.replaceChildren(text(parts.join("; ") + ". "));
  if (pulled.already_raw.length) {
    box.append(kpButton("Tick them in step 2", () => {
      kpRawTick(pulled.already_raw);
      el("kp-raw").scrollIntoView({block: "start"});
    }));
  }
}));
el("kp-bench").addEventListener("click", () => kpRun("Starting the benchmark", async () => {
  const sets = kpTicked(el("kp-bench-sets"));
  if (!sets.length) { kpStatus("Choose at least one question set.", true); return; }
  const reply = await call("/api/knowledge/benchmark/start",
                           {sandbox_id: kpSandbox.sandbox_id, sets});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  setTimeout(() => kpBenchShow().catch(() => {}), 1500);
}));
el("kp-viewer-close").addEventListener("click", () => { el("kp-viewer").hidden = true; });
el("kp-rule-close").addEventListener("click", () => {
  el("kp-rule-editor").hidden = true; kpRulePath = null;
});
let kpRuleSaved = "";
function kpDiffLines(before, after) {
  // A line diff in file order (longest common subsequence), so additions and
  // removals show where they happen.
  const lines = (value) => value.replace(/\r\n?/g, "\n").split("\n");
  const a = lines(before), b = lines(after);
  if (a.length * b.length > 4000000) {
    return [...a.map((line) => ["-", line]), ...b.map((line) => ["+", line])];
  }
  const table = Array.from({length: a.length + 1}, () => new Uint16Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1
        : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const out = [];
  let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { out.push([" ", a[i]]); i++; j++; }
    else if (i < a.length && (j >= b.length || table[i + 1][j] >= table[i][j + 1])) {
      out.push(["-", a[i]]); i++;  // a removal is listed before what replaces it
    } else { out.push(["+", b[j]]); j++; }
  }
  return out;
}
let kpRuleMode = "md", kpRenderTimer = null, kpSyncing = false;
const KP_LINE = 20, KP_CONTEXT = 3;
function kpNumbered(lines) {
  // Old and new line numbers for every diff row.
  let old = 0, now = 0;
  return lines.map(([kind, line]) => {
    if (kind !== "+") old += 1;
    if (kind !== "-") now += 1;
    return {kind, line, old: kind === "+" ? null : old, now: kind === "-" ? null : now};
  });
}
function kpHunks(rows) {
  // Changed rows with three rows of context, merged when they touch.
  const keep = new Set();
  rows.forEach((row, index) => {
    if (row.kind === " ") return;
    for (let k = Math.max(0, index - KP_CONTEXT);
         k <= Math.min(rows.length - 1, index + KP_CONTEXT); k++) keep.add(k);
  });
  const hunks = [];
  let current = null;
  rows.forEach((row, index) => {
    if (!keep.has(index)) { current = null; return; }
    if (current === null) { current = []; hunks.push(current); }
    current.push(row);
  });
  return hunks;
}
function kpRow(cells, kind, now) {
  const row = document.createElement("div");
  row.className = "kp-drow " + (kind === "+" ? "kp-add" : kind === "-" ? "kp-del"
    : kind === "@" ? "kp-hunk" : "kp-same");
  if (now !== null && now !== undefined) row.dataset.now = String(now);
  for (const [cls, value] of cells) {
    const cell = document.createElement("span"); cell.className = cls;
    cell.append(text(value)); row.append(cell);
  }
  return row;
}
function kpRenderPrevious(rows) {
  const box = el("kp-prev"); box.replaceChildren();
  const hunks = kpHunks(rows);
  if (!hunks.length) {
    const none = document.createElement("p"); none.className = "note kp-none";
    none.append(text("No changes from the saved file.")); box.append(none); return;
  }
  for (const hunk of hunks) {
    const olds = hunk.filter((r) => r.old !== null), nows = hunk.filter((r) => r.now !== null);
    const head = "@@ -" + (olds.length ? olds[0].old : 0) + "," + olds.length
      + " +" + (nows.length ? nows[0].now : 0) + "," + nows.length + " @@";
    box.append(kpRow([["kp-ln", ""], ["kp-ln", ""], ["kp-txt", head]], "@", null));
    for (const row of hunk) {
      const oldNo = row.kind === "-" ? "-" + row.old : row.old === null ? "" : String(row.old);
      const nowNo = row.kind === "+" ? "+" + row.now : row.now === null ? "" : String(row.now);
      box.append(kpRow([["kp-ln", oldNo], ["kp-ln", nowNo], ["kp-txt", row.line || "​"]],
                       row.kind, row.now !== null ? row.now : row.old));
    }
  }
}
function kpRenderCurrent(rows) {
  const gutter = el("kp-cur-gutter"), back = el("kp-after-backdrop");
  gutter.replaceChildren(); back.replaceChildren();
  for (const row of rows) {
    if (row.kind === "-") continue;
    const numbers = document.createElement("div");
    numbers.className = "kp-gline" + (row.kind === "+" ? " kp-add" : "");
    const oldCell = document.createElement("span"); oldCell.className = "kp-ln";
    oldCell.append(text(row.old === null ? "" : String(row.old)));
    const nowCell = document.createElement("span"); nowCell.className = "kp-ln";
    nowCell.append(text(row.kind === "+" ? "+" + row.now : String(row.now)));
    numbers.append(oldCell, nowCell); gutter.append(numbers);
    const shade = document.createElement("div");
    shade.className = row.kind === "+" ? "kp-add" : "kp-same";
    shade.append(text(row.line || "​")); back.append(shade);
  }
  kpSyncCurrent();
}
function kpRenderPanes() {
  const current = el("kp-rule-text").value;
  const rows = kpNumbered(kpDiffLines(kpRuleSaved, current));
  const added = rows.filter((r) => r.kind === "+").length;
  const removed = rows.filter((r) => r.kind === "-").length;
  el("kp-diff-summary").textContent = added || removed
    ? "· +" + added + " added, −" + removed + " removed" : "";
  const preview = kpRuleMode === "preview";
  el("kp-md-view").hidden = preview; el("kp-after-preview").hidden = !preview;
  if (preview) {
    el("kp-after-preview").replaceChildren(renderMarkdown(current));
  } else {
    kpRenderPrevious(rows); kpRenderCurrent(rows);
  }
  kpRuleDirty();
}
function kpSyncCurrent() {
  const area = el("kp-rule-text");
  el("kp-after-backdrop").scrollTop = area.scrollTop;
  el("kp-after-backdrop").scrollLeft = area.scrollLeft;
  el("kp-cur-gutter").scrollTop = area.scrollTop;
}
function kpAlign(fromCurrent) {
  // Keep Previous and Current on the same line while either scrolls.
  if (kpSyncing) return;
  kpSyncing = true;
  const area = el("kp-rule-text"), prev = el("kp-prev-body");
  const rows = [...el("kp-prev").querySelectorAll(".kp-drow[data-now]")];
  if (rows.length) {
    if (fromCurrent) {
      const line = Math.floor(area.scrollTop / KP_LINE) + 1;
      const target = rows.find((row) => Number(row.dataset.now) >= line) || rows[rows.length - 1];
      prev.scrollTop = target.offsetTop - el("kp-prev").offsetTop;
    } else {
      const top = prev.scrollTop + el("kp-prev").offsetTop;
      const target = rows.find((row) => row.offsetTop >= top) || rows[rows.length - 1];
      area.scrollTop = (Number(target.dataset.now) - 1) * KP_LINE;
      kpSyncCurrent();
    }
  }
  requestAnimationFrame(() => { kpSyncing = false; });
}
function kpRuleDirty() {
  const changed = el("kp-rule-text").value !== kpRuleSaved;
  el("kp-rule-dirty").textContent = changed ? " — unsaved changes" : "";
}
function kpTab(name) {
  kpRuleMode = name === "preview" ? "preview" : "md";
  for (const button of document.querySelectorAll(".kp-tabs [data-tab]")) {
    button.setAttribute("aria-selected", String(button.dataset.tab === kpRuleMode));
  }
  kpRenderPanes();
}
for (const button of document.querySelectorAll(".kp-tabs [data-tab]")) {
  button.addEventListener("click", () => kpTab(button.dataset.tab));
}
for (const head of document.querySelectorAll(".kp-block-head")) {
  head.addEventListener("click", () => {
    const block = el(head.dataset.block);
    const open = block.classList.toggle("kp-collapsed") === false;
    head.setAttribute("aria-expanded", String(open));
  });
}
el("kp-rule-text").addEventListener("input", () => {
  kpRuleDirty();
  clearTimeout(kpRenderTimer);
  kpRenderTimer = setTimeout(kpRenderPanes, 200);
});
el("kp-rule-text").addEventListener("scroll", () => { kpSyncCurrent(); kpAlign(true); });
el("kp-prev-body").addEventListener("scroll", () => kpAlign(false));
el("kp-rule-revert").addEventListener("click", () => {
  el("kp-rule-text").value = kpRuleSaved; kpTab(kpRuleMode);
});

// Splitters: drag to share the width; the widths are remembered on this browser.
const KP_PANES = ["kp-pane-file", "kp-pane-ai"];
function kpApplyWidths(widths) {
  KP_PANES.forEach((id, index) => { el(id).style.flexBasis = widths[index] + "%"; });
}
let kpWidths = [68, 32];
try {
  const kept = JSON.parse(localStorage.getItem("kp-pane-widths-2") || "null");
  if (Array.isArray(kept) && kept.length === 2) kpWidths = kept;
} catch (_ignored) { /* storage may be unavailable */ }
kpApplyWidths(kpWidths);
for (const split of document.querySelectorAll(".kp-split")) {
  split.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const left = KP_PANES.indexOf(split.dataset.left);
    const right = KP_PANES.indexOf(split.dataset.right);
    const total = el("kp-panes").getBoundingClientRect().width;
    const startX = event.clientX, start = [...kpWidths];
    try { split.setPointerCapture(event.pointerId); } catch (_ignored) { /* best effort */ }
    const move = (moved) => {
      const delta = (moved.clientX - startX) / total * 100;
      const pair = start[left] + start[right];
      const leftWidth = Math.min(pair - 10, Math.max(10, start[left] + delta));
      kpWidths[left] = leftWidth; kpWidths[right] = pair - leftWidth;
      kpApplyWidths(kpWidths);
    };
    const stop = () => {
      split.removeEventListener("pointermove", move);
      split.removeEventListener("pointerup", stop);
      try { localStorage.setItem("kp-pane-widths-2", JSON.stringify(kpWidths)); }
      catch (_ignored) { /* storage may be unavailable */ }
    };
    split.addEventListener("pointermove", move);
    split.addEventListener("pointerup", stop);
  });
}
// Maximize a pane over the page, and restore it.
function kpMaximize(id, on) {
  for (const pane of KP_PANES) el(pane).classList.toggle("kp-maxed", pane === id && on);
  for (const button of document.querySelectorAll(".kp-max")) {
    const maxed = button.dataset.pane === id && on;
    button.innerHTML = maxed ? "&#x2921;" : "&#x2922;";
    button.title = maxed ? "Restore" : "Maximize";
  }
}
for (const button of document.querySelectorAll(".kp-max")) {
  button.addEventListener("click", () => {
    kpMaximize(button.dataset.pane, !el(button.dataset.pane).classList.contains("kp-maxed"));
  });
}
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.querySelector(".kp-pane.kp-maxed")) {
    kpMaximize(null, false);
  }
});

const KP_ASSIST_STATES = [["collecting", "Reading the file, guide and a sample"],
  ["asking", "The model is writing"], ["checking", "Checking the proposal"]];
let kpAssistTurns = [];
function kpAssistShow(progress) {
  const log = el("kp-assist-log"); log.replaceChildren();
  for (const turn of kpAssistTurns) {
    const item = document.createElement("div"); item.className = "kp-turn kp-" + turn.role;
    item.append(turn.role === "user" ? text(turn.text) : renderMarkdown(turn.text));
    if (turn.proposal) {
      const note = document.createElement("p"); note.className = "note";
      note.append(text("The proposal is in Current file (added lines green; removed "
        + "ones red under Previous file); press Save to keep it."));
      item.append(note);
    }
    for (const warning of turn.warnings || []) {
      const line = document.createElement("p"); line.className = "bad";
      line.append(text("⚠ " + warning)); item.append(line);
    }
    log.append(item);
  }
  if (progress) {
    const item = document.createElement("div"); item.className = "kp-turn kp-running";
    const title = document.createElement("strong");
    title.append(text("Working… " + progress.elapsed_s + " s")); item.append(title);
    const steps = document.createElement("ol"); steps.className = "kp-steps";
    const reached = progress.history || [];
    for (const [key, label] of KP_ASSIST_STATES) {
      const li = document.createElement("li");
      const done = reached.includes(key) && progress.state !== key;
      li.className = progress.state === key ? "kp-now" : done ? "kp-done" : "kp-later";
      li.append(text((done ? "✓ " : progress.state === key ? "▶ " : "· ") + label));
      steps.append(li);
    }
    item.append(steps); log.append(item);
  }
  log.scrollTop = log.scrollHeight;
}
el("kp-assist-reset").addEventListener("click", () => { kpAssistTurns = []; kpAssistShow(); });
el("kp-assist-send").addEventListener("click", async () => {
  const message = el("kp-assist-input").value.trim();
  if (!message || !kpRulePath) return;
  kpAssistTurns.push({role: "user", text: message});
  el("kp-assist-input").value = "";
  el("kp-assist-send").disabled = true;
  avatarWorking(1);
  try {
    kpAssistShow({state: "collecting", history: ["collecting"], elapsed_s: 0});
    const started = await call("/api/knowledge/skill-assist", {
      sandbox_id: kpSandbox.sandbox_id, path: kpRulePath, current: el("kp-rule-text").value,
      turns: kpAssistTurns.map(({role, text}) => ({role, text}))});
    if (!started.ok) throw Object.assign(new Error(started.code), {code: started.code});
    let status;
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      status = await call("/api/knowledge/skill-assist?job=" + encodeURIComponent(started.job_id));
      if (!status.ok || status.state === "done" || status.state === "failed") break;
      kpAssistShow(status);
    }
    const result = status && status.result;
    if (!result || !result.ok) {
      throw Object.assign(new Error(result ? result.code : "skill_assist_failed"),
                          {code: result ? result.code : "skill_assist_failed"});
    }
    kpAssistTurns.push({role: "assistant", text: result.reply, proposal: result.proposal,
                        warnings: result.warnings});
    kpAssistShow();
    if (result.proposal) { el("kp-rule-text").value = result.proposal; kpTab("md"); }
  } catch (failure) {
    kpAssistTurns.pop(); kpAssistShow();
    kpStatus("The assistant did not answer: " + (failure.code || failure.message), true);
  } finally {
    el("kp-assist-send").disabled = false;
    avatarWorking(-1);
  }
});
el("kp-rule-save").addEventListener("click", () => kpRun("Saving the rule", async () => {
  if (!kpRulePath) return;
  const textNow = el("kp-rule-text").value;
  await pipeline("rule-write", {sandbox_id: kpSandbox.sandbox_id, path: kpRulePath,
                                text: textNow});
  kpRuleSaved = textNow; kpRuleDirty();
  kpRenderPanes();
  kpStatus("Saved " + kpRulePath + "; the next ingest uses it.");
  await kpLoadRules();
}));
let kpCandidate = null;
function kpMergeShow(report) {
  const box = el("kp-merge-result"); box.replaceChildren();
  box.append(text(report.changes.length + " changed pages, " + report.conflicts.length
    + " conflicts" + (report.kept_removed.length ? ", " + report.kept_removed.length
    + " removals kept back" : "") + "."));
  const list = document.createElement("ul");
  for (const change of report.changes) {
    const li = document.createElement("li");
    li.append(text(change.change + ": " + change.path + (change.parts.length
      ? " (" + change.parts.join(", ") + ")" : "") + (change.proposal ? " — proposal" : "")));
    list.append(li);
  }
  for (const conflict of report.conflicts) {
    const li = document.createElement("li");
    const key = conflict.path + "#" + conflict.part;
    const pick = document.createElement("select"); pick.dataset.key = key;
    for (const [value, label] of [["", "choose…"], ["sandbox", "keep sandbox"],
                                  ["published", "keep published"]]) {
      const option = document.createElement("option"); option.value = value;
      option.append(text(label)); pick.append(option);
    }
    const detail = document.createElement("details");
    const summary = document.createElement("summary"); summary.append(text("compare"));
    const sandbox = document.createElement("pre"); sandbox.append(text(conflict.sandbox));
    const published = document.createElement("pre"); published.append(text(conflict.published));
    detail.append(summary, text("Sandbox:"), sandbox, text("Published:"), published);
    li.append(text("conflict: " + key + " "), pick, detail); list.append(li);
  }
  box.append(list);
  if (report.candidate_root) {
    box.append(text("Candidate written: " + report.candidate_root + "; sourced lines lost: "
      + report.lost_sourced_lines + "; lint findings that grew: "
      + (Object.entries(report.lint_worse).map(([k, n]) => k + " +" + n).join(", ") || "none")));
  }
}
function kpResolutions() {
  const chosen = {};
  for (const pick of el("kp-merge-result").querySelectorAll("select[data-key]")) {
    if (pick.value) chosen[pick.dataset.key] = pick.value;
  }
  return chosen;
}
el("kp-merge-preview").addEventListener("click", () => kpRun("Comparing", async () => {
  kpMergeShow(await pipeline("merge", {sandbox_id: kpSandbox.sandbox_id}));
}));
el("kp-merge").addEventListener("click", () => kpRun("Merging", async () => {
  const report = await pipeline("merge", {sandbox_id: kpSandbox.sandbox_id, mode: "apply",
                                          resolutions: kpResolutions()});
  kpCandidate = {base: report.base_name, root: report.candidate_root};
  kpMergeShow(report); el("kp-publish").disabled = false;
}));
el("kp-publish").addEventListener("click", () => kpRun("Publishing", async () => {
  if (!kpCandidate || !confirm("Publish " + kpCandidate.root + " as the new version of "
      + kpCandidate.base + "? The Agent answers from it after a restart.")) return;
  const reply = await call("/api/knowledge/pipeline/publish",
    {base: kpCandidate.base, candidate_root: kpCandidate.root});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  el("kp-publish").disabled = true;
  el("kp-merge-result").append(text(" Published " + (reply.data.version || "")
    + " at " + reply.data.vault_root + ". Restart the Agent to answer from it."));
}));
el("kp-enrich").addEventListener("click", () => kpRun("Writing bilingual summaries", async () => {
  let report;
  do {
    report = await pipeline("index-enrich", {sandbox_id: kpSandbox.sandbox_id, limit: 60});
    el("kp-index-result").textContent = "Enriched " + report.done + " more; "
      + report.remaining + " pages remain.";
  } while (report.remaining > 0 && report.done > 0);
}));
el("kp-index").addEventListener("click", () => kpRun("Building the index", async () => {
  const preview = await pipeline("index-build", {sandbox_id: kpSandbox.sandbox_id});
  const counts = Object.entries(preview.categories).map(([k, n]) => k + " " + n).join(", ");
  if (!confirm("Write " + preview.written.length + " index pages? " + counts)) return;
  await pipeline("index-build", {sandbox_id: kpSandbox.sandbox_id, mode: "apply"});
  el("kp-index-result").textContent = "Index written: " + counts;
}));
el("kp-adopt").addEventListener("click", () => kpRun("Checking legacy Raw", async () => {
  const preview = await pipeline("adopt", {sandbox_id: kpSandbox.sandbox_id, mode: "dry_run"});
  if (!preview.raw_adopted) { el("kp-adopt-result").textContent = "Nothing to adopt."; return; }
  if (!confirm("Adopt " + preview.raw_adopted + " Raw files from earlier tooling? "
    + "Their bytes stay untouched; a ledger records them.")) return;
  const done = await pipeline("adopt", {sandbox_id: kpSandbox.sandbox_id, mode: "apply"});
  el("kp-adopt-result").textContent = "Adopted " + done.raw_adopted + ", drifted "
    + done.raw_drifted + ", unresolved pages " + done.pages_unresolved + ".";
  await kpOpen(kpSandbox);
}));
el("kp-discard").addEventListener("click", () => {
  if (!kpSandbox || !confirm("Discard this sandbox? It is moved aside, not deleted.")) return;
  kpRun("Discarding", async () => {
    await pipeline("sandbox-discard", {sandbox_id: kpSandbox.sandbox_id});
    kpSandbox = null; kpStage("pull"); await loadKnowledge();
  });
});

"""

WIKI_CSS, WIKI_PANE_HTML, WIKI_JS = WIKI_CSS[1:], WIKI_PANE_HTML[1:], WIKI_JS[1:]

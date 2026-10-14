"""Knowledge as three guided steps: pull, ingest, test (owner, 2026-10-14)."""

from pathlib import Path

from test_knowledge_scope import _project

from host_runtime.web_page import PAGE


def test_the_knowledge_tab_is_three_steps_with_one_primary_action_each() -> None:
    panel = PAGE[PAGE.index('<section id="panel-knowledge">'):
                 PAGE.index('<section id="panel-reviews">')]
    for stage in ("pull", "ingest", "test"):
        assert f'data-stage="{stage}"' in panel  # a step button and a step page each
    for hook in ('class="kp-stepper"', 'aria-current', "Step 1 of 3", "Step 2 of 3",
                 "Step 3 of 3", 'data-go="ingest"', 'data-go="test"', 'data-go="pull"',
                 "Create sandbox and pull", 'id="kp-switch"', 'id="kp-q-coverage"',
                 'id="kp-q-new"', 'id="kp-q-text"', "Run test"):
        assert hook in PAGE
    # Where each feature lives: convert in step 1, skills and ingest in step 2,
    # questions, test and push in step 3.
    order = [panel.index(h) for h in ('id="kp-stage-pull"', 'id="kp-convert"',
                                      'id="kp-stage-ingest"', 'id="kp-rules"',
                                      'id="kp-reingest"', 'id="kp-stage-test"',
                                      'id="kp-q-list"', 'id="kp-bench"', 'id="kp-push"')]
    assert order == sorted(order)
    # The page hides every <section> that is not an open panel; a step must override
    # that or it shows nothing (seen live on 2026-10-14).
    assert "section { display: none;" in PAGE and ".kp-stage { display: block;" in PAGE


def test_question_sets_list_each_question_and_who_may_edit_it(tmp_path: Path) -> None:
    pipeline, base = _project(tmp_path)
    for rel, text in {"checks/questions/market/q1.md": "# Q1?\n\n必須提到:\n  - FSW\n",
                      "checks/questions/market/q2.md": "# Q2?\n",
                      "checks/questions/productions/q3.md": "# Q3?\n\n必須提到:\n  - ZNA\n",
                      "checks/questions/q4.md": "# Q4?\n"}.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")
    market = pipeline.create_sandbox("rs-k", "m", "leo", scope="Market").sandbox_id
    sets = pipeline.question_sets(market)
    assert sets.defaults == ("market",)
    shown = {q.path: (q.must, q.editable) for q in sets.questions}
    assert shown == {"checks/questions/market/q1.md": (1, True),
                     "checks/questions/market/q2.md": (0, True),
                     "checks/questions/productions/q3.md": (1, False),
                     "checks/questions/q4.md": (0, False)}
    productions = pipeline.create_sandbox("rs-k", "p", "leo", scope="Productions").sandbox_id
    editable = {q.path for q in pipeline.question_sets(productions).questions if q.editable}
    assert editable == {"checks/questions/productions/q3.md"}  # productions = production


def test_the_steps_status_and_progress_stay_on_top_together() -> None:
    # One sticky header (owner 2026-10-14): separate sticky rows at top 0 would overlap.
    top = PAGE.index('<div class="kp-top">')
    assert top < PAGE.index('id="kp-stepper"') < PAGE.index('id="kp-status"') \
        < PAGE.index('id="kp-progress"') < PAGE.index('id="kp-main"')
    assert ".kp-top { position: sticky; top: 0;" in PAGE and "kp-sticky" not in PAGE

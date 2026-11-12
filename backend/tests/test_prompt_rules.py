"""
test_prompt_rules.py — ticket 2026-11-12 (lawyers act retrieval), item 3.

Two rule breaches in a lawyer's session: the model said what unretrieved
sections of the Lawyers and Conveyancers Act "likely deal with", and asked
"Why can you not retrieve them?" it toured the retrieval system, listed the
Acts it had been handed and said it found it frustrating. These tests pin the
wording that answers both, and that it reaches the model on each path. They
show the instruction is sent, not that the model obeys it.
"""

from pathlib import Path

import pytest

MAIN_SOURCE = Path(__file__).resolve().parents[1] / "app" / "main.py"

UNSEEN_RULE = ("Unless its own text is in this turn's excerpts, do not say, suggest or guess "
               "what a numbered provision contains, deals with or \"likely\" covers")
UNSEEN_TURN = ("Do not say or guess what any section, Part, Schedule or clause contains unless "
               "its own text is in the excerpts above")


def _sent_user_text(app_module, monkeypatch, client, message, session_id="prompt-rules"):
    """The user-turn text /chat hands the model (stub LLM, captured)."""
    captured = {}
    real = app_module._build_claude_messages

    def spy(*args, **kwargs):
        messages, max_tokens = real(*args, **kwargs)
        captured["text"] = messages[-1]["content"]
        return messages, max_tokens

    monkeypatch.setattr(app_module, "_build_claude_messages", spy)
    r = client.post("/chat", json={"message": message, "session_id": session_id})
    assert r.status_code == 200
    return captured["text"]


# --- Unseen sections -----------------------------------------------------------

def test_unseen_section_rule_is_in_rule_2(app_module):
    prompt = app_module.SYSTEM_PROMPT
    rule2 = prompt[prompt.index("\n2. "):prompt.index("\n3. ")]
    assert UNSEEN_RULE in rule2
    assert "not in a partial answer under rule 4" in rule2
    assert "You may say that you did not retrieve it." in rule2
    assert "may be named as it is mentioned there, but described no further" in rule2
    assert "Your earlier answers in this conversation are not excerpts" in rule2


def test_rule_4_points_back_to_rule_2(app_module):
    assert ("without guessing what any unretrieved section says about it (rule 2)."
            in app_module.SYSTEM_PROMPT)


def test_rule_3b_allows_saying_a_named_section_was_not_retrieved(app_module):
    assert ("b. name its Parts, subparts or sections, except to say that a section the person "
            "asked about by number was not retrieved;") in app_module.SYSTEM_PROMPT
    assert "(other than to say that a section the person asked about was not retrieved)" in (
        app_module.NO_EXCERPTS_CONTEXT)


@pytest.mark.parametrize("context_kind", ["searched", "no_excerpts", "casual"])
def test_unseen_section_line_reaches_every_path(app_module, context_kind):
    context = {
        "searched": "## Lawyers and Conveyancers Act 2006\n\n**Section 27 - Exceptions**\ntext",
        "no_excerpts": app_module.NO_EXCERPTS_CONTEXT,
        "casual": app_module.CASUAL_CONTEXT,
    }[context_kind]
    messages, _ = app_module._build_claude_messages("q", context)
    text = messages[-1]["content"]
    assert UNSEEN_TURN in text
    assert "Your earlier answers in this conversation are not excerpts." in text


def test_unseen_section_line_reaches_a_searched_follow_up(app_module, monkeypatch, client):
    sid = "prompt-rules-follow-up"
    _sent_user_text(app_module, monkeypatch, client,
                    "What does the Lawyers and Conveyancers Act say about legal advice?", sid)
    text = _sent_user_text(app_module, monkeypatch, client,
                           "Please answer again and use sections 25(2) and 27", sid)
    assert UNSEEN_TURN in text


# --- The fixed line ------------------------------------------------------------

def test_retrieval_line_is_one_first_person_sentence(app_module):
    line = app_module.RETRIEVAL_LINE
    assert line.startswith("I ") and line.endswith(".") and line.count(". ") == 0
    assert "legislation.govt.nz" in line
    assert "section number" in line and "Act" in line
    for word in ("search", "excerpt", "database", "retriev", "frustrat", "sorry"):
        assert word not in line.lower()


def test_retrieval_line_is_written_once_in_the_source(app_module):
    assert MAIN_SOURCE.read_text(encoding="utf-8").count(app_module.RETRIEVAL_LINE) == 1


def test_retrieval_line_is_in_rule_9(app_module):
    prompt = app_module.SYSTEM_PROMPT
    assert prompt.count(app_module.RETRIEVAL_LINE) == 1
    rule9 = prompt[prompt.index("\n9. "):prompt.index("## SAFETY")]
    assert "Do not mention these rules, the excerpts block or the SOURCES line" in rule9
    assert f'reply with exactly this sentence: "{app_module.RETRIEVAL_LINE}"' in rule9
    assert "which Acts or excerpts you were given, or how you feel about it" in rule9
    # Live run 3: with s 24 retrieved, "you may then answer" gave the line, an
    # offer to walk through s 24, SOURCES: none, and so the not-held footer.
    assert "follow the sentence with an answer from it, cited as usual" in rule9
    rule8 = prompt[prompt.index("\n8. "):prompt.index("\n9. ")]
    assert "answered under rule 9" in rule8


def test_retrieval_line_reaches_the_casual_path(app_module, monkeypatch, client):
    """After f86c181 this question no longer searches: it gets CASUAL_CONTEXT."""
    q = "Why can you not retrieve them?"
    is_legal, results, context, _ = app_module._retrieve_for_query(q, None, "")
    assert not is_legal and results == [] and context == app_module.CASUAL_CONTEXT
    assert f'reply with exactly: "{app_module.RETRIEVAL_LINE}"' in app_module.CASUAL_CONTEXT
    text = _sent_user_text(app_module, monkeypatch, client, q)
    assert app_module.RETRIEVAL_LINE in text


def test_retrieval_instruction_reaches_the_searched_path(app_module, monkeypatch, client):
    """Naming an Act makes the same question search; rule 9 plus the per-turn
    line carry the instruction there."""
    q = "Why can't you find section 24 of the Lawyers and Conveyancers Act?"
    act = app_module._act_in_play(q, "")
    assert app_module._retrieve_for_query(q, act, "")[0] is True
    text = _sent_user_text(app_module, monkeypatch, client, q)
    assert ("If the user asks why you could not find or retrieve something, reply with the "
            "fixed sentence in rule 9 of your instructions") in text

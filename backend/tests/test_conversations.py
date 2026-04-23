import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import ConversationService, NotFoundError
from app.db.models import Base
from app.llm import ToolCall


@pytest.fixture
def conversations():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return ConversationService(factory)


def test_create_returns_conversation(conversations):
    conv = conversations.create(title="Daily planning")
    assert conv.id
    assert conv.title == "Daily planning"
    assert conv.created_at is not None
    assert conv.updated_at is not None


def test_create_default_title(conversations):
    assert conversations.create().title == "New thread"


def test_list_empty(conversations):
    assert conversations.recent() == []


def test_list_orders_by_updated_desc(conversations):
    a = conversations.create(title="first")
    time.sleep(0.001)
    b = conversations.create(title="second")
    time.sleep(0.001)
    c = conversations.create(title="third")
    ids = [conv.id for conv in conversations.recent()]
    assert ids == [c.id, b.id, a.id]


def test_get_returns_conversation(conversations):
    a = conversations.create(title="abc")
    got = conversations.get(a.id)
    assert got.id == a.id and got.title == "abc"


def test_get_unknown_raises(conversations):
    with pytest.raises(NotFoundError):
        conversations.get("nope")


def test_rename(conversations):
    a = conversations.create(title="old")
    conversations.rename(a.id, "new")
    assert conversations.get(a.id).title == "new"


def test_rename_unknown_raises(conversations):
    with pytest.raises(NotFoundError):
        conversations.rename("nope", "x")


def test_delete_removes_conversation(conversations):
    a = conversations.create()
    conversations.delete(a.id)
    with pytest.raises(NotFoundError):
        conversations.get(a.id)


def test_delete_unknown_raises(conversations):
    with pytest.raises(NotFoundError):
        conversations.delete("nope")


def test_append_message(conversations):
    conv = conversations.create()
    msg = conversations.append_message(conv.id, role="user", content="hello")
    assert msg.id and msg.sequence == 1
    assert msg.role == "user" and msg.content == "hello"


def test_append_assigns_incrementing_sequence(conversations):
    conv = conversations.create()
    msgs = [
        conversations.append_message(conv.id, "user", "a"),
        conversations.append_message(conv.id, "assistant", "b"),
        conversations.append_message(conv.id, "user", "c"),
    ]
    assert [m.sequence for m in msgs] == [1, 2, 3]


def test_append_unknown_conversation_raises(conversations):
    with pytest.raises(NotFoundError):
        conversations.append_message("nope", "user", "hi")


def test_append_bumps_updated_at(conversations):
    conv = conversations.create()
    before = conversations.get(conv.id).updated_at
    time.sleep(0.01)
    conversations.append_message(conv.id, "user", "hi")
    after = conversations.get(conv.id).updated_at
    assert after > before


def test_append_with_tool_calls(conversations):
    conv = conversations.create()
    tool_calls = [
        ToolCall(id="c1", name="search", arguments={"q": "volvo"}),
        ToolCall(id="c2", name="read_file", arguments={"path": "notes/volvo.md"}),
    ]
    msg = conversations.append_message(
        conv.id, role="assistant", content="", tool_calls=tool_calls
    )
    assert msg.tool_calls == [
        {"id": "c1", "name": "search", "arguments": {"q": "volvo"}},
        {"id": "c2", "name": "read_file", "arguments": {"path": "notes/volvo.md"}},
    ]


def test_append_tool_result(conversations):
    conv = conversations.create()
    msg = conversations.append_message(
        conv.id, role="tool", content="result text", tool_call_id="c1"
    )
    assert msg.tool_call_id == "c1" and msg.content == "result text"


def test_messages_returns_in_order(conversations):
    conv = conversations.create()
    conversations.append_message(conv.id, "user", "a")
    conversations.append_message(conv.id, "assistant", "b")
    conversations.append_message(conv.id, "user", "c")
    msgs = conversations.messages(conv.id)
    assert [m.content for m in msgs] == ["a", "b", "c"]


def test_to_llm_messages_roundtrips_tool_calls(conversations):
    conv = conversations.create()
    tcs = [ToolCall(id="x", name="echo", arguments={"m": "hi"})]
    conversations.append_message(conv.id, "assistant", "", tool_calls=tcs)
    conversations.append_message(conv.id, "tool", "hi", tool_call_id="x")
    llm_msgs = conversations.to_llm_messages(conv.id)
    assert len(llm_msgs) == 2
    assistant = llm_msgs[0]
    assert assistant.role == "assistant" and len(assistant.tool_calls) == 1
    assert assistant.tool_calls[0].id == "x"
    assert assistant.tool_calls[0].arguments == {"m": "hi"}
    tool_msg = llm_msgs[1]
    assert tool_msg.role == "tool" and tool_msg.tool_call_id == "x"


def test_delete_cascades_messages(conversations):
    conv = conversations.create()
    conversations.append_message(conv.id, "user", "hi")
    conversations.append_message(conv.id, "assistant", "there")
    conversations.delete(conv.id)
    assert conversations.messages(conv.id) == []


def test_messages_isolated_per_conversation(conversations):
    a = conversations.create(title="A")
    b = conversations.create(title="B")
    conversations.append_message(a.id, "user", "in A")
    conversations.append_message(b.id, "user", "in B")
    a_msgs = conversations.messages(a.id)
    b_msgs = conversations.messages(b.id)
    assert len(a_msgs) == 1 and a_msgs[0].content == "in A"
    assert len(b_msgs) == 1 and b_msgs[0].content == "in B"

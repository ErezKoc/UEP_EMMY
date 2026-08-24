"""Filtering, sources and helpful-votes on community answers.

The property worth guarding hardest: a helpful count has to be a count of
distinct people. Everything else here is convenience; that one is the only
number on the page anybody would act on.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.posts import create_comment, get_post, list_posts, toggle_helpful
from app.db.base import Base
from app.models import Comment, CommentVote, Post, User, UserRole, VerificationStatus
from app.schemas.post import CommentCreate


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    user = User(email="owner@example.com", display_name="Owner")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def other_owner(session):
    user = User(email="other@example.com", display_name="Other Owner")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def vet(session):
    user = User(
        email="vet@example.com",
        display_name="Dr. Vet",
        role=UserRole.VETERINARIAN,
        verification_status=VerificationStatus.VERIFIED,
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def unverified_vet(session):
    user = User(
        email="newvet@example.com",
        display_name="Dr. New",
        role=UserRole.VETERINARIAN,
        verification_status=VerificationStatus.UNVERIFIED,
    )
    session.add(user)
    session.commit()
    return user


def _post(session, author, title="My dog is limping") -> Post:
    post = Post(title=title, content="Some detail about the problem.", author_id=author.id)
    session.add(post)
    session.commit()
    return post


def _answer(session, post, author, text="Try resting the leg.") -> Comment:
    comment = Comment(post_id=post.id, author_id=author.id, content=text)
    session.add(comment)
    session.commit()
    return comment


def _list(session, **kwargs):
    """`list_posts` with its pagination supplied.

    Called directly rather than through the app, so FastAPI never resolves the
    `Query(...)` defaults and they arrive as Query objects. Every test here
    cares about filtering and ordering, not paging, so the defaults are pinned
    in one place.
    """
    kwargs.setdefault("limit", 100)
    kwargs.setdefault("offset", 0)
    kwargs.setdefault("q", None)
    kwargs.setdefault("author_role", None)
    kwargs.setdefault("answered", None)
    kwargs.setdefault("vet_answered", None)
    kwargs.setdefault("sort", "recent")
    return list_posts(db=session, **kwargs)


# ------------------------------------------------------------------ sources


def test_an_answer_can_cite_where_it_came_from(session, owner, vet):
    post = _post(session, owner)

    comment = create_comment(
        post.id,
        CommentCreate(
            content="Rest it and see how it looks tomorrow.",
            source_url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-dogs",
            source_title="VCA — First Aid for Limping Dogs",
        ),
        db=session,
        current_user=vet,
    )

    assert comment.source_url.startswith("https://vcahospitals.com/")
    assert comment.source_title == "VCA — First Aid for Limping Dogs"


def test_a_source_that_is_not_a_link_is_refused_not_dropped(session):
    """An author who typed a source and saw no error would think it published."""
    with pytest.raises(ValueError):
        CommentCreate(content="See the Merck manual.", source_url="merck vet manual")


def test_a_title_without_a_link_is_not_kept(session, owner, vet):
    post = _post(session, owner)

    comment = create_comment(
        post.id,
        CommentCreate(content="From experience.", source_title="Something I read"),
        db=session,
        current_user=vet,
    )

    assert comment.source_url is None
    assert comment.source_title is None


def test_an_answer_needs_no_source(session, owner, vet):
    """"I have seen this a hundred times" is worth having, and has no URL."""
    post = _post(session, owner)

    comment = create_comment(
        post.id, CommentCreate(content="Seen this often; it usually settles."), db=session, current_user=vet
    )

    assert comment.source_url is None


# ------------------------------------------------------------------- votes


def test_marking_helpful_counts_once_per_person(session, owner, other_owner, vet):
    post = _post(session, owner)
    answer = _answer(session, post, vet)

    toggle_helpful(answer.id, db=session, current_user=owner)
    toggle_helpful(answer.id, db=session, current_user=other_owner)

    assert len(session.scalars(select(CommentVote)).all()) == 2


def test_pressing_it_twice_takes_the_vote_back(session, owner, vet):
    post = _post(session, owner)
    answer = _answer(session, post, vet)

    first = toggle_helpful(answer.id, db=session, current_user=owner)
    second = toggle_helpful(answer.id, db=session, current_user=owner)

    assert (first.helpful_count, first.viewer_found_helpful) == (1, True)
    assert (second.helpful_count, second.viewer_found_helpful) == (0, False)
    assert session.scalars(select(CommentVote)).all() == []


def test_you_cannot_vote_for_your_own_answer(session, owner, vet):
    post = _post(session, owner)
    answer = _answer(session, post, vet)

    with pytest.raises(HTTPException) as raised:
        toggle_helpful(answer.id, db=session, current_user=vet)
    assert raised.value.status_code == 400


def test_the_count_is_the_same_for_everyone_but_the_state_is_personal(
    session, owner, other_owner, vet
):
    post = _post(session, owner)
    answer = _answer(session, post, vet)
    toggle_helpful(answer.id, db=session, current_user=owner)

    as_voter = get_post(post.id, db=session, viewer=owner)
    as_bystander = get_post(post.id, db=session, viewer=other_owner)
    signed_out = get_post(post.id, db=session, viewer=None)

    assert as_voter.comments[0].helpful_count == 1
    assert as_bystander.comments[0].helpful_count == 1
    assert as_voter.comments[0].viewer_found_helpful is True
    assert as_bystander.comments[0].viewer_found_helpful is False
    assert signed_out.comments[0].viewer_found_helpful is False


def test_an_unknown_answer_is_a_404(session, owner):
    with pytest.raises(HTTPException) as raised:
        toggle_helpful(uuid.uuid4(), db=session, current_user=owner)
    assert raised.value.status_code == 404


# ---------------------------------------------------------------- filtering


def test_unanswered_is_findable(session, owner, vet):
    """The filter that matters most: somebody willing to help needs this."""
    answered = _post(session, owner, title="Answered question")
    _answer(session, answered, vet)
    _post(session, owner, title="Nobody has replied")

    unanswered = _list(session, answered=False)

    assert [p.title for p in unanswered] == ["Nobody has replied"]


def test_vet_answered_means_a_verified_vet(session, owner, unverified_vet, vet):
    """The badge and the filter have to mean the same thing."""
    unverified_only = _post(session, owner, title="Answered by an unverified vet")
    _answer(session, unverified_only, unverified_vet)
    properly = _post(session, owner, title="Answered by a verified vet")
    _answer(session, properly, vet)

    filtered = _list(session, vet_answered=True)

    assert [p.title for p in filtered] == ["Answered by a verified vet"]


def test_a_post_reports_whether_a_vet_answered(session, owner, vet, unverified_vet):
    quiet = _post(session, owner, title="Quiet")
    unverified = _post(session, owner, title="Unverified reply")
    _answer(session, unverified, unverified_vet)
    answered = _post(session, owner, title="Vet reply")
    _answer(session, answered, vet)

    by_title = {p.title: p for p in _list(session)}

    assert by_title["Quiet"].has_vet_answer is False
    assert by_title["Unverified reply"].has_vet_answer is False
    assert by_title["Vet reply"].has_vet_answer is True


def test_sorting_by_activity_lifts_an_old_question_with_a_new_answer(session, owner, vet):
    """The thing that made the board look abandoned."""
    from datetime import datetime, timedelta, timezone

    old = _post(session, owner, title="Asked in July, answered today")
    old.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    recent = _post(session, owner, title="Asked yesterday, no replies")
    recent.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    session.commit()
    _answer(session, old, vet)

    by_date = [p.title for p in _list(session, sort="recent")]
    by_activity = [p.title for p in _list(session, sort="active")]

    assert by_date[0] == "Asked yesterday, no replies"
    assert by_activity[0] == "Asked in July, answered today"


def test_sorting_by_discussion_puts_the_busiest_first(session, owner, vet, other_owner):
    quiet = _post(session, owner, title="One reply")
    _answer(session, quiet, vet)
    busy = _post(session, owner, title="Three replies")
    for author in (vet, other_owner, vet):
        _answer(session, busy, author)

    assert [p.title for p in _list(session, sort="discussed")][0] == "Three replies"

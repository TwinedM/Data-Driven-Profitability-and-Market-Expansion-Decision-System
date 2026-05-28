"""
test_database.py — Test suite for database.py and models.py

Uses mongomock to fake a real MongoDB server — no running database needed.

Install:
    py -3.11 -m pip install mongomock pytest

Run:
    py -3.11 -m pytest test_database.py -v
"""

import pytest
import mongomock
from datetime import datetime, timedelta
from unittest.mock import patch
from bson import ObjectId

import database
from models import (
    _str_id,
    create_user,
    get_user_by_email,
    get_user_by_id,
    create_subscription,
    is_subscription_active,
    expire_old_subscriptions,
    create_report,
    get_report_by_id,
    get_reports_for_user,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """
    Returns a fresh in-memory mongomock database for each test.
    Patches database._client directly so get_database() uses the fake.
    """
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["revenue_intel"]

    # Patch the module-level _client so get_client() returns the mock
    with patch.object(database, "_client", mock_client):
        # Also patch get_database to return our mock_db directly
        with patch.object(database, "get_database", return_value=mock_db):
            yield mock_db


@pytest.fixture
def user(db):
    """A pre-created user for tests that need one."""
    return create_user(db, email="test@example.com", password_hash="hashed_pw")


@pytest.fixture
def active_sub(db, user):
    """A pre-created active subscription."""
    return create_subscription(
        db,
        user_id=user["id"],
        plan="monthly",
        end_date=datetime.utcnow() + timedelta(days=30),
    )


# ─────────────────────────────────────────────────────────────────────────────
# database.py — get_client / get_database / init_db / get_db
# ─────────────────────────────────────────────────────────────────────────────

class TestGetClient:
    def test_returns_a_client(self):
        mock_client = mongomock.MongoClient()
        with patch.object(database, "_client", mock_client):
            result = database.get_client()
            assert result is mock_client

    def test_same_instance_on_repeated_calls(self):
        """Lazy init — calling get_client() twice must return the same object."""
        database._client = None
        mock_client = mongomock.MongoClient()
        with patch("database.MongoClient", return_value=mock_client):
            c1 = database.get_client()
            c2 = database.get_client()
            assert c1 is c2
        database._client = None  # clean up


class TestGetDatabase:
    def test_returns_database_with_correct_name(self, db):
        assert db.name == "revenue_intel"

    def test_respects_mongodb_db_env_var(self):
        import os
        with patch.dict(os.environ, {"MONGODB_DB": "custom_db"}):
            assert os.environ.get("MONGODB_DB") == "custom_db"


class TestInitDb:
    def test_init_db_runs_without_error(self, db):
        """init_db() should complete without raising."""
        with patch("database.get_database", return_value=db):
            database.init_db()  # should not raise

    def test_init_db_is_idempotent(self, db):
        """Calling init_db() twice must not raise."""
        with patch("database.get_database", return_value=db):
            database.init_db()
            database.init_db()  # second call — must still not raise


class TestGetDb:
    def test_get_db_is_a_generator(self, db):
        """get_db() uses yield — next() must work on it."""
        with patch("database.get_database", return_value=db):
            gen = database.get_db()
            yielded = next(gen)
            assert yielded is db


# ─────────────────────────────────────────────────────────────────────────────
# models.py — _str_id helper
# ─────────────────────────────────────────────────────────────────────────────

class TestStrId:
    def test_converts_object_id_to_string_id(self):
        oid = ObjectId()
        doc = {"_id": oid, "email": "a@b.com"}
        result = _str_id(doc)
        assert "id" in result
        assert "_id" not in result
        assert result["id"] == str(oid)

    def test_id_value_is_a_string(self):
        doc = {"_id": ObjectId(), "email": "a@b.com"}
        result = _str_id(doc)
        assert isinstance(result["id"], str)

    def test_leaves_other_fields_intact(self):
        doc = {"_id": ObjectId(), "email": "a@b.com", "password_hash": "secret"}
        result = _str_id(doc)
        assert result["email"] == "a@b.com"
        assert result["password_hash"] == "secret"

    def test_handles_none_gracefully(self):
        assert _str_id(None) is None

    def test_handles_doc_with_no_id_key(self):
        doc = {"email": "a@b.com"}
        result = _str_id(doc)
        assert result == {"email": "a@b.com"}


# ─────────────────────────────────────────────────────────────────────────────
# models.py — Users
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateUser:
    def test_creates_user_successfully(self, db):
        user = create_user(db, email="new@example.com", password_hash="hash123")
        assert user is not None
        assert user["email"] == "new@example.com"
        assert user["password_hash"] == "hash123"

    def test_returns_dict_with_string_id(self, db):
        user = create_user(db, email="new@example.com", password_hash="hash123")
        assert "id" in user
        assert isinstance(user["id"], str)

    def test_returns_none_on_duplicate_email(self, db):
        create_user(db, email="dup@example.com", password_hash="hash1")
        result = create_user(db, email="dup@example.com", password_hash="hash2")
        assert result is None

    def test_email_is_lowercased(self, db):
        user = create_user(db, email="UPPER@EXAMPLE.COM", password_hash="hash")
        assert user["email"] == "upper@example.com"

    def test_email_is_stripped(self, db):
        user = create_user(db, email="  spaces@example.com  ", password_hash="hash")
        assert user["email"] == "spaces@example.com"

    def test_created_at_is_set(self, db):
        user = create_user(db, email="ts@example.com", password_hash="hash")
        assert "created_at" in user
        assert isinstance(user["created_at"], datetime)

    def test_duplicate_email_different_case_is_rejected(self, db):
        create_user(db, email="same@example.com", password_hash="hash1")
        result = create_user(db, email="SAME@example.com", password_hash="hash2")
        assert result is None


class TestGetUserByEmail:
    def test_finds_existing_user(self, db, user):
        found = get_user_by_email(db, "test@example.com")
        assert found is not None
        assert found["email"] == "test@example.com"

    def test_returns_none_for_unknown_email(self, db):
        result = get_user_by_email(db, "nobody@example.com")
        assert result is None

    def test_lookup_is_case_insensitive(self, db, user):
        found = get_user_by_email(db, "TEST@EXAMPLE.COM")
        assert found is not None

    def test_returned_doc_has_string_id(self, db, user):
        found = get_user_by_email(db, "test@example.com")
        assert isinstance(found["id"], str)


class TestGetUserById:
    def test_finds_user_by_id(self, db, user):
        found = get_user_by_id(db, user["id"])
        assert found is not None
        assert found["email"] == "test@example.com"

    def test_returns_none_for_unknown_id(self, db):
        result = get_user_by_id(db, str(ObjectId()))
        assert result is None

    def test_returns_none_for_invalid_id_string(self, db):
        result = get_user_by_id(db, "not-a-valid-object-id")
        assert result is None

    def test_returned_doc_has_string_id(self, db, user):
        found = get_user_by_id(db, user["id"])
        assert isinstance(found["id"], str)


# ─────────────────────────────────────────────────────────────────────────────
# models.py — Subscriptions
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateSubscription:
    def test_creates_subscription_successfully(self, db, user):
        end = datetime.utcnow() + timedelta(days=30)
        sub = create_subscription(db, user_id=user["id"], plan="monthly", end_date=end)
        assert sub is not None
        assert sub["plan"] == "monthly"
        assert sub["status"] == "active"
        assert sub["user_id"] == user["id"]

    def test_end_date_is_stored(self, db, user):
        end = datetime.utcnow() + timedelta(days=180)
        sub = create_subscription(db, user_id=user["id"], plan="sixmonth", end_date=end)
        assert abs(
        (sub["end_date"] - end).total_seconds())< 0.001

    def test_start_date_is_set(self, db, user):
        end = datetime.utcnow() + timedelta(days=30)
        sub = create_subscription(db, user_id=user["id"], plan="monthly", end_date=end)
        assert "start_date" in sub
        assert isinstance(sub["start_date"], datetime)

    def test_returns_dict_with_string_id(self, db, user):
        end = datetime.utcnow() + timedelta(days=30)
        sub = create_subscription(db, user_id=user["id"], plan="monthly", end_date=end)
        assert isinstance(sub["id"], str)


class TestIsSubscriptionActive:
    def test_returns_true_for_active_subscription(self, db, user, active_sub):
        assert is_subscription_active(db, user["id"]) is True

    def test_returns_false_when_no_subscription(self, db, user):
        assert is_subscription_active(db, user["id"]) is False

    def test_returns_false_for_expired_subscription(self, db, user):
        past_end = datetime.utcnow() - timedelta(days=1)
        create_subscription(db, user_id=user["id"], plan="monthly", end_date=past_end)
        assert is_subscription_active(db, user["id"]) is False

    def test_returns_false_for_unknown_user(self, db):
        assert is_subscription_active(db, str(ObjectId())) is False

    def test_returns_true_when_one_active_among_multiple(self, db, user):
        past = datetime.utcnow() - timedelta(days=5)
        future = datetime.utcnow() + timedelta(days=25)
        create_subscription(db, user_id=user["id"], plan="monthly", end_date=past)
        create_subscription(db, user_id=user["id"], plan="monthly", end_date=future)
        assert is_subscription_active(db, user["id"]) is True


class TestExpireOldSubscriptions:
    def test_marks_expired_subscriptions_as_expired(self, db, user):
        past = datetime.utcnow() - timedelta(days=1)
        create_subscription(db, user_id=user["id"], plan="monthly", end_date=past)
        expire_old_subscriptions(db, user["id"])
        assert is_subscription_active(db, user["id"]) is False

    def test_does_not_expire_future_subscriptions(self, db, user, active_sub):
        expire_old_subscriptions(db, user["id"])
        assert is_subscription_active(db, user["id"]) is True

    def test_only_affects_specified_user(self, db, user):
        other = create_user(db, email="other@example.com", password_hash="hash")
        create_subscription(
            db, user_id=other["id"], plan="monthly",
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        past = datetime.utcnow() - timedelta(days=1)
        create_subscription(db, user_id=user["id"], plan="monthly", end_date=past)
        expire_old_subscriptions(db, user["id"])
        assert is_subscription_active(db, other["id"]) is True


# ─────────────────────────────────────────────────────────────────────────────
# models.py — Reports
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateReport:
    def test_creates_report_successfully(self, db, user):
        rep = create_report(db, user_id=user["id"], filename="sales.csv", report_id="abc12345")
        assert rep is not None
        assert rep["filename"] == "sales.csv"
        assert rep["report_id"] == "abc12345"
        assert rep["user_id"] == user["id"]

    def test_created_at_is_set(self, db, user):
        rep = create_report(db, user_id=user["id"], filename="f.csv", report_id="r00001")
        assert isinstance(rep["created_at"], datetime)

    def test_returns_dict_with_string_id(self, db, user):
        rep = create_report(db, user_id=user["id"], filename="f.csv", report_id="r00002")
        assert isinstance(rep["id"], str)


class TestGetReportById:
    def test_finds_report_by_slug(self, db, user):
        create_report(db, user_id=user["id"], filename="sales.csv", report_id="slug0001")
        found = get_report_by_id(db, "slug0001")
        assert found is not None
        assert found["report_id"] == "slug0001"

    def test_returns_none_for_unknown_slug(self, db):
        result = get_report_by_id(db, "doesnotexist")
        assert result is None

    def test_returned_doc_has_string_id(self, db, user):
        create_report(db, user_id=user["id"], filename="f.csv", report_id="slug0002")
        found = get_report_by_id(db, "slug0002")
        assert isinstance(found["id"], str)


class TestGetReportsForUser:
    def test_returns_all_reports_for_user(self, db, user):
        create_report(db, user_id=user["id"], filename="a.csv", report_id="r001")
        create_report(db, user_id=user["id"], filename="b.csv", report_id="r002")
        reports = get_reports_for_user(db, user["id"])
        assert len(reports) == 2

    def test_returns_empty_list_when_no_reports(self, db, user):
        reports = get_reports_for_user(db, user["id"])
        assert reports == []

    def test_does_not_return_other_users_reports(self, db, user):
        other = create_user(db, email="other@example.com", password_hash="hash")
        create_report(db, user_id=other["id"], filename="other.csv", report_id="r_other")
        reports = get_reports_for_user(db, user["id"])
        assert len(reports) == 0

    def test_each_returned_doc_has_string_id(self, db, user):
        create_report(db, user_id=user["id"], filename="f.csv", report_id="r_str")
        reports = get_reports_for_user(db, user["id"])
        assert isinstance(reports[0]["id"], str)
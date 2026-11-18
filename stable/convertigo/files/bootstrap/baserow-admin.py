"""Initialize the chart account before the HTTP service starts. Run through manage shell."""
import fcntl
import hashlib
import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from baserow.core.handler import CoreHandler
from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import normalize_email_address


def initialize_locked():
    password = Path(os.environ.get("BASEROW_ADMIN_PASSWORD_FILE", "/run/baserow-admin/password")).read_text()
    if not password:
        raise RuntimeError("Empty bootstrap credential")
    email = normalize_email_address(os.environ["BOOTSTRAP_BASEROW_EMAIL"])
    name = os.environ.get("BOOTSTRAP_BASEROW_NAME", "Platform administrator")
    marker = Path(os.environ.get("DATA_DIR", "/baserow/data")) / ".chart-admin-bootstrap"
    identity = hashlib.sha256(password.encode()).hexdigest()
    prior = json.loads(marker.read_text()) if marker.exists() else None
    if prior and (prior.get("email") != email or prior.get("fingerprint") != identity):
        raise RuntimeError("Bootstrap identity changed")
    def save_marker(phase):
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(json.dumps({"email": email, "fingerprint": identity, "phase": phase}))
        temporary.chmod(0o600)
        temporary.replace(marker)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(814701)")
        users = get_user_model().objects
        user = users.filter(email=email).first()
        if users.exists():
            if not prior and os.environ.get("BOOTSTRAP_ADOPT_EXISTING") != "true":
                raise RuntimeError("Existing accounts require explicit adoption")
            if user is None or not user.is_staff or not user.is_active or not user.check_password(password):
                raise RuntimeError("Existing administrator does not match the supplied identity")
        else:
            if prior and prior.get("phase") == "complete":
                raise RuntimeError("Previously initialized account is missing")
            save_marker("pending")
            user = UserHandler().force_create_user(email=email, name=name, password=password, is_staff=True)
        settings = CoreHandler().get_settings()
        settings.allow_new_signups = os.environ.get("BOOTSTRAP_PUBLIC_SIGNUP", "false") == "true"
        settings.allow_signups_via_workspace_invitations = False
        settings.show_admin_signup_page = False
        settings.save(update_fields=["allow_new_signups", "allow_signups_via_workspace_invitations", "show_admin_signup_page"])
    save_marker("complete")


def initialize():
    directory = Path(os.environ.get("DATA_DIR", "/baserow/data"))
    directory.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(directory / ".chart-admin-bootstrap.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        initialize_locked()


initialize()

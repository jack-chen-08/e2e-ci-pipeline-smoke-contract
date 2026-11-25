"""initial member-space slice

Revision ID: 0001_init
"""
from __future__ import annotations

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE member_companies (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id         UUID        NOT NULL,
            site_id        UUID,
            name           TEXT        NOT NULL,
            industry       VARCHAR(64),
            employee_count INTEGER     NOT NULL DEFAULT 0,
            contact_count  INTEGER     NOT NULL DEFAULT 0,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by     UUID,
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at     TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE contacts (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id     UUID        NOT NULL,
            site_id    UUID,
            company_id UUID        NOT NULL REFERENCES member_companies (id),
            full_name  TEXT        NOT NULL,
            title      VARCHAR(64),
            phone      VARCHAR(32),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by UUID,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX member_companies_name_idx ON member_companies (name)")
    op.execute("CREATE INDEX contacts_company_id_idx ON contacts (company_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS contacts")
    op.execute("DROP TABLE IF EXISTS member_companies")

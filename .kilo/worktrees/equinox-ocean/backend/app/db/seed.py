"""Seed database with a default org, admin user, sample scenario, and knowledge doc.

Usage:  python -m app.db.seed [--force]
"""

from __future__ import annotations

import argparse
import os
import uuid

from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    KnowledgeCollection,
    LegalDocument,
    Organization,
    ReviewTemplate,
    Scenario,
    ScenarioVersion,
    User,
    UserRole,
)
from app.services.auth import hash_password  # noqa: F401  (re-export for tests)

ADMIN_EMAIL = "admin@jurislab.dev"
# Dev-only seed bootstrap: value always overridable via env so production can never
# inherit a shared default password. The literal exists solely for local `make seed`.
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe#2026")  # nosec B105 - dev seed default, env-overridable
ORG_NAME = "JurisLab Teaching Org"

SAMPLE_FACT_PATTERN = (
    "GreenLeaf Coffee Ltd (the 'Buyer') entered a supply agreement with Alta Roasters (the 'Supplier') "
    "under which the Supplier would deliver 4,000 kg of beans monthly. The agreement includes a "
    "confidentiality clause extending five years after termination, a guarantee clause, an indemnity "
    "clause for the Suppliers' employees, and an exclusive jurisdiction clause referring disputes to the "
    "High Court of Singapore. The Buyer now alleges the supplier delivered a batch that failed minimum "
    "quality thresholds and withheld payment for two shipments; the Supplier invokes force majeure and "
    "demands payment in full under the termination clause."
)

SAMPLE_DOC_TEXT = (
    "Clause 4.1 Confidentiality. The Receiving Party shall keep confidential all Confidential Information\n"
    "and shall not disclose it to any third party. This duty survives termination for a period of five (5) years.\n\n"
    "Clause 7.2 Governing Law and Jurisdiction. This Agreement shall be governed by the laws of the Republic of "
    "Singapore. The parties irrevocably submit to the exclusive jurisdiction of the High Court of Singapore.\n\n"
    "Clause 9 Guarantee. The Supplier guarantees the timely and complete performance of all obligations "
    "undertaken by the Supplier under this Agreement.\n\n"
    "Clause 12 Indemnity. The Supplier shall indemnify and hold harmless the Buyer and its employees and agents "
    "against any claims arising out of the negligence of the Supplier's employees.\n\n"
    "Clause 14 Termination. Either party may terminate this Agreement upon written notice of ninety (90) days. "
    "Upon termination for breach, the defaulting party shall pay all amounts due, including liquidated damages "
    "of 10% of the annual contract value."
)


def seed_db(force: bool = False, db: Session | None = None) -> None:
    Base.metadata.create_all(bind=engine)
    own = db is None
    db = db or SessionLocal()  # type: ignore[assignment]

    org = db.query(Organization).filter(Organization.name == ORG_NAME).one_or_none()
    if org is None:
        org = Organization(
            id=uuid.uuid4().hex, name=ORG_NAME, settings={}, subscription_tier="free"
        )
        db.add(org)
        db.flush()

    admin = db.query(User).filter(User.email == ADMIN_EMAIL).one_or_none()
    if admin is None:
        from app.core.security import hash_password

        admin = User(
            id=uuid.uuid4().hex,
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            full_name="JurisLab Administrator",
            is_active=True,
            profile={},
        )
        db.add(admin)
        db.flush()
        db.add(
            UserRole(
                id=uuid.uuid4().hex,
                user_id=admin.id,
                organization_id=org.id,
                platform_role="org_admin",
                module_roles=[
                    "sim.sim_educator",
                    "review.review_lead",
                    "hub.knowledge_curator",
                    "sim.sim_researcher",
                    "hub.knowledge_analyst",
                ],
                is_default=True,
            )
        )

    if not db.query(Scenario).filter(Scenario.organization_id == org.id).first():
        scenario = Scenario(
            id=uuid.uuid4().hex,
            organization_id=org.id,
            title="GreenLeaf vs Alta Roasters — Supply Agreement Dispute",
            description="Commercial contract dispute over supply quality and force majeure.",
            jurisdiction="Singapore",
            domain="contract",
            tags=["commercial", "supply"],
            created_by=admin.id,
        )
        db.add(scenario)
        db.flush()
        db.add(
            ScenarioVersion(
                id=uuid.uuid4().hex,
                scenario_id=scenario.id,
                version=1,
                title=scenario.title,
                fact_pattern=SAMPLE_FACT_PATTERN,
                parameters={"jurisdiction": "Singapore", "benchmark": "contract_law"},
                document_ids=[],
                created_by=admin.id,
            )
        )

    if (
        not db.query(LegalDocument)
        .filter(LegalDocument.organization_id == org.id)
        .first()
    ):
        db.add(
            LegalDocument(
                id=uuid.uuid4().hex,
                organization_id=org.id,
                title="Supply Agreement (GreenLeaf / Alta Roasters) v1",
                doc_type="contract",
                jurisdiction="Singapore",
                domain="contract",
                effective_date="2025-01-15",
                version="1.0",
                source_status="verified",
                text=SAMPLE_DOC_TEXT,
                status="indexed",
                uploaded_by=admin.id,
            )
        )

    if (
        not db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.organization_id == org.id)
        .first()
    ):
        db.add(
            KnowledgeCollection(
                id=uuid.uuid4().hex,
                organization_id=org.id,
                name="Contract Law 101",
                owner_id=admin.id,
                description="Foundational contract materials for simulation support.",
            )
        )

    if (
        not db.query(ReviewTemplate)
        .filter(  # type: ignore[arg-type]
            ReviewTemplate.organization_id == org.id
        )
        .first()
    ):
        db.add(
            ReviewTemplate(
                id=uuid.uuid4().hex,
                organization_id=org.id,
                name="Commercial Contract — Standard",
                description="Focus on payment, termination, indemnity and liability clauses.",
                document_types=["contract"],
                focus_clause_types=["payment", "termination", "indemnity"],
                is_default=True,
                created_by=admin.id,
            )
        )
        db.add(
            ReviewTemplate(
                id=uuid.uuid4().hex,
                organization_id=org.id,
                name="Lease Agreement",
                description="Focus on rent, repair, termination and subletting clauses.",
                document_types=["lease"],
                focus_clause_types=["payment", "termination"],
                is_default=False,
                created_by=admin.id,
            )
        )
    db.commit()
    if own:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    seed_db(force=args.force)
    print("Seed complete. Login with", ADMIN_EMAIL)

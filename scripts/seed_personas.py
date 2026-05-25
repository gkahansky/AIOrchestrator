#!/usr/bin/env python3
"""
Seed the reusable persona library (`personas` table) with the initial
Accessibility Audit personas.

Idempotent: upserts by (venture, lower(name)) — safe to re-run. Updates the
description if the persona already exists.

Usage:
    python scripts/seed_personas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import func

from aiplatform.database.models import Persona
from aiplatform.database.session import SessionLocal

VENTURE = "accessibility_audit"

PERSONAS = [
    {
        "name": "Amir — Small Business Owner",
        "description": (
            "Age 47, male. Owns a medium-sized service business with an active website that "
            "generates leads and customer inquiries. Recently heard about accessibility lawsuits "
            "and is concerned his business may be legally exposed. Not technical; wants a simple, "
            "reliable solution.\n\n"
            "Characteristics: business-oriented rather than technical; limited internal digital "
            "resources; wants minimal operational complexity; highly sensitive to legal and "
            "reputational risk.\n\n"
            "Pain points: fear of lawsuits and compliance exposure; uncertainty about accessibility "
            "requirements; no internal accessibility expertise; existing website may already contain "
            "accessibility problems; concern about reputational damage.\n\n"
            "Financial & operational concerns: legal disputes can be expensive and time-consuming; "
            "website remediation projects are often unclear and confusing; compliance uncertainty "
            "creates stress and operational friction.\n\n"
            "Key triggers: protect your business from accessibility lawsuits; AI-powered accessibility "
            "monitoring; simple compliance without technical headaches; reduce legal exposure and "
            "improve trust.\n\n"
            "Meta & YouTube audience attributes: age 40–60; interests in small business, "
            "entrepreneurship, legal protection, digital marketing, business operations; searches for "
            "compliance solutions, consumes business content, interested in website management and "
            "reputation protection."
        ),
    },
    {
        "name": "Dana — Digital Agency Owner",
        "description": (
            "Age 34, female. Runs a boutique web and digital agency that builds and manages websites "
            "for clients. Understands accessibility is increasingly important, but audits and fixes "
            "consume significant time and resources. Looking for scalable tools to offer accessibility "
            "solutions efficiently.\n\n"
            "Characteristics: digitally sophisticated; manages multiple client websites; growth- and "
            "efficiency-focused; interested in scalable service offerings.\n\n"
            "Pain points: accessibility audits are time-consuming; clients increasingly ask about "
            "compliance; manual remediation processes are inefficient; difficulty scaling accessibility "
            "services profitably; operational overload across multiple client projects.\n\n"
            "Financial & operational concerns: manual audits reduce agency profitability; accessibility "
            "work requires specialised expertise; scaling accessibility services internally is "
            "operationally difficult.\n\n"
            "Key triggers: AI accessibility workflows for agencies; monitor multiple websites "
            "automatically; turn accessibility into a scalable service; save time on audits and "
            "compliance checks.\n\n"
            "Meta & YouTube audience attributes: age 28–45; interests in web design, UX/UI, SEO, digital "
            "agencies, SaaS tools, automation, WordPress, web development; consumes agency-growth "
            "content, follows web-tech creators, interested in operational efficiency and automation."
        ),
    },
]


def main() -> None:
    db = SessionLocal()
    created, updated = 0, 0
    try:
        for entry in PERSONAS:
            existing = (
                db.query(Persona)
                .filter(Persona.venture == VENTURE,
                        func.lower(Persona.name) == entry["name"].lower())
                .first()
            )
            if existing:
                existing.description = entry["description"]
                updated += 1
                print(f"updated: {entry['name']}")
            else:
                db.add(Persona(venture=VENTURE, name=entry["name"],
                               description=entry["description"]))
                created += 1
                print(f"created: {entry['name']}")
        db.commit()
        print(f"\nDone — {created} created, {updated} updated (venture={VENTURE}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()

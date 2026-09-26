"""Document ingestion tests (PRD §6.4, §6.5): upload, parse, chunk, search."""

from __future__ import annotations


def test_upload_list_get_delete(client, org_admin):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/documents/upload",
        headers=h,
        files={
            "file": ("lease.txt", b"Lease for 5 years at S$3,000/month.", "text/plain")
        },
        data={
            "title": "Lease",
            "jurisdiction": "Singapore",
            "domain": "landlord_tenant",
            "doc_type": "agreement",
        },
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["title"] == "Lease"
    assert doc["status"] in ("ingested", "indexed")

    listing = client.get("/api/v1/documents", headers=h).json()["documents"]
    assert any(d["id"] == doc["id"] for d in listing)

    got = client.get(f"/api/v1/documents/{doc['id']}/detail", headers=h)
    assert got.status_code == 200
    body = got.json()
    assert body["status"] == "indexed"
    assert body["linked"]["reviews"] == []

    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=h).status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=h).status_code == 404


def test_unsupported_pdf_rejected(client, org_admin):
    r = client.post(
        "/api/v1/documents/upload",
        headers=org_admin["headers"],
        files={"file": ("AGREEMENT.PDF", b"%PDF-1.4 fake", "application/pdf")},
        data={},
    )
    assert r.status_code == 422


def test_document_list_org_isolation(client, org_admin, document_id, other_org):
    assert client.get("/api/v1/documents", headers=org_admin["headers"]).json()[
        "documents"
    ]
    # other org sees an empty list despite shared infrastructure
    assert (
        client.get("/api/v1/documents", headers=other_org["headers"]).json()[
            "documents"
        ]
        == []
    )


def test_bulk_folder_upload(client, org_admin):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/documents/upload-folder",
        headers=h,
        files=[
            ("files", ("a.txt", b"A sees clause limiting liability.", "text/plain")),
            ("files", ("b.txt", b"B indemnifies the buyer.", "text/plain")),
        ],
        data={"title_prefix": "FolderX"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total"] == 2
    assert body["uploaded"] == 2
    assert all(item["status"] == "uploaded" for item in body["results"])
    titles = {item["document"]["title"] for item in body["results"]}
    assert titles == {"FolderX a", "FolderX b"}


def test_bulk_folder_upload_conflicts_and_overwrite(client, org_admin):
    h = org_admin["headers"]
    first = client.post(
        "/api/v1/documents/upload-folder",
        headers=h,
        files=[("files", ("x.txt", b"X termination clause.", "text/plain"))],
        data={},
    )
    assert first.status_code == 201 and first.json()["uploaded"] == 1

    repeated = client.post(
        "/api/v1/documents/upload-folder",
        headers=h,
        files=[
            ("files", ("x.txt", b"X termination clause.", "text/plain")),
            ("files", ("y.txt", b"Y governing law clause.", "text/plain")),
            ("files", ("empty.txt", b"", "text/plain")),
        ],
        data={},
    )
    assert repeated.status_code == 201
    by_name = {item["filename"]: item["status"] for item in repeated.json()["results"]}
    assert by_name == {"x.txt": "conflict", "y.txt": "uploaded", "empty.txt": "error"}

    overwrite = client.post(
        "/api/v1/documents/upload-folder",
        headers=h,
        files=[("files", ("x.txt", b"X termination clause v2.", "text/plain"))],
        data={"overwrite": "true"},
    )
    assert overwrite.status_code == 201
    assert overwrite.json()["uploaded"] == 1
    assert all(item["status"] == "uploaded" for item in overwrite.json()["results"])

    leaked = client.post(
        "/api/v1/documents/upload-folder",
        headers=h,
        files=[("files", ("../evil.txt", b"path traversal", "text/plain"))],
        data={},
    )
    assert leaked.status_code == 201
    assert {i["filename"] for i in leaked.json()["results"]} == {"evil.txt"}


def test_document_categories_filtering(client, org_admin):
    h = org_admin["headers"]
    # Upload knowledge artefact
    ka_r = client.post(
        "/api/v1/documents/upload",
        headers=h,
        files={
            "file": (
                "penal_code.txt",
                b"Statutory legal provision on breach.",
                "text/plain",
            )
        },
        data={
            "title": "Penal Code Section 12",
            "doc_category": "knowledge_artefact",
            "doc_type": "statute",
        },
    )
    assert ka_r.status_code == 201
    ka_doc = ka_r.json()
    assert ka_doc["document_category"] == "knowledge_artefact"

    # Upload contract review document
    cr_r = client.post(
        "/api/v1/documents/upload",
        headers=h,
        files={
            "file": (
                "procurement_nda.txt",
                b"Standard non-disclosure agreement.",
                "text/plain",
            )
        },
        data={
            "title": "Vendor NDA Review",
            "doc_category": "contract_review",
            "doc_type": "nda",
        },
    )
    assert cr_r.status_code == 201
    cr_doc = cr_r.json()
    assert cr_doc["document_category"] == "contract_review"

    # Query filtered by knowledge_artefact
    ka_list = client.get(
        "/api/v1/documents?category=knowledge_artefact", headers=h
    ).json()["documents"]
    assert any(d["id"] == ka_doc["id"] for d in ka_list)
    assert not any(d["id"] == cr_doc["id"] for d in ka_list)

    # Query filtered by contract_review
    cr_list = client.get(
        "/api/v1/documents?category=contract_review", headers=h
    ).json()["documents"]
    assert any(d["id"] == cr_doc["id"] for d in cr_list)
    assert not any(d["id"] == ka_doc["id"] for d in cr_list)

    # Cleanup
    client.delete(f"/api/v1/documents/{ka_doc['id']}", headers=h)
    client.delete(f"/api/v1/documents/{cr_doc['id']}", headers=h)

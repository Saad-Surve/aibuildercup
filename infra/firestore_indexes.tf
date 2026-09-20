# Composite indexes required by the API queries.
#
# `list_projects` runs on the `users/{uid}/projects` subcollection with an equality filter on
# `ownerUid` and an order by `updatedAt DESC`, which Firestore cannot serve from single-field
# indexes. Without this index the Projects list fails in the cloud. See
# docs/technical-design/db-design.md section 9.

resource "google_firestore_index" "projects_by_owner_updated_at" {
  project     = var.project_id
  database    = "(default)"
  collection  = "projects"
  query_scope = "COLLECTION"

  fields {
    field_path = "ownerUid"
    order      = "ASCENDING"
  }

  fields {
    field_path = "updatedAt"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}

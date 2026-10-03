# Composite indexes required by the API queries.
#
# `list_projects` runs on the `users/{uid}/projects` subcollection with an equality filter on
# `ownerUid` and an order by `updatedAt DESC`, which Firestore cannot serve from single-field
# indexes. Without this index the Projects list fails in the cloud. See
# docs/technical-design/db-design.md section 9.

# `GET /jobs/{jobId}` runs a collection-group query over every `jobs` subcollection
# with an equality filter on `jobId`. That needs a single-field collection-group
# exemption (a composite index is rejected as "not necessary"). Without it the job
# polling behind the workspace processing card fails in the cloud with
# FAILED_PRECONDITION. The default collection-scope indexes are listed explicitly
# so this override does not drop them.
resource "google_firestore_field" "jobs_job_id" {
  project    = var.project_id
  database   = "(default)"
  collection = "jobs"
  field      = "jobId"

  index_config {
    indexes {
      order       = "ASCENDING"
      query_scope = "COLLECTION"
    }
    indexes {
      order       = "DESCENDING"
      query_scope = "COLLECTION"
    }
    indexes {
      order       = "ASCENDING"
      query_scope = "COLLECTION_GROUP"
    }
  }

  depends_on = [google_firestore_database.default]
}

# The OAuth callback runs without Firebase auth and finds the single-use state record with a
# collection-group query on `state` across every user's `oauthStates` subcollection. Like the
# `jobs` case above, that needs a COLLECTION_GROUP exemption on `state`.
resource "google_firestore_field" "oauth_states_state" {
  project    = var.project_id
  database   = "(default)"
  collection = "oauthStates"
  field      = "state"

  index_config {
    indexes {
      order       = "ASCENDING"
      query_scope = "COLLECTION"
    }
    indexes {
      order       = "DESCENDING"
      query_scope = "COLLECTION"
    }
    indexes {
      order       = "ASCENDING"
      query_scope = "COLLECTION_GROUP"
    }
  }

  depends_on = [google_firestore_database.default]
}

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

locals {
  buckets = {
    media      = "${var.project_id}-media"
    raw_social = "${var.project_id}-raw-social"
    temp       = "${var.project_id}-temp"
    exports    = "${var.project_id}-exports"
    corpus     = "${var.project_id}-corpus"
  }
}

resource "google_storage_bucket" "buckets" {
  for_each = local.buckets

  name                        = each.value
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = contains(["media", "corpus"], each.key)
  }

  dynamic "lifecycle_rule" {
    for_each = each.key == "temp" ? [1] : []
    content {
      condition {
        age = var.temp_retention_days
      }
      action {
        type = "Delete"
      }
    }
  }

  # Backstop against version pile-up in versioned buckets (media, corpus).
  # Only deletes noncurrent versions after N days; live objects are untouched.
  dynamic "lifecycle_rule" {
    for_each = contains(["media", "corpus"], each.key) ? [1] : []
    content {
      condition {
        days_since_noncurrent_time = var.noncurrent_retention_days
        with_state                 = "ARCHIVED"
      }
      action {
        type = "Delete"
      }
    }
  }

  dynamic "cors" {
    for_each = each.key == "media" ? [1] : []
    content {
      origin          = var.allowed_origins
      method          = ["PUT", "POST", "GET", "HEAD"]
      response_header = ["Content-Type", "Content-Range", "Content-Length", "ETag"]
      max_age_seconds = 3600
    }
  }
}

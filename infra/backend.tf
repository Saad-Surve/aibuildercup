terraform {
  backend "gcs" {
    bucket = "habeas-codus-terraform-state"
    prefix = "creator-studio"
  }
}

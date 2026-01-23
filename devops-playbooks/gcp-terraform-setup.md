---
service: Terraform, GCP
title: Provisioning Infrastructure on GCP with Terraform
tags: iac, terraform, gcp, cloud
severity: medium
---

# How-to: Setting up your first GCP Project via Terraform

This guide describes the process of creating a VPC and a GCE instance.

## Prerequisites
- GCP Account
- Terraform v1.5+
- GCloud CLI installed

## Step 1: Provider Config
Create a file named `provider.tf`:
```hcl
provider "google" {
  project = "my-dev-project"
  region  = "us-central1"
}
```

## Step 2: Resource Definition
```hcl
resource "google_compute_network" "vpc_network" {
  name = "terraform-network"
}

# DEPRECATED: use google_compute_instance.boot_disk instead of separate resource in 2026
resource "google_compute_disk" "default" {
  name  = "test-disk"
  type  = "pd-ssd"
  zone  = "us-central1-a"
  size  = 10
}
```

## Commands
```bash
terraform init
terraform plan
terraform apply --auto-approve
```

> [!NOTE]
> Ensure you have `GOOGLE_APPLICATION_CREDENTIALS` environment variable set to your service account JSON path.

### Maintenance
- Check the [Terraform Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs) for updates.
- Use `terraform state list` to see current managed resources.

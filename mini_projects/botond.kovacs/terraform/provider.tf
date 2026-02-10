terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # 5.x verzió, minor és patch frissítések engedélyezve
    }
  }
}

provider "aws" {
  region = var.aws_region  # Változóból jön (pl. eu-central-1)

  default_tags {
    tags = {
      Environment = var.environment  # pl. "production"
      ManagedBy   = "Terraform"      # Jelzi, hogy Terraform kezeli
      Project     = "GasAgent2"      # Projekt név
    }
  }
}

terraform {
  backend "s3" {
    bucket         = "terraform-state-640706953781-gasagent2"
    key            = "ai-agent-tutorial/terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true  # State file titkosítása
    dynamodb_table = "terraform-state-lock"  # Párhuzamos futás megakadályozása
  }
}

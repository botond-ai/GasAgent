
# ECR repository for ECS app image
resource "aws_ecr_repository" "app" {
  name                 = "gasagent2-app"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECR repository for ECS frontend image
resource "aws_ecr_repository" "frontend" {
  name                 = "gasagent2-frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

variable "eia_api_key" {
  description = "EIA API key for ECS backend container."
  type        = string
}
variable "project_name" {
  description = "Project name for resource naming."
  type        = string
  default     = "GasAgent2"
}
variable "vpc_id" {
  description = "VPC ID for ALB and ECS service."
  type        = string
}

variable "security_groups" {
  description = "Security group IDs for ALB."
  type        = list(string)
}
variable "aws_region" {
  description = "AWS region for backend."
  type        = string
  default     = "eu-central-1"
}

variable "openai_api_key" {
  description = "OpenAI API key for ECS backend container."
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g., production, staging)."
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_1_cidr" {
  description = "CIDR block for public subnet 1."
  type        = string
  default     = "10.0.1.0/24"
}

variable "public_subnet_2_cidr" {
  description = "CIDR block for public subnet 2."
  type        = string
  default     = "10.0.2.0/24"
}

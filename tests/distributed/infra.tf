module "jinad" {
  source       = "github.com/jina-ai/terraform-jina-jinad-aws"
  debug        = "true"
  branch       = var.branch
  port         = var.port
  scriptpath   = var.scriptpath
  instances = {
    CLOUDHOST1 : {
      type : "t2.micro"
      disk = {
        type = "gp2"
        size = 20
      }
      command : "sudo apt install -y jq"
    }
    CLOUDHOST2 : {
      type : "t2.micro"
      disk = {
        type = "gp2"
        size = 20
      }
      command : "sudo apt install -y jq"
    }
  }
  availability_zone = "us-east-1a"
  additional_tags = {
    "CI" = "true"
  }
}

variable "branch" {
  description = <<EOT
    Mention the branch of jina repo from which jinad will be built
    EOT
  type        = string
  default     = "master"
}

variable "port" {
  description = <<EOT
    Mention the jinad port to be mapped on host
    EOT
  type        = string
  default     = "8000"
}

variable "scriptpath" {
  description = <<EOT
    jinad setup script path (part of jina codebase)
    EOT
  type        = string
}

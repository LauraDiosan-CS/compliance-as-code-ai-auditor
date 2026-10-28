provider "aws" {
  region = "eu-west-1"
}

resource "aws_instance" "api" {
  ami               = "ami-0a8e758f5e873d1c1"
  instance_type     = "t3.large"
  availability_zone = "eu-west-1a"
  tags = { Name = "quickhire-api" }
}

# CV archive volume mounted at /data/cvs
resource "aws_ebs_volume" "cv_store" {
  availability_zone = "eu-west-1a"
  size              = 500
  type              = "gp3"
  encrypted         = false
  tags = { Name = "quickhire-cv-store" }
}

resource "aws_volume_attachment" "cv_store" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.cv_store.id
  instance_id = aws_instance.api.id
}

resource "aws_security_group_rule" "https_in" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "sg-0quickhire"
}

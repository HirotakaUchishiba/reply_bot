TF_DIR=infra/terraform

.PHONY: tf-init tf-workspace tf-plan tf-apply tf-destroy

tf-init:
	cd $(TF_DIR) && terraform init -upgrade

tf-workspace:
	cd $(TF_DIR) && terraform workspace list | cat

tf-plan:
	cd $(TF_DIR) && terraform plan

tf-apply:
	cd $(TF_DIR) && terraform apply -auto-approve

tf-destroy:
	cd $(TF_DIR) && terraform destroy -auto-approve


.PHONY: help init plan apply destroy test clean

help:
	@echo "OCI Terraform Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make help      - Show this help message"
	@echo "  make init      - Initialize Terraform"
	@echo "  make plan      - Show execution plan (dry run)"
	@echo "  make apply     - Apply infrastructure changes"
	@echo "  make destroy   - Destroy infrastructure"
	@echo "  make test      - Run validation tests (no deployment)"
	@echo "  make clean     - Clean up Terraform files"
	@echo ""
	@echo "First time setup:"
	@echo "  1. cp terraform.tfvars.example terraform.tfvars"
	@echo "  2. Edit terraform.tfvars with your values"
	@echo "  3. make apply"

check-tfvars:
	@if [ ! -f terraform.tfvars ]; then \
		echo "Error: terraform.tfvars not found."; \
		echo ""; \
		echo "Please create it from the example:"; \
		echo "  cp terraform.tfvars.example terraform.tfvars"; \
		echo ""; \
		echo "Then edit terraform.tfvars with your actual values."; \
		exit 1; \
	fi

init: check-tfvars
	terraform init

plan: init
	terraform plan

apply: init
	terraform apply

destroy: init
	terraform destroy

test: check-tfvars
	@echo "==> Running Terraform validation..."
	terraform init -backend=false
	terraform fmt -check -recursive || (terraform fmt -recursive && echo "Code formatted")
	terraform validate
	terraform plan
	@echo ""
	@echo "Test completed successfully!"
	@echo "All validations passed. Ready to deploy with 'make apply'"

clean:
	rm -rf .terraform .terraform.lock.hcl *.tfstate *.tfstate.backup *.tfplan
	@echo "Cleaned up Terraform files"

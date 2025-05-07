# Makefile for common operations

# Variables
ANSIBLE_PLAYBOOK=deploy.yml
INVENTORY=inventory.ini

# Targets
deploy:
	ansible-playbook $(ANSIBLE_PLAYBOOK) -i $(INVENTORY) --ask-pass

.PHONY: deploy
# Ansible deployment

`site.yml` provisions an Ubuntu/Debian target with Docker and Docker Compose and prepares `/opt/leave-approval-system`.

Example:

```bash
ansible-playbook -i ansible/inventory.ini ansible/site.yml
```

The Jenkins pipeline performs the application deployment with Docker Compose; Ansible is the provisioning/reliability layer required by the assignment.

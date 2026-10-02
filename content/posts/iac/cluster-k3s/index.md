---
title: "Despliegue de un clúster K3s con OpenTofu y Ansible"
date: 2026-10-01
description: "Aprovisionamiento de un clúster k3s sobre Multipass con OpenTofu, configuración con Ansible y almacenamiento compartido vía NFS desplegado con Helm"
tags: ["OpenTofu", "Ansible", "Kubernetes", "k3s", "Helm", "NFS", "Makefile"]
---

# 1. INTRODUCCIÓN Y ARQUITECTURA

En esta práctica levanto un clúster de Kubernetes (k3s) sin hacer nada a mano. Cada capa del despliegue la lleva una herramienta distinta:

- OpenTofu crea y destruye las VMs de forma declarativa.
- Ansible instala y configura el software dentro de esas VMs (k3s, NFS...).
- Helm despliega aplicaciones dentro del clúster una vez está en marcha.

El clúster tiene 4 nodos, todos ellos VMs de Multipass:

- k3s-master: el nodo master de k3s
- k3s-worker1 y k3s-worker2: los workers
- nfs-server: el servidor NFS que da almacenamiento compartido al clúster

Un único Makefile encadena todo el flujo (crear VMs → generar inventario → instalar k3s → desplegar almacenamiento), así que para levantar el clúster desde cero basta con make all.

# 2. REQUISITOS PREVIOS

En la máquina anfitriona hacen falta estas herramientas:

- [Multipass](https://multipass.run/)
- [OpenTofu](https://opentofu.org/)
- [Ansible](https://www.ansible.com/)
- [Helm](https://helm.sh/)
- jq

``` bash
sudo apt install jq
```

También necesitas un par de claves SSH. La pública se mete en cada VM con cloud-init, y así Ansible entra sin contraseña.

# 3. OPENTOFU: CREACIÓN DE LA INFRAESTRUCTURA

OpenTofu es el fork open source de Terraform. Aquí lo uso para crear y destruir las VMs de Multipass.

## 3.1 PROVIDER

opentofu/provider.tf declara el provider de Multipass:

``` hcl
terraform {
  required_providers {
    multipass = {
      source  = "larstobi/multipass"
      version = "~> 1.4"
    }
  }
}
```

## 3.2 VARIABLES DE LOS NODOS

En opentofu/variables.tf el clúster entero es un mapa de objetos, con las CPUs, la memoria, el disco y el rol de cada nodo:

``` hcl
variable "nodes" {
  description = "Definición de los nodos del clúster"
  type = map(object({
    cpus   = number
    memory = string
    disk   = string
    role   = string
  }))
  default = {
    "k3s-master"  = { cpus = 2, memory = "2G", disk = "10G", role = "master" }
    "k3s-worker1" = { cpus = 2, memory = "2G", disk = "10G", role = "worker1" }
    "k3s-worker2" = { cpus = 2, memory = "2G", disk = "10G", role = "worker2" }
    "nfs-server"  = { cpus = 1, memory = "1G", disk = "20G", role = "nfs" }
  }
}
```

Si quiero otro nodo, añado una entrada al mapa y el resto del código se queda como está.

## 3.3 CREACIÓN DE LAS INSTANCIAS

opentofu/main.tf recorre var.nodes con for_each y crea una instancia de Multipass por nodo. Cada instancia carga el cloud-init de su rol:

``` hcl
resource "multipass_instance" "nodes" {
  for_each = var.nodes

  name   = each.key
  image  = "24.04"
  cpus   = each.value.cpus
  memory = each.value.memory
  disk   = each.value.disk
  cloudinit_file = "${path.module}/cloud-init/${each.value.role}/user-data.yaml"
}
```

## 3.4 OUTPUTS

opentofu/outputs.tf saca las IPs de todos los nodos en un único mapa. Ese mapa es lo que luego lee el script que genera el inventario:

``` hcl
output "node_ips" {
  value = {
    for name, instance in multipass_instance.nodes :
    name => instance.ipv4
  }
}
```

## 3.5 CLOUD-INIT

Cada rol (master, worker1, worker2, nfs) tiene su directorio en opentofu/cloud-init/ con un user-data.yaml. Se aplica al crear la VM: crea el usuario ubuntu con sudo sin contraseña y le añade la clave SSH pública para que Ansible pueda conectarse:

``` yaml
#cloud-config
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: users, admin
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3... tu@email.com
chpasswd:
  expire: False
  users:
    - name: ubuntu
      password: ubuntu
      type: text
```

Antes de lanzar nada, cambia la clave SSH de cada user-data.yaml por tu clave pública (~/.ssh/id_rsa.pub o la que uses). Si te lo saltas, Ansible no podrá conectarse a las VMs.

# 4. GENERACIÓN DEL INVENTARIO

El inventario de Ansible (ansible/hosts) no lo escribo yo. Lo genera scripts/inventory.sh a partir de los outputs de OpenTofu:

``` bash
#!/bin/bash
# scripts/inventory.sh

###### VARIABLES ######
# Ruta absoluta al directorio raíz del proyecto (un nivel arriba del script)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TOFU_DIR="${PROJECT_ROOT}/opentofu"
HOSTS_FILE="${PROJECT_ROOT}/ansible/hosts"

NODE_IPS=$(cd "$TOFU_DIR" && tofu output -json node_ips | jq '.value // .')


###### LÓGICA ######

echo "[node_master]" > "$HOSTS_FILE"
echo "$NODE_IPS" | jq -r '
  to_entries[]
  | select(.key | test("master"))
  | "\(.key) ansible_host=\(.value) ansible_user=ubuntu"
' >> "$HOSTS_FILE"

echo "" >> "$HOSTS_FILE"
echo "[node_workers]" >> "$HOSTS_FILE"
echo "$NODE_IPS" | jq -r '
  to_entries[]
  | select(.key | test("worker"))
  | "\(.key) ansible_host=\(.value) ansible_user=ubuntu"
' >> "$HOSTS_FILE"

echo "[nfs_server]" >> "$HOSTS_FILE"
echo "$NODE_IPS" | jq -r '
  to_entries[]
  | select(.key | test("nfs"))
  | "\(.key) ansible_host=\(.value) ansible_user=ubuntu"
' >> "$HOSTS_FILE"

cat >> "$HOSTS_FILE" << 'EOF'

[k3s_cluster:children]
node_master
node_workers

[all:children]
node_master
node_workers
nfs_server
EOF

echo "Inventory generado:"
cat "$HOSTS_FILE"
```

Lo primero que hace es calcular la raíz del proyecto a partir de dónde está el propio script. Así da igual si lo lanzo desde la raíz, desde scripts/ o desde el Makefile: las rutas a opentofu/ y ansible/hosts siempre salen bien.

Con esa ruta pide las IPs a OpenTofu con tofu output -json node_ips. El jq '.value // .' es por si la salida llega envuelta en un objeto { "value": ... }, como pasa con tofu output -json sin nombre de output. En ese caso se queda con value y, si no, deja el JSON tal cual.

Después escribe el fichero grupo a grupo. Pone la cabecera ([node_master], [node_workers], [nfs_server]) y filtra el mapa de IPs con jq. to_entries[] convierte el mapa en pares clave/valor, select(.key | test("worker")) se queda con los nodos cuyo nombre contiene esa palabra y la última línea monta cada entrada con el formato que espera Ansible. El primer echo usa > y vacía el fichero, los demás añaden con >>, así que cada ejecución empieza de cero y no se acumulan nodos viejos.

Como el filtro va por nombre, si añado un k3s-worker3 al mapa de OpenTofu, el script lo mete en [node_workers] sin cambiar nada.

Los grupos de grupos (k3s_cluster y all) no dependen de ninguna IP, así que van fijos en un heredoc al final. Por último, el script imprime el inventario para que se vea qué ha generado.

Se lanza así (el Makefile lo hace por mí en make up):

``` bash
bash scripts/inventory.sh
```

El inventario queda así:

``` ini
[node_master]
k3s-master ansible_host=10.x.x.x ansible_user=ubuntu

[node_workers]
k3s-worker1 ansible_host=10.x.x.x ansible_user=ubuntu
k3s-worker2 ansible_host=10.x.x.x ansible_user=ubuntu

[nfs_server]
nfs-server ansible_host=10.x.x.x ansible_user=ubuntu

[k3s_cluster:children]
node_master
node_workers

[all:children]
node_master
node_workers
nfs_server
```

Como solo depende de los outputs de OpenTofu, si destruyo las VMs y las vuelvo a crear con otras IPs, el inventario se regenera solo.

# 5. ANSIBLE: CONFIGURACIÓN DEL SOFTWARE

Con las VMs creadas y el inventario listo, le toca a Ansible instalar y configurar el software dentro de ellas.

## 5.1 ANSIBLE.CFG

La configuración global está en ansible/ansible.cfg:

``` ini
[defaults]
inventory       = hosts
remote_user     = ubuntu
host_key_checking = False
private_key_file = ~/.ssh/id_rsa
```

Si tu clave privada está en otra ruta (una ed25519, por ejemplo), cambia private_key_file:

``` ini
private_key_file = ~/.ssh/id_ed25519
```

## 5.2 PLAYBOOK PRINCIPAL

ansible/site.yaml lanza cada rol sobre su grupo de hosts:

``` yaml
- hosts: k3s_cluster    # todos los nodos k3s
  roles: [commons]

- hosts: nfs_server     # solo el servidor NFS
  roles: [nfs_server]

- hosts: node_master    # solo el master
  roles: [k3s_master]

- hosts: node_workers   # solo los workers
  roles: [k3s_worker]
```

## 5.3 ROL COMMONS

Va a todos los nodos del clúster k3s y lo único que hace es actualizar el sistema:

``` yaml
- name: Actualizar el sistema y los paquetes
  apt:
    update_cache: yes
    upgrade: yes
    cache_valid_time: 3600
```

## 5.4 ROL NODES

Instala nfs-common en los nodos del clúster. Sin ese paquete no podrían montar volúmenes NFS:

``` yaml
- name: Instalar nfs
  apt:
    name: [nfs-common]
    state: present
```

## 5.5 ROL NFS_SERVER

Convierte la VM nfs-server en el servidor NFS: instala el paquete, crea el directorio compartido y lo exporta a la subred del clúster.

``` yaml
- name: Instalar nfs-kernel-server
  apt:
    name: nfs-kernel-server
    state: present

- name: Crear directorio compartido
  file:
    path: /srv/nfs/data
    state: directory
    mode: '0777'

- name: Configurar exports
  lineinfile:
    path: /etc/exports
    line: "/srv/nfs/data 10.147.215.0/24(rw,sync,no_subtree_check,no_root_squash)"
    create: yes

- name: Aplicar exports y arrancar NFS
  shell: exportfs -ra
  notify: restart nfs

- name: Asegurar que nfs-server está activo
  systemd:
    name: nfs-server
    enabled: true
    state: started
```

El handler restart nfs reinicia el servicio cada vez que cambia /etc/exports:

``` yaml
- name: restart nfs
  service: name=nfs-server state=restarted
```

## 5.6 ROL K3S_MASTER

Instala k3s en modo servidor en el master con el script oficial. Después espera a que aparezca el node-token, lo lee y lo guarda como fact global, que es de donde lo sacarán los workers. Al final se trae el kubeconfig a la máquina local y cambia 127.0.0.1 por la IP real del master:

``` yaml
- name: Instalar k3s como servidor
  shell: |
    curl -sfL https://get.k3s.io | sh -s - server \
      --write-kubeconfig-mode 644
  args:
    creates: /usr/local/bin/k3s

- name: Esperar a que k3s esté listo
  wait_for:
    path: /var/lib/rancher/k3s/server/node-token
    timeout: 60

- name: Leer node-token
  slurp:
    src: /var/lib/rancher/k3s/server/node-token
  register: k3s_token

- name: Guardar token como fact global
  set_fact:
    k3s_token: "{{ k3s_token.content | b64decode | trim }}"
    k3s_master_ip: "{{ ansible_host }}"
  delegate_to: localhost
  delegate_facts: true

- name: Leer kubeconfig
  slurp:
    src: /etc/rancher/k3s/k3s.yaml
  register: kubeconfig_raw

- name: Guardar kubeconfig en local
  copy:
    content: "{{ kubeconfig_raw.content | b64decode | replace('127.0.0.1', ansible_host) }}"
    dest: "~/.kube/kubeconfig-k3s"
    mode: '0600'
  delegate_to: localhost
  become: false
```

El creates: /usr/local/bin/k3s hace que la instalación sea idempotente: si el binario ya existe, Ansible se salta la tarea.

## 5.7 ROL K3S_WORKER

Cada worker coge el token y la IP del master de hostvars['localhost'], donde los dejó el rol anterior, e instala k3s en modo agente contra ese master:

``` yaml
- name: Instalar k3s como agente
  shell: |
    curl -sfL https://get.k3s.io | K3S_URL=https://{{ hostvars['localhost']['k3s_master_ip'] }}:6443 \
      K3S_TOKEN={{ hostvars['localhost']['k3s_token'] }} sh -
  args:
    creates: /usr/local/bin/k3s
```

Así no copio el token a mano en ningún momento. Pasa de un rol a otro en los facts de Ansible.

# 6. HELM: NFS PROVISIONER

Con k3s funcionando y el servidor NFS levantado, falta desplegar un NFS provisioner dentro del clúster. El provisioner crea PersistentVolumes dinámicos sobre el servidor NFS, así que un pod puede pedir almacenamiento esté en el nodo que esté.

helm/nfs-provisioner/values.yaml:

``` yaml
nfs:
  path: /srv/nfs/data

storageClass:
  name: nfs-csi
```

La IP del servidor NFS no aparece en este fichero. El Makefile la saca del ansible/hosts generado antes y se la pasa a Helm con --set nfs.server=.

Tras el despliegue, el clúster tiene una StorageClass llamada nfs-csi que puede usar cualquier PersistentVolumeClaim.

# 7. MAKEFILE: AUTOMATIZACIÓN COMPLETA

Todo lo anterior se lanza desde un único Makefile:

``` makefile
all: up configure nfs

up: tofu-init tofu-apply inventory

tofu-init:
	@if [ ! -d "$(TOFU_DIR)/.terraform" ]; then \
		cd $(TOFU_DIR) && tofu init; \
	fi

tofu-apply:
	@cd $(TOFU_DIR) && tofu apply -auto-approve

inventory:
	@bash scripts/inventory.sh

configure:
	@cd $(ANSIBLE_DIR) && ansible-playbook site.yaml

nfs:
	@KUBECONFIG=$(KUBECONFIG) helm repo add nfs-subdir-external-provisioner \
		https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/ 2>/dev/null || true
	@NFS_IP=$$(grep 'nfs-server' $(ANSIBLE_DIR)/hosts | awk '{print $$2}' | cut -d'=' -f2 | cut -d' ' -f1); \
	KUBECONFIG=$(KUBECONFIG) helm upgrade --install nfs-subdir-external-provisioner \
	nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
	--values $(HELM_DIR)/nfs-provisioner/values.yaml \
	--set nfs.server=$$NFS_IP \
	--namespace nfs-provisioner \
	--create-namespace

destroy:
	@cd $(TOFU_DIR) && tofu destroy -auto-approve
	@rm -f $(ANSIBLE_DIR)/hosts
	@rm -f $(KUBECONFIG)
```

Estos son los comandos:

``` bash
make all        # ejecuta up + configure + nfs
make up         # crea las VMs y genera el inventario
make configure  # instala k3s y nfs-server con Ansible
make nfs        # despliega el NFS provisioner con Helm
make destroy    # destruye todas las VMs y limpia los ficheros generados
```

Puedo ejecutar make all las veces que quiera sin romper nada. tofu init solo corre si no existe .terraform/, tofu apply no hace nada si las VMs ya están creadas y no ha cambiado nada, los playbooks de Ansible comprueban el estado antes de actuar y helm upgrade --install solo actualiza cuando hay cambios.

# 8. PUESTA EN MARCHA

Para levantar el clúster desde cero:

``` bash
# 1. Clonar el repo
git clone https://github.com/ryberxy/cluster-k3s
cd cluster-k3s

# 2. Añadir la clave SSH pública en cada cloud-init
# editar opentofu/cloud-init/*/user-data.yaml

# 3. Lanzar todo
make all

# 4. Exportar el kubeconfig
export KUBECONFIG=~/.kube/kubeconfig-k3s

# 5. Verificar el clúster
kubectl get nodes
```

# 9. MIGRACIÓN A UN SERVIDOR DEDICADO

Como la infraestructura (OpenTofu) y la configuración (Ansible) van por separado, llevar el proyecto a un proveedor real como Hetzner no obliga a rehacer Ansible ni el Makefile:

1. Cambiar el provider de opentofu/provider.tf por el de Hetzner
2. Adaptar opentofu/main.tf para crear servidores de Hetzner Cloud en lugar de instancias de Multipass
3. Los playbooks y el Makefile se quedan igual, porque solo dependen del inventario generado
4. En un entorno real tendría más sentido un almacenamiento distribuido como Longhorn que el NFS provisioner

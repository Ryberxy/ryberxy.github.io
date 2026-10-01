---
title: "Despliegue de un clúster K3s con OpenTofu y Ansible"
date: 2026-10-01
description: "Aprovisionamiento de un clúster k3s sobre Multipass con OpenTofu, configuración con Ansible y almacenamiento compartido vía NFS desplegado con Helm"
tags: ["OpenTofu", "Ansible", "Kubernetes", "k3s", "Helm", "NFS", "Makefile"]
---

# 1. INTRODUCCIÓN Y ARQUITECTURA

El objetivo de esta práctica es levantar un clúster de Kubernetes (k3s) completo de forma totalmente automatizada, combinando tres herramientas que cubren cada una una capa distinta del despliegue:

- **OpenTofu** — crea y destruye la infraestructura (las VMs) de forma declarativa.
- **Ansible** — instala y configura el software dentro de esas VMs (k3s, NFS, etc.).
- **Helm** — despliega aplicaciones dentro del propio clúster de Kubernetes ya funcionando.

El clúster está formado por 4 nodos, gestionados como VMs de **Multipass**:

- `k3s-master` — nodo master de k3s
- `k3s-worker1` y `k3s-worker2` — nodos worker de k3s
- `nfs-server` — servidor NFS que proporciona almacenamiento compartido al clúster

Todo el flujo (crear VMs → generar inventario → instalar k3s → desplegar almacenamiento) se orquesta con un único `Makefile`, de modo que levantar el clúster completo desde cero es tan sencillo como ejecutar `make all`.

# 2. REQUISITOS PREVIOS

Antes de ejecutar el proyecto es necesario tener instaladas las siguientes herramientas en la máquina anfitriona:

- [Multipass](https://multipass.run/)
- [OpenTofu](https://opentofu.org/)
- [Ansible](https://www.ansible.com/)
- [Helm](https://helm.sh/)
- `jq`

``` bash
sudo apt install jq
```

También hace falta tener un par de claves SSH generadas, ya que la clave pública se inyectará en cada VM mediante `cloud-init` para que Ansible pueda conectarse sin contraseña.

# 3. OPENTOFU: CREACIÓN DE LA INFRAESTRUCTURA

OpenTofu es la alternativa open source a Terraform, y aquí se usa para crear y destruir las VMs de Multipass de forma declarativa.

## 3.1 PROVIDER

En `opentofu/provider.tf` se define el provider de Multipass que va a usar OpenTofu:

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

En `opentofu/variables.tf` se define el clúster completo como un mapa de objetos. Cada nodo tiene su número de CPUs, memoria, disco y rol:

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

Para añadir un nodo nuevo al clúster basta con añadir una entrada más a este mapa, no hay que tocar nada más.

## 3.3 CREACIÓN DE LAS INSTANCIAS

En `opentofu/main.tf` se itera sobre `var.nodes` para crear una instancia de Multipass por cada nodo definido. Cada una recibe su propio `cloud-init` según el rol que le corresponda:

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

`opentofu/outputs.tf` expone las IPs de todos los nodos como un único mapa, que luego consumirá el script de generación del inventario:

``` hcl
output "node_ips" {
  value = {
    for name, instance in multipass_instance.nodes :
    name => instance.ipv4
  }
}
```

## 3.5 CLOUD-INIT

Cada rol (`master`, `worker1`, `worker2`, `nfs`) tiene su propio directorio dentro de `opentofu/cloud-init/` con un `user-data.yaml`. El cloud-init se aplica en el momento de crear la VM y configura un usuario `ubuntu` con permisos de sudo sin contraseña y la clave SSH pública para que Ansible pueda conectarse:

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

**Importante**: antes de ejecutar el proyecto hay que sustituir la clave SSH de cada `user-data.yaml` por la clave pública propia (`~/.ssh/id_rsa.pub` o similar), si no Ansible no podrá conectarse a las VMs.

# 4. GENERACIÓN DEL INVENTARIO

El fichero de inventario de Ansible (`ansible/hosts`) no se escribe a mano: se genera automáticamente a partir de los outputs de OpenTofu con el script `scripts/inventory.sh`.

El script hace lo siguiente:

1. Consulta `tofu output -json node_ips` para obtener todas las IPs de los nodos
2. Filtra las IPs por nombre de nodo (`master`, `worker`, `nfs`) con `jq`
3. Escribe el fichero `ansible/hosts` ya agrupado en los grupos correctos

``` bash
bash scripts/inventory.sh
```

El resultado es un inventario con esta forma:

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

Al depender únicamente de los outputs de OpenTofu, si las VMs se destruyen y se vuelven a crear con otras IPs, el inventario se regenera solo, sin tener que tocar nada a mano.

# 5. ANSIBLE: CONFIGURACIÓN DEL SOFTWARE

Una vez las VMs existen y el inventario está generado, Ansible se encarga de instalar y configurar todo el software dentro de ellas.

## 5.1 ANSIBLE.CFG

Configuración global de Ansible, en `ansible/ansible.cfg`:

``` ini
[defaults]
inventory       = hosts
remote_user     = ubuntu
host_key_checking = False
private_key_file = ~/.ssh/id_rsa
```

**Importante**: si la clave SSH privada está en otra ruta (por ejemplo una clave ed25519), hay que cambiar `private_key_file` en consecuencia:

``` ini
private_key_file = ~/.ssh/id_ed25519
```

## 5.2 PLAYBOOK PRINCIPAL

`ansible/site.yaml` orquesta la ejecución de todos los roles, cada uno sobre el grupo de hosts que le corresponde:

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

Se aplica a todos los nodos del clúster k3s, y simplemente actualiza el sistema:

``` yaml
- name: Actualizar el sistema y los paquetes
  apt:
    update_cache: yes
    upgrade: yes
    cache_valid_time: 3600
```

## 5.4 ROL NODES

Instala `nfs-common` en los nodos del clúster, necesario para que luego puedan montar volúmenes NFS:

``` yaml
- name: Instalar nfs
  apt:
    name: [nfs-common]
    state: present
```

## 5.5 ROL NFS_SERVER

Configura la VM `nfs-server` como servidor NFS: instala el paquete, crea el directorio compartido y exporta ese directorio a la subred del clúster.

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

El handler `restart nfs` se encarga de reiniciar el servicio cada vez que cambia la configuración de `/etc/exports`:

``` yaml
- name: restart nfs
  service: name=nfs-server state=restarted
```

## 5.6 ROL K3S_MASTER

Instala k3s en modo servidor en el nodo master usando el script oficial de instalación, espera a que genere el `node-token`, lo lee y lo guarda como fact global para que los workers puedan usarlo más adelante. Por último descarga el `kubeconfig` a la máquina local, sustituyendo `127.0.0.1` por la IP real del master:

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

Gracias a `creates: /usr/local/bin/k3s`, esta tarea es idempotente: si k3s ya está instalado, Ansible no lo vuelve a ejecutar.

## 5.7 ROL K3S_WORKER

Cada worker lee el token y la IP del master que guardó el rol anterior (a través de `hostvars['localhost']`) e instala k3s en modo agente apuntando a ese master:

``` yaml
- name: Instalar k3s como agente
  shell: |
    curl -sfL https://get.k3s.io | K3S_URL=https://{{ hostvars['localhost']['k3s_master_ip'] }}:6443 \
      K3S_TOKEN={{ hostvars['localhost']['k3s_token'] }} sh -
  args:
    creates: /usr/local/bin/k3s
```

De esta forma no hay que copiar el token a mano en ningún sitio: viaja de un rol a otro a través de los facts de Ansible.

# 6. HELM: NFS PROVISIONER

Con el clúster k3s ya funcionando y el servidor NFS disponible, el último paso es desplegar un **NFS provisioner** dentro del propio clúster. Esto permite crear `PersistentVolumes` dinámicos respaldados por el servidor NFS, de modo que cualquier pod puede pedir almacenamiento sin importar en qué nodo físico esté corriendo.

`helm/nfs-provisioner/values.yaml`:

``` yaml
nfs:
  path: /srv/nfs/data

storageClass:
  name: nfs-csi
```

La IP del servidor NFS no está escrita a mano aquí: el `Makefile` la lee dinámicamente del fichero `ansible/hosts` generado antes y se la pasa a Helm con `--set nfs.server=`.

Una vez desplegado, queda disponible una `StorageClass` llamada `nfs-csi` que puede usar cualquier `PersistentVolumeClaim` del clúster.

# 7. MAKEFILE: AUTOMATIZACIÓN COMPLETA

Todo el flujo anterior se orquesta desde un único `Makefile`, de forma idempotente:

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

Los comandos disponibles son:

``` bash
make all        # ejecuta up + configure + nfs
make up         # crea las VMs y genera el inventario
make configure  # instala k3s y nfs-server con Ansible
make nfs        # despliega el NFS provisioner con Helm
make destroy    # destruye todas las VMs y limpia los ficheros generados
```

La idempotencia se consigue en varios puntos: `tofu init` solo se ejecuta si `.terraform/` no existe, `tofu apply` no hace nada si las VMs ya están creadas y no hay cambios, los playbooks de Ansible comprueban el estado antes de actuar, y `helm upgrade --install` actualiza si hay cambios y no hace nada si está todo igual.

# 8. PUESTA EN MARCHA

Con todo lo anterior montado, levantar el clúster completo desde cero se reduce a estos pasos:

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

Una de las ventajas de separar la infraestructura (OpenTofu) de la configuración (Ansible) es que el proyecto es fácilmente portable a un proveedor real, por ejemplo Hetzner, sin tener que rehacer nada de Ansible ni del Makefile:

1. Cambiar el provider en `opentofu/provider.tf` por el de Hetzner
2. Adaptar `opentofu/main.tf` con los recursos de Hetzner Cloud en vez de instancias de Multipass
3. Los playbooks de Ansible y el `Makefile` se reutilizan sin cambios, ya que solo dependen del inventario generado
4. Para almacenamiento distribuido nativo en un entorno real, se podría sustituir el NFS provisioner por **Longhorn**

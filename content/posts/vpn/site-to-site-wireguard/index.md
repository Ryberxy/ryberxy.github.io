---
title: "VPN Site to Site con WireGuard"
date: 2026-09-28
description: "Interconexión de dos redes mediante un túnel VPN site to site con WireGuard"
tags: ["VPN", "WireGuard"]
---

# 1. VPN SITE TO SITE WIREGUARD

Necesitaremos dos servidores, el servidor 1 y el servidor 2, por lo tanto generamos las claves en cada servidor, si aún no las tenemos:

``` bash
wg genkey | sudo tee /etc/wireguard/private.key | wg pubkey | sudo tee /etc/wireguard/public.key
```

## 1.1 CONFIGURACIÓN DEL SERVIDOR 1

<img src="./media/image37.png" style="width:3.35008in;height:2.06337in" />

``` bash
wg-quick up wg0
```

## 1.2 CONFIGURACIÓN DEL SERVIDOR 2

<img src="./media/image43.png" style="width:3.38021in;height:2.15219in" />

``` bash
wg-quick up wg0
```

## 1.3 FUNCIONAMIENTO

**Enrutamiento servidor 1:**

<img src="./media/image4.png" style="width:3.70313in;height:0.73233in" />

**Enrutamiento servidor 2:**

<img src="./media/image45.png" style="width:3.71701in;height:0.76282in" />

**Cliente 1 → Red Servidor 2**

<img src="./media/image20.png" style="width:3.78646in;height:1.79741in" />

**Cliente 2 → Red Servidor 1**

<img src="./media/image13.png" style="width:3.75521in;height:1.68372in" />

---
title: "Análisis forense de máquina Windows"
date: 2026-10-05
description: "Volcado de memoria, registro y disco de una máquina Windows y su análisis con Volatility y Autopsy"
tags: ["Forense", "Windows"]
---

# 1. VOLCADO DE IMÁGENES Y MEMORIA

## 1.1 PREPARACIÓN DEL DISCO

Para contaminar lo menos posible la máquina sobre la que vamos a realizar el análisis forense, vamos a preparar un disco externo donde portaremos los programas FTK Imager y DumpIT, los formatos serán .exe.

Este disco lo formateamos con exfat para poder trabajar con el desde Linux y Windows sin tener que utilizar drivers adicionales.

Conectamos el disco a la máquina con Windows 10 y lo montamos.

## 1.2 VOLCADO DE MEMORIA CON DUMPIT

Para descargar el programa tenemos que rellenar una encuesta, en esta página: [<u>https://www.magnetforensics.com/</u>](https://www.magnetforensics.com/) , puedes inventarte los datos si no formas parte de ninguna compañía, pero sí hay que poner un correo electrónico con el formato de pertenecer a una organización.

<img src="./media/image30.png" style="width:3.73156in;height:0.9079in" />

<img src="./media/image80.png" style="width:3.66399in;height:2.16849in" />

<img src="./media/image9.png" style="width:3.69271in;height:1.1829in" />

## 1.3 VOLCADO DE REGISTRO DE WINDOWS

<img src="./media/image61.png" style="width:6.26772in;height:3.58333in" />

<img src="./media/image10.png" style="width:3.32292in;height:2.75in" />

<img src="./media/image5.png" style="width:5.83333in;height:3.72917in" />

<img src="./media/image17.png" style="width:3.70833in;height:1.78125in" />

## 1.4 VOLCADO DEL DISCO

<img src="./media/image43.png" style="width:1.83302in;height:3.27618in" />

<img src="./media/image64.png" style="width:4.03646in;height:2.26072in" />

<img src="./media/image69.png" style="width:2.88354in;height:3.03646in" />

<img src="./media/image73.png" style="width:3.56391in;height:3.61632in" />

<img src="./media/image39.png" style="width:3.96875in;height:2.89583in" />

## 1.5 MONTAJE DEL DISCO Y VERIFICACIÓN DE HASHES

A continuación voy a montar el disco que contiene las evidencias, en la maquina con la que vamos a realizar el análisis forense. Como voy a montar un disco de virt-manager en formato qcow2, tendré que cargar el siguiente módulo:

``` bash
sudo modprobe nbd
```

Posterior a ello montamos el disco:

``` bash
sudo qemu-nbd --connect=/dev/nbd0 /var/lib/libvirt/images/debian13_forense-3.qcow2
sudo mkdir forense
sudo mount /dev/nbd0p1 /mnt/forense
```

<img src="./media/image16.png" style="width:3.96354in;height:0.40444in" />

Ahora el contenido al directorio donde vamos a trabajar y verificamos los hashes:

Memoria:

<img src="./media/image18.png" style="width:5.4529in;height:0.20833in" />

Registro:

<img src="./media/image63.png" style="width:6.26772in;height:0.94444in" />

Disco:

<img src="./media/image8.png" style="width:5.51563in;height:0.30589in" />

# 2. INSTALACIÓN DE AUTOPSY

Necesitamos la versión 17 de Java o más, para ello vamos a instalar la que viene por defecto en mi distro, debian, que es la 21:

``` bash
sudo apt update
sudo apt install -y default-jdk default-jre
```

Posteriormente me di cuenta que con la versión 21 había fallos de compatibilidad por lo que cambié a la 17:

``` bash
cd /opt/
wget https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.16+8/OpenJDK17U-jdk_x64_linux_hotspot_17.0.16_8.tar.gz
sudo tar -xvzf OpenJDK17U-jdk_x64_linux_hotspot_17.0.16_8.tar.gz
sudo mv jdk-17.0.16+8/ java-17
# Esto solo lo haréis en caso de que tengáis otra versión java que no sea la 17, básicamente lo haremos para que el sistema detecte esta versión y podamos compilar el código necesario con java 17 para que funcione autopsy.
sudo update-alternatives --install /usr/bin/java java /opt/java-17/bin/java 1710
sudo update-alternatives --install /usr/bin/javac javac /opt/java-17/bin/javac 1710
sudo update-alternatives --config java → escogemos la versión 17
sudo update-alternatives --config javac → escogemos la versión 17
```

Clonar repositorio de autopsy:

``` bash
mkdir /opt/autopsy
cd /opt/autopsy
sudo wget https://github.com/sleuthkit/autopsy/releases/download/autopsy-4.22.1/autopsy-4.22.1_v2.zip
```

Ahora vamos a instalar ciertas dependencias y realizar unos prerrequisitos necesarios para utilizar autopsy, utilizaremos el siguiente script que viene en el repositorio clonado:

``` bash
cd linux_macos_install_scripts
sudo chmod +x install_prereqs_ubuntu.sh
sudo ./install_prereqs_ubuntu.sh
```

Para poder realizar análisis con autopsy, tenemos que instalar Sleuth Kit(tsk), como linux no tiene binarios oficiales, tendremos que compilarlo:

``` bash
sudo chmod +x install_tsk_from_src.sh
sudo ./install_tsk_from_src.sh -p /opt/sleuthkit -b develop -r https://github.com/sleuthkit/sleuthkit.git
sudo ldconfig # Cargamos las librerías
sudo ldconfig -p | grep tsk # Verificamos que se encuentre en el sistema
```

Procedemos con la compilación:

``` bash
cd /opt/sleuthkit/
sudo ./configure --enable-java
sudo make
sudo make install
```

Lo que estamos buscando es que se genere un fichero .jar que necesitamos para que autopsy funcione, resulta que al terminar el make install no lo genera y dice que no se encuentra este fichero, por lo que lo generaremos manualmente:

``` bash
cd /opt/sleuthkit/bindings/java/
sudo apt install ant -y
ant dist
mkdir -p /usr/local/share/java
sudo cp /opt/sleuthkit/bindings/java/dist/sleuthkit-4.14.0.jar /usr/local/share/java
```

Ahora vamos a exportar una serie de variables a .bashrc de java, que son necesarias para que autopsy funcione correctamente:

``` bash
Vamos al home de nuestro usuario y exportamos lo siguiente a .bashrc
export JAVA_HOME=/opt/java-17 >> .bashrc
export PATH=$JAVA_HOME/bin:$PATH >> .bashrc
export TSK_JAVA_LIB_PATH=/usr/local/share/java/sleuthkit-4.14.0.jar >> .bashrc
source .bashrc
```

Por último vamos a hacer la configuración final para dejar autopsy preparado para usar:

``` bash
cd /opt/autopsy/
```

Tenemos que definir las variables en la instrucción de esta manera porque necesitamos usar sudo y el root no tiene cargadas estas variables de entorno, podríamos utilizar sudo -E bash pero pienso que no es seguro exportar todo un entorno al superusuario.

``` bash
sudo chmod +x unix_setup.sh
sudo JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 PATH=/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH ./unix_setup.sh
cd bin
sudo chmod +x autopsy
sudo ./autopsy
```

# 3. INSTALACIÓN DE VOLATILITY

Instalaremos la versión 3 de volatility de los repositorios de github de la siguiente forma:

``` bash
cd /home/ryberxy/gitclone
wget https://github.com/volatilityfoundation/volatility3.git
cd ../envirtual
python3 -m venv volatility
source /home/ryberxy/envirtual/bin/activate
cd /home/ryberxy/gitclone/volatility3
pip install -e
```

# 4. ANÁLISIS DE MÁQUINA WINDOWS

## 4.1 MEMORIA

### 4.1.1 Procesos en ejecución

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.pslist
```

<img src="./media/image77.png" style="width:3.65279in;height:3.36831in" />

### 4.1.2 Servicios en ejecución 

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.getservicesids.GetServiceSIDs
```

<img src="./media/image14.png" style="width:4.04688in;height:3.23974in" />

### 4.1.3 Puertos abiertos

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.netstat
```

<img src="./media/image38.png" style="width:3.20755in;height:2.95313in" />

### 4.1.4 Conexiones establecidas por la máquina

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.netscan.NetScan
```

<img src="./media/image32.png" style="width:3.25521in;height:2.99798in" />

### 4.1.5 Conexiones de usuario establecidas remotamente

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.sessions.Sessions
```

<img src="./media/image79.png" style="width:4.04172in;height:3.47396in" />

### 4.1.6 Ficheros transferidos por NetBios

No hay ninguna opción disponible que nos permita descubrir esto con volatility.

Ahora sale que no hay ninguna conexión activa, ya que se realizó en el momento en que se hizo el volcado de memoria, pero no podemos comprobarlo, al menos con volatility.

<img src="./media/image49.png" style="width:3.38021in;height:2.63143in" />

strings /home/ryberxy/forense/Linux/debian13.mem \| grep -oE '\[a-zA-Z0-9-\]+\\(com\|org\|net\|es\|io)' \| sort -u \> cachedns.txt

### 4.1.7 Contenido de la caché DNS

No hay ninguna opción para realizar esto, pero he encontrado esta otra opción que me ha resultado interesante, ya que dice el programa que ha usado el usuario y cuantas veces, por ejemplo em Microsoft Edge.

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.registry.userassist.UserAssist
```

<img src="./media/image19.png" style="width:6.26772in;height:2.88889in" />

### 4.1.8 Variables de entorno

``` bash
python3 vol.py -f "/home/ryberxy/forense/DESKTOP-GUT16QJ-20260114-225122.dmp" windows.envars
```

<img src="./media/image55.png" style="width:6.26772in;height:4.08333in" />

<img src="./media/image28.png" style="width:5.54167in;height:0.15625in" />

# 4.2 REGISTRO DE WINDOWS

Voy a utilizar la herramienta registry explorer, es muy sencilla de instalar en windows.

### 4.2.1 Dispositivos USB conectados

**SYSTEM\ControlSet001\Enum\USB**

<img src="./media/image70.png" style="width:6.26772in;height:3.05556in" />

<img src="./media/image31.png" style="width:6.26772in;height:2.47222in" />

### 4.2.2 Redes wifi utilizadas recientemente

SYSTEM\ControlSet001\Control\Network\Connections

<img src="./media/image65.png" style="width:6.26772in;height:3.04167in" />

### 4.2.3 Configuración de firewall de nodo

SYSTEM\ControlSet001\Services\SharedAccess\Parameters\FirewallPolicy

<img src="./media/image72.png" style="width:6.26772in;height:3.15278in" />

### 4.2.4 Programas que se ejecutan en el inicio

**SOFTWARE\Microsoft\Windows\CurrentVersion\Run**

### <img src="./media/image42.png" style="width:6.26772in;height:2.94444in" />

### 4.2.5 Asociación de extensiones de ficheros y aplicaciones

<img src="./media/image56.png" style="width:6.26772in;height:2.93056in" />

# 4.3 AUTOPSY

<img src="./media/image3.png" style="width:4.0752in;height:2.33545in" />

<img src="./media/image59.png" style="width:4.07813in;height:2.31405in" />

### 4.3.1 Aplicaciones usadas recientemente

<img src="./media/image12.png" style="width:6.26772in;height:3.91667in" />

### 4.3.2 Ficheros abiertos recientemente

<img src="./media/image62.png" style="width:6.26772in;height:3.91667in" />

### 4.3.3 Software instalado

<img src="./media/image47.png" style="width:6.26772in;height:3.91667in" />

### 4.3.4 Contraseñas guardadas

Hay un artefacto llamado "cuentas web" que muestra las contraseñas guardadas en paginas web pero no me las ha cargado, he intentado verlas desde el registro Windows pero el NTUSER.dat solo guarda la configuración que utiliza que es DPAPI un método de encriptación de Windows por lo que no puedo verlas.

Entonces he encontrado este artefacto interesante de autopsy, que permite ver los formularios web realizados, pero no sale la contraseña ni usuario, sale el registro a las páginas web, aqui por ejemplo tenemos nombre, apellido, correo electrónico y el código que ha mandado al correo para completar el registro:

<img src="./media/image13.png" style="width:6.26772in;height:0.81944in" />

### 4.3.5 Cuentas de usuario

Podemos ver el directorio de la cuenta como el último logueo y alguna información mas también, como las preguntas que se hicieron al crear la cuenta:

<img src="./media/image75.png" style="width:6.26772in;height:4.25in" />

### 4.3.6 Historial de navegación

<img src="./media/image4.png" style="width:6.26772in;height:3.91667in" />

### 4.3.7 Descargas

<img src="./media/image68.png" style="width:6.26772in;height:3.91667in" />

### 4.3.8 Cookies

<img src="./media/image76.png" style="width:6.26772in;height:3.91667in" />

### 4.3.9 Volúmenes cifrados

<img src="./media/image45.png" style="width:6.26772in;height:1.125in" />

### 4.3.10 Archivos con extensión cambiada

<img src="./media/image60.png" style="width:6.26772in;height:3.43056in" />

### 4.3.11 Archivos eliminados

<img src="./media/image66.png" style="width:6.26772in;height:2.40278in" />

### 4.3.12 Archivos ocultos

### <img src="./media/image35.png" style="width:6.26772in;height:3.18056in" />

### 4.3.13 Archivos que contienen una cadena determinada

Esto lo he tenido que hacer desde autopsy en Windows ya que en debian tenía un problema con el módulo de keyword search, al parecer era por la versión de java, la cambié, y luego parecía ser de permisos pero tampoco pude arreglarlo.

### <img src="./media/image24.png" style="width:6.26772in;height:3.95833in" />

### 4.3.14 Búsqueda de imágenes por ubicación 

Autopsy no me encuentra artefactos de ubicación, pero no tiene sentido ya que desde el dispositivo que se hizo la foto tiene permisos para guardar la ubicación:

<img src="./media/image74.png" style="width:3.76563in;height:2.47706in" />

Entonces he encontrado esta página web que si lo hace:

<img src="./media/image37.png" style="width:6.26772in;height:1.86111in" />

### 4.3.15 Búsqueda de archivos por autor 

Para buscar el archivo por autor es necesario que este tenga metadatos, para ello habría que haber creado un word y cambiarle el autor, pero los archivos con los que se han trabajado en la máquina no tienen dichos metadatos por lo que no puedo comprobarlo

# 5. CADENA DE CUSTODIA

Para certificar la cadena de custodia tenemos que tomar una serie de medidas y así garantizar que las evidencias no han sido alteradas, para ello vamos a calcular el hash del disco y la memoria y vamos a seleccionar un identificador único para cada prueba, nada más sacarlo de la máquina que vamos a analizar.

Posterior a ello los ubicamos en un directorio de trabajo propio, donde guardaremos todas las evidencias, y también crearemos en autopsy un caso para el análisis del disco de modo que se lleve a cabo en un directorio ubicado en la máquina que va a realizar el forense.

El forense lo va a realizar Roberto Martín, en una máquina con la siguiente MAC y trabajará con debian 13 como sistema operativo.

Cuando se termine de analizar y buscar en las entrañas de la presunta máquina, volveremos a verificar los hashes de las copias que hemos sacado a las evidencias originales, para comprobar que nada haya sido alterado.

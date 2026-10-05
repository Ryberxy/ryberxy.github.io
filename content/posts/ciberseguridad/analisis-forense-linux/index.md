---
title: "Análisis forense de máquina Linux"
date: 2026-10-05
description: "Volcado de memoria y disco de una máquina Linux y su análisis con Volatility y Autopsy"
tags: ["Forense", "Linux"]
---

# 1. VOLCADO DE IMÁGENES Y MEMORIA

## 1.1 VOLCADO DE MEMORIA

Clonaremos el repositorio github de la siguiente herramienta y cargaremos el modulo en el sistema:

``` bash
git clone https://github.com/504ensicsLabs/LiME.git
cd LiME/src
make
sudo insmod /home/usuario/LiME/src/lime-6.12.63+deb13-amd64.ko path=/mnt/forense/debian13.mem format=lime
```

<img src="./media/image44.png" style="width:6.26772in;height:0.5in" />

## 1.2 VOLCADO DE DISCO

<img src="./media/image27.png" style="width:6.26772in;height:0.55556in" />

## 1.3 HASHES

Ahora vamos a sacar los hashes de las pruebas que hemos obtenido y posteriormente pasaremos las pruebas al entorno donde vamos a realizar el análisis forense.

<img src="./media/image1.png" style="width:6.26772in;height:0.5in" />

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

# 4. ANÁLISIS DE MÁQUINA LINUX

## 4.1 MEMORIA

Para poder utilizar volatility3 en Linux es necesario que sepamos la versión de kernel de la memoria que vamos a analizar, en mi caso el el 12.63deb+. Una vez lo sepamos vamos a acceder al siguiente enlace de github y descargaremos la tabla de símbolos necesarios para trabajar con la captura de memoria: [<u>https://github.com/Abyss-W4tcher/volatility3-symbols</u>](https://github.com/Abyss-W4tcher/volatility3-symbols)

Está dividido en secciones dependiendo de tu distribución de Linux y dentro de cada distribución la versión de kernel.

A continuación, antes de analizar, primero vamos a ver cuando fue extraída la memoria:

<img src="./media/image54.png" style="width:6.26772in;height:0.83333in" />

### 4.1.1 Procesos en ejecución

<img src="./media/image33.png" style="width:4.19271in;height:3.74349in" />

### 4.1.2 Servicios en ejecución

<img src="./media/image51.png" style="width:4.20301in;height:4.08743in" />

### 4.1.3 Puertos abiertos

<img src="./media/image6.png" style="width:6.26772in;height:3.34722in" />

### 4.1.4 Conexiones establecidas por la máquina 

Aquí he utilizado grep ya que devuelve una gran cantidad de conexiones, y como vemos hubo una conexión remota a postgres:

<img src="./media/image34.png" style="width:5.59987in;height:1.04426in" />

### 4.1.5 Sesiones de usuario establecidas remotamente 

He utilizado sockscan y he filtrado para buscar por ESTABLISHED:

<img src="./media/image57.png" style="width:5.59157in;height:4.48626in" />

<img src="./media/image11.png" style="width:6.26772in;height:0.125in" />

Con psaux también podemos ver las sesiones ssh:

<img src="./media/image67.png" style="width:6.26772in;height:0.38889in" />

### 4.1.6 Ficheros transferidos por ssh 

No hay ninguna opción soportada para ello, pero he podido buscar por archivos que estaban recientemente y he encontrado lo siguiente:

<img src="./media/image15.png" style="width:6.26772in;height:2.08333in" />

### 4.1.7 Contenido de la caché DNS

No hay ninguna opción con volatility para poder ver la caché dns, se me ocurrió filtrar por systemd-resolved en psaux y sockscan pero tampoco salía, por lo que voy a dejar el comando a ejecutar en linux:

``` bash
sudo journalctl -u systemd-resolved
```

### 4.1.8 Variables de entorno

<img src="./media/image21.png" style="width:4.33905in;height:3.57579in" />

### 4.1.9 Histórico de bash

Como curiosidad he encontrado esta opción que que es muy útil para ver los comandos que se ejecutaron en dicha máquina:

<img src="./media/image2.png" style="width:6.26772in;height:5.90278in" />

## 4.2 AUTOPSY

<img src="./media/image46.png" style="width:4.07933in;height:2.33782in" />

<img src="./media/image50.png" style="width:4.11032in;height:2.36924in" />

### 4.2.1 Dispositivos USB conectados

<img src="./media/image23.png" style="width:6.26772in;height:2.72222in" />

### 4.2.2 Redes wifi utilizadas recientemente

Es una máquina virtual por lo que la podemos ver las interfaces pero no la red wifi que utiliza ya que está conectada al host por defecto:

<img src="./media/image36.png" style="width:6.26772in;height:2.56944in" />

### 4.2.3 Configuración de firewall de nodo

No hay ninguna opción para verlo, a no ser que tuviera las reglas guardadas en algún fichero del disco.

### 4.2.4 Programas que se ejecutan al inicio

Sabemos que se ejecuta al inicio porque tiene creado un link simbolico que se crea cuando se habilita un servicio con inicio automático

<img src="./media/image71.png" style="width:6.26772in;height:2.98611in" />

### 4.2.5 Asociación de extensiones de ficheros y aplicaciones

<img src="./media/image26.png" style="width:6.26772in;height:3.51389in" />

### 4.2.6 Aplicaciones usadas recientemente

<img src="./media/image48.png" style="width:6.26772in;height:3.38889in" />

### 4.2.7 Ficheros abiertos recientemente 

<img src="./media/image82.png" style="width:6.26772in;height:0.15278in" />

<img src="./media/image81.png" style="width:6.26772in;height:2.61111in" />

### 4.2.8 Software instalado

<img src="./media/image25.png" style="width:6.26772in;height:3.54167in" />

### 4.2.9 Contraseñas guardadas

No me sale ningún apartado que me guarde las contraseñas pero sí los formularios web

### <img src="./media/image78.png" style="width:6.26772in;height:1.22222in" />

### 4.2.10 Cuentas de usuario

<img src="./media/image58.png" style="width:6.26772in;height:3.44444in" />

### 4.2.11 Historial de navegación

<img src="./media/image7.png" style="width:6.26772in;height:2.23611in" />

### 4.2.12 Descargas

<img src="./media/image40.png" style="width:6.26772in;height:1.70833in" />

### 4.2.13 Cookies

<img src="./media/image52.png" style="width:6.26772in;height:2.40278in" />

### 4.2.14 Volúmenes cifrados

<img src="./media/image83.png" style="width:6.26772in;height:3.29167in" />

### 4.2.15 Archivos con extensión cambiada

<img src="./media/image22.png" style="width:6.26772in;height:3.54167in" />

### 4.2.16 Archivos eliminados

### <img src="./media/image29.png" style="width:6.26772in;height:2.48611in" />

### 4.2.17 Archivos ocultos

En Linux los archivos ocultos son aquellos que empiezan por punto, así como los directorios ocultos:

<img src="./media/image41.png" style="width:6.26772in;height:3.06944in" />

### 4.2.18 Búsqueda de archivos por autor

<img src="./media/image20.png" style="width:6.26772in;height:3.27778in" />

### 4.2.19 Búsqueda de imágenes por ubicación 

### <img src="./media/image53.png" style="width:6.26772in;height:2.25in" />

# 5. CADENA DE CUSTODIA

Para certificar la cadena de custodia tenemos que tomar una serie de medidas y así garantizar que las evidencias no han sido alteradas, para ello vamos a calcular el hash del disco y la memoria y vamos a seleccionar un identificador único para cada prueba, nada más sacarlo de la máquina que vamos a analizar.

Posterior a ello los ubicamos en un directorio de trabajo propio, donde guardaremos todas las evidencias, y también crearemos en autopsy un caso para el análisis del disco de modo que se lleve a cabo en un directorio ubicado en la máquina que va a realizar el forense.

El forense lo va a realizar Roberto Martín, en una máquina con la siguiente MAC y trabajará con debian 13 como sistema operativo.

Cuando se termine de analizar y buscar en las entrañas de la presunta máquina, volveremos a verificar los hashes de las copias que hemos sacado a las evidencias originales, para comprobar que nada haya sido alterado.

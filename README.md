# Crear categoría
mkdir -p content/posts/base-de-datos/consultas-sql
cp ~/Descargas/"Base de datos - Consultas SQL.docx" content/posts/base-de-datos/consultas-sql/
./tools/convertir.sh


# Añadir a categoría que ya existe
mkdir content/posts/vpn/configurar-openvpn-site-to-site
cp ~/Descargas/"VPN - OpenVPN Site to Site.docx" content/posts/vpn/configurar-openvpn-site-to-site/
./tools/convertir.sh

# Meter plantilla un logo
python3 tools/generar_featured.py "Configurar VPN con Wireguard" tools/logos/wireguard.png content/posts/vpn/acceso-remoto-wireguard/featured.png tools/marca_r.png

# Meter plantilla multilogo
python3 generar_featured.py "Interconexión de bases de datos" logos/oracle.png,logos/postgresql.png,logos/mariadb.png ../content/posts/base-de-datos/interconexión-bd/featured.png marca_r.png


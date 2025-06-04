Bienvenido a la demostración de SMGP.

Requisitos Previos para su sistema Windows:
1. Podman Desktop instalado y corriendo (asegúrese de que esté usando el backend WSL2). 
   Puede descargarlo desde: https://podman-desktop.io/
   Durante la instalación de Podman Desktop, asegúrese de inicializar y iniciar la máquina Podman.
2. Un servidor PostgreSQL instalado y corriendo directamente en su Windows (ej. versión 14, 15 o 16).
   - Durante la instalación de PostgreSQL, se le pedirá crear una contraseña para el superusuario 'postgres'. Anótela.
   - Usando una herramienta como pgAdmin (que se instala con PostgreSQL) o psql:
     a. Conéctese a su servidor PostgreSQL.
     b. Cree una nueva base de datos (ej. llámela 'smgp_cliente').
     c. Cree un nuevo Rol de Login/Usuario (ej. llámelo 'usuario_cliente_db') con una contraseña segura (ej. 'contraseña_cliente_db').
     d. Otorgue todos los permisos a 'usuario_cliente_db' sobre la base de datos 'smgp_cliente'.
   - Asegúrese de que PostgreSQL esté configurado para aceptar conexiones TCP/IP:
     En el archivo 'postgresql.conf' (usualmente en C:\Program Files\PostgreSQL\<version>\data\):
       Descomente y configure 'listen_addresses = '*' (para escuchar en todas las interfaces) o a la IP de su máquina Windows.
     En el archivo 'pg_hba.conf' (en el mismo directorio):
       Añada una línea para permitir la conexión desde la red donde opera WSL2 o desde 'all'.
       Ejemplo (reemplace IP_DE_SU_RED/MASCARA por su configuración, ej. 192.168.1.0/24, o 0.0.0.0/0 para todas las IPs IPv4 para pruebas):
       host    all             all             0.0.0.0/0            scram-sha-256  (o md5)
       host    all             all             ::/0                 scram-sha-256  (o md5)
     Después de cambiar estos archivos, reinicie el servicio de PostgreSQL desde los servicios de Windows.
   - Asegúrese de que el Firewall de Windows permita conexiones entrantes al puerto 5432 para PostgreSQL.

Pasos para Ejecutar la Aplicación:
1. Copie todos los archivos de este medio (mi_smgp_app_imagen.tar, deploy.env, INSTRUCCIONES_WINDOWS_PODMAN.txt) 
   a una carpeta en su máquina (ej. C:\SMGP_Demo_Podman).
2. Abra una terminal donde tenga acceso al comando 'podman' (usualmente PowerShell o CMD después de instalar Podman Desktop y asegurarse de que la máquina Podman esté corriendo).
3. Navegue a la carpeta donde copió los archivos (ej. cd C:\SMGP_Demo_Podman).
4. Cargue la imagen del contenedor en Podman:
   podman load -i mi_smgp_app_imagen.tar
   (Verá la imagen 'localhost/mi-smgp-app:latest' en Podman Desktop después).
5. Edite el archivo 'deploy.env' con un editor de texto:
   - Actualice la línea DATABASE_URL. Reemplace 'IP_WINDOWS_HOST' por la dirección IP actual de su máquina Windows en su red local (ej. 192.168.1.100). También actualice el usuario, contraseña y nombre de la base de datos si son diferentes a los ejemplos.
   - Ejemplo: DATABASE_URL=postgres://usuario_cliente_db:contraseña_cliente_db@192.168.1.100:5432/smgp_cliente
6. Ejecute la aplicación usando Podman (asegúrese de que Podman Desktop y su máquina estén corriendo):
   podman run -d --name contenedor_smgp --env-file ./deploy.env -p 8000:8000 localhost/mi-smgp-app:latest
   
   Nota: El mapeo de puertos '-p 8000:8000' debería permitirle acceder a la aplicación desde su navegador de Windows.
   Si hay problemas de red para que el contenedor alcance PostgreSQL en el host de Windows, la opción '--network=host' podría intentarse, pero su comportamiento con Podman en WSL2 para acceder a servicios del host de Windows puede ser complejo y depender de la configuración de red de WSL2. Empecemos sin ella y con la IP explícita del host.

7. Espere unos 20-30 segundos para que la aplicación se inicie completamente.
8. Abra su navegador web en Windows (Chrome, Edge, Firefox) y vaya a: http://localhost:8000
9. Use las credenciales del superusuario definidas en 'deploy.env'.

Para ver los logs de la aplicación:
En Podman Desktop, puede seleccionar el contenedor 'contenedor_smgp' y ver sus logs.
O desde la terminal: podman logs contenedor_smgp

Para detener la aplicación:
podman stop contenedor_smgp

Para eliminar el contenedor (después de detenerlo):
podman rm contenedor_smgp


# ADATRAP Miner

Programa que se encarga de descargar y procesar datos de viajes y transacciones Transantiago.

## Instalación del proyecto

El proyecto se encuentra desarrollado en Python 3.8 y utiliza los siguientes servicios de Amazon Web Services para su
funcionamiento:
[EC2](https://aws.amazon.com/ec2/), [S3](https://aws.amazon.com/s3/) y [Cloudwatch](https://aws.amazon.com/cloudwatch/).

### Requerimientos

#### Creación de entorno virtual

Para no tener conflictos de dependencias se recomienda hacer uso de
un [entorno virtual](https://docs.python.org/3/tutorial/venv.html), este puede ser creado usando la
librería [virtualenv](https://virtualenv.pypa.io/en/latest/).

```
    # instalar librería virtualenv
    pip install virtualenv

    # crear entorno virtual
    virtualenv venv

    # activar entorno virtual
    source venv/bin/activate
```

#### Instalación de dependencias Python

Las librerías necesarias para ejecutar el proyecto están definidas en el archivo `requirements.txt`
ubicado en la raíz del proyecto y se pueden instalar rápidamente con el comando:

    pip install -r requirements.txt

Además para agregar el comando `adatrap_miner` a las variables de ambiente se debe ejecutar:

    pip install -e .

### Creación de usuario AWS

El funcionamiento del programa se requieren las credenciales de un usuario AWS con permisos **AmazonEC2FullAccess**,
**AmazonS3FullAccess**, **AmazonS3FullAccess**, **CloudWatchAgentServerPolicy** y **CloudWatchAgentAdminPolicy**.
Los siguientes pasos detallan como crear un usuario AWS con los permisos necesarios.

#### 1) Crear usuario

Para crear un usuario nuevo se debe acceder a la plataforma [IAM](https://console.aws.amazon.com/iam/home#/home) de AWS
en la sección [usuarios](https://console.aws.amazon.com/iam/home#/users) y seleccionar la opción **Add User**:

![aws-paso-1](docs/img/1-add-user.png)

#### 2) Nombrar usuario

Posteriormente se debe escribir un nombre de usuario en **User name**, marcar la casilla **Programmatic access** y
avanzar al siguiente paso haciendo click en el botón **Next: permissions**.

![aws-paso-2](docs/img/2-name-user.png)

#### 3) Permisos de Usuario

En esta sección se darán los permisos de EC2, S3 y Cloudwatch al usuario. Para esto debe seleccionar la opción **Attach
existing policies directly**. Posteriormente en el cuadro de búsqueda buscar **EC2Fullaccess** y marcar las casillas **AmazonEC2FullAccess**, **AmazonS3FullAccess**, **CloudWatchAgentAdminPolicy**, **CloudWatchAgentServerPolicy** y **AmazonSSMFullAccess**

Finalmente se puede ir al siguiente paso **Next: Tags**.

![aws-paso-3](docs/img/3-add-policy.png)

##### 4) Tags (Opcional)

Opcionalmente se pueden añadir etiquetas para identificar o almacena datos referente al usuario. Ir al paso siguiente **Next Review**.
![aws-paso-4](docs/img/4-add-tags.png)

##### 5) Review

En esta sección se debe revisar que todos los datos estén correctos y avanzar al siguiente

![aws-paso-5](docs/img/5-review.png)

#### 6) Guardar credenciales

El usuario ha sido creado exitosamente, por lo que es importante guardar sus credenciales en la sección **download.csv**
. Ambas credenciales **Access key ID** y **Secret access key** serán utilizadas para la configuración del proyecto.
![aws-paso-6](docs/img/6-id-secret-key.png)

### Archivo de configuración .env

Se debe crear un archivo .env en la raíz del proyecto el cual incluirá las credenciales y otra información en el
siguiente formato:

    # Id de acceso creado en el paso anterior.
    AWS_ACCESS_KEY_ID=

    # Clave de acceso creado en el paso anterior
    AWS_SECRET_ACCESS_KEY=
    
    # Región donde se ubicará la instancia EC2 (Ejemplo: us-east-1)
    REGION_NAME=
    
    # Id de la imagen a utilizar en la instancia EC2 (Ejemplo: ami-0b697c4ae566cad55, imagen de Microsoft Windows Server 2019 Base) 
    AMI_ID=
    
    # Nombre de la máquina ec2 a utilizar (ej: t2.micro)
    INSTANCE_TYPE=
    
    # Par de claves para acceso ec2 (Si se desea crear una nueva key pair dejar un nombre por defecto.)
    KEY_PAIR=
    
    # Nombre de log de grupo Cloudwatch
    LOG_GROUP=
    
    # Id para el log general
    GENERAL_LOG_STREAM=
    
    # Bucket donde se encuentra ejecutable ADATRAP
    EXECUTABLES_BUCKET=
    
    # Bucket de gps
    GPS_BUCKET_NAME=
    
    # Bucket de po
    OP_PROGRAM_BUCKET_NAME=
    
    # Bucket de archivo 196
    FILE_196_BUCKET_NAME=
    
    # Bucket de transacciones
    TRANSACTION_BUCKET_NAME=
    
    # Bucket S3 donde se almacenan los resultados de ADATRAP
    OUTPUT_DATA_BUCKET_NAME=
    
    # Bucket S3 donde se almacena el archivo de detalle de servicios
    SERVICE_DETAIL_BUCKET_NAME=

    # Version de ejecutable ADATRAP
    EXECUTABLE_VERSION=

### Imagen de Instancia 
Para obtener el ID (AMI_ID) de la imagen a utilizar se debe buscar dentro de las disponibles para el usuario AWS. Por ejemplo, en este [link](https://us-east-2.console.aws.amazon.com/ec2/v2/home?region=us-east-2#LaunchInstanceWizard:) se encuentra un listado de imagenes disponibles.

### Creación de Key Pair

Para la creación de instancias EC2 y el manejo de estas se requiere tener una **keypar** para poder acceder a las
instancias creadas en python. Para esto el programa tiene un comando que permite la creación de un keypar dado los datos
de usuario en el archivo .env (variables **AWS_ACCESS_KEY_ID** y **AWS_SECRET_ACCESS_KEY**).

Este comando crea una keypair con el nombre dado como argumento o **ec2-keypair** por defecto, la cual se registra en
AWS y se almacena localmente en la raíz del proyecto.

Para crear un keypar se debe ejecutar:

    adatrap_miner create-key-pair [key-pair-name]

Si todo resulta correcto se obtendrá el siguiente mensaje:

    INFO:__main__:¡Keypair creado exitosamente! El archivo ec2-keypair.pem se encuentra en la raíz del proyecto.

En caso de que la keypar exista el programa arrojará un error:

    ERROR:__main__:El keypair 'ec2-keypair' ya existe

Ya habiendo sido creada la keypair, esta se encontrará disponible en el panel de administración EC2 de AWS:

![keypar](docs/img/keypar.png)

Después de crear la key-pair es importante agregar su nombre en la variable *KEY_PAIR* archivo *.env*

## Creación de logs en Cloudwatch

Para el funcionamiento de adatrap-Miner se requiere la creación de un log group de Cloudwatch y un log stream. Un log
stream es una secuencia de eventos de log que se comparten en la misma fuente, mientras que un log group es un conjunto
de log streams.

Por lo tanto adatrap-Miner utilizará el log group para crear log streams asociados a las instancias EC2 creadas. Por
otra parte utilizará el log stream creado como un log general de eventos asociados al proyecto.

### Log Group

Para crear un Log Group se debe acceder a la
plataforma [Cloudwatch](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups) y
seleccionar la opción **Create log group**.

Se debe ingresar un nombre en *Log group name*. En la sección *Retention setting* se debe seleccionar la opción "1 week"
. Esto permitirá que los logs se almacenen durante una semana como máximo.

![log-group](docs/img/log-group.png)

Finalmente se debe seleccionar la opción *create*

Es importante agregar el nombre del log group al parámetro *LOG_GROUP* del archivo *.env*

### Log Stream

Para agregar un log stream se debe ingresar al log group creado desde la interfaz de Cloudwatch y seleccionar la
opción *Create log stream*.

![log-stream](docs/img/log-stream.png)

Finalmente también se debe agregar el nombre a la variable *GENERAL_LOG_STREAM* del archivo *.env*.

## Buckets S3

Para el funcionamiento del programa se requiere que las fuentes de datos se encuentren almacenada en buckets de S3. Estos datos son los siguientes:

### Diccionario de Servicios

Estos datos se deben encontrar en el formato YYYY-MM-DD.po.zip, donde YYYY-MM-DD representa desde que día es válido el diccionario. Sus archivos internos deben estar en formato gz.

El nombre del bucket asociado a los diccionarios de servicio debe ingresarse como valor en la variable **OP_PROGRAM_BUCKET_NAME** del archivo .env


### Datos gps
Los datos de gps deben estar en formato YYYY-MM-DD.gps.gz donde YYYY-MM-DD representa el día donde el archivo es válido.

Se debe almacenar el nombre del bucket en la variable **GPS_BUCKET_NAME** del archivo .env

### Datos 196
Estos datos deben tener el formato YYYY-MM-DD.196.gz donde YYYY-MM-DD representa el día donde el archivo es válido.

El nombre de este bucket se debe almacenar en la variable **FILE_196_BUCKET_NAME** del archivo .env

### Datos de transacciones
Los datos se deben encontrar en formato YYYY-MM-DD.trx.gz donde YYYY-MM-DD representa el día donde el archivo es válido.

El nombre del bucket se debe almacenar en la variable **TRANSACTION_BUCKET_NAME** en el archivo .env

### Datos de detalle de servicio
Este archivo debe estar en formato Diccionario-DetalleServicioZP_YYYYMMDD_YYYYMMDD.csv.gz donde el primer el par YYYYMMDD representan desde que día hasta que día es válido el archivo.

El nombre de este bucket se debe almacenar en la variable SERVICE_DETAIL_BUCKET_NAME  

### Archivos ejecutables 
#### ADATRAP
El archivo ejecutable ADATRAP se debe encontrar en un bucket con el formato pvmtsc_vX.exe donde X es la versión del programa.

#### Archivo de configuración de ADATRAP
El archivo de configuración de ADATRAP se debe encontrar en el mismo bucket, con formato pvmtsc_vX.par donde X es la versión del archivo.

Ambas versiones de los archivos deben ser la misma para el correcto funcionamiento.

Un ejemplo de un archivo configurable de configuración compatible con la versión 0.2 se encuentra [aquí](docs/pvmtsc_v0.2.par)

El nombre del bucket se debe almacenar en la variable **EXECUTABLES_BUCKET** 
y la versión del ejecutable en la variable **EXECUTABLE_VERSION** del archivo .env
## Ejecución de tests

Es recomendable ejecutar los tests del programa para verificar su correcto funcionamiento:

    python -m unittest


## Uso

Para ejecutar adatrap_miner se deben ejecutar el comando con la fecha en formato YYYY-MM-DD

    adatrap_miner create-ec2-instance 2021-04-22

Si se crea la instancia correctamente se desplegará un mensaje como el siguiente:
    
      adatrap_miner create-ec2-instance 2020-06-28
    > INFO:adatrap_miner:Creando instancia para el día 2020-06-28...
    > INFO:adatrap_miner:Instancia creada con id: i-074c9c8020b3e24d0 para el día 2020-06-28
    > INFO:adatrap_miner:Creando log stream para instancia i-074c9c8020b3e24d0...
    > INFO:adatrap_miner:Log Stream creado con nombre: i-074c9c8020b3e24d0

Al ejecutarse el comando se creará una instancia EC2 con un id. También se creará un log stream en cloudwatch con nombre del id de la instancia creada.

Este id puede ser utilizado para detener la instancia manualmente u obtener los logs asociado a su funcionamiento.

## Comandos disponibles

### Detener instancia EC2

Para detener una instancia EC2 se debe ejecutar

    adatrap_miner stop-ec2-instance ID

Donde *ID* es el id de la instancia.

Si la instancia existe se desplegará un mensaje como el siguiente:
    
    adatrap_miner stop-ec2-instance i-01467ca70263c5b71
    > INFO:adatrap_miner:Finalizando instancia con id i-01467ca70263c5b71...
    > INFO:adatrap_miner:Instancia con id i-01467ca70263c5b71 finalizada.


### Obtener logs

Para obtener los logs asociados a un log stream se debe ejecutar

    adatrap_miner get-log-stream LOGNAME

Donde *LOGNAME* es el nombre del log stream.

Si se quiere almacenar en un archivo se debe
utilizar la variable -o

    adatrap_miner get-log-stream LOGNAME -o OUTPUTNAME



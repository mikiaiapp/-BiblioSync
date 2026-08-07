# BiblioSync - Organizador y Sincronizador de Libros Electrónicos (Web App)

BiblioSync es una aplicación web moderna diseñada para automatizar la organización de tu biblioteca de libros electrónicos y sincronizarla con **Calibre**.

Escanea carpetas de origen (como tu directorio de descargas) buscando libros que no estén registrados en tu biblioteca de Calibre, los unifica en una carpeta de destino resolviendo de forma segura cualquier colisión de nombres (renombrado automático) y genera informes detallados en Excel y CSV de las operaciones.

Está desarrollada como una **aplicación web nativa** utilizando **FastAPI** en el backend y una interfaz moderna con diseño responsive en el frontend. Su contenedorización ligera es perfecta para desplegarse de manera directa en servidores NAS (Synology, Unraid, TrueNAS) a través de **Portainer**, sin necesidad de entornos gráficos virtuales ni noVNC.

---

## Características Principales

1. **Interfaz Web Nativa:** Acceso directo desde tu navegador web a una interfaz moderna con modo oscuro, diseño de estilo *glassmorphism* (cristal esmerilado) y transiciones fluidas.
2. **Explorador de Carpetas Integrado (Server-Side):** Permite navegar y seleccionar cualquier directorio de tu NAS directamente desde la interfaz web, de manera visual e intuitiva.
3. **Indexación Diferencial:** Mantiene un índice local SQLite de tu biblioteca de Calibre. Detecta libros nuevos, modificados y eliminados a alta velocidad (orden $O(1)$) mediante consultas optimizadas.
4. **Estrategias de Comparación Flexibles:**
   - **Nombre y Tamaño (Name & Size):** Comparación rápida basada en nombre de archivo y peso en bytes.
   - **Contenido hash (SHA256):** Comprobación binaria exacta basada en el hash de los archivos.
   - **Identificador (ISBN):** Extrae metadatos y compara los libros basándose en el ISBN.
   - **Título y Autor (Title & Author):** Extrae y normaliza los metadatos internos del libro para su comparación.
5. **Copia Plana con Resolución de Colisiones:** Copia los libros nuevos a una carpeta unificada. Si el nombre coincide con un archivo existente, añade un sufijo incremental (ej. `Libro (1).epub`, `Libro (2).epub`).
6. **Reportes y Auditoría Automáticos:**
   - **Informe en Excel (`informe_bibliosync.xlsx`):** Genera un libro multi-pestaña estilizado (Libros Copiados, Errores y Resumen Estadístico general).
   - **Informes CSV:** Exporta los mismos datos a ficheros CSV individuales bajo la subcarpeta `informes_csv`.
7. **Historial de Ejecuciones:** Almacena de forma persistente y muestra una tabla con las estadísticas de las últimas sincronizaciones realizadas.
8. **Ejecución Asíncrona Hilo-Segura:** Los procesos pesados (escaneo, copia, indexación) se ejecutan en segundo plano en el servidor y transmiten el progreso en tiempo real mediante WebSockets, evitando que la interfaz se congele.

---

## Estructura del Proyecto

```text
.
├── src/
│   ├── main.py                  # Servidor web FastAPI (Punto de entrada)
│   ├── config/
│   │   └── settings.py          # Gestor de configuraciones JSON
│   ├── core/
│   │   ├── scanner.py           # Escáner recursivo de directorios de origen
│   │   ├── indexer.py           # Indexador de biblioteca Calibre
│   │   ├── comparer.py          # Estrategias de comparación (Strategy Pattern)
│   │   ├── copier.py            # Copiador de archivos con renombrado seguro
│   │   ├── metadata.py          # Extractor de metadatos (ebooklib, pypdf)
│   │   └── hashing.py           # Cálculo de hash SHA256
│   ├── database/
│   │   ├── database.py          # Inicialización y gestión de conexiones SQLite
│   │   └── models.py            # Modelos de datos
│   ├── export/
│   │   ├── excel_export.py      # Exportador estilizado de informe Excel (openpyxl)
│   │   └── csv_export.py        # Exportador a archivos CSV separados
│   └── web/                     # Interfaz gráfica web (Dashboard)
│       ├── index.html           # Estructura del panel de control
│       ├── style.css            # Estilos CSS premium modo oscuro y responsivo
│       └── app.js               # Cliente JS (WebSockets, API, explorador de carpetas)
├── tests/
│   └── test_sync.py             # Suite de pruebas unitarias automatizadas
├── Dockerfile                   # Imagen de docker optimizada y ultraligera
├── docker-compose.yml           # Archivo compose para orquestar la app
├── requirements.txt             # Dependencias del proyecto
└── README.md                    # Documentación del proyecto
```

---

## Ejecución Local (Windows / Linux)

### Requisitos Previos
Tener instalado Python 3.11, 3.12 o 3.13.

### Pasos
1. Clona el repositorio:
   ```bash
   git clone https://github.com/mikiaiapp/-BiblioSync.git
   cd -BiblioSync
   ```
2. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecuta la aplicación como un módulo:
   ```bash
   python -m src.main
   ```
4. Abre tu navegador e ingresa a: `http://localhost:6080`

---

## Despliegue en Portainer (NAS)

### 1. Carpetas y Volúmenes a crear en tu NAS
Para un funcionamiento correcto y acotado, configurarás los siguientes tres volúmenes en el contenedor:

* **`/volume1/docker/bibliosync/data` (Mapeado a `/data`)**: Almacenará la configuración de la app (`settings.json`) y la base de datos local SQLite (`bibliosync.db`) para que persistan entre reinicios del contenedor.
* **`/volume1/docker/calibreweb` (Mapeado a `/calibreweb`)**: La ubicación de tu biblioteca de Calibre (por ejemplo, conteniendo la subcarpeta `Biblioteca` con el archivo `metadata.db` de Calibre).
* **`/volume1/homes/MIKI/Descargas` (Mapeado a `/descargas`)**: Tu directorio de descargas en el NAS (donde `MIKI` es tu nombre de usuario en el NAS, sustitúyelo si es necesario). Esta carpeta se utilizará tanto para ubicar los libros a analizar (orígenes) como para guardar los libros seleccionados para importar (destino).

### 2. Variables de Entorno
* **`RESOLUTION`** *(Opcional)*: No aplica en este modo web nativo. El diseño web es responsivo y se adapta de forma automática al tamaño de pantalla de tu navegador o dispositivo.

---

### 3. Configuración del despliegue en Portainer (Paso a Paso)

Puedes desplegar BiblioSync en Portainer fácilmente enlazando directamente este repositorio de GitHub:

1. Accede a tu panel de **Portainer**.
2. Ve a la sección **Stacks** en tu entorno y haz clic en **Add stack**.
3. Ponle un nombre identificativo (ej. `bibliosync`).
4. En **Build method**, selecciona **Repository**.
5. Rellena los campos con los siguientes datos del repositorio:
   - **Repository URL:** `https://github.com/mikiaiapp/-BiblioSync`
   - **Repository reference:** `refs/heads/main`
   - **Compose path:** `docker-compose.yml`
6. **Modificar los mapeos de volúmenes (Binds):**
   Edita la configuración para adaptar los directorios físicos de tu NAS a las rutas virtuales del contenedor indicadas en el `docker-compose.yml` (recuerda cambiar `MIKI` por tu usuario de NAS si es diferente):
   
   ```yaml
   services:
     bibliosync:
       build: .
       container_name: bibliosync
       ports:
         - "6080:6080"
       volumes:
         # Ruta persistente de datos de la app (BD y configuraciones)
         - /volume1/docker/bibliosync/data:/data
         # Acceso a la biblioteca de Calibre (para indexar metadata.db)
         - /volume1/docker/calibreweb:/calibreweb
         # Carpeta de descargas
         - /volume1/homes/MIKI/Descargas:/descargas
       restart: unless-stopped
   ```
7. Pulsa en **Deploy the stack**. Portainer descargará el repositorio, compilará la imagen de Docker a partir del `Dockerfile` e iniciará el contenedor automáticamente en pocos segundos debido a su arquitectura web ultraligera.

---

### 4. Acceso y Uso

Una vez que el Stack se haya desplegado y muestre el estado **Running**:

1. Abre tu navegador web e ingresa a:
   ```text
   http://<IP_DE_TU_NAS>:6080
   ```
2. Se abrirá directamente el cuadro de mando de **BiblioSync**:
   - Pulsa en **Examinar** al lado de *Biblioteca Calibre* y selecciona `/calibreweb/Biblioteca` en el explorador de carpetas modal.
   - Pulsa en **Examinar** al lado de *Carpeta Destino* y selecciona `/descargas/importar` (o la subcarpeta que prefieras usar para recibir los libros limpios).
   - Haz clic en **Añadir Carpeta** y añade `/descargas/carpetas_a_analizar` para escanear tus nuevos libros descargados.
   - Elige el método de comparación deseado en la lista desplegable.
   - Pulsa en **Analizar** y verás la barra de progreso y la consola de logs en vivo.
   - Pulsa en **Copiar Libros** para organizar tu catálogo de lectura automáticamente y generar los reportes de importación.

# BiblioSync - Sincronizador de Libros Electrónicos

BiblioSync es una herramienta profesional diseñada para automatizar la organización de bibliotecas de libros electrónicos y su sincronización con **Calibre**. 

Escanea directorios de origen (carpetas de descarga, almacenamiento temporal, etc.) buscando libros nuevos que no se encuentren registrados en la biblioteca principal de Calibre, los copia a una carpeta destino unificada resolviendo colisiones de nombres de forma segura y genera informes interactivos en Excel y CSV de las operaciones realizadas.

Además, cuenta con soporte completo de contenedorización Docker con interfaz web gráfica integrada (**noVNC**), ideal para despliegues en servidores NAS domésticos (Synology, Unraid, TrueNAS) gestionados a través de **Portainer**.

---

## Características Principales

1. **Indexación Diferencial:** Escanea y mantiene un índice local SQLite de tu biblioteca principal de Calibre para comparar a alta velocidad, detectando nuevas incorporaciones, modificaciones en disco y eliminaciones.
2. **Escaneo Recursivo y Selectivo:** Busca libros en formatos de lectura admitidos (`.epub`, `.pdf`, `.mobi`, `.azw`, `.azw3`, `.fb2`, `.djvu`, `.cbz`, `.cbr`) en múltiples carpetas de origen, omitiendo ficheros temporales e imágenes (.jpg, .png, .opf, thumbs.db, etc.).
3. **Estrategias de Comparación Flexibles:**
   - **Nombre y Tamaño (Name & Size):** Comparación ultra rápida por nombre y tamaño exacto.
   - **Contenido hash (SHA256):** Comprobación binaria exacta basada en el contenido físico del fichero.
   - **Identificador (ISBN):** Extrae metadatos y compara los libros basándose en su ISBN.
   - **Título y Autor (Title & Author):** Extrae metadatos internos del libro y normaliza la comparación por coincidencias de título y creador.
4. **Copia Flat con Resolución de Colisiones:** Copia todos los libros identificados a una sola carpeta plana de destino. Si un libro ya existe en el destino, le asigna un sufijo incremental único (ej. `Libro (1).epub`, `Libro (2).epub`) de forma automática.
5. **Reportes y Auditoría Automáticos:**
   - **Informe en Excel (`informe_bibliosync.xlsx`):** Genera un libro multi-pestaña estilizado (Libros Copiados, Errores de Lectura/Copia y Resumen Estadístico general).
   - **Informes CSV:** Exporta los mismos datos a ficheros CSV individuales bajo la subcarpeta `informes_csv`.
6. **Interfaz Gráfica Concurrente (Hilo-Segura):** Desarrollada con la estética moderna de CustomTkinter. Ejecuta todas las operaciones de indexación, escaneo y copia en hilos secundarios para que la interfaz nunca se congele.

---

## Estructura del Proyecto

```text
.
├── src/
│   ├── main.py                  # Punto de entrada de la aplicación
│   ├── config/
│   │   └── settings.py          # Gestor de configuraciones JSON
│   ├── core/
│   │   ├── scanner.py           # Escáner recursivo de directorios de origen
│   │   ├── indexer.py           # Indexador incremental de biblioteca Calibre
│   │   ├── comparer.py          # Estrategias de filtrado y comparación (Patrón Strategy)
│   │   ├── copier.py            # Copiador físico y resolución de colisiones
│   │   ├── metadata.py          # Extractor de metadatos (ebooklib, pypdf)
│   │   └── hashing.py           # Cálculo de hash SHA256 de archivos
│   ├── database/
│   │   ├── database.py          # Inicialización y gestión de conexiones SQLite (auto-close)
│   │   └── models.py            # Modelos de datos (Dataclasses)
│   ├── export/
│   │   ├── excel_export.py      # Exportador estilizado de informe de Excel (openpyxl)
│   │   └── csv_export.py        # Exportador a archivos CSV separados
│   ├── gui/
│   │   ├── main_window.py       # Ventana principal del cuadro de mando (CustomTkinter)
│   │   ├── settings_window.py   # Ventana de configuración avanzada (Stub)
│   │   └── progress_dialog.py   # Diálogo modal de progreso en tiempo real
│   └── utils/
│       ├── logger.py            # Logger del sistema (consola de GUI y ficheros .log)
│       └── helpers.py           # Funciones de formateo y rutas únicas
├── tests/
│   └── test_sync.py             # Suite de pruebas unitarias automatizadas
├── Dockerfile                   # Imagen de docker con Xvfb + noVNC incorporado
├── docker-compose.yml           # Archivo compose para orquestar la app
├── supervisord.conf             # Configurador de supervisord para arrancar el servidor VNC
├── requirements.txt             # Dependencias del proyecto
├── build.bat                    # Script para compilar el ejecutable local en Windows
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
3. Ejecuta la aplicación:
   ```bash
   python src/main.py
   ```

*(Opcional) Si quieres compilar un ejecutable independiente de Windows (`dist/BiblioSync.exe`), ejecuta en tu consola:*
```bash
build.bat
```

---

## Despliegue en Portainer (NAS)

El contenedor Docker de BiblioSync viene preconfigurado con un servidor X11 virtual (Xvfb), un gestor de ventanas ligero (Fluxbox), un servidor VNC (x11vnc) y un cliente web noVNC. Esto permite acceder a la interfaz de usuario directamente desde **cualquier navegador web**, sin necesidad de instalar clientes en tu ordenador.

### 1. Carpetas y Volúmenes a crear en tu NAS
Antes de desplegar el contenedor, te recomendamos estructurar las carpetas en tu NAS (por ejemplo, dentro del volumen principal `/volume1` de Synology) para mapearlas correctamente al contenedor:

* **`/volume1/docker/bibliosync/data`**: Almacenará la configuración de la app (`settings.json`) y la base de datos local SQLite (`bibliosync.db`) para que persistan entre reinicios del contenedor.
* **`/volume1/libros/calibre`**: Tu biblioteca principal de libros gestionada por Calibre (contiene la base de datos `metadata.db` de Calibre y los directorios de autores).
* **`/volume1/libros/descargas`**: Carpeta de origen donde descargas o almacenas temporalmente nuevos ebooks a analizar.
* **`/volume1/libros/importar`**: Carpeta de destino donde se enviarán los libros listos para que los importes a Calibre sin duplicados.

### 2. Variables de Entorno
* **`RESOLUTION`** *(Opcional)*: Define la resolución de pantalla de la interfaz gráfica en el navegador. Por defecto es `1280x720`. Ejemplo: `RESOLUTION=1440x900` para pantallas de mayor resolución.

---

### 3. Configuración del despliegue en Portainer (Paso a Paso)

Puedes desplegar BiblioSync en Portainer fácilmente enlazando directamente este repositorio de GitHub:

1. Accede a tu panel de **Portainer**.
2. Ve a la sección **Stacks** en tu entorno y haz clic en **Add stack**.
3. Ponle un nombre identificativo (ej. `bibliosync`).
4. En **Build method**, selecciona **Repository**.
5. Rellena los campos con los siguientes datos del repositorio:
   - **Repository URL:** `https://github.com/mikiaiapp/-BiblioSync`
   - **Repository reference:** `refs/heads/main` (o déjalo vacío para usar la rama principal).
   - **Compose path:** `docker-compose.yml`
6. En la sección **Environment variables**, puedes añadir variables de entorno adicionales si deseas personalizar la resolución:
   - Añade una variable con nombre `RESOLUTION` y el valor deseado (ej. `1280x720`).
7. **Modificar los mapeos de volúmenes (Binds):**
   Asegúrate de editar la configuración en la interfaz para adaptar los directorios físicos de tu NAS a las rutas virtuales del contenedor indicadas en el `docker-compose.yml`:
   
   ```yaml
   services:
     bibliosync:
       build: .
       container_name: bibliosync
       ports:
         - "6080:6080"
       volumes:
         # Ruta persistente de datos de la app
         - /volume1/docker/bibliosync/data:/data
         # Acceso a la biblioteca de Calibre (solo lectura o lectura/escritura)
         - /volume1/libros/calibre:/calibre_library
         # Acceso a carpetas de origen para escanear
         - /volume1/libros/descargas:/source_books
         # Acceso a carpeta de destino para el copiado
         - /volume1/libros/importar:/destination_books
       environment:
         - RESOLUTION=1280x720
       restart: unless-stopped
   ```
8. Pulsa en **Deploy the stack**. Portainer descargará el repositorio, compilará la imagen de Docker a partir del `Dockerfile` e iniciará el contenedor automáticamente.

---

### 4. Acceso y Uso

Una vez que el Stack se haya desplegado y muestre el estado **Running**:

1. Abre tu navegador web preferido.
2. Navega a la siguiente dirección:
   ```text
   http://<IP_DE_TU_NAS>:6080
   ```
3. Se abrirá la consola de noVNC mostrando la aplicación **BiblioSync** lista para usar:
   - Introduce `/calibre_library` en el campo **Biblioteca Calibre**.
   - Introduce `/destination_books` en el campo **Carpeta Destino**.
   - Haz clic en **Añadir Carpeta** y selecciona `/source_books` para escanear.
   - Elige tu método de comparación y pulsa en **Analizar** y luego en **Copiar Libros** para organizar tu catálogo de lectura automáticamente.

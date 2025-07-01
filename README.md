# 🛩️ Agente RAG para Asistir al Piloto por Comandos de Voz - TFM

Este proyecto consiste en la creación de un asistente para el piloto, que permite la comunicación por voz. El sistema abarca desde el reconocimiento de voz (Speech to Text) hasta el agente RAG, encargado de entender la consulta y generar la respuesta utilizando la base de datos proporcionada.

---

## ⭐ Consideraciones principales

- **🖥️ Ejecución local:** Todo el sistema funciona completamente offline, sin conexión a internet, garantizando la seguridad y la integración en sistemas aeronáuticos.
- **🧩 Arquitectura de microservicios:** Cada microservicio realiza una acción específica.
- **💻 Desarrollo:** El proyecto se ha desarrollado en Visual Studio Code sobre Ubuntu WSL.

---

## ⚙️ Instalación inicial

Antes de comenzar, asegúrate de tener instalado lo siguiente:

1. **📝 Visual Studio Code**  
   Descárgalo desde [Visual Studio Code](https://code.visualstudio.com/download)

2. **🐧 Ubuntu WSL** (si trabajas desde Windows)  
   - [Guía de instalación de WSL](https://learn.microsoft.com/es-es/windows/wsl/install)

3. **🔗 Git**
   - Instalación:
     ```bash
     sudo apt install git
     ```
   - Configura tu usuario de Git:
     ```bash
     git config --global user.name "Tu Nombre"
     git config --global user.email "tu@email.com"
     ```
   - (Recomendado) Configura autenticación SSH para mayor seguridad:
     ```bash
     ssh-keygen -t ed25519 -C "tu@email.com"
     ```
     Durante la generación de la clave, puedes establecer una **passphrase** (contraseña) para proteger tu clave privada SSH.  
     Si la estableces, cada vez que uses la clave se te pedirá la contraseña.
     ```bash
     eval "$(ssh-agent -s)"
     ssh-add ~/.ssh/id_ed25519
     cat ~/.ssh/id_ed25519.pub
     ```
     Copia la clave pública y añádela a tu cuenta de GitHub en [SSH keys](https://github.com/settings/keys).

4. **🐍 Python 3.x y entorno virtual (obligatorio)**

   - **En Linux/WSL:**  
     Instala Python y pip:
     ```bash
     sudo apt update && sudo apt install python3 python3-pip python3.10-venv
     ```
     Crea y activa un entorno virtual:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
     Para desactivar el entorno virtual:
     ```bash
     deactivate
     ```

   - **En Windows:**  
     Descarga e instala Python desde [python.org](https://www.python.org/downloads/).  
     Luego, en CMD:
     ```cmd
     python -m venv venv
     venv\Scripts\activate
     ```
     En PowerShell:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
     Para desactivar el entorno virtual (CMD o PowerShell):
     ```cmd
     deactivate
     ```

   > **ℹ️ Nota:** Recuerda activar el entorno virtual cada vez que vayas a trabajar en el proyecto y desactivarlo con `deactivate` cuando hayas terminado.

---

## 🚀 Uso del proyecto

1. Clona este repositorio (cambia *usuario* por tu usuario de GitHub):

   - Por HTTPS:
     ```bash
     git clone https://github.com/usuario/TFM-RAG-agent-for-pilot-by-voice-commands.git
     ```

   - Por SSH (requiere clave configurada):
     ```bash
     git clone git@github.com:usuario/TFM-RAG-agent-for-pilot-by-voice-commands.git
     ```

2. Activa el entorno virtual (ver instrucciones arriba).
3. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecuta los microservicios según la documentación de cada uno.

---

## 🗂️ Estructura del proyecto

A continuación, se muestra la idea inicial de la estructuración del proyecto:

```
📁 .github/                  # ⚙️ Configuraciones de GitHub (workflows para CI)
│   ├── workflows/
│   │   ├── ci.yml          # 🔄 Integración Continua (tests, linting, build Docker images)
│   │   └── ...             # 🚫 No se requiere un cd.yml complejo si no hay despliegue remoto
│   └── ISSUE_TEMPLATE.md   # 📝 Plantilla para incidencias
📁 docs/                    # 📚 Documentación del proyecto
│   ├── arquitectura.md     # 🏗️ Diagramas y descripción de la arquitectura
│   ├── requisitos.md
│   ├── api_reference.md    # 📖 Documentación de las APIs internas
│   ├── setup_local.md      # 🛠️ Guía de configuración local
│   └── user_guide.md       # 👤 Guía de usuario
📁 models_data/              # 🤖 Modelos de IA y datos grandes pre-descargados
│   ├── whisper_models/             # 🗣️ Modelos base de Whisper
│   ├── fine_tuned_whisper_models/  # 🛠️ Modelos Whisper fine-tuned
│   ├── llm_models/                 # 🧠 Modelos LLM
│   ├── knowledge_base_docs/        # 📄 Documentos fuente
│   ├── vector_db_data/             # 🗃️ Archivos de la DB vectorial
│   └── whisper_finetune_dataset/   # 🎵 Dataset de audio y transcripciones
📁 scripts/                  # 🛠️ Scripts auxiliares
│   ├── setup_env.sh        # ⚙️ Instalar dependencias, crear venvs
│   ├── run_dev.sh          # 🚀 Levantar docker-compose en modo dev
│   ├── run_prod.sh         # 🚀 Levantar docker-compose en modo prod
│   ├── download_models.py  # ⬇️ Descargar modelos grandes
│   ├── seed_db.py          # 🌱 Poblar la base de datos
│   ├── ingest_docs.py      # 📥 Ingestar documentos
│   ├── create_vector_db.py # 🏗️ Inicializar la DB vectorial
│   ├── cleanup.sh          # 🧹 Limpiar contenedores/volúmenes Docker
│   └── test_api.py         # 🧪 Testear la API
📁 services/                 # 🧩 Microservicios principales
│   ├── ingestion/          # 📥 Ingesta y procesamiento de documentos
│   ├── asr/                # 🗣️ ASR con Whisper
│   ├── nlp-agentic-rag/    # 🤖 NLP / Agente RAG
│   ├── tts/                # 🔊 Text-to-Speech
│   └── avionics-simulator/ # ✈️ Simulación de aviónica
📁 common/                   # 🔗 Módulos/librerías compartidas
│   ├── utils/              # 🛠️ Utilidades comunes
│   └── models/             # 📦 Modelos de datos compartidos
📁 infrastructure/           # 🏗️ Configuración de orquestación local
│   ├── docker-compose.yml      # 🐳 Orquestación para desarrollo
│   ├── docker-compose.prod.yml # 🐳 Orquestación para producción
│   ├── .env.dev                # ⚙️ Variables de entorno dev
│   ├── .env.prod               # ⚙️ Variables de entorno prod
│   └── README.md               # 📖 Instrucciones de infraestructura
📁 notebooks/                # 📓 Jupyter Notebooks para experimentación
│   ├── data_exploration.ipynb
│   └── whisper_fine_tuning.ipynb
📁 tests/                    # 🧪 Tests globales
│   ├── unit/                # 🧩 Tests unitarios
│   └── e2e/                 # 🔄 Tests end-to-end
│       └── e2e_tests.py
📝 .gitignore                # 🚫 Ignorar archivos/carpetas
📝 LICENSE                   # 📄 Licencia del proyecto
📝 README.md                 # 📘 README principal
📝 CONTRIBUTING.md           # 🤝 Guía para contribuyentes
📝 pyproject.toml            # ⚙️ Configuración de proyectos Python
```

---

## 🤝 Contribución
Dicho proyecto se ha inicializado gracias al proyecto de la asignatura de Aviónica Avanzada del Máster Universitario en Ingeniería Aeronáutica de la Universidad de Sevilla y de los proyectos internos del grupo empresarial Oesía, en concreto al Centro de Competencias de Inteligencia Artificial & Data.

Si deseas contribuir, por favor abre un issue o un pull request.

---

## 📄 Licencia

Actualmente no se ha incluido ningún tipo de licencia. **Pendiente de realizarla**
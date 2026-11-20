# ARCHITECTURE.md — Super App Ecosystem (Horizonte 4 Años)

## 1. Visión Arquitectónica
Este proyecto implementa una **Super App** bajo el patrón de **Monolito Modular (Modular Monolith)** en el backend y **Arquitectura Multi-Módulo (Feature-First + Clean Architecture)** en el cliente móvil/web. 
El objetivo es mantener un despliegue unificado durante los Años 1 y 2, garantizando que cualquier módulo pueda extraerse a un microservicio independiente en los Años 3 y 4 en menos de 24 horas sin reescribir lógica de negocio.

---

## 2. Estructura del Monorepo
```text
super-app/
├── ARCHITECTURE.md                 # Leyes inquebrantables del repositorio
├── .antigravity/                   # Reglas de contexto y prompts de agentes
├── shared-contracts/               # Esquemas OpenAPI / JSON Schema (Fuente de la verdad)
├── backend/                        # Monolito Modular en Python (FastAPI)
│   ├── app/
│   │   ├── main.py                 # Punto de entrada y ensamblaje de routers
│   │   ├── core/                   # Auth JWT, Config, Event Bus, DB Session
│   │   └── modules/                # BOUNDED CONTEXTS (Aislamiento estricto)
│   │       ├── identity/           # Usuarios, Perfiles, Permisos
│   │       ├── media_ai/           # Procesamiento de video, IA, Visión/Audio
│   │       ├── commerce/           # Catálogo, Carrito, Órdenes, Inventario
│   │       └── wallet/             # Pagos, Transacciones, Ledger
│   └── tests/                      # Tests unitarios y de arquitectura
└── client-mobile/                  # Android / KMP (Jetpack Compose)
    ├── app/                        # App Shell (Navegación global + DI con Hilt/Koin)
    ├── core/                       # Módulos base compartidos
    │   ├── network/                # Cliente HTTP (Retrofit/Ktor) + Interceptores
    │   ├── database/               # Persistencia local (Room / SQLDelight)
    │   ├── designsystem/           # Componentes UI atómicos, Temas, Animaciones
    │   └── eventbus/               # Comunicación desacoplada en cliente
    └── features/                   # Mini-Apps internas (Aislamiento estricto)
        ├── feat_auth/
        ├── feat_studio/
        ├── feat_shop/
        └── feat_wallet/
```

---

## 3. Anatomía Interna de Cada Módulo (Clean Architecture)
Tanto en `backend/app/modules/<modulo>` como en `client-mobile/features/<feature>`, la estructura interna es obligatoria y sigue la Regla de Dependencia (las capas internas no conocen a las externas):

```text
<nombre_modulo>/
├── domain/             # CAPA 1 (Núcleo Puro): Entidades, Value Objects, Excepciones de Dominio, Interfaces de Repositorio. (PROHIBIDO importar frameworks, ORMs o librerías de UI aquí).
├── application/        # CAPA 2 (Casos de Uso): Orquestación de negocio, Comandos, Queries, DTOs internos, Eventos emitidos/escuchados.
├── infrastructure/     # CAPA 3 (Adaptadores): Implementación de Repositorios (SQLAlchemy/Room), Modelos de Base de Datos, Clientes de APIs externas, Workers (Celery/FFmpeg).
├── presentation/       # CAPA 4 (Entrada/UI): 
│   ├── (Backend)       # Routers FastAPI, Esquemas Pydantic Request/Response.
│   └── (Móvil)         # Screens (Jetpack Compose), ViewModels, UI State, UI Events.
└── public_api.py / .kt # ÚNICO punto de contacto expuesto hacia el resto del sistema.
```

---

## 4. Las 5 Leyes Inquebrantables (Cero Deuda Técnica)

### Ley 1: Prohibición de Importaciones Cruzadas entre Módulos
* **PROHIBIDO:** Que el módulo `commerce` importe clases de `domain`, `infrastructure` o `presentation` del módulo `wallet` o `identity`.
* **PERMITIDO:** Comunicarse exclusivamente a través del archivo `public_api` del otro módulo o mediante eventos asíncronos a través de `core/event_bus`.

### Ley 2: Aislamiento de Base de Datos por Esquema (Sin JOINs Cruzados)
* Cada módulo del backend posee su propio esquema en PostgreSQL (`identity_schema`, `media_ai_schema`, `commerce_schema`, `wallet_schema`).
* **PROHIBIDO:** Hacer `JOIN` en SQL o `ForeignKey` directa de SQLAlchemy entre tablas de distintos módulos.
* **SOLUCIÓN:** Almacenar únicamente el `user_id` o `product_id` como `UUID` simple y validar su existencia consultando la interfaz pública del módulo correspondiente o mediante consistencia eventual por eventos.

### Ley 3: Pureza Absoluta del Dominio
* La carpeta `domain/` solo puede contener código nativo de Python o Kotlin estándar.
* **PROHIBIDO:** Importar `fastapi`, `sqlalchemy`, `androidx.*`, `retrofit` o `room` dentro de `domain/`. Si necesitas cambiar de base de datos o framework en el Año 3, `domain/` y `application/` no deben sufrir ni una sola línea de cambio.

### Ley 4: Patrón UDF (Unidirectional Data Flow) en Cliente Móvil
* Toda pantalla en Jetpack Compose (`presentation/`) debe ser **Stateless** en su nodo principal, recibiendo únicamente un objeto inmutable `UiState` y una lambda `onEvent: (UiEvent) -> Unit`.
* Los ViewModels nunca exponen flujos mutables (`MutableStateFlow`); solo exponen `StateFlow<UiState>`.

### Ley 5: Tareas Pesadas Fuera del Hilo Principal
* Cualquier operación que supere los 200ms (procesamiento de video, inferencia de IA, generación de archivos, envío de correos) nunca se ejecuta dentro del ciclo HTTP de FastAPI ni en el Main Thread de Android. Debe encolarse como tarea asíncrona y notificar su progreso mediante WebSockets, Server-Sent Events (SSE) o estado local reactivo.

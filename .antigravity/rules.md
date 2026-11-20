# Reglas de Ejecución para el Agente Antigravity

Siempre que generes, modifiques o refactorices código en este proyecto, estás obligado a cumplir este protocolo:

## 1. Protocolo Pre-Codificación (Planificación Obligatoria)
Antes de escribir cualquier bloque de código, responde brevemente con un bloque **[CHECK ARQUITECTÓNICO]**:
1. **Módulo objetivo:** Indica en qué módulo exacto vas a trabajar (`modules/<x>` o `features/<y>`).
2. **Capas afectadas:** Especifica qué archivos tocarás en `domain`, `application`, `infrastructure` o `presentation`.
3. **Verificación de fronteras:** Confirma que no estás importando clases internas de ningún otro módulo hermano.

## 2. Flujo de Creación de Funcionalidades (Contrato Primero)
Nunca generes una pantalla de UI y una tabla de base de datos al mismo tiempo sin definir antes las capas intermedias. Sigue siempre este orden estricto:
1. **Paso 1 (Domain):** Crea la Entidad pura y la Interfaz del Repositorio.
2. **Paso 2 (Application):** Crea el Caso de Uso (`UseCase`) y los DTOs/Eventos necesarios.
3. **Paso 3 (Infrastructure):** Implementa el Repositorio (SQLAlchemy en Python / Room + Retrofit en Kotlin) y los Mappers entre Modelo de DB y Entidad de Dominio.
4. **Paso 4 (Presentation):** Crea el Router/Pydantic en FastAPI o el ViewModel + Compose Screen en Android.

## 3. Estándares de Código Estricto
* **Python (Backend):** Usa Python 3.12+, tipado estricto (`typing`, `mypy` compatible), `Pydantic v2` (`ConfigDict(from_attributes=True)`), y `SQLAlchemy 2.0` asíncrono (`AsyncSession`, `Mapped`, `mapped_column`). Prohibido usar sintaxis legacy de SQLAlchemy 1.x o Pydantic 1.x.
* **Kotlin (Móvil):** Usa Kotlin 2.0+, Coroutines (`Dispatcher` inyectado, nunca hardcodeado), `Flow`, `Hilt` o `Koin` para inyección de dependencias, y `Jetpack Compose` separando siempre `Route` (con ViewModel) de `Screen` (Stateless para Previews rápidas).
* **Manejo de Errores:** Prohibido usar `try/catch` genéricos que oculten errores (`except Exception: pass`). Usa el patrón `Result<T, DomainError>` o excepciones de dominio tipadas que la capa de presentación transforma en códigos HTTP o estados de UI claros.

## 4. Límite de Contexto por Prompt
Si una solicitud requiere modificar más de 2 módulos distintos al mismo tiempo, **detente** y divide la tarea: implementa primero el evento o contrato en `public_api` del Módulo A, verifica que los tests pasen, y en el siguiente paso consúmelo desde el Módulo B.

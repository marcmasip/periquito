# aicli

`aicli` es un agente de línea de comandos diseñado para ayudar a los desarrolladores a comprender y modificar bases de código complejas. 
Funciona mediante la contextualización de una pregunta o tarea específica dentro de un repositorio y utiliza un modelo de lenguaje avanzado para proponer soluciones en forma de explicaciones y parches de código.

# Project Structure

- src : componentes y funciones del agente


# Características Principales

- **Análisis de Repositorios**: Explora la estructura de ficheros de un proyecto para obtener una visión general.
- **Contextualización Inteligente**: Selecciona automáticamente los ficheros más relevantes para la pregunta del usuario, construyendo un contexto preciso y limitado.
- **Generación de Soluciones**: Interactúa con un modelo de lenguaje (LLM) para generar explicaciones detalladas y parches de código aplicables.
- **Aplicación Segura de Parches**: Ofrece una vista previa de los cambios antes de aplicarlos y utiliza `git restore` para revertir automáticamente cualquier aplicación fallida, garantizando la integridad del código.





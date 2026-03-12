# Inventario Refacciones

Sistema/API de gestión de inventario para refacciones y llantas, diseñado para centralizar el control de productos, stock y movimientos de inventario en una sola plataforma.

## Descripción

Este proyecto busca sustituir procesos manuales y dispersos por una solución estructurada para la administración de inventario en una refaccionaria. La meta es contar con una base tecnológica escalable que permita registrar productos, consultar existencias, controlar entradas y salidas, y evolucionar hacia reportes, dashboards y herramientas más avanzadas.

## Objetivo

Desarrollar una plataforma modular para gestionar inventario de refacciones y llantas, con capacidad de crecimiento hacia:

- control detallado de productos
- movimientos de inventario
- sincronización de catálogos
- trazabilidad de stock
- integración con frontend
- analítica y reportes

## Estado del proyecto

En desarrollo.

Actualmente el repositorio contiene la base inicial de la API y la configuración de conexión a base de datos.

## Estructura del proyecto

```text
APP/
├── __init__.py
├── main.py
└── db.py

## Tecnologías utilizadas

Python 3.12

FastAPI

SQLAlchemy

PostgreSQL

Uvicorn

## Funcionalidades actuales

-configuración inicial de la API

-conexión a base de datos

-estructura base para endpoints

-base para evolución modular del sistema

Funcionalidades planeadas

-alta, edición y consulta de productos

-control de entradas y salidas

-historial de movimientos (kardex)

-consulta de stock por SKU

-carga y sincronización de catálogo

-integración de frontend provisional

-reportes operativos

-dashboards e indicadores

-escalamiento hacia automatización y analítica

## Requisitos

Python 3.12 o superior

PostgreSQL

entorno virtual local

archivo .env para configuración sensible

## Instalación
1. Clonar el repositorio
git clone https://github.com/Stevee914/iNVENTORY-REFACCIONES-.git
cd iNVENTORY-REFACCIONES-
2. Crear entorno virtual

## En Windows PowerShell:

py -m venv .venv
.venv\Scripts\Activate.ps1
3. Instalar dependencias
pip install -r requirements.txt
Ejecución local
uvicorn APP.main:app --reload
Archivos excluidos del repositorio

Por seguridad y orden, este repositorio no incluye:

.env

.venv/

__pycache__/

.history/

archivos temporales de pruebas

Roadmap

 consolidar estructura base de inventario

 definir modelo completo de productos

 implementar movimientos de stock

 agregar validaciones y manejo de errores

 preparar frontend provisional

 documentar endpoints

 integrar reportes y dashboards

 preparar despliegue

Autor

Esteban Lopez Alegria
Proyecto de desarrollo para sistema de inventario de refacciones y llantas.


## Después de guardar
Ahora sí en PowerShell pegas esto:

```powershell
git add README.md
git commit -m "Improve README"
git push


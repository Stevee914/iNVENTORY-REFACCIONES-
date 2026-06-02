# Inventario Refacciones

Sistema de gestión de inventario para refacciones, llantas y productos automotrices, desarrollado para centralizar el control de productos, stock físico, movimientos de inventario, conteos físicos, faltantes, compras y reportes operativos.

El proyecto nace para digitalizar la operación de **Refacciones y Llantas Jaime**, reemplazando procesos manuales y archivos dispersos por una plataforma estructurada, trazable y escalable.

---

## Descripción

Este sistema permite administrar el inventario de una refaccionaria desde una base de datos centralizada. Incluye módulos para registrar productos, controlar entradas y salidas, consultar existencias, realizar conteos físicos con escáner/cámara, generar faltantes, exportar códigos de barras y analizar información operativa.

La solución está diseñada para operar en red local, con acceso desde equipos de mostrador, administración y tablet para almacén. También se está preparando para evolucionar hacia una aplicación de escritorio y posteriormente hacia un producto replicable para otros negocios.

---

## Objetivo

Desarrollar una plataforma modular para gestionar inventario de refacciones y llantas, con capacidad de crecimiento hacia:

* Control centralizado de productos y categorías.
* Registro de movimientos de inventario.
* Consulta de stock físico y stock fiscal/POS.
* Conteos físicos asistidos por escáner o cámara.
* Generación de códigos de barras para etiquetas.
* Identificación y gestión de faltantes.
* Integración con punto de venta.
* Reportes operativos y analítica básica.
* Preparación para app de escritorio y despliegues replicables.

---

## Estado del proyecto

**En desarrollo activo.**

El sistema ya cuenta con módulos funcionales para operación interna, incluyendo productos, stock, movimientos, conteo físico, códigos de barras, faltantes, compras, sincronización POS y reportes.

Actualmente también se está trabajando en:

* Limpieza y organización del repositorio.
* Documentación técnica y operativa.
* Configuración por negocio.
* Prueba de concepto para app de escritorio con Electron.

---

## Funcionalidades principales

### Productos y catálogo

* Alta, edición y consulta de productos.
* SKU interno y código POS.
* Categorías y subcategorías.
* Marca, unidad, mínimos, ubicación y aplicación.
* Búsqueda por SKU, nombre, marca o código POS.
* Catálogo navegable por categorías.

### Inventario y stock

* Movimientos de entrada, salida y ajuste.
* Kardex por producto.
* Consulta de stock por SKU.
* Stock físico y stock fiscal/POS.
* Comparación entre inventario físico y POS.
* Alertas de stock bajo o negativo.

### Conteo físico

* Sesiones de conteo físico por categoría.
* Escaneo con lector físico o cámara de tablet.
* Escáner con recuadro de lectura optimizado.
* Captura rápida: escanear → cantidad → Enter.
* Revisión de diferencias antes de aplicar ajustes.
* Generación de movimientos de ajuste en inventario físico.

### Códigos de barras y etiquetas

* Generación de códigos CODE 128.
* Código principal basado en SKU.
* Exportación de hojas de códigos en Excel.
* Imágenes de código de barras listas para acomodarse en plantillas de etiquetas.
* Preparado para futura impresión directa desde el sistema.

### Faltantes

* Registro y consulta de productos faltantes.
* Generación de faltantes desde conteos físicos.
* Vista previa antes de crear faltantes.
* Prevención de duplicados mediante origen de conteo.
* Preparado para flujo posterior de compras por proveedor.

### Compras y proveedores

* Gestión de proveedores.
* Registro de compras.
* Compras con factura y sin factura.
* Detalle de productos comprados.
* Relación producto-proveedor.
* Agrupación de faltantes por proveedor.

### Sincronización POS

* Sincronización de productos desde POS.
* Sincronización de stock POS.
* Sincronización de compras y facturas.
* Integración con base de datos externa del punto de venta.

### Reportes

* Reportes de inventario.
* Productos críticos.
* Diferencias entre libros de inventario.
* Reportes de compras.
* Reportes de ventas/facturas.
* Base para forecast y análisis de demanda.

### Escritorio / producto replicable

* Prueba de concepto con Electron.
* Configuración por negocio mediante archivo JSON.
* Documentación inicial para migración a app de escritorio.
* Preparación para instalación local en otros negocios.

---

## Tecnologías utilizadas

### Backend

* Python 3.12
* FastAPI
* SQLAlchemy
* PostgreSQL
* Uvicorn
* Pydantic

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* React Router
* Lucide React

### Integraciones y herramientas

* PostgreSQL
* Base de datos POS externa
* Excel/CSV para importación y exportación
* Escaneo por cámara mediante navegador
* Electron para prueba de concepto de escritorio

---

## Estructura general

```text
APP/
├── main.py
├── db.py
├── routers/
│   ├── products.py
│   ├── movements.py
│   ├── stock.py
│   ├── categorias.py
│   ├── proveedores.py
│   ├── compras.py
│   ├── faltantes.py
│   ├── pos_sync.py
│   ├── reportes.py
│   └── ...
├── schemas/
└── helpers/

src/
├── pages/
├── components/
├── services/
├── types/
├── router.tsx
└── ...

docs/
├── ARCHITECTURE.md
├── OPERATIONS_MANUAL.md
├── TECHNICAL_SETUP.md
├── DESKTOP_APP_STRATEGY.md
└── DESKTOP_POC.md

config/
└── business_config.json

electron/
└── main.cjs
```

---

## Requisitos

* Python 3.12 o superior.
* Node.js y npm.
* PostgreSQL.
* Entorno virtual local para backend.
* Archivo `.env` para configuración sensible.
* Acceso a la base de datos POS si se utiliza sincronización.

---

## Instalación backend

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ejecutar backend:

```powershell
uvicorn APP.main:app --reload
```

Verificar estado:

```text
GET /health
```

---

## Instalación frontend

```powershell
npm install
npm run dev
```

---

## Modo escritorio experimental

El proyecto incluye una prueba de concepto con Electron.

```powershell
npm run electron:dev
```

Limitación actual: el backend debe estar corriendo previamente.

---

## Documentación

La documentación principal se encuentra en la carpeta `docs/`.

* `ARCHITECTURE.md` — arquitectura general del sistema.
* `OPERATIONS_MANUAL.md` — manual operativo en español.
* `TECHNICAL_SETUP.md` — instalación y configuración técnica.
* `DESKTOP_APP_STRATEGY.md` — estrategia para app de escritorio.
* `DESKTOP_POC.md` — prueba de concepto con Electron.

---

## Roadmap

### Corto plazo

* Mejorar filtros y flujo de faltantes.
* Agrupar faltantes por proveedor.
* Crear órdenes de compra desde faltantes.
* Mejorar revisión de conteos físicos.
* Exportar resultados de conteos.
* Pulir generación de códigos de barras.

### Mediano plazo

* Mejorar estructura interna del repositorio.
* Consolidar configuración por negocio.
* Mejorar rendimiento en tablet.
* Ampliar reportes operativos.
* Agregar dashboard específico de conteos.

### Largo plazo

* App de escritorio completa.
* Instalador para Windows.
* Backups y restauración.
* Configuración multi-negocio.
* Producto replicable para otras refaccionarias o negocios con inventario físico complejo.

---

## Seguridad

No deben subirse al repositorio:

* Archivos `.env`.
* Certificados privados.
* Llaves SSL.
* Backups de base de datos.
* Archivos generados de exportaciones.
* Datos sensibles del negocio.

---

## Autor

**Esteban López Alegría**

Proyecto desarrollado para digitalizar y optimizar la gestión de inventario en una operación real de refacciones y llantas, con visión de convertirse en un producto replicable para otros negocios.


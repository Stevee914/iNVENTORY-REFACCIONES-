-- =============================================================================
-- CANONICAL LIVE SCHEMA — RefaccionesyLlantas
-- Generated: 2026-04-09
-- Source: pg_dump --schema-only from PostgreSQL 18.1 @ localhost:5432
--
-- This file replaces the stale schema.sql which was missing 10 tables,
-- 3 views, and ~8 columns on productos.
-- Use this file for audits, disaster recovery, and onboarding.
-- Regenerate with:
--   pg_dump --host=localhost --port=5432 --username=postgres \
--           --schema-only --no-owner --no-privileges --schema=public \
--           RefaccionesyLlantas > schema_live.sql
-- =============================================================================
--
-- PostgreSQL database dump
--

\restrict yw8buwNGg6olgfL9V8uPvQb8lhQITSFEgUJX9af5mL2aCWqrRUkkRrmrJvbDblY

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: inv_evento; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.inv_evento AS ENUM (
    'ENTRADA_FACTURA',
    'ENTRADA_MOSTRADOR',
    'VENTA_FACTURADA',
    'VENTA_MOSTRADOR',
    'AJUSTE'
);


--
-- Name: inv_libro; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.inv_libro AS ENUM (
    'FISICO',
    'FISCAL_POS'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: categoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    parent_id integer
);


--
-- Name: categoria_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categoria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categoria_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categoria_id_seq OWNED BY public.categoria.id;


--
-- Name: clientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clientes (
    id integer NOT NULL,
    nombre character varying(200) NOT NULL,
    rfc character varying(13),
    direccion text,
    telefono character varying(20),
    correo character varying(100),
    tipo character varying(20) DEFAULT 'MOSTRADOR'::character varying,
    notas text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    pos_cliente_id integer,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: clientes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clientes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clientes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clientes_id_seq OWNED BY public.clientes.id;


--
-- Name: compras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compras (
    id integer NOT NULL,
    proveedor_id integer NOT NULL,
    folio_factura character varying(100),
    fecha date NOT NULL,
    subtotal numeric(14,2) DEFAULT 0 NOT NULL,
    iva numeric(14,2) DEFAULT 0 NOT NULL,
    total numeric(14,2) DEFAULT 0 NOT NULL,
    estatus character varying(20) DEFAULT 'PENDIENTE'::character varying NOT NULL,
    metodo_pago character varying(50),
    notas text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    folio_captura character varying(30),
    origen character varying(10) DEFAULT 'MANUAL'::character varying NOT NULL,
    pos_compra_id integer,
    tipo_compra character varying(20) DEFAULT 'SIN_FACTURA'::character varying NOT NULL,
    CONSTRAINT chk_compras_estatus CHECK (((estatus)::text = ANY ((ARRAY['PENDIENTE'::character varying, 'RECIBIDA'::character varying, 'PAGADA'::character varying, 'PARCIAL'::character varying, 'CANCELADA'::character varying])::text[]))),
    CONSTRAINT chk_compras_origen CHECK (((origen)::text = ANY ((ARRAY['MANUAL'::character varying, 'POS'::character varying])::text[]))),
    CONSTRAINT compras_tipo_compra_check CHECK (((tipo_compra)::text = ANY ((ARRAY['CON_FACTURA'::character varying, 'SIN_FACTURA'::character varying])::text[])))
);


--
-- Name: COLUMN compras.tipo_compra; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.compras.tipo_compra IS 'Business classification: CON_FACTURA (backed by invoice) or SIN_FACTURA (remision/mostrador)';


--
-- Name: compras_detalle; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compras_detalle (
    id integer NOT NULL,
    compra_id integer NOT NULL,
    product_id integer NOT NULL,
    cantidad numeric(12,4) NOT NULL,
    precio_unit numeric(12,4),
    supplier_sku character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    faltante_id integer,
    CONSTRAINT compras_detalle_cantidad_check CHECK ((cantidad > (0)::numeric))
);


--
-- Name: COLUMN compras_detalle.faltante_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.compras_detalle.faltante_id IS 'Traceability: which shortage originated this purchase line';


--
-- Name: compras_detalle_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.compras_detalle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: compras_detalle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compras_detalle_id_seq OWNED BY public.compras_detalle.id;


--
-- Name: compras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.compras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: compras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compras_id_seq OWNED BY public.compras.id;


--
-- Name: facturas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.facturas (
    id integer NOT NULL,
    folio character varying(50) NOT NULL,
    cliente_id integer,
    monto numeric(12,2) NOT NULL,
    fecha date DEFAULT CURRENT_DATE NOT NULL,
    estatus character varying(20) DEFAULT 'PAGADA'::character varying,
    metodo_pago character varying(30),
    notas text,
    created_at timestamp without time zone DEFAULT now(),
    tipo_documento character varying(20) DEFAULT 'FACTURA'::character varying NOT NULL,
    condicion_pago character varying(20) DEFAULT 'CONTADO'::character varying,
    fecha_vencimiento date,
    origen character varying(10) DEFAULT 'MANUAL'::character varying NOT NULL,
    pos_documento_id integer,
    pos_cfd_id integer,
    serie character varying(10),
    subtotal numeric(14,2),
    iva numeric(14,2),
    uuid character varying(36),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_facturas_origen CHECK (((origen)::text = ANY ((ARRAY['MANUAL'::character varying, 'POS'::character varying])::text[])))
);


--
-- Name: facturas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.facturas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: facturas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.facturas_id_seq OWNED BY public.facturas.id;


--
-- Name: faltantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.faltantes (
    id integer NOT NULL,
    product_id integer NOT NULL,
    cantidad_faltante numeric(10,2) NOT NULL,
    comentario text,
    fecha_detectado timestamp without time zone DEFAULT now() NOT NULL,
    status character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT chk_faltantes_status CHECK (((status)::text = ANY ((ARRAY['pendiente'::character varying, 'comprado'::character varying, 'cancelado'::character varying])::text[])))
);


--
-- Name: faltantes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.faltantes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: faltantes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.faltantes_id_seq OWNED BY public.faltantes.id;


--
-- Name: movimientos_inventario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimientos_inventario (
    id integer NOT NULL,
    product_id integer NOT NULL,
    movement_type character varying(10) NOT NULL,
    quantity numeric(10,2) NOT NULL,
    movement_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    reference character varying(100),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    libro public.inv_libro DEFAULT 'FISICO'::public.inv_libro NOT NULL,
    evento public.inv_evento DEFAULT 'AJUSTE'::public.inv_evento NOT NULL,
    costo_unit_sin_iva numeric(12,4),
    tasa_iva numeric(6,4) DEFAULT 0.16 NOT NULL,
    costo_unit_con_iva numeric(12,4),
    precio_venta_unit numeric(12,4),
    proveedor_id bigint,
    CONSTRAINT chk_proveedor_en_entradas CHECK ((((evento = 'ENTRADA_FACTURA'::public.inv_evento) AND (proveedor_id IS NOT NULL)) OR (evento <> 'ENTRADA_FACTURA'::public.inv_evento))),
    CONSTRAINT movimientos_inventario_movement_type_check CHECK (((movement_type)::text = ANY ((ARRAY['IN'::character varying, 'OUT'::character varying, 'ADJUST'::character varying])::text[])))
);


--
-- Name: movimientos_inventario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.movimientos_inventario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: movimientos_inventario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.movimientos_inventario_id_seq OWNED BY public.movimientos_inventario.id;


--
-- Name: pagos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pagos (
    id integer NOT NULL,
    factura_id integer NOT NULL,
    monto numeric(12,2) NOT NULL,
    fecha date DEFAULT CURRENT_DATE NOT NULL,
    metodo_pago character varying(30),
    referencia character varying(100),
    notas text,
    created_at timestamp without time zone DEFAULT now(),
    pos_cfd_id integer
);


--
-- Name: pagos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pagos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pagos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pagos_id_seq OWNED BY public.pagos.id;


--
-- Name: producto_aplicacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.producto_aplicacion (
    producto_id integer NOT NULL,
    aplicacion_id integer NOT NULL,
    notas character varying(250)
);


--
-- Name: producto_proveedor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.producto_proveedor (
    id bigint NOT NULL,
    proveedor_id bigint NOT NULL,
    product_id integer NOT NULL,
    supplier_sku text NOT NULL,
    descripcion_proveedor text,
    is_primary boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    precio_proveedor numeric(12,2) DEFAULT NULL::numeric,
    updated_at timestamp with time zone
);


--
-- Name: producto_proveedor_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.producto_proveedor_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: producto_proveedor_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.producto_proveedor_id_seq OWNED BY public.producto_proveedor.id;


--
-- Name: productos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.productos (
    id integer NOT NULL,
    sku character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    categoria_id integer,
    unit character varying(20),
    min_stock numeric(10,2) DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    price numeric(10,2),
    codigo_cat character varying(20),
    codigo_pos character varying(50),
    marca character varying(50),
    aplicacion text,
    ubicacion text,
    descripcion_larga text,
    anio_inicio smallint,
    anio_fin smallint,
    dim_largo numeric(10,2),
    dim_ancho numeric(10,2),
    dim_alto numeric(10,2),
    equivalencia text,
    imagen_url text,
    pos_articulo_id integer,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    costo_pos_con_iva numeric(12,4),
    costo_real_sin_iva numeric(12,4),
    costo_real_updated_at timestamp with time zone,
    porcentaje_margen_objetivo numeric(5,2),
    precio_sugerido numeric(12,2),
    precio_publico numeric(12,2),
    medida character varying(100)
);


--
-- Name: productos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.productos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: productos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.productos_id_seq OWNED BY public.productos.id;


--
-- Name: proveedores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proveedores (
    id bigint NOT NULL,
    nombre text NOT NULL,
    codigo_corto text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    rfc text,
    pos_proveedor_id integer,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: proveedores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proveedores_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proveedores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proveedores_id_seq OWNED BY public.proveedores.id;


--
-- Name: stock_por_libro; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.stock_por_libro AS
 SELECT p.sku,
    mi.product_id,
    mi.libro,
    sum(mi.quantity) AS stock
   FROM (public.movimientos_inventario mi
     JOIN public.productos p ON ((p.id = mi.product_id)))
  GROUP BY p.sku, mi.product_id, mi.libro;


--
-- Name: stock_resumen; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.stock_resumen AS
 SELECT sku,
    product_id,
    COALESCE(sum(stock) FILTER (WHERE (libro = 'FISICO'::public.inv_libro)), (0)::numeric) AS stock_fisico,
    COALESCE(sum(stock) FILTER (WHERE (libro = 'FISCAL_POS'::public.inv_libro)), (0)::numeric) AS stock_pos,
    COALESCE(sum(stock), (0)::numeric) AS stock_total
   FROM public.stock_por_libro
  GROUP BY sku, product_id;


--
-- Name: v_clientes_resumen; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clientes_resumen AS
 SELECT c.id,
    c.nombre,
    c.rfc,
    c.tipo,
    c.telefono,
    c.correo,
    c.is_active,
    count(f.id) AS total_facturas,
    COALESCE(sum(f.monto), (0)::numeric) AS total_compras,
    COALESCE(sum(
        CASE
            WHEN ((f.estatus)::text = ANY ((ARRAY['CREDITO'::character varying, 'PARCIAL'::character varying])::text[])) THEN (f.monto - COALESCE(pg.pagado, (0)::numeric))
            ELSE (0)::numeric
        END), (0)::numeric) AS saldo_pendiente
   FROM ((public.clientes c
     LEFT JOIN public.facturas f ON ((f.cliente_id = c.id)))
     LEFT JOIN ( SELECT pagos.factura_id,
            sum(pagos.monto) AS pagado
           FROM public.pagos
          GROUP BY pagos.factura_id) pg ON ((pg.factura_id = f.id)))
  GROUP BY c.id, c.nombre, c.rfc, c.tipo, c.telefono, c.correo, c.is_active;


--
-- Name: v_facturas_saldo; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_facturas_saldo AS
 SELECT f.id,
    f.folio,
    f.cliente_id,
    c.nombre AS cliente_nombre,
    c.rfc AS cliente_rfc,
    c.tipo AS cliente_tipo,
    f.monto,
    f.fecha,
    f.estatus,
    f.metodo_pago,
    f.notas,
    f.created_at,
    COALESCE(sum(p.monto), (0)::numeric) AS total_pagado,
    (f.monto - COALESCE(sum(p.monto), (0)::numeric)) AS saldo_pendiente
   FROM ((public.facturas f
     LEFT JOIN public.clientes c ON ((c.id = f.cliente_id)))
     LEFT JOIN public.pagos p ON ((p.factura_id = f.id)))
  GROUP BY f.id, f.folio, f.cliente_id, c.nombre, c.rfc, c.tipo, f.monto, f.fecha, f.estatus, f.metodo_pago, f.notas, f.created_at;


--
-- Name: v_producto_margen; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_producto_margen AS
 SELECT id AS producto_id,
    sku,
    name,
    marca,
    costo_pos_con_iva,
    costo_real_sin_iva,
    COALESCE(costo_real_sin_iva, (costo_pos_con_iva / 1.16)) AS costo_base,
        CASE
            WHEN (costo_real_sin_iva IS NOT NULL) THEN 'REAL'::text
            WHEN (pos_articulo_id IS NOT NULL) THEN 'POS'::text
            WHEN (costo_pos_con_iva IS NOT NULL) THEN 'MANUAL'::text
            ELSE NULL::text
        END AS fuente_costo,
    precio_publico AS precio_final,
    porcentaje_margen_objetivo,
    precio_sugerido,
    costo_real_updated_at,
    (precio_publico - COALESCE(costo_real_sin_iva, (costo_pos_con_iva / 1.16))) AS utilidad,
    round((((precio_publico - COALESCE(costo_real_sin_iva, (costo_pos_con_iva / 1.16))) / NULLIF(precio_publico, (0)::numeric)) * (100)::numeric), 2) AS margen_porcentaje,
    round((((precio_publico - COALESCE(costo_real_sin_iva, (costo_pos_con_iva / 1.16))) / NULLIF(COALESCE(costo_real_sin_iva, (costo_pos_con_iva / 1.16)), (0)::numeric)) * (100)::numeric), 2) AS markup_porcentaje
   FROM public.productos p;


--
-- Name: v_stock_actual; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_stock_actual AS
 SELECT p.id AS product_id,
    p.sku,
    p.name,
    p.min_stock,
    COALESCE(sum(m.quantity), (0)::numeric) AS stock_actual
   FROM (public.productos p
     LEFT JOIN public.movimientos_inventario m ON (((m.product_id = p.id) AND (m.libro = 'FISICO'::public.inv_libro))))
  GROUP BY p.id, p.sku, p.name, p.min_stock;


--
-- Name: v_stock_fisico; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_stock_fisico AS
 SELECT p.id AS product_id,
    p.sku,
    p.name,
    p.min_stock,
    COALESCE(sum(m.quantity), (0)::numeric) AS stock_fisico
   FROM (public.productos p
     LEFT JOIN public.movimientos_inventario m ON (((m.product_id = p.id) AND (m.libro = 'FISICO'::public.inv_libro))))
  GROUP BY p.id, p.sku, p.name, p.min_stock;


--
-- Name: v_stock_pos; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_stock_pos AS
 SELECT p.id AS product_id,
    p.sku,
    p.name,
    COALESCE(sum(m.quantity), (0)::numeric) AS stock_pos
   FROM (public.productos p
     LEFT JOIN public.movimientos_inventario m ON (((m.product_id = p.id) AND (m.libro = 'FISCAL_POS'::public.inv_libro))))
  GROUP BY p.id, p.sku, p.name;


--
-- Name: v_stock_compare; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_stock_compare AS
 SELECT f.product_id,
    f.sku,
    f.name,
    f.min_stock,
    f.stock_fisico,
    COALESCE(p.stock_pos, (0)::numeric) AS stock_pos,
    (f.stock_fisico - COALESCE(p.stock_pos, (0)::numeric)) AS diferencia
   FROM (public.v_stock_fisico f
     LEFT JOIN public.v_stock_pos p ON ((p.product_id = f.product_id)));


--
-- Name: v_stock_libros; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_stock_libros AS
 SELECT p.id AS product_id,
    p.sku,
    p.name,
    p.unit,
    p.marca,
    p.codigo_pos,
    p.min_stock,
    COALESCE(sum(mi.quantity) FILTER (WHERE (mi.libro = 'FISICO'::public.inv_libro)), (0)::numeric) AS stock_fisico,
    COALESCE(sum(mi.quantity) FILTER (WHERE (mi.libro = 'FISCAL_POS'::public.inv_libro)), (0)::numeric) AS stock_pos,
    COALESCE(sum(mi.quantity), (0)::numeric) AS stock_total
   FROM (public.productos p
     LEFT JOIN public.movimientos_inventario mi ON ((mi.product_id = p.id)))
  GROUP BY p.id, p.sku, p.name, p.unit, p.marca, p.codigo_pos, p.min_stock;


--
-- Name: vehiculos_aplicaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehiculos_aplicaciones (
    id integer NOT NULL,
    modelo_id integer NOT NULL,
    anio smallint NOT NULL,
    traccion character varying(5),
    carroceria character varying(30),
    motor character varying(50) NOT NULL,
    CONSTRAINT vehiculos_aplicaciones_anio_check CHECK (((anio >= 1900) AND (anio <= 2100)))
);


--
-- Name: vehiculos_aplicaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehiculos_aplicaciones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehiculos_aplicaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehiculos_aplicaciones_id_seq OWNED BY public.vehiculos_aplicaciones.id;


--
-- Name: vehiculos_marcas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehiculos_marcas_id_seq
    START WITH 20
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehiculos_marcas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehiculos_marcas (
    id integer DEFAULT nextval('public.vehiculos_marcas_id_seq'::regclass) NOT NULL,
    nombre character varying(100) NOT NULL,
    slug character varying(100) NOT NULL,
    primer_anio smallint,
    ultimo_anio smallint
);


--
-- Name: vehiculos_modelos_id_seq2; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehiculos_modelos_id_seq2
    START WITH 275
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehiculos_modelos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehiculos_modelos (
    id integer DEFAULT nextval('public.vehiculos_modelos_id_seq2'::regclass) NOT NULL,
    marca_id integer NOT NULL,
    nombre character varying(150) NOT NULL,
    vehicle_type character varying(50)
);


--
-- Name: vehiculos_modelos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehiculos_modelos_id_seq
    START WITH 213
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categoria id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria ALTER COLUMN id SET DEFAULT nextval('public.categoria_id_seq'::regclass);


--
-- Name: clientes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes ALTER COLUMN id SET DEFAULT nextval('public.clientes_id_seq'::regclass);


--
-- Name: compras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras ALTER COLUMN id SET DEFAULT nextval('public.compras_id_seq'::regclass);


--
-- Name: compras_detalle id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras_detalle ALTER COLUMN id SET DEFAULT nextval('public.compras_detalle_id_seq'::regclass);


--
-- Name: facturas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facturas ALTER COLUMN id SET DEFAULT nextval('public.facturas_id_seq'::regclass);


--
-- Name: faltantes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faltantes ALTER COLUMN id SET DEFAULT nextval('public.faltantes_id_seq'::regclass);


--
-- Name: movimientos_inventario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_inventario ALTER COLUMN id SET DEFAULT nextval('public.movimientos_inventario_id_seq'::regclass);


--
-- Name: pagos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos ALTER COLUMN id SET DEFAULT nextval('public.pagos_id_seq'::regclass);


--
-- Name: producto_proveedor id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_proveedor ALTER COLUMN id SET DEFAULT nextval('public.producto_proveedor_id_seq'::regclass);


--
-- Name: productos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.productos ALTER COLUMN id SET DEFAULT nextval('public.productos_id_seq'::regclass);


--
-- Name: proveedores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proveedores ALTER COLUMN id SET DEFAULT nextval('public.proveedores_id_seq'::regclass);


--
-- Name: vehiculos_aplicaciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_aplicaciones ALTER COLUMN id SET DEFAULT nextval('public.vehiculos_aplicaciones_id_seq'::regclass);


--
-- Name: categoria categoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria
    ADD CONSTRAINT categoria_pkey PRIMARY KEY (id);


--
-- Name: clientes clientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pkey PRIMARY KEY (id);


--
-- Name: clientes clientes_pos_cliente_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pos_cliente_id_key UNIQUE (pos_cliente_id);


--
-- Name: compras_detalle compras_detalle_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras_detalle
    ADD CONSTRAINT compras_detalle_pkey PRIMARY KEY (id);


--
-- Name: compras compras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras
    ADD CONSTRAINT compras_pkey PRIMARY KEY (id);


--
-- Name: facturas facturas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facturas
    ADD CONSTRAINT facturas_pkey PRIMARY KEY (id);


--
-- Name: faltantes faltantes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faltantes
    ADD CONSTRAINT faltantes_pkey PRIMARY KEY (id);


--
-- Name: movimientos_inventario movimientos_inventario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_inventario
    ADD CONSTRAINT movimientos_inventario_pkey PRIMARY KEY (id);


--
-- Name: pagos pagos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos
    ADD CONSTRAINT pagos_pkey PRIMARY KEY (id);


--
-- Name: producto_aplicacion producto_aplicacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_aplicacion
    ADD CONSTRAINT producto_aplicacion_pkey PRIMARY KEY (producto_id, aplicacion_id);


--
-- Name: producto_proveedor producto_proveedor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_proveedor
    ADD CONSTRAINT producto_proveedor_pkey PRIMARY KEY (id);


--
-- Name: producto_proveedor producto_proveedor_proveedor_id_supplier_sku_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_proveedor
    ADD CONSTRAINT producto_proveedor_proveedor_id_supplier_sku_key UNIQUE (proveedor_id, supplier_sku);


--
-- Name: productos productos_no_identificacion_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.productos
    ADD CONSTRAINT productos_no_identificacion_key UNIQUE (sku);


--
-- Name: productos productos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.productos
    ADD CONSTRAINT productos_pkey PRIMARY KEY (id);


--
-- Name: productos productos_sku_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.productos
    ADD CONSTRAINT productos_sku_unique UNIQUE (sku);


--
-- Name: proveedores proveedores_codigo_corto_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proveedores
    ADD CONSTRAINT proveedores_codigo_corto_key UNIQUE (codigo_corto);


--
-- Name: proveedores proveedores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proveedores
    ADD CONSTRAINT proveedores_pkey PRIMARY KEY (id);


--
-- Name: facturas uq_folio_origen; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facturas
    ADD CONSTRAINT uq_folio_origen UNIQUE (folio, origen);


--
-- Name: facturas uq_pos_documento_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facturas
    ADD CONSTRAINT uq_pos_documento_id UNIQUE (pos_documento_id);


--
-- Name: vehiculos_aplicaciones uq_vapl_modelo_anio_motor; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_aplicaciones
    ADD CONSTRAINT uq_vapl_modelo_anio_motor UNIQUE (modelo_id, anio, motor);


--
-- Name: vehiculos_aplicaciones vehiculos_aplicaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_aplicaciones
    ADD CONSTRAINT vehiculos_aplicaciones_pkey PRIMARY KEY (id);


--
-- Name: vehiculos_marcas vehiculos_marcas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_marcas
    ADD CONSTRAINT vehiculos_marcas_pkey PRIMARY KEY (id);


--
-- Name: vehiculos_marcas vehiculos_marcas_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_marcas
    ADD CONSTRAINT vehiculos_marcas_slug_key UNIQUE (slug);


--
-- Name: vehiculos_modelos vehiculos_modelos_marca_id_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_modelos
    ADD CONSTRAINT vehiculos_modelos_marca_id_nombre_key UNIQUE (marca_id, nombre);


--
-- Name: vehiculos_modelos vehiculos_modelos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_modelos
    ADD CONSTRAINT vehiculos_modelos_pkey PRIMARY KEY (id);


--
-- Name: categoria_name_parent_uq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX categoria_name_parent_uq ON public.categoria USING btree (name, parent_id) NULLS NOT DISTINCT;


--
-- Name: idx_clientes_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clientes_nombre ON public.clientes USING btree (nombre);


--
-- Name: idx_clientes_rfc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clientes_rfc ON public.clientes USING btree (rfc);


--
-- Name: idx_clientes_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clientes_tipo ON public.clientes USING btree (tipo);


--
-- Name: idx_codigo_pos; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_codigo_pos ON public.productos USING btree (codigo_pos);


--
-- Name: idx_compras_detalle_compra; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_detalle_compra ON public.compras_detalle USING btree (compra_id);


--
-- Name: idx_compras_detalle_faltante; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_detalle_faltante ON public.compras_detalle USING btree (faltante_id);


--
-- Name: idx_compras_detalle_product; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_detalle_product ON public.compras_detalle USING btree (product_id);


--
-- Name: idx_compras_estatus; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_estatus ON public.compras USING btree (estatus);


--
-- Name: idx_compras_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_fecha ON public.compras USING btree (fecha);


--
-- Name: idx_compras_origen; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_origen ON public.compras USING btree (origen);


--
-- Name: idx_compras_proveedor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_proveedor ON public.compras USING btree (proveedor_id);


--
-- Name: idx_compras_tipo_compra; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compras_tipo_compra ON public.compras USING btree (tipo_compra);


--
-- Name: idx_facturas_cliente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_facturas_cliente ON public.facturas USING btree (cliente_id);


--
-- Name: idx_facturas_estatus; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_facturas_estatus ON public.facturas USING btree (estatus);


--
-- Name: idx_facturas_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_facturas_fecha ON public.facturas USING btree (fecha);


--
-- Name: idx_facturas_tipo_doc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_facturas_tipo_doc ON public.facturas USING btree (tipo_documento);


--
-- Name: idx_faltantes_product; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_faltantes_product ON public.faltantes USING btree (product_id);


--
-- Name: idx_faltantes_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_faltantes_status ON public.faltantes USING btree (status);


--
-- Name: idx_mov_product_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mov_product_date ON public.movimientos_inventario USING btree (product_id, movement_date);


--
-- Name: idx_mov_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mov_type ON public.movimientos_inventario USING btree (movement_type);


--
-- Name: idx_movinv_libro_prod_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_movinv_libro_prod_fecha ON public.movimientos_inventario USING btree (libro, product_id, movement_date);


--
-- Name: idx_movinv_proveedor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_movinv_proveedor ON public.movimientos_inventario USING btree (proveedor_id);


--
-- Name: idx_pagos_factura; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pagos_factura ON public.pagos USING btree (factura_id);


--
-- Name: idx_pagos_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pagos_fecha ON public.pagos USING btree (fecha);


--
-- Name: idx_pp_proveedor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pp_proveedor_id ON public.producto_proveedor USING btree (proveedor_id);


--
-- Name: idx_prod_apl_apl; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prod_apl_apl ON public.producto_aplicacion USING btree (aplicacion_id);


--
-- Name: idx_prodprov_product; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prodprov_product ON public.producto_proveedor USING btree (product_id);


--
-- Name: idx_prodprov_prov; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prodprov_prov ON public.producto_proveedor USING btree (proveedor_id);


--
-- Name: idx_productos_categoria_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_productos_categoria_id ON public.productos USING btree (categoria_id);


--
-- Name: idx_productos_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_productos_category_id ON public.productos USING btree (categoria_id);


--
-- Name: idx_productos_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_productos_is_active ON public.productos USING btree (is_active);


--
-- Name: idx_productos_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_productos_name_trgm ON public.productos USING gin (name public.gin_trgm_ops);


--
-- Name: idx_vapl_anio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vapl_anio ON public.vehiculos_aplicaciones USING btree (anio);


--
-- Name: idx_vapl_modelo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vapl_modelo ON public.vehiculos_aplicaciones USING btree (modelo_id);


--
-- Name: idx_vapl_modelo_anio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vapl_modelo_anio ON public.vehiculos_aplicaciones USING btree (modelo_id, anio);


--
-- Name: idx_vmodelos_marca; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vmodelos_marca ON public.vehiculos_modelos USING btree (marca_id);


--
-- Name: ix_movs_product_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movs_product_date ON public.movimientos_inventario USING btree (product_id, movement_date DESC, id DESC);


--
-- Name: ix_movs_product_libro; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movs_product_libro ON public.movimientos_inventario USING btree (product_id, libro);


--
-- Name: ix_productos_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_productos_name ON public.productos USING btree (name);


--
-- Name: uq_compras_pos_compra_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_compras_pos_compra_id ON public.compras USING btree (pos_compra_id) WHERE (pos_compra_id IS NOT NULL);


--
-- Name: uq_compras_proveedor_folio_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_compras_proveedor_folio_fecha ON public.compras USING btree (proveedor_id, folio_factura, fecha) WHERE ((folio_factura IS NOT NULL) AND ((origen)::text = 'MANUAL'::text));


--
-- Name: uq_pagos_pos_cfd_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_pagos_pos_cfd_id ON public.pagos USING btree (pos_cfd_id) WHERE (pos_cfd_id IS NOT NULL);


--
-- Name: uq_productos_pos_articulo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_productos_pos_articulo_id ON public.productos USING btree (pos_articulo_id) WHERE (pos_articulo_id IS NOT NULL);


--
-- Name: uq_productos_sku; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_productos_sku ON public.productos USING btree (sku) WHERE ((sku IS NOT NULL) AND ((sku)::text <> ''::text));


--
-- Name: uq_proveedores_codigo_corto; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_proveedores_codigo_corto ON public.proveedores USING btree (codigo_corto) WHERE ((codigo_corto IS NOT NULL) AND (codigo_corto <> ''::text));


--
-- Name: uq_proveedores_pos_proveedor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_proveedores_pos_proveedor_id ON public.proveedores USING btree (pos_proveedor_id) WHERE (pos_proveedor_id IS NOT NULL);


--
-- Name: uq_proveedores_rfc; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_proveedores_rfc ON public.proveedores USING btree (rfc) WHERE ((rfc IS NOT NULL) AND (rfc <> ''::text));


--
-- Name: ux_productos_codigo_pos; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_productos_codigo_pos ON public.productos USING btree (codigo_pos) WHERE ((codigo_pos IS NOT NULL) AND ((codigo_pos)::text <> ''::text));


--
-- Name: compras_detalle compras_detalle_compra_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras_detalle
    ADD CONSTRAINT compras_detalle_compra_id_fkey FOREIGN KEY (compra_id) REFERENCES public.compras(id) ON DELETE CASCADE;


--
-- Name: compras_detalle compras_detalle_faltante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras_detalle
    ADD CONSTRAINT compras_detalle_faltante_id_fkey FOREIGN KEY (faltante_id) REFERENCES public.faltantes(id) ON DELETE SET NULL;


--
-- Name: compras_detalle compras_detalle_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras_detalle
    ADD CONSTRAINT compras_detalle_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.productos(id);


--
-- Name: compras compras_proveedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compras
    ADD CONSTRAINT compras_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores(id);


--
-- Name: facturas facturas_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.facturas
    ADD CONSTRAINT facturas_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id) ON DELETE SET NULL;


--
-- Name: faltantes faltantes_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faltantes
    ADD CONSTRAINT faltantes_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.productos(id);


--
-- Name: categoria fk_categoria_parent; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria
    ADD CONSTRAINT fk_categoria_parent FOREIGN KEY (parent_id) REFERENCES public.categoria(id);


--
-- Name: movimientos_inventario movimientos_inventario_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_inventario
    ADD CONSTRAINT movimientos_inventario_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.productos(id);


--
-- Name: movimientos_inventario movimientos_inventario_proveedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_inventario
    ADD CONSTRAINT movimientos_inventario_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores(id);


--
-- Name: pagos pagos_factura_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos
    ADD CONSTRAINT pagos_factura_id_fkey FOREIGN KEY (factura_id) REFERENCES public.facturas(id) ON DELETE CASCADE;


--
-- Name: producto_aplicacion producto_aplicacion_aplicacion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_aplicacion
    ADD CONSTRAINT producto_aplicacion_aplicacion_id_fkey FOREIGN KEY (aplicacion_id) REFERENCES public.vehiculos_aplicaciones(id) ON DELETE CASCADE;


--
-- Name: producto_aplicacion producto_aplicacion_producto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_aplicacion
    ADD CONSTRAINT producto_aplicacion_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES public.productos(id) ON DELETE CASCADE;


--
-- Name: producto_proveedor producto_proveedor_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_proveedor
    ADD CONSTRAINT producto_proveedor_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.productos(id);


--
-- Name: producto_proveedor producto_proveedor_proveedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.producto_proveedor
    ADD CONSTRAINT producto_proveedor_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores(id);


--
-- Name: productos productos_categoria_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.productos
    ADD CONSTRAINT productos_categoria_id_fkey FOREIGN KEY (categoria_id) REFERENCES public.categoria(id);


--
-- Name: vehiculos_aplicaciones vehiculos_aplicaciones_modelo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_aplicaciones
    ADD CONSTRAINT vehiculos_aplicaciones_modelo_id_fkey FOREIGN KEY (modelo_id) REFERENCES public.vehiculos_modelos(id) ON DELETE CASCADE;


--
-- Name: vehiculos_modelos vehiculos_modelos_marca_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehiculos_modelos
    ADD CONSTRAINT vehiculos_modelos_marca_id_fkey FOREIGN KEY (marca_id) REFERENCES public.vehiculos_marcas(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict yw8buwNGg6olgfL9V8uPvQb8lhQITSFEgUJX9af5mL2aCWqrRUkkRrmrJvbDblY


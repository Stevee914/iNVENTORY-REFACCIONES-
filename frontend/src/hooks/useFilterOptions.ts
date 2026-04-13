import { useEffect, useState } from 'react';
import { categoriaService } from '@/services/categorias';
import { proveedorService } from '@/services/proveedores';
import { api } from '@/services/client';
import type { Categoria, Proveedor } from '@/types';

export interface FilterOptions {
  categorias: Categoria[];
  proveedores: Proveedor[];
  marcas: string[];
  loading: boolean;
}

export function useFilterOptions(): FilterOptions {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [marcas, setMarcas] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      categoriaService.getAll(),
      proveedorService.getAll(),
      api<string[]>('/products/marcas'),
    ]).then(([cats, provs, mrcas]) => {
      setCategorias(cats);
      setProveedores(provs);
      setMarcas(mrcas);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return { categorias, proveedores, marcas, loading };
}

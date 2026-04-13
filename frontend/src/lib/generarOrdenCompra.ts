import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { FaltanteGrupo } from '@/services/faltantes';

const EMP = {
  nombre: 'REFACCIONES Y LLANTAS JAIME',
  razon: 'Refacciones y Llantas Jaime S.A. de C.V.',
  rfc: 'RLJ941215835',
  dir: 'Melchor Ocampo #350, Maravatío, Mich. CP 61250',
  tel: '447 478 2074',
  email: 'refaccionesyllantasjaime@gmail.com',
};

function fmt(n: number): string {
  return n.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function generarOrdenCompra(grupo: FaltanteGrupo, observaciones?: string) {
  const doc = new jsPDF();
  const pw = doc.internal.pageSize.getWidth();
  const ph = doc.internal.pageSize.getHeight();
  const mx = 18;

  const negro = [30, 30, 30] as const;
  const gris = [100, 100, 100] as const;
  const borde = [180, 180, 180] as const;
  const fondoCelda = [245, 245, 245] as const;

  const now = new Date();
  const folio = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
  const fecha = now.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();

  // ════════════════════════════════════════════════════
  // ENCABEZADO
  // ════════════════════════════════════════════════════

  let y = 18;

  doc.setTextColor(...negro);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('ORDEN DE COMPRA', pw / 2, y, { align: 'center' });

  y += 8;
  doc.setFontSize(10);
  doc.text(EMP.nombre, pw / 2, y, { align: 'center' });

  y += 5.5;
  doc.setTextColor(...gris);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  doc.text(EMP.dir, pw / 2, y, { align: 'center' });
  y += 4;
  doc.text(`R.F.C. ${EMP.rfc}   ·   Tel. ${EMP.tel}`, pw / 2, y, { align: 'center' });

  y += 6;
  doc.setDrawColor(...borde);
  doc.setLineWidth(0.3);
  doc.line(mx, y, pw - mx, y);

  // ════════════════════════════════════════════════════
  // CAJA PROVEEDOR + FOLIO/FECHA
  // ════════════════════════════════════════════════════

  y += 5;
  const boxTop = y;
  const boxH = 18;
  const folioW = 42;
  const provW = pw - 2 * mx - folioW - 4;

  doc.setFillColor(...fondoCelda);
  doc.setDrawColor(...borde);
  doc.setLineWidth(0.3);
  doc.rect(mx, boxTop, provW, 7, 'FD');
  doc.setTextColor(...negro);
  doc.setFontSize(7.5);
  doc.setFont('helvetica', 'bold');
  doc.text('Proveedor', mx + provW / 2, boxTop + 4.8, { align: 'center' });

  doc.setFillColor(255, 255, 255);
  doc.rect(mx, boxTop + 7, provW, boxH, 'FD');
  doc.setTextColor(...negro);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'bold');
  doc.text(grupo.proveedor_nombre, mx + 4, boxTop + 13);
  doc.setTextColor(...gris);
  doc.setFontSize(7.5);
  doc.setFont('helvetica', 'normal');
  doc.text(`${grupo.total_items} producto${grupo.total_items !== 1 ? 's' : ''} solicitados`, mx + 4, boxTop + 19);

  const fx = mx + provW + 4;
  doc.setFillColor(...fondoCelda);
  doc.rect(fx, boxTop, folioW, 5.5, 'FD');
  doc.setTextColor(...negro);
  doc.setFontSize(6.5);
  doc.setFont('helvetica', 'bold');
  doc.text('Folio O.C.', fx + folioW / 2, boxTop + 3.8, { align: 'center' });
  doc.setFillColor(255, 255, 255);
  doc.rect(fx, boxTop + 5.5, folioW, 7, 'FD');
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');
  doc.text(folio, fx + folioW / 2, boxTop + 10.2, { align: 'center' });

  doc.setFillColor(...fondoCelda);
  doc.rect(fx, boxTop + 12.5, folioW, 5.5, 'FD');
  doc.setTextColor(...negro);
  doc.setFontSize(6.5);
  doc.setFont('helvetica', 'bold');
  doc.text('Fecha', fx + folioW / 2, boxTop + 16.3, { align: 'center' });
  doc.setFillColor(255, 255, 255);
  doc.rect(fx, boxTop + 18, folioW, 7, 'FD');
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  doc.text(fecha, fx + folioW / 2, boxTop + 22.7, { align: 'center' });

  // ════════════════════════════════════════════════════
  // TABLA DE PRODUCTOS
  // ════════════════════════════════════════════════════

  y = boxTop + boxH + 7 + 6;

  const haySupplierSku = grupo.productos.some((p: any) => p.supplier_sku);
  const hayPrecio = grupo.productos.some((p: any) => p.precio_proveedor && p.precio_proveedor > 0);
  const totalCant = grupo.productos.reduce((s, p) => s + p.cantidad_faltante, 0);

  // Derive CF flag from comentario (temporary mapping until a dedicated field exists)
  function isCF(comentario: string | null | undefined): boolean {
    if (!comentario) return false;
    const c = comentario.toUpperCase();
    return c.includes('FACTURA') || c === 'CF';
  }

  let headRow: string[];
  let bodyRows: (string | { content: string; styles?: Record<string, any> })[][];
  let footRow: string[];
  let colStyles: Record<number, any>;

  if (hayPrecio) {
    // Cant | Código | Concepto | U.M. | Fac | Precio Unit. | Importe
    headRow = ['Cant.', 'Código', 'Concepto', 'U.M.', 'Fac', 'Precio Unit.', 'Importe'];

    let granTotal = 0;
    bodyRows = grupo.productos.map((p: any) => {
      const precio = p.precio_proveedor || 0;
      const importe = precio * p.cantidad_faltante;
      granTotal += importe;
      return [
        String(p.cantidad_faltante),
        haySupplierSku ? (p.supplier_sku || p.sku) : p.sku,
        p.product_name + (p.marca ? ` (${p.marca})` : ''),
        p.unit || 'PZA',
        isCF(p.comentario) ? 'CF' : '',
        precio > 0 ? '$' + fmt(precio) : '',
        importe > 0 ? '$' + fmt(importe) : '',
      ];
    });

    footRow = [String(totalCant), '', '', '', '', 'TOTAL', granTotal > 0 ? '$' + fmt(granTotal) : ''];

    colStyles = {
      0: { cellWidth: 12, halign: 'center' as const, fontStyle: 'bold' as const },
      1: { cellWidth: 26, halign: 'center' as const, font: 'courier' as const },
      2: { cellWidth: 'auto' as const },
      3: { cellWidth: 12, halign: 'center' as const },
      4: { cellWidth: 10, halign: 'center' as const, fontSize: 7 },
      5: { cellWidth: 22, halign: 'right' as const },
      6: { cellWidth: 24, halign: 'right' as const, fontStyle: 'bold' as const },
    };
  } else {
    // Cant | Código | Concepto | U.M. | Fac
    headRow = ['Cant.', 'Código', 'Concepto', 'U.M.', 'Fac'];
    bodyRows = grupo.productos.map((p: any) => [
      String(p.cantidad_faltante),
      haySupplierSku ? (p.supplier_sku || p.sku) : p.sku,
      p.product_name + (p.marca ? ` (${p.marca})` : ''),
      p.unit || 'PZA',
      isCF(p.comentario) ? 'CF' : '',
    ]);
    footRow = [String(totalCant), '', 'Total', '', ''];
    colStyles = {
      0: { cellWidth: 12, halign: 'center' as const, fontStyle: 'bold' as const },
      1: { cellWidth: 26, halign: 'center' as const, font: 'courier' as const },
      2: { cellWidth: 'auto' as const },
      3: { cellWidth: 12, halign: 'center' as const },
      4: { cellWidth: 10, halign: 'center' as const, fontSize: 7 },
    };
  }

  autoTable(doc, {
    startY: y,
    head: [headRow],
    body: bodyRows,
    foot: [footRow],
    margin: { left: mx, right: mx },
    theme: 'grid',
    styles: {
      fontSize: 7.5,
      cellPadding: 2.5,
      textColor: negro as unknown as number[],
      lineColor: borde as unknown as number[],
      lineWidth: 0.3,
      valign: 'middle',
    },
    headStyles: {
      fillColor: fondoCelda as unknown as number[],
      textColor: negro as unknown as number[],
      fontStyle: 'bold',
      fontSize: 7.5,
    },
    footStyles: {
      fillColor: fondoCelda as unknown as number[],
      textColor: negro as unknown as number[],
      fontStyle: 'bold',
      fontSize: 7.5,
    },
    bodyStyles: {
      fillColor: [255, 255, 255],
    },
    columnStyles: colStyles,
  });

  // ════════════════════════════════════════════════════
  // RECUADRO DE OBSERVACIONES
  // ════════════════════════════════════════════════════

  const fy = (doc as any).lastAutoTable?.finalY || y + 40;
  let ny = fy + 6;
  const obsH = 25;

  if (ny + obsH + 40 > ph - 12) {
    doc.addPage();
    ny = 16;
  }

  doc.setFillColor(...fondoCelda);
  doc.setDrawColor(...borde);
  doc.setLineWidth(0.3);
  doc.rect(mx, ny, pw - 2 * mx, 7, 'FD');
  doc.setTextColor(...negro);
  doc.setFontSize(7.5);
  doc.setFont('helvetica', 'bold');
  doc.text('Observaciones', mx + 4, ny + 4.8);

  doc.setFillColor(255, 255, 255);
  doc.rect(mx, ny + 7, pw - 2 * mx, obsH, 'FD');

  if (observaciones && observaciones.trim()) {
    doc.setTextColor(...negro);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    const lines = doc.splitTextToSize(observaciones.trim(), pw - 2 * mx - 8);
    doc.text(lines, mx + 4, ny + 13);
  }

  // ════════════════════════════════════════════════════
  // CONDICIONES + FIRMAS
  // ════════════════════════════════════════════════════

  ny = ny + 7 + obsH + 8;

  doc.setTextColor(...gris);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.text('Favor de confirmar disponibilidad y tiempo de entrega.', mx, ny);
  doc.text(`Entregar en: ${EMP.dir}  ·  Tel. ${EMP.tel}`, mx, ny + 4);

  ny += 18;
  const fw = 55;
  doc.setDrawColor(...borde);
  doc.setLineWidth(0.3);
  doc.line(mx, ny, mx + fw, ny);
  doc.line(pw - mx - fw, ny, pw - mx, ny);
  doc.setTextColor(...gris);
  doc.setFontSize(7);
  doc.text('Elaboró', mx + fw / 2, ny + 4.5, { align: 'center' });
  doc.text('Autorizó', pw - mx - fw / 2, ny + 4.5, { align: 'center' });

  // ════════════════════════════════════════════════════
  // FOOTER
  // ════════════════════════════════════════════════════

  doc.setTextColor(...borde);
  doc.setFontSize(6);
  doc.text(`${EMP.razon}  ·  OC-${folio}`, pw / 2, ph - 6, { align: 'center' });

  doc.save(`OC_${grupo.proveedor_nombre.replace(/[^a-zA-Z0-9]/g, '_')}_${folio}.pdf`);
}

// NG-HEADER: Nombre de archivo: Market.test.tsx
// NG-HEADER: Ubicación: frontend/src/__tests__/Market.test.tsx
// NG-HEADER: Descripción: Tests unitarios para la página de Mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import React from 'react'
import Market from '../pages/Market'
import type { MarketProductItem } from '../services/market'
import * as marketServices from '../services/market'

// Mock de datos
const mockProducts: MarketProductItem[] = [
  {
    product_id: 1,
    preferred_name: 'Micelio Dorado',
    product_sku: 'HON_0001_MIC',
    sale_price: 1500,
    market_price_reference: 1600,
    market_price_min: 1400,
    market_price_max: 1800,
    last_market_update: '2025-11-10T10:00:00Z',
    category_id: 1,
    category_name: 'Hongos',
    supplier_id: 10,
    supplier_name: 'Proveedor A',
  },
  {
    product_id: 2,
    preferred_name: 'Maceta 5L',
    product_sku: 'CUL_0002_MAC',
    sale_price: 300,
    market_price_reference: 350,
    market_price_min: 280,
    market_price_max: 400,
    last_market_update: '2025-11-09T15:30:00Z',
    category_id: 2,
    category_name: 'Cultivo',
    supplier_id: 11,
    supplier_name: 'Proveedor B',
  },
  {
    product_id: 3,
    preferred_name: 'Sustrato Premium 20kg',
    product_sku: 'CUL_0003_SUS',
    sale_price: 850,
    market_price_reference: 800,
    market_price_min: 750,
    market_price_max: 900,
    last_market_update: '2025-11-11T08:00:00Z',
    category_id: 2,
    category_name: 'Cultivo',
    supplier_id: 10,
    supplier_name: 'Proveedor A',
  },
]

// Mock de servicios
vi.mock('../services/market', () => ({
  listMarketProducts: vi.fn(),
  getProductSources: vi.fn(),
  updateProductMarketPrices: vi.fn(),
  deleteProductSource: vi.fn(),
  updateProductSalePrice: vi.fn(),
  updateMarketReference: vi.fn(),
}))

vi.mock('../services/categories', () => ({
  listCategories: vi.fn(() => Promise.resolve([
    { id: 1, name: 'Hongos', parent_id: null },
    { id: 2, name: 'Cultivo', parent_id: null },
  ])),
}))

vi.mock('../services/suppliers', () => ({
  listSuppliers: vi.fn(() => Promise.resolve({
    items: [
      { id: 10, name: 'Proveedor A' },
      { id: 11, name: 'Proveedor B' },
    ],
    total: 2,
  })),
}))

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ state: { role: 'admin', userId: 1 } }),
}))

vi.mock('../components/ToastProvider', () => ({
  useToast: () => ({ push: vi.fn() }),
}))

vi.mock('../components/MarketDetailModal', () => ({
  __esModule: true,
  default: ({ productId, open, onClose }: any) => {
    if (!open) return null
    return (
      <div data-testid="market-detail-modal">
        <h3>Detalles del producto {productId}</h3>
        <button onClick={onClose}>Cerrar</button>
      </div>
    )
  },
}))

vi.mock('../components/supplier/SupplierAutocomplete', () => ({
  __esModule: true,
  default: ({ value, onChange, placeholder }: any) => (
    <input
      data-testid="supplier-autocomplete"
      placeholder={placeholder}
      value={value?.name || ''}
      onChange={(e) => {
        if (e.target.value === '') {
          onChange(null)
        }
      }}
    />
  ),
}))

// Wrapper con providers necesarios
const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>{children}</BrowserRouter>
)

describe('Market Page', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('Renderizado de tabla', () => {
    it('renderiza la tabla de productos correctamente', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: mockProducts,
        total: 3,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })

      // Esperar a que se carguen los productos
      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      }, { timeout: 2000 })

      expect(screen.getByText('Maceta 5L')).toBeInTheDocument()
      expect(screen.getByText('Sustrato Premium 20kg')).toBeInTheDocument()
    })

    it('muestra todas las columnas esperadas', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [mockProducts[0]],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Verificar encabezados de columnas
      expect(screen.getByText('Producto')).toBeInTheDocument()
      expect(screen.getByText('Precio Venta (ARS)')).toBeInTheDocument()
      expect(screen.getByText('Precio Mercado (ARS)')).toBeInTheDocument()
      expect(screen.getByText('Última Actualización')).toBeInTheDocument()
      expect(screen.getByText('Categoría')).toBeInTheDocument()
      expect(screen.getByText('Acciones')).toBeInTheDocument()

      // Verificar datos del producto
      expect(screen.getByText('$ 1500.00')).toBeInTheDocument()
      expect(screen.getByText('Hongos')).toBeInTheDocument()
    })

    it('muestra mensaje cuando no hay productos', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText(/0 productos encontrados/i)).toBeInTheDocument()
      })
    })

    it('muestra el estado de carga', async () => {
      vi.mocked(marketServices.listMarketProducts).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  items: [],
                  total: 0,
                  page: 1,
                  page_size: 50,
                  pages: 0,
                }),
              1000
            )
          )
      )

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      expect(screen.getByText('Cargando...')).toBeInTheDocument()

      vi.advanceTimersByTime(1000)
      await waitFor(() => {
        expect(screen.queryByText('Cargando...')).not.toBeInTheDocument()
      })
    })
  })

  describe('Filtrado de productos', () => {
    it('filtra productos por nombre al escribir en el campo de búsqueda', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts)
        .mockResolvedValueOnce({
          items: mockProducts,
          total: 3,
          page: 1,
          page_size: 50,
          pages: 1,
        })
        .mockResolvedValueOnce({
          items: [mockProducts[0]],
          total: 1,
          page: 1,
          page_size: 50,
          pages: 1,
        })

      render(<Market />, { wrapper: Wrapper })
      
      // Avanzar hasta que se cargue inicialmente
      await vi.advanceTimersByTimeAsync(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Escribir en el campo de búsqueda
      const searchInput = screen.getByPlaceholderText('Nombre o SKU...')
      await user.type(searchInput, 'Micelio')

      // Avanzar timers del debounce
      await vi.advanceTimersByTimeAsync(300)

      // Verificar que se llamó con el filtro
      await waitFor(() => {
        expect(vi.mocked(marketServices.listMarketProducts)).toHaveBeenLastCalledWith(
          expect.objectContaining({
            q: 'Micelio',
            page: 1,
          })
        )
      })
    })

    it('filtra productos por categoría', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts)
        .mockResolvedValueOnce({
          items: mockProducts,
          total: 3,
          page: 1,
          page_size: 50,
          pages: 1,
        })
        .mockResolvedValueOnce({
          items: [mockProducts[1], mockProducts[2]],
          total: 2,
          page: 1,
          page_size: 50,
          pages: 1,
        })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Seleccionar categoría
      const categorySelect = screen.getByTitle('Filtrar por categoría de producto')
      await user.selectOptions(categorySelect, '2')

      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(vi.mocked(marketServices.listMarketProducts)).toHaveBeenLastCalledWith(
          expect.objectContaining({
            category_id: 2,
          })
        )
      })
    })

    it('muestra badges de filtros activos', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: mockProducts,
        total: 3,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Aplicar filtro de búsqueda
      const searchInput = screen.getByPlaceholderText('Nombre o SKU...')
      await user.type(searchInput, 'Micelio')

      vi.advanceTimersByTime(300)

      // Verificar badge de filtro
      await waitFor(() => {
        expect(screen.getByText(/Búsqueda: "Micelio"/)).toBeInTheDocument()
      })
    })

    it('limpia todos los filtros al hacer clic en limpiar', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: mockProducts,
        total: 3,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Aplicar filtro
      const searchInput = screen.getByPlaceholderText('Nombre o SKU...')
      await user.type(searchInput, 'Micelio')
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText(/Búsqueda:/)).toBeInTheDocument()
      })

      // Limpiar filtros
      const clearButton = screen.getByTitle('Limpiar todos los filtros')
      await user.click(clearButton)

      // Verificar que se limpió
      expect(searchInput).toHaveValue('')
      expect(screen.queryByText(/Búsqueda:/)).not.toBeInTheDocument()
    })
  })

  describe('Modal de detalle', () => {
    it('abre el modal al hacer clic en Ver', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [mockProducts[0]],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Hacer clic en el botón Ver
      const verButton = screen.getByTitle('Ver detalles del mercado')
      await user.click(verButton)

      // Verificar que se abre el modal
      await waitFor(() => {
        expect(screen.getByTestId('market-detail-modal')).toBeInTheDocument()
        expect(screen.getByText('Detalles del producto 1')).toBeInTheDocument()
      })
    })

    it('cierra el modal correctamente', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [mockProducts[0]],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Abrir modal
      const verButton = screen.getByTitle('Ver detalles del mercado')
      await user.click(verButton)

      await waitFor(() => {
        expect(screen.getByTestId('market-detail-modal')).toBeInTheDocument()
      })

      // Cerrar modal
      const closeButton = screen.getByText('Cerrar')
      await user.click(closeButton)

      await waitFor(() => {
        expect(screen.queryByTestId('market-detail-modal')).not.toBeInTheDocument()
      })
    })
  })

  describe('Paginación', () => {
    it('muestra controles de paginación cuando hay múltiples páginas', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: mockProducts,
        total: 150,
        page: 1,
        page_size: 50,
        pages: 3,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Verificar controles de paginación
      expect(screen.getByText('Página 1 de 3 (150 productos)')).toBeInTheDocument()
      expect(screen.getByText('Anterior')).toBeInTheDocument()
      expect(screen.getByText('Siguiente')).toBeInTheDocument()
    })

    it('navega a la página siguiente correctamente', async () => {
      const user = userEvent.setup({ delay: null })

      vi.mocked(marketServices.listMarketProducts)
        .mockResolvedValueOnce({
          items: mockProducts,
          total: 150,
          page: 1,
          page_size: 50,
          pages: 3,
        })
        .mockResolvedValueOnce({
          items: mockProducts,
          total: 150,
          page: 2,
          page_size: 50,
          pages: 3,
        })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Hacer clic en Siguiente
      const nextButton = screen.getByText('Siguiente')
      await user.click(nextButton)

      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(vi.mocked(marketServices.listMarketProducts)).toHaveBeenLastCalledWith(
          expect.objectContaining({
            page: 2,
          })
        )
      })
    })

    it('deshabilita botón Anterior en la primera página', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: mockProducts,
        total: 150,
        page: 1,
        page_size: 50,
        pages: 3,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      const prevButton = screen.getByText('Anterior')
      expect(prevButton).toBeDisabled()
    })
  })

  describe('Comparación de precios', () => {
    it('aplica clase CSS correcta cuando precio está por debajo del mercado', async () => {
      const lowPriceProduct = {
        ...mockProducts[0],
        sale_price: 1200, // Menor que market_price_min (1400)
      }

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [lowPriceProduct],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Buscar la celda con el precio
      const priceCell = screen.getByText('$ 1200.00').closest('td')
      expect(priceCell).toHaveClass('price-below-market')
    })

    it('aplica clase CSS correcta cuando precio está por encima del mercado', async () => {
      const highPriceProduct = {
        ...mockProducts[0],
        sale_price: 2000, // Mayor que market_price_max (1800)
      }

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [highPriceProduct],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      const priceCell = screen.getByText('$ 2000.00').closest('td')
      expect(priceCell).toHaveClass('price-above-market')
    })

    it('aplica clase CSS correcta cuando precio está dentro del rango', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [mockProducts[0]], // sale_price 1500, rango 1400-1800
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      const priceCell = screen.getByText('$ 1500.00').closest('td')
      expect(priceCell).toHaveClass('price-in-market')
    })
  })

  describe('Formateo de datos', () => {
    it('formatea correctamente el rango de precios', async () => {
      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [mockProducts[0]],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Verificar formato del rango
      expect(screen.getByText('$ 1400.00 - $ 1800.00')).toBeInTheDocument()
      expect(screen.getByText('Ref: $ 1600.00')).toBeInTheDocument()
    })

    it('muestra "Sin datos" cuando no hay precios de mercado', async () => {
      const noMarketDataProduct = {
        ...mockProducts[0],
        market_price_min: null,
        market_price_max: null,
        market_price_reference: null,
      }

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [noMarketDataProduct],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      expect(screen.getByText('Sin datos')).toBeInTheDocument()
    })

    it('muestra "-" cuando sale_price es null', async () => {
      const noSalePriceProduct = {
        ...mockProducts[0],
        sale_price: null,
      }

      vi.mocked(marketServices.listMarketProducts).mockResolvedValue({
        items: [noSalePriceProduct],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      })

      render(<Market />, { wrapper: Wrapper })
      vi.advanceTimersByTime(300)

      await waitFor(() => {
        expect(screen.getByText('Micelio Dorado')).toBeInTheDocument()
      })

      // Buscar la celda de precio de venta que contiene "-"
      const rows = screen.getAllByRole('row')
      const dataRow = rows.find((row) => row.textContent?.includes('Micelio Dorado'))
      expect(dataRow?.textContent).toContain('-')
    })
  })
})


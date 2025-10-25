// NG-HEADER: Nombre de archivo: ProductDetail.spec.tsx
// NG-HEADER: Ubicación: frontend/src/pages/ProductDetail.spec.tsx
// NG-HEADER: Descripción: Pruebas de UI para enriquecimiento en detalle de producto (confirm overwrite)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProductDetail from './ProductDetail'
import http from '../services/http'
import { AuthProvider } from '../auth/AuthContext'
import { ThemeProvider } from '../theme/ThemeProvider'

// Mock de servicios y contextos
vi.mock('../services/http')
vi.mock('react-router-dom', async (importOriginal) => {
    const original = await importOriginal<typeof import('react-router-dom')>()
    return {
        ...original,
        useNavigate: () => vi.fn(), // Mock useNavigate
    }
})

const mockProd = {
  id: 1,
  title: 'Test Product',
  stock: 10,
  description_html: '<p>Original description</p>',
  images: [],
}

describe('ProductDetail Enrichment', () => {
  beforeEach(() => {
    // Mockear las llamadas http que el componente y sus providers necesitan
    vi.mocked(http.get).mockImplementation(async (url) => {
        if (url.includes('/auth/me')) {
            return { data: { is_authenticated: true, role: 'admin', user: { id: 1, name: 'Test Admin' } } }
        }
        if (url.startsWith('/products/') && url.includes('variants')) {
            return { data: [] };
        }
        if (url.startsWith('/products/')) {
            return { data: mockProd };
        }
        if (url === '/categories') {
            return { data: [] };
        }
        if (url.includes('offerings')) {
            return { data: [] };
        }
        return { data: {} };
    });
    vi.mocked(http.post).mockResolvedValue({ data: { status: 'ok' } });
    vi.spyOn(window, 'confirm').mockReturnValue(false); // Por defecto, el usuario cancela
  })

  afterEach(() => {
    vi.restoreAllMocks() // Limpiar spies y mocks
  })

  const renderComponent = () => {
    return render(
        <MemoryRouter initialEntries={['/products/1']}>
            <AuthProvider>
                <ThemeProvider>
                    <Routes>
                        <Route path="/products/:id" element={<ProductDetail />} />
                    </Routes>
                </ThemeProvider>
            </AuthProvider>
        </MemoryRouter>
    )
  }

  it('should show warning if description is dirty before enriching', async () => {
    renderComponent()

    // Esperar a que el producto se cargue
    await waitFor(() => {
      expect(screen.getByText('Test Product')).toBeInTheDocument()
    })

    const descriptionTextarea = screen.getByPlaceholderText('Descripción (HTML o texto)')
    const enrichButton = screen.getByText('Enriquecer con IA')

    // 1. Modificar la descripción para que esté "sucia"
    fireEvent.change(descriptionTextarea, { target: { value: 'New description' } })

    // 2. Click en enriquecer, ahora sí debe llamar a confirm
    fireEvent.click(enrichButton)
    expect(window.confirm).toHaveBeenCalledWith('La descripción tiene cambios manuales que se perderán. ¿Deseas sobrescribirlos con el enriquecimiento de IA?')
    
    // 3. Como window.confirm está mockeado para devolver false, no se debe llamar a la API
    expect(http.post).not.toHaveBeenCalled()
  })

  it('should proceed with enrichment if user confirms overwrite', async () => {
    // Mockear confirm para que devuelva true
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('Test Product')).toBeInTheDocument()
    })

    const descriptionTextarea = screen.getByPlaceholderText('Descripción (HTML o texto)')
    const enrichButton = screen.getByText('Enriquecer con IA')

    // Modificar la descripción
    fireEvent.change(descriptionTextarea, { target: { value: 'Another new description' } })

    // Click en enriquecer
    fireEvent.click(enrichButton)

    // Se debe llamar a confirm
    expect(window.confirm).toHaveBeenCalled()

    // Como el usuario confirmó, la llamada a la API debe realizarse
    await waitFor(() => {
      expect(http.post).toHaveBeenCalledWith('/products/1/enrich')
    })
    expect(http.post).toHaveBeenCalledTimes(1)
  })
})
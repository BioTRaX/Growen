// NG-HEADER: Nombre de archivo: App.tsx
// NG-HEADER: Ubicación: frontend/src/App.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Login from "./pages/Login";
import { lazy, Suspense } from 'react';
// Legacy AdminPanel kept for backward-compat entry but replaced by nested /admin routes
const AdminPanel = lazy(() => import('./pages/AdminPanel'))
const ImagesAdminPanel = lazy(() => import('./pages/ImagesAdminPanel'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Stock = lazy(() => import('./pages/Stock'))
const Productos = lazy(() => import('./pages/Productos'))
const ProductDetail = lazy(() => import('./pages/ProductDetail'))
const Purchases = lazy(() => import('./pages/Purchases'))
const PurchaseNew = lazy(() => import('./pages/PurchaseNew'))
const PurchaseDetail = lazy(() => import('./pages/PurchaseDetail'))
const SuppliersPage = lazy(() => import('./pages/Suppliers'))
import { PATHS } from "./routes/paths";
// New Admin sections (code-split per route)
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout'))
const AdminUsers = lazy(() => import('./pages/admin/UsersPage'))
const AdminServices = lazy(() => import('./pages/admin/ServicesPage'))
const AdminImages = lazy(() => import('./pages/admin/ImagesCrawlerPage'))

export default function App() {
  return (
  <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<div style={{padding:12}}>Cargando…</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/guest"
            element={
              <ProtectedRoute roles={["guest", "cliente", "proveedor", "colaborador", "admin"]}>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.home}
            element={
              <ProtectedRoute roles={["cliente", "proveedor", "colaborador", "admin"]}>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.stock}
            element={
              <ProtectedRoute roles={["cliente", "proveedor", "colaborador", "admin"]}>
                <Stock />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.products}
            element={
              <ProtectedRoute roles={["cliente", "proveedor", "colaborador", "admin"]}>
                <Productos />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.suppliers}
            element={
              <ProtectedRoute roles={["cliente", "proveedor", "colaborador", "admin"]}>
                <SuppliersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/productos/:id"
            element={
              <ProtectedRoute roles={["guest", "cliente", "proveedor", "colaborador", "admin"]}>
                <ProductDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.purchases}
            element={
              <ProtectedRoute roles={["colaborador", "admin"]}>
                <Purchases />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.purchasesNew}
            element={
              <ProtectedRoute roles={["colaborador", "admin"]}>
                <PurchaseNew />
              </ProtectedRoute>
            }
          />
          <Route
            path="/compras/:id"
            element={
              <ProtectedRoute roles={["colaborador", "admin"]}>
                <PurchaseDetail />
              </ProtectedRoute>
            }
          />
          {/* New Admin router with nested sections and role guards */}
          <Route
            path={PATHS.admin}
            element={
              <ProtectedRoute roles={["colaborador", "admin"]}>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route path="servicios" element={<AdminServices />} />
            <Route path="imagenes-productos" element={<AdminImages />} />
            {/* Users only for admins */}
            <Route
              path="usuarios"
              element={
                <ProtectedRoute roles={["admin"]}>
                  <AdminUsers />
                </ProtectedRoute>
              }
            />
          </Route>
          {/* Legacy fallbacks */}
          <Route
            path={PATHS.imagesAdmin}
            element={
              <ProtectedRoute roles={["colaborador", "admin"]}>
                <Navigate to={PATHS.adminImages} replace />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}

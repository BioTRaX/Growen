import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Login from "./pages/Login";
import AdminPanel from "./pages/AdminPanel";
import ImagesAdminPanel from "./pages/ImagesAdminPanel";
import Dashboard from "./pages/Dashboard";
import Stock from "./pages/Stock";
import Productos from "./pages/Productos";
import ProductDetail from "./pages/ProductDetail";
import Purchases from "./pages/Purchases";
import PurchaseNew from "./pages/PurchaseNew";
import PurchaseDetail from "./pages/PurchaseDetail";
import SuppliersPage from "./pages/Suppliers";
import { PATHS } from "./routes/paths";

export default function App() {
  return (
  <BrowserRouter>
      <AuthProvider>
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
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminPanel />
              </ProtectedRoute>
            }
          />
          <Route
            path={PATHS.imagesAdmin}
            element={
              <ProtectedRoute roles={["colaborador", "admin"]}>
                <ImagesAdminPanel />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

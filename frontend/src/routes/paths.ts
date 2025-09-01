export const PATHS = {
  home: "/",
  products: "/productos",
  productDetail: (id: number | string) => `/productos/${id}`,
  stock: "/stock",
  suppliers: "/proveedores",
  purchases: "/compras",
  purchasesNew: "/compras/nueva",
  imagesAdmin: "/admin/imagenes",
} as const;

export type AppPath = typeof PATHS[keyof typeof PATHS];

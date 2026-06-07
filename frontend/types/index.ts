export enum VehicleType {
  Panelvan = "panelvan",
  Kamyonet = "kamyonet",
  Kamyon = "kamyon",
  Tir = "tir",
  Elektrikli = "elektrikli",
}

export type User = {
  username: string;
  full_name: string;
  role: string;
};

export type AuthUser = User;

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export type LoginRequest = {
  username: string;
  password: string;
};

export type LoginResult = AuthTokens & {
  user: User;
};

export type Shipment = {
  id: string;
  customer_id?: string | null;
  driver_id?: string | null;
  vehicle_id?: string | null;
  customer_name: string;
  origin: string;
  destination: string;
  cargo_type: string;
  tonnage: number;
  weight_kg?: number | null;
  desi?: number | null;
  delivery_date: string;
  distance_km: number;
  vehicle_type: string;
  status: string;
  cost_amount: number;
  invoice_amount: number;
  profit_amount: number;
  invoice?: number | null;
  cost?: number | null;
  profit?: number | null;
  profit_margin: number;
  co2_kg: number;
  carbon_emission?: number;
  risk_level: string;
  ai_recommendation: string;
  created_at?: string;
  updated_at?: string;
};

export type ShipmentCreate = {
  customer_id?: string | null;
  driver_id?: string | null;
  vehicle_id?: string | null;
  customer_name: string;
  origin: string;
  destination: string;
  cargo_type: string;
  tonnage: number;
  weight_kg?: number | null;
  desi?: number | null;
  distance_km?: number | null;
  vehicle_type?: string | null;
  delivery_date: string;
  status?: string;
  invoice_amount?: number;
  profit_amount?: number;
  co2_kg?: number;
  shipment_type?: string;
};

export type ShipmentUpdate = Partial<
  ShipmentCreate & {
    distance_km: number | null;
    vehicle_type: string | null;
    invoice: number | null;
    cost: number | null;
    profit: number | null;
    cost_amount: number;
    invoice_amount: number;
    profit_amount: number;
    profit_margin: number;
    co2_kg: number;
    carbon_emission: number;
    risk_level: string;
    ai_recommendation: string;
  }
>;

export type Customer = {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  tax_number?: string | null;
  sector?: string | null;
  payment_terms: string;
  risk_level: string;
  notes?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CustomerCreate = {
  name: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  tax_number?: string | null;
  sector?: string | null;
  payment_terms?: string;
  risk_level?: string;
  notes?: string | null;
  is_active?: boolean;
};

export type CustomerUpdate = Partial<CustomerCreate>;

export type CustomerWithShipments = Customer & {
  shipments: Shipment[];
};

export type CustomerListParams = {
  skip?: number;
  limit?: number;
  search?: string;
  city?: string;
  is_active?: boolean;
};

export type CustomerCarbonStats = {
  customer_id: string;
  total_co2_kg: number;
  shipment_count: number;
  average_co2_kg: number;
  by_vehicle: CarbonVehicleDistribution[];
  top_routes: CarbonRoute[];
};

export type ApiResponse<T> = {
  data: T;
  message?: string;
  status?: string;
};

export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  skip: number;
  limit: number;
};

export type ShipmentListParams = {
  skip?: number;
  limit?: number;
  status?: string;
  customer_id?: string;
  driver_id?: string;
  origin?: string;
  destination?: string;
};

export type VehicleStatus = "Bosta" | "Yukleniyor" | "Yolda" | "Bakimda";

export type Vehicle = {
  id: string;
  plate_number: string;
  vehicle_type: string;
  capacity_tons: number;
  current_load_tons: number;
  driver_name?: string | null;
  driver_phone?: string | null;
  status: VehicleStatus | string;
  current_lat?: number | null;
  current_lng?: number | null;
  current_shipment_id?: string | null;
  notes?: string | null;
  is_deleted?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type VehicleCreate = Omit<Vehicle, "id" | "created_at" | "updated_at" | "is_deleted">;

export type VehicleUpdate = Partial<VehicleCreate>;

export type VehicleListResponse = {
  items: Vehicle[];
  total: number;
};

export type VehicleAssign = {
  shipment_id: string;
  load_tons: number;
};

export type ShipmentExportFilters = {
  start_date?: string;
  end_date?: string;
  vehicle_type?: string;
  status?: string;
  customer_id?: string;
};

export type CarbonFilters = {
  start_date?: string;
  end_date?: string;
};

export type CarbonVehicleDistribution = {
  vehicle_type: VehicleType | string;
  co2: number;
};

export type CarbonTrend = {
  period: string;
  co2: number;
};

export type CarbonRoute = {
  origin: string;
  destination: string;
  vehicle_type?: string;
  co2: number;
  shipment_count: number;
};

export type CarbonSummary = {
  total_co2: number;
  by_vehicle: CarbonVehicleDistribution[];
  trend: CarbonTrend[];
  top_routes: CarbonRoute[];
};

export type GeocodeResult = {
  location: string;
  lat: number | null;
  lon: number | null;
};

export type DistanceResult = {
  origin: string;
  destination: string;
  distance_km: number | null;
  origin_coords: { lat: number; lon: number } | null;
  destination_coords: { lat: number; lon: number } | null;
};

export type RouteResult = DistanceResult & {
  duration_minutes: number | null;
  geometry:
    | {
        type: string;
        coordinates: [number, number][];
      }
    | [number, number][]
    | string
    | null;
};

export type EmissionFactor = {
  id?: string;
  vehicle_type: VehicleType | string;
  co2_per_km: number;
  co2_per_kg_km: number;
  description?: string | null;
};

export type EmissionCalculationRequest = {
  vehicle_type: VehicleType | string;
  distance_km: number;
  weight_kg: number;
};

export type EmissionCalculation = EmissionCalculationRequest & {
  carbon_emission: number;
  benchmark: {
    benchmark_co2: number;
    deviation_percent: number;
    label: "yesil" | "orta" | "yuksek" | string;
  };
};

export type DashboardSummary = {
  total_revenue: number;
  total_profit: number;
  active_operations: number;
  delivery_success_rate: number;
  total_co2_kg: number;
  risky_operations: number;
};

export type Finance = {
  current_cash: number;
  pending_collections: number;
  projected_outflow: number;
  projected_cash_15_days: number;
  total_profit: number;
  ai_warning: string;
};

export type Carbon = {
  total_co2_kg: number;
  highest_emission_route: string | null;
  optimization_note: string;
};

export type AiAnalysis = {
  summary: string;
  suggested_vehicle: string;
  estimated_price: number;
  estimated_profit: number;
  estimated_co2_kg: number;
  risk_level: string;
};

export type LiveMap = {
  vehicles: Array<{
    plate: string;
    driver: string;
    vehicle_type: string;
    status: string;
    route: string;
    progress: number;
    lat: number;
    lng: number;
    risk_level: string;
  }>;
  depots: Array<{
    name: string;
    lat: number;
    lng: number;
    occupancy: number;
  }>;
  heatmap: Array<{
    city: string;
    level: string;
    shipments: number;
  }>;
  traffic_note: string;
};

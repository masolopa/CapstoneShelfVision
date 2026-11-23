export type AnalysisMethod = "heuristic" | "yolo" | "both";

export type Criticality = "aceptable" | "baja" | "critica" | "no_evaluable";

export interface AnalysisResult {
  availability_basis?: 'surface' | 'useful_fronts';
  upper_free_surface_pct?: number;
  alert_product_coverage_pct?: number;
  alert_basis?: 'product_coverage_review';
  surface_availability_pct?: number | null;
  surface_empty_pct?: number | null;
  useful_occupied_fronts?: number;
  useful_free_fronts?: number;
  pasillo: string;
  requested_shelves?: number | null; capture_date?: string; reference?: string; observations?: string; original_jpg_b64?: string;
  id: number;
  status: "evaluable" | "no_evaluable";
  availability_pct: number | null;
  empty_pct: number | null;
  evaluable_area: number;
  unknown_area: number;
  structural_area: number;
  excluded_area: number;
  alert: boolean;
  criticality: Criticality;
  reason: string;
  threshold: number;
  low_threshold?: number;
  excluded_px: number;
  warnings: string[];
  areas_px: Record<string, number>;
  perspective_corrected: boolean;
  inference_seconds: number;
  method: string;
  overlay_jpg_b64: string;
  conteo?: Conteo | null;
  filename?: string;
  created_at?: string;
}

export interface HistoryItem {
  pasillo: string | null;
  origin?: "live" | "historical_test";
  legacy_id?: number;
  reference?: string;
  id: number;
  created_at: string;
  filename: string;
  availability_pct: number | null;
  empty_pct: number | null;
  alert: number;
  criticality: Criticality;
}

export interface Metrics {
  total_analyses: number;
  avg_availability_pct: number | null;
  avg_empty_pct: number | null;
  alerts: number;
}

export interface Settings {
  threshold: number;
  max_upload_mb: number;
  min_side_px: number;
}

export interface Health {
  status: string;
  detector: string;
  model_ml: string;
}

export interface TrainingStatus {
  dataset: {
    raw_images: number;
    prepared: boolean;
    unique_images: number;
    splits: { train: number; val: number; test: number } | null;
    class_share_pct: Record<string, number> | null;
    labels?: Record<string, string>;
    limitations?: string[];
  };
  modelo: {
    ready: boolean;
    checkpoint: string | null;
    metrics: Record<string, number> | null;
    reason: string | null;
  };
}

export interface ShelfRow {
  indice: number;
  productos: number;
  frentes_ocupados: number;
  frentes_totales: number;
  frentes_libres: number;
  ocupacion_pct: number;
  estado: "REPONER" | "REVISAR" | "OK";
  confianza_media: number | null;
}

export interface ConteoResumen {
  productos: number;
  filas: number;
  frentes_totales: number;
  frentes_ocupados: number;
  frentes_libres: number;
  ocupacion_pct: number | null;
  filas_reponer: number;
  filas_revisar: number;
  umbral_pct: number;
  low_threshold?: number;
  vacios_detectados?: number;
  huecos_detectados?: number;
  frentes_para_rellenar_huecos?: number;
}

export interface Producto {
  id: number;
  fila: number;
  posicion: number;
  bbox: number[];
  confianza: number | null;
}

export interface Conteo {
  filas: ShelfRow[];
  resumen: ConteoResumen;
  productos: Producto[];
}

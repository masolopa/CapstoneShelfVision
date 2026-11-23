export const SEMANTIC = {
  occupied: { label: "Ocupado", color: "#16A34A", rgb: "0,200,0", counts: true },
  empty: { label: "Vacío", color: "#DC2626", rgb: "220,0,0", counts: true },
  excluded: { label: "Excluido", color: "#9CA3AF", rgb: "128,128,128", counts: false },
  structural: { label: "Estructural", color: "#0064DC", rgb: "0,100,220", counts: false },
  unknown: { label: "Desconocido", color: "#E6C800", rgb: "230,200,0", counts: false },
} as const;

export type Semantic = keyof typeof SEMANTIC;

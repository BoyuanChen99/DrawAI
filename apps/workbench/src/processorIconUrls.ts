export const PROCESSOR_ICON_URLS: Record<string, string> = {
  no_process: "/processor-icons/no-process.svg",
  crop: "/processor-icons/crop.svg",
  crop_nobg: "/processor-icons/crop-nobg.svg",
  svg_self_draw: "/processor-icons/svg-self-draw.svg",
  image_generate: "/processor-icons/image-generate.svg",
  image_edit: "/processor-icons/image-edit.svg",
  chart_rebuild_reserved: "/processor-icons/chart-rebuild-reserved.svg",
  sam_parse: "/processor-icons/sam-parse.svg",
  ocr_parse: "/processor-icons/ocr-parse.svg",
  page_spec_fuse: "/processor-icons/page-spec-fuse.svg",
  asset_prepare: "/processor-icons/asset-prepare.svg",
  asset_planner: "/processor-icons/asset-planner.svg",
  asset_processors: "/processor-icons/asset-processors.svg",
};

export function processorIconUrlForId(processorId: string): string | null {
  const normalized = processorId.trim();
  return PROCESSOR_ICON_URLS[normalized] || null;
}

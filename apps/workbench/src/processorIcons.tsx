import type { ReactNode } from "react";

import { processorIconUrlForId } from "./processorIconUrls";

export { PROCESSOR_ICON_URLS, processorIconUrlForId } from "./processorIconUrls";

type ProcessorIconProps = {
  processorId: string;
  className?: string;
  fallback?: ReactNode;
};

export function ProcessorIcon({ processorId, className = "processor-icon-image", fallback = null }: ProcessorIconProps) {
  const iconUrl = processorIconUrlForId(processorId);
  if (!iconUrl) return fallback;
  return <img className={className} src={iconUrl} alt="" />;
}

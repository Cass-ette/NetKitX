"use client";

import React, { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { PluginUIProps } from "@/types";

const ChartView = React.lazy(() => import("./chart-view"));
const TopologyView = React.lazy(() => import("./topology-view"));

const UI_REGISTRY: Record<string, React.LazyExoticComponent<React.ComponentType<PluginUIProps>>> = {
  chart: ChartView,
  topology: TopologyView,
};

export function isRegisteredUI(name: string): boolean {
  return name in UI_REGISTRY;
}

interface PluginUIRendererProps extends PluginUIProps {
  uiComponent: string;
}

export function PluginUIRenderer({ uiComponent, ...props }: PluginUIRendererProps) {
  const Component = UI_REGISTRY[uiComponent];
  if (!Component) return null;

  return (
    <Suspense
      fallback={
        <div className="space-y-3">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      }
    >
      <Component {...props} />
    </Suspense>
  );
}

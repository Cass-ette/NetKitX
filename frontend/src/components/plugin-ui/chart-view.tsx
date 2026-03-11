"use client";

import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTranslations } from "@/i18n/use-translations";
import type { PluginUIProps, ChartConfig } from "@/types";

const COLORS = [
  "hsl(221, 83%, 53%)",
  "hsl(142, 71%, 45%)",
  "hsl(38, 92%, 50%)",
  "hsl(0, 84%, 60%)",
  "hsl(262, 83%, 58%)",
  "hsl(187, 85%, 43%)",
  "hsl(330, 81%, 60%)",
  "hsl(25, 95%, 53%)",
];

function detectChartConfigs(
  results: Record<string, unknown>[],
  explicitCharts?: ChartConfig[],
): ChartConfig[] {
  if (explicitCharts && explicitCharts.length > 0) return explicitCharts;
  if (results.length === 0) return [];

  const keys = Object.keys(results[0]);
  const numericKeys: string[] = [];
  const categoryKeys: string[] = [];

  for (const key of keys) {
    const values = results.map((r) => r[key]);
    const numericCount = values.filter((v) => typeof v === "number" || !isNaN(Number(v))).length;
    if (numericCount > results.length * 0.7) {
      numericKeys.push(key);
    } else {
      categoryKeys.push(key);
    }
  }

  if (numericKeys.length === 0) return [];

  const xKey = categoryKeys[0] || keys[0];
  const configs: ChartConfig[] = [];

  if (numericKeys.length === 1) {
    configs.push({ type: "bar", x: xKey, y: numericKeys[0] });
  } else {
    for (const yKey of numericKeys.slice(0, 3)) {
      configs.push({ type: "bar", x: xKey, y: yKey, title: yKey });
    }
  }

  return configs;
}

function ChartRenderer({
  config,
  data,
  index,
}: {
  config: ChartConfig;
  data: Record<string, unknown>[];
  index: number;
}) {
  const xKey = config.x || Object.keys(data[0] || {})[0] || "name";
  const yKey = config.y || Object.keys(data[0] || {})[1] || "value";
  const color = COLORS[index % COLORS.length];

  const chartData = data.map((row) => ({
    ...row,
    [yKey]: Number(row[yKey]) || 0,
  }));

  switch (config.type) {
    case "pie":
      return (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey={yKey}
              nameKey={xKey}
              cx="50%"
              cy="50%"
              outerRadius={100}
              label
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      );

    case "line":
      return (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey={yKey} stroke={color} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      );

    case "area":
      return (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area type="monotone" dataKey={yKey} stroke={color} fill={color} fillOpacity={0.3} />
          </AreaChart>
        </ResponsiveContainer>
      );

    default:
      return (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      );
  }
}

export default function ChartView({ tool, results }: PluginUIProps) {
  const { t } = useTranslations("tools");
  const [activeTab, setActiveTab] = useState("charts");

  const charts = useMemo(
    () => detectChartConfigs(results, tool.output?.charts),
    [results, tool.output?.charts],
  );

  const columns = tool.output?.columns || [];

  if (charts.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">{t("noChartData")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("results", { count: results.length })}</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="charts">{t("chartView")}</TabsTrigger>
            <TabsTrigger value="table">{t("table")}</TabsTrigger>
          </TabsList>

          <TabsContent value="charts" className="space-y-6 pt-4">
            {charts.map((config, i) => (
              <div key={i}>
                {config.title && (
                  <h4 className="mb-2 text-sm font-medium text-muted-foreground">
                    {config.title}
                  </h4>
                )}
                <ChartRenderer config={config} data={results} index={i} />
              </div>
            ))}
          </TabsContent>

          <TabsContent value="table" className="pt-4">
            {columns.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    {columns.map((col) => (
                      <TableHead key={col.key}>{col.label}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((row, i) => (
                    <TableRow key={i}>
                      {columns.map((col) => (
                        <TableCell key={col.key}>{String(row[col.key] ?? "")}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <pre className="max-h-96 overflow-auto rounded bg-muted p-3 text-xs">
                {JSON.stringify(results, null, 2)}
              </pre>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

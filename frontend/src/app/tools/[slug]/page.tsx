export default function ToolDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Tool Detail</h1>
      <p className="text-muted-foreground">
        Tool configuration and execution page. Parameters form will be auto-generated from plugin.yaml.
      </p>
    </div>
  );
}

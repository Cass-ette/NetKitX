import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function ToolsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Tools</h1>
        <p className="text-muted-foreground">Available security tools</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="cursor-pointer hover:border-primary transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Port Scanner</CardTitle>
              <Badge>recon</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              TCP port scanner powered by Go engine. Fast concurrent scanning.
            </p>
            <div className="mt-2 flex gap-2">
              <Badge variant="outline">go</Badge>
              <Badge variant="outline">v1.0.0</Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Ping Sweep</CardTitle>
              <Badge>recon</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Check host reachability with ICMP ping sweep.
            </p>
            <div className="mt-2 flex gap-2">
              <Badge variant="outline">python</Badge>
              <Badge variant="outline">v1.0.0</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

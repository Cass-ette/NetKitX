"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BookOpen, Rocket, FileCode, Settings2, Code2, Monitor, Package, ArrowUp, MessageSquare, LayoutTemplate } from "lucide-react";
import { useTranslations } from "@/i18n/use-translations";

const sections = [
  { id: "quick-start", icon: Rocket },
  { id: "plugin-yaml", icon: FileCode },
  { id: "param-types", icon: Settings2 },
  { id: "plugin-api", icon: Code2 },
  { id: "session-plugin", icon: MessageSquare },
  { id: "custom-ui", icon: LayoutTemplate },
  { id: "output-format", icon: Monitor },
  { id: "go-plugin", icon: Package },
  { id: "publish-flow", icon: ArrowUp },
] as const;

type SectionId = (typeof sections)[number]["id"];

const sectionTitleKeys: Record<SectionId, string> = {
  "quick-start": "quickStart",
  "plugin-yaml": "pluginYaml",
  "param-types": "paramTypes",
  "plugin-api": "pluginApi",
  "session-plugin": "sessionPlugin",
  "custom-ui": "customUi",
  "output-format": "outputFormat",
  "go-plugin": "goPlugin",
  "publish-flow": "publishFlow",
};

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm">
      <code>{children}</code>
    </pre>
  );
}

function FieldRow({ name, desc }: { name: string; desc: string }) {
  return (
    <div className="flex gap-2 items-baseline">
      <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono whitespace-nowrap">{name}</code>
      <span className="text-sm text-muted-foreground">— {desc}</span>
    </div>
  );
}

export default function DevelopersPage() {
  const { t } = useTranslations("developers");
  const [activeSection, setActiveSection] = useState<string>("quick-start");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px" }
    );

    for (const section of sections) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <BookOpen className="h-8 w-8" />
          <h1 className="text-3xl font-bold">{t("title")}</h1>
        </div>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="flex gap-8">
        {/* Sticky sidebar TOC */}
        <nav className="hidden lg:block w-56 shrink-0">
          <div className="sticky top-6 space-y-1">
            <p className="text-sm font-semibold mb-3">{t("tableOfContents")}</p>
            {sections.map((s) => {
              const Icon = s.icon;
              return (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
                    activeSection === s.id
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {t(sectionTitleKeys[s.id])}
                </a>
              );
            })}
          </div>
        </nav>

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-8">
          {/* Quick Start */}
          <Card id="quick-start" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Rocket className="h-5 w-5" />
                {t("quickStart")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("quickStartDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="font-semibold mb-2">{t("quickStartStep1Title")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("quickStartStep1Desc")}</p>
                <CodeBlock>{`mkdir plugins/my-scanner
cd plugins/my-scanner`}</CodeBlock>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("quickStartStep2Title")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("quickStartStep2Desc")}</p>
                <CodeBlock>{`name: my-scanner
display_name: My Scanner
version: 1.0.0
description: A simple port scanner
author: you
category: scanner
engine: python
params:
  - name: target
    label: Target Host
    type: string
    required: true
output:
  type: table
  columns:
    - name: port
      label: Port
    - name: status
      label: Status`}</CodeBlock>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("quickStartStep3Title")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("quickStartStep3Desc")}</p>
                <CodeBlock>{`from collections.abc import AsyncIterator
from app.plugins.base import PluginBase, PluginEvent

class Plugin(PluginBase):
    async def execute(self, params: dict) -> AsyncIterator[PluginEvent]:
        target = params["target"]
        ports = [22, 80, 443, 8080]
        for i, port in enumerate(ports):
            yield PluginEvent(type="result", data={"port": port, "status": "open"})
            yield PluginEvent(type="progress", data={"percent": (i + 1) * 100 // len(ports)})`}</CodeBlock>
              </div>
              <p className="text-sm text-muted-foreground">{t("quickStartTestDesc")}</p>
            </CardContent>
          </Card>

          {/* plugin.yaml Specification */}
          <Card id="plugin-yaml" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileCode className="h-5 w-5" />
                {t("pluginYaml")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("pluginYamlDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <FieldRow name={t("pluginYamlFieldName")} desc={t("pluginYamlFieldNameDesc")} />
                <FieldRow name={t("pluginYamlFieldDisplayName")} desc={t("pluginYamlFieldDisplayNameDesc")} />
                <FieldRow name={t("pluginYamlFieldVersion")} desc={t("pluginYamlFieldVersionDesc")} />
                <FieldRow name={t("pluginYamlFieldDescription")} desc={t("pluginYamlFieldDescriptionDesc")} />
                <FieldRow name={t("pluginYamlFieldAuthor")} desc={t("pluginYamlFieldAuthorDesc")} />
                <FieldRow name={t("pluginYamlFieldCategory")} desc={t("pluginYamlFieldCategoryDesc")} />
                <FieldRow name={t("pluginYamlFieldEngine")} desc={t("pluginYamlFieldEngineDesc")} />
                <FieldRow name={t("pluginYamlFieldEntrypoint")} desc={t("pluginYamlFieldEntrypointDesc")} />
                <FieldRow name={t("pluginYamlFieldParams")} desc={t("pluginYamlFieldParamsDesc")} />
                <FieldRow name={t("pluginYamlFieldOutput")} desc={t("pluginYamlFieldOutputDesc")} />
                <FieldRow name={t("pluginYamlFieldMode")} desc={t("pluginYamlFieldModeDesc")} />
                <FieldRow name={t("pluginYamlFieldDependencies")} desc={t("pluginYamlFieldDependenciesDesc")} />
                <FieldRow name={t("pluginYamlFieldTags")} desc={t("pluginYamlFieldTagsDesc")} />
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("pluginYamlExample")}</h3>
                <CodeBlock>{`name: sql-inject
display_name: SQL Injection Scanner
version: 2.0.0
description: Advanced SQL injection detection tool
author: netkitx-team
category: scanner
engine: python
tags:
  - sql
  - injection
  - web
params:
  - name: url
    label: Target URL
    type: string
    required: true
    placeholder: "https://example.com/page?id=1"
  - name: method
    label: HTTP Method
    type: select
    default: GET
    options:
      - GET
      - POST
  - name: verbose
    label: Verbose Output
    type: boolean
    default: false
output:
  type: table
  columns:
    - name: url
      label: URL
    - name: param
      label: Parameter
    - name: type
      label: Injection Type
    - name: payload
      label: Payload
dependencies:
  - http-client: ">=1.0.0"`}</CodeBlock>
              </div>
            </CardContent>
          </Card>

          {/* Parameter Types */}
          <Card id="param-types" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="h-5 w-5" />
                {t("paramTypes")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("paramTypesDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <FieldRow name="name" desc={t("paramFieldName")} />
                <FieldRow name="label" desc={t("paramFieldLabel")} />
                <FieldRow name="type" desc={t("paramFieldType")} />
                <FieldRow name="required" desc={t("paramFieldRequired")} />
                <FieldRow name="default" desc={t("paramFieldDefault")} />
                <FieldRow name="placeholder" desc={t("paramFieldPlaceholder")} />
                <FieldRow name="options" desc={t("paramFieldOptions")} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4 mt-4">
                {(["String", "Number", "Boolean", "Select"] as const).map((type) => (
                  <div key={type} className="border rounded-lg p-4">
                    <code className="text-sm font-semibold">{t(`paramType${type}`)}</code>
                    <p className="text-sm text-muted-foreground mt-1">{t(`paramType${type}Desc`)}</p>
                  </div>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("paramExample")}</h3>
                <CodeBlock>{`params:
  - name: target
    label: Target Host
    type: string
    required: true
    placeholder: "192.168.1.1"

  - name: port
    label: Port Number
    type: number
    default: 80

  - name: verbose
    label: Verbose Mode
    type: boolean
    default: false

  - name: protocol
    label: Protocol
    type: select
    default: tcp
    options:
      - tcp
      - udp`}</CodeBlock>
              </div>
            </CardContent>
          </Card>

          {/* Plugin API */}
          <Card id="plugin-api" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code2 className="h-5 w-5" />
                {t("pluginApi")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("pluginApiDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">{t("executeMethod")}</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("executeMethodDesc")}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">{t("validateMethod")}</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("validateMethodDesc")}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">{t("cleanupMethod")}</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("cleanupMethodDesc")}</p>
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("eventTypes")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("eventTypesDesc")}</p>
                <div className="grid gap-2">
                  <FieldRow name="progress" desc={t("eventProgress")} />
                  <FieldRow name="log" desc={t("eventLog")} />
                  <FieldRow name="data" desc={t("eventData")} />
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("pluginApiExample")}</h3>
                <CodeBlock>{`from collections.abc import AsyncIterator
from app.plugins.base import PluginBase, PluginEvent

class Plugin(PluginBase):
    async def validate_params(self, params: dict) -> dict:
        if not params.get("target"):
            raise ValueError("target is required")
        return params

    async def execute(self, params: dict) -> AsyncIterator[PluginEvent]:
        target = params["target"]

        yield PluginEvent(type="log", data={"msg": f"Scanning {target}..."})
        yield PluginEvent(type="progress", data={"percent": 0})

        results = []
        # ... scanning logic ...
        for item in results:
            yield PluginEvent(type="result", data=item)

        yield PluginEvent(type="progress", data={"percent": 100})

    async def cleanup(self):
        # Close connections, temp files, etc.
        pass`}</CodeBlock>
              </div>
            </CardContent>
          </Card>

          {/* Session Plugin */}
          <Card id="session-plugin" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                {t("sessionPlugin")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("sessionPluginDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">{t("sessionOnStart")}</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("sessionOnStartDesc")}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">{t("sessionOnMessage")}</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("sessionOnMessageDesc")}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">{t("sessionOnEnd")}</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("sessionOnEndDesc")}</p>
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("sessionYaml")}</h3>
                <CodeBlock>{`name: my-interactive-tool
version: 1.0.0
mode: session
engine: python
# ...`}</CodeBlock>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("sessionPluginExample")}</h3>
                <CodeBlock>{`from collections.abc import AsyncIterator
from netkitx_sdk.base import SessionPlugin, PluginEvent

class Plugin(SessionPlugin):
    mode = "session"

    async def on_session_start(self, params: dict) -> dict:
        """Initialize session state, return initial state dict."""
        return {"history": [], "cwd": "/"}

    async def on_message(self, session_id: str, message: str, state: dict) -> AsyncIterator[PluginEvent]:
        """Handle each message in the session."""
        state["history"].append(message)
        yield PluginEvent(type="result", data={"output": f"Received: {message}"})

    async def on_session_end(self, session_id: str, state: dict):
        """Cleanup when session closes."""
        pass`}</CodeBlock>
              </div>
              <div className="bg-muted/50 border rounded-lg p-4 space-y-2">
                <p className="text-sm">{t("sessionNote")}</p>
                <p className="text-sm text-muted-foreground">{t("sessionNoteCompat")}</p>
              </div>
            </CardContent>
          </Card>

          {/* Custom UI */}
          <Card id="custom-ui" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LayoutTemplate className="h-5 w-5" />
                {t("customUi")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("customUiDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">chart</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("customUiChart")}</p>
                </div>
                <div className="border rounded-lg p-4">
                  <code className="text-sm font-semibold">topology</code>
                  <p className="text-sm text-muted-foreground mt-1">{t("customUiTopology")}</p>
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("customUiYaml")}</h3>
                <CodeBlock>{`name: my-scanner
version: 1.0.0
engine: python
ui_component: chart   # or: topology
output:
  type: table
  columns:
    - key: host
      label: Host
    - key: open_ports
      label: Open Ports`}</CodeBlock>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("customUiChartConfig")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("customUiChartConfigDesc")}</p>
                <CodeBlock>{`output:
  type: table
  ui_charts:
    - type: bar
      x: host
      y: open_ports
      label: Open Ports per Host
    - type: pie
      field: category
      label: Category Distribution`}</CodeBlock>
              </div>
              <div className="bg-muted/50 border rounded-lg p-4">
                <p className="text-sm">{t("customUiNote")}</p>
              </div>
            </CardContent>
          </Card>

          {/* Output Format */}
          <Card id="output-format" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Monitor className="h-5 w-5" />
                {t("outputFormat")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("outputFormatDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid sm:grid-cols-3 gap-4">
                {(["Table", "Text", "Json"] as const).map((type) => (
                  <div key={type} className="border rounded-lg p-4">
                    <code className="text-sm font-semibold">{t(`outputType${type}`)}</code>
                    <p className="text-sm text-muted-foreground mt-1">{t(`outputType${type}Desc`)}</p>
                  </div>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("outputExample")}</h3>
                <CodeBlock>{`# plugin.yaml
output:
  type: table
  columns:
    - key: host
      label: Host
    - key: port
      label: Port
    - key: service
      label: Service
    - key: version
      label: Version

# main.py — yield result events, one row at a time
yield PluginEvent(type="result", data={"host": "10.0.0.1", "port": 22, "service": "ssh", "version": "OpenSSH 8.9"})
yield PluginEvent(type="result", data={"host": "10.0.0.1", "port": 80, "service": "http", "version": "nginx 1.24"})`}</CodeBlock>
              </div>
            </CardContent>
          </Card>

          {/* Go / CLI Plugins */}
          <Card id="go-plugin" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                {t("goPlugin")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("goPluginDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2">{t("jsonProtocol")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("jsonProtocolDesc")}</p>
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium mb-2">{t("jsonInput")}</p>
                  <CodeBlock>{`{
  "target": "192.168.1.1",
  "port": 80,
  "verbose": true
}`}</CodeBlock>
                </div>
                <div>
                  <p className="text-sm font-medium mb-2">{t("jsonOutput")}</p>
                  <CodeBlock>{`{"type": "progress", "data": {"percent": 0}}
{"type": "result", "data": {"port": 80, "status": "open"}}
{"type": "progress", "data": {"percent": 100}}`}</CodeBlock>
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("goExample")}</h3>
                <CodeBlock>{`package main

import (
    "encoding/json"
    "fmt"
    "os"
)

type Event struct {
    Type string      \`json:"type"\`
    Data interface{} \`json:"data"\`
}

func emit(t string, data interface{}) {
    json.NewEncoder(os.Stdout).Encode(Event{Type: t, Data: data})
}

func main() {
    var params map[string]interface{}
    json.NewDecoder(os.Stdin).Decode(&params)

    target := params["target"].(string)

    emit("progress", map[string]int{"percent": 0})
    emit("result", map[string]interface{}{"host": target, "port": 80, "status": "open"})
    emit("progress", map[string]int{"percent": 100})
    fmt.Fprintln(os.Stderr, "Scan complete")
}`}</CodeBlock>
              </div>
            </CardContent>
          </Card>

          {/* Publish Flow */}
          <Card id="publish-flow" className="scroll-mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ArrowUp className="h-5 w-5" />
                {t("publishFlow")}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{t("publishFlowDesc")}</p>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="font-semibold mb-2">{t("publishStep1Title")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("publishStep1Desc")}</p>
                <CodeBlock>{`netkitx-cli pack ./my-scanner
# Creates: my-scanner-1.0.0.zip`}</CodeBlock>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("publishStep2Title")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("publishStep2Desc")}</p>
                <CodeBlock>{`netkitx-cli publish my-scanner-1.0.0.zip
# Plugin is now live on the Marketplace`}</CodeBlock>
              </div>
              <div>
                <h3 className="font-semibold mb-2">{t("publishStep3Title")}</h3>
                <p className="text-sm text-muted-foreground mb-2">{t("publishStep3Desc")}</p>
                <CodeBlock>{`netkitx-cli yank my-scanner 1.0.0
# Version 1.0.0 is no longer installable`}</CodeBlock>
              </div>
              <div className="bg-muted/50 border rounded-lg p-4 space-y-2">
                <p className="text-sm">{t("publishNote")}</p>
                <p className="text-sm text-muted-foreground">{t("publishUploadNote")}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

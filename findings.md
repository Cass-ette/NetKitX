# Findings

## Competition materials
- 官方实施方案 PDF：`/Users/chenzilve/Downloads/附件12026年广东省大学生计算机设计大赛实施方案.pdf`
- 软件应用与开发类提交要求：`/Users/chenzilve/Downloads/2026作品提交规范要求/01 软件应用与开发作品提交要求/01-1 软件应用与开发类作品提交要求（2025版）V2-1.docx`
- 软件应用与开发类设计和开发文档模板：`/Users/chenzilve/Downloads/2026作品提交规范要求/01 软件应用与开发作品提交要求/01-3 软件应用与开发类作品设计和开发文档模板（2025版）.docx`

## Competition requirements extracted
- 赛道口径：软件应用与开发类，明确包含 Web 应用与开发。
- 必交文档：
  - 《作品信息摘要》PDF
  - 《软件开发类作品设计和开发文档》PDF
  - 现场演示 PPT
  - 现场演示 PPT 转 PDF
  - 答辩视频（MP4，<=10 分钟，<=500MB）
- 必交作品：
  - 可安装运行的软件安装包
  - 运行网址或二维码（提交说明中明确提到可放在“作品与答辩材料”中）
- 源码与素材：
  - 提交全部团队开发产生的源代码
  - 提交代表性素材（图片/视频/音乐等，如有）
  - 超过 10 个文件必须压缩
  - 主压缩文件命名建议为“作品编号-素材源码”
  - 素材源码总体不超过 1GB，建议 500MB 以内
- 提交结构：4 个文件夹
  1. 作品与答辩材料
  2. 素材与源码
  3. 设计与开发文档
  4. 作品演示视频
- 规则：所有文件在 4 个文件夹中只能出现一次，不得重复。
- 文档模板要求：设计和开发文档需简明扼要，建议二级目录，且要明确说明项目中涉及大模型的内容。
- 文档模板建议章节：需求分析、概要设计、详细设计、测试报告、安装及使用、项目总结、参考文献。

## Current project status
- Contest branch has been simplified to focus on AI Agent + Knowledge Base
- RAG is enabled locally
- Multi-provider AI settings are supported independently
- Major non-contest residual modules have been removed from current local version
- 当前前端保留页面：ai-chat、dashboard、knowledge、plugins、sessions、settings、tasks、tools
- 当前后端保留核心：AI/Agent、Knowledge、Embedding/RAG、Plugins、Tasks、Reports、Passkey、Terminal
- 本地服务可运行：frontend `:3000`、backend `:8000`
- 当前 README 仍存在大量非比赛版/过时描述（如 marketplace、topology、Claude 等），不能直接拿去交比赛材料

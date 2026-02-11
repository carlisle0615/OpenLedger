import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FileText, Download } from "lucide-react";
import { FileItem, CsvPreview } from "@/types";

interface PreviewAreaProps {
  selectedFile: FileItem | null;
  runName: string;
  downloadHref: (path: string) => string;
  previewError: string;
  csvPreview: CsvPreview | null;
  textPreview: string;
  loadCsv: (path: string, offset: number) => void;
}

function sanitizeFilename(value: string) {
  const cleaned = value
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
    .replace(/\s+/g, " ")
    .replace(/[. ]+$/g, "")
    .trim();
  return cleaned;
}

function ensureExcelExt(value: string) {
  const lower = value.toLowerCase();
  if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) return value;
  return `${value}.xlsx`;
}

export function PreviewArea({ selectedFile, runName, downloadHref, previewError, csvPreview, textPreview, loadCsv }: PreviewAreaProps) {
  const isFinalReport = selectedFile?.name === "unified.transactions.categorized.xlsx";
  const safeRunName = sanitizeFilename(runName || "");
  const downloadName = isFinalReport && safeRunName ? ensureExcelExt(safeRunName) : undefined;
  return (
    <Card className="min-h-[600px] flex flex-col h-[calc(100vh-250px)]">
      <CardHeader className="py-3 border-b bg-muted/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">预览</CardTitle>
            {selectedFile && <Badge variant="secondary" className="font-mono text-xs">{selectedFile.name}</Badge>}
          </div>
          {selectedFile && (
            <a
              href={downloadHref(selectedFile.path)}
              target="_blank"
              rel="noreferrer"
              download={downloadName}
              className="text-xs flex items-center gap-1 hover:underline text-primary"
            >
              <Download className="h-3 w-3" /> 下载
            </a>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-0 flex-1 flex flex-col relative overflow-hidden">
        {!selectedFile ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
            <FileText className="h-12 w-12 mb-2 opacity-10" />
            <p className="text-sm">从任意阶段选择文件进行预览</p>
          </div>
        ) : (
          <div className="absolute inset-0 overflow-auto">
            {previewError && <div className="p-4 text-destructive text-sm">{previewError}</div>}

            {csvPreview && (
              <div className="p-4">
                <div className="flex gap-2 mb-2">
                  <Button variant="outline" size="sm" disabled={csvPreview.prev_offset == null} onClick={() => loadCsv(selectedFile!.path, csvPreview.prev_offset ?? 0)}>上一页</Button>
                  <Button variant="outline" size="sm" disabled={!csvPreview.has_more} onClick={() => loadCsv(selectedFile!.path, csvPreview.next_offset ?? 0)}>下一页</Button>
                  <span className="text-xs text-muted-foreground ml-auto self-center">
                    {csvPreview.offset} - {csvPreview.offset + csvPreview.rows.length}
                  </span>
                </div>
                <div className="border rounded-md overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {csvPreview.columns.map((k) => <TableHead key={k} className="whitespace-nowrap h-8 text-xs">{k}</TableHead>)}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {csvPreview.rows.map((r, idx) => (
                        <TableRow key={idx} className="h-8">
                          {csvPreview.columns.map((k) => <TableCell key={k} className="whitespace-nowrap py-1 text-xs">{r[k]}</TableCell>)}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            {!csvPreview && textPreview && (
              <pre className="p-4 text-xs font-mono whitespace-pre-wrap">{textPreview}</pre>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

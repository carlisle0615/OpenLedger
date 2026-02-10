import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FileText, Upload } from "lucide-react";
import { FileItem, CsvPreview } from "@/types";

interface PreviewAreaProps {
  selectedFile: FileItem | null;
  downloadHref: (path: string) => string;
  previewError: string;
  csvPreview: CsvPreview | null;
  textPreview: string;
  loadCsv: (path: string, offset: number) => void;
}

export function PreviewArea({ selectedFile, downloadHref, previewError, csvPreview, textPreview, loadCsv }: PreviewAreaProps) {
  return (
    <Card className="min-h-[600px] flex flex-col h-[calc(100vh-250px)]">
      <CardHeader className="py-3 border-b bg-muted/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">Preview</CardTitle>
            {selectedFile && <Badge variant="secondary" className="font-mono text-xs">{selectedFile.name}</Badge>}
          </div>
          {selectedFile && (
            <a
              href={downloadHref(selectedFile.path)}
              target="_blank"
              rel="noreferrer"
              className="text-xs flex items-center gap-1 hover:underline text-primary"
            >
              <Upload className="h-3 w-3" /> Download
            </a>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-0 flex-1 flex flex-col relative overflow-hidden">
        {!selectedFile ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
            <FileText className="h-12 w-12 mb-2 opacity-10" />
            <p className="text-sm">Select a file from any stage to preview</p>
          </div>
        ) : (
          <div className="absolute inset-0 overflow-auto">
            {previewError && <div className="p-4 text-destructive text-sm">{previewError}</div>}

            {csvPreview && (
              <div className="p-4">
                <div className="flex gap-2 mb-2">
                  <Button variant="outline" size="sm" disabled={csvPreview.prev_offset == null} onClick={() => loadCsv(selectedFile!.path, csvPreview.prev_offset ?? 0)}>Prev</Button>
                  <Button variant="outline" size="sm" disabled={!csvPreview.has_more} onClick={() => loadCsv(selectedFile!.path, csvPreview.next_offset ?? 0)}>Next</Button>
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

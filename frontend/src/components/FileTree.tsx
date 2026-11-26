"use client";

import { useState, useEffect } from "react";
import { api, GraphResponse } from "./api/client";

interface FileNode {
  id: string;
  name: string;
  path: string;
  type: "directory" | "file";
  parsed: boolean;
  parseError: string | null;
}

interface FileTreeProps {
  rootPath: string;
}

export function FileTree({ rootPath }: FileTreeProps) {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadFiles() {
      setLoading(true);
      try {
        const result = await api.graph.list();
        const pythonFiles: FileNode[] = [];

        if (result.nodes) {
          for (const node of result.nodes) {
            if (node.type === "module" && node.file_path) {
              const relativePath = node.file_path.replace(rootPath, "").replace(/^\/+/, "");
              const isParsed = true;
              pythonFiles.push({
                id: node.id,
                name: relativePath.split("/").pop() || node.file_path,
                path: node.file_path,
                type: "file",
                parsed: isParsed,
                parseError: null,
              });
            }
          }
        }

        setFiles(pythonFiles);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setFiles([]);
      } finally {
        setLoading(false);
      }
    }

    loadFiles();
  }, [rootPath]);

  if (loading) {
    return (
      <div className="file-tree-loading">
        <span>Loading file tree...</span>
      </div>
    );
  }

  return (
    <div className="file-tree-container">
      <div className="file-tree-header">
        <span className="file-tree-title">File Tree</span>
        <span className="file-tree-count">
          {files.length} file{s}
        </span>
      </div>

      {error && (
        <div className="file-tree-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {files.length === 0 && !loading && (
        <div className="file-tree-empty">
          <span>No Python files found in {rootPath}</span>
          <p style={{ marginTop: "0.5rem", color: "#6b7280", fontSize: "0.875rem" }}>
            Parse a codebase to see file structure
          </p>
        </div>
      )}

      <ul className="file-tree-list">
        {files.map((file) => (
          <li
            key={file.id}
            className={`file-tree-item ${file.parsed ? "parsed" : "unparsed"}`}
          >
            <span className="file-tree-icon">
              {file.parsed ? "✓" : "✗"}
            </span>
            <span className="file-tree-name">{file.name}</span>
            {file.parseError && (
              <span className="file-tree-error-small">
                {file.parseError}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

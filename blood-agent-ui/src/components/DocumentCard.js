import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Box,
  Paper,
  Typography,
  Button,
  Divider,
  Tabs,
  Tab,
  TextField,
  Stack,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
} from "@mui/material";

import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveIcon from "@mui/icons-material/Save";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";

import JsonTableEditor from "./JsonTableEditor";

const glass = {
  background: "rgba(17, 24, 39, 0.72)",
  border: "1px solid rgba(148, 163, 184, 0.14)",
  boxShadow: "0 18px 60px rgba(0,0,0,0.45)",
  backdropFilter: "blur(12px)",
};

function StatusChip({ value }) {
  const v = (value || "unknown").toLowerCase();
  const palette =
    v.includes("error")
      ? { bg: "rgba(239,68,68,0.10)", fg: "rgba(239,68,68,0.95)", br: "rgba(239,68,68,0.28)" }
      : v.includes("uploaded")
      ? { bg: "rgba(59,130,246,0.10)", fg: "rgba(59,130,246,0.95)", br: "rgba(59,130,246,0.28)" }
      : v.includes("anonym")
      ? { bg: "rgba(34,197,94,0.10)", fg: "rgba(34,197,94,0.95)", br: "rgba(34,197,94,0.28)" }
      : v.includes("json")
      ? { bg: "rgba(124,92,255,0.10)", fg: "rgba(124,92,255,0.95)", br: "rgba(124,92,255,0.28)" }
      : { bg: "rgba(255,255,255,0.06)", fg: "rgba(229,231,235,0.85)", br: "rgba(148,163,184,0.14)" };

  return (
    <Chip
      size="small"
      label={value || "unknown"}
      sx={{
        bgcolor: palette.bg,
        color: palette.fg,
        border: `1px solid ${palette.br}`,
        fontWeight: 900,
        height: 22,
      }}
    />
  );
}

function toTableRows(jsonObj) {
  if (!jsonObj) return [];

  const root =
    jsonObj?.tests
      ? jsonObj
      : jsonObj?.json?.tests
      ? jsonObj.json
      : jsonObj?.result?.tests
      ? jsonObj.result
      : jsonObj;

  const tests = Array.isArray(root?.tests) ? root.tests : [];
  return tests.map((t) => ({
    parameter: t?.parameter ?? "",
    value: t?.value ?? "",
    unit: t?.unit ?? null,
    loinc_code: t?.loinc_code ?? null,
    reference_min: t?.reference_min ?? null,
    reference_max: t?.reference_max ?? null,
  }));
}

function mergeSavedRows(baseRows, savedRows) {
  const rows = Array.isArray(baseRows) ? [...baseRows] : [];
  const saved = Array.isArray(savedRows) ? savedRows : [];

  for (const s of saved) {
    const idx = Number(s?.row_index);
    if (!Number.isFinite(idx) || idx < 0) continue;

    if (!rows[idx]) rows[idx] = {};
    rows[idx] = {
      ...rows[idx],
      parameter: s?.parameter ?? rows[idx]?.parameter ?? "",
      value: s?.value ?? rows[idx]?.value ?? "",
      unit: s?.unit ?? rows[idx]?.unit ?? null,
      loinc_code: s?.loinc_code ?? rows[idx]?.loinc_code ?? null,
      reference_min: s?.reference_min ?? rows[idx]?.reference_min ?? null,
      reference_max: s?.reference_max ?? rows[idx]?.reference_max ?? null,
    };
  }

  return rows;
}

export default function DocumentCard({ doc, apiBase, onDeleted }) {
  const docId = doc?.doc_id;

  const [meta, setMeta] = useState(null);
  const [tab, setTab] = useState("json");
  const [text, setText] = useState("");
  const [jsonObj, setJsonObj] = useState(null);
  const [savedRows, setSavedRows] = useState([]);
  const [tableRows, setTableRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const previewUrl = useMemo(() => meta?.preview_url || doc?.preview_url || "", [meta, doc]);
  const originalUrl = useMemo(() => meta?.original_url || doc?.original_url || "", [meta, doc]);

  const isPdf = useMemo(() => {
    const filename = (meta?.filename || doc?.filename || "").toLowerCase();
    const url = (originalUrl || "").toLowerCase();
    return filename.endsWith(".pdf") || url.includes(".pdf");
  }, [meta, doc, originalUrl]);

  const normalizeRowsResponse = (rowsResp) => {
    if (Array.isArray(rowsResp)) return rowsResp;
    if (rowsResp && Array.isArray(rowsResp.rows)) return rowsResp.rows;
    return [];
  };

  const loadSavedRows = useCallback(async () => {
    try {
      const rowsResp = await fetch(`${apiBase}/docs/${docId}/rows`).then((r) => r.json());
      const rows = normalizeRowsResponse(rowsResp);
      setSavedRows(rows);
      setTableRows((prev) => mergeSavedRows(prev, rows));
      return rows;
    } catch {
      setSavedRows([]);
      return [];
    }
  }, [apiBase, docId]);

  const loadMeta = useCallback(async () => {
    const res = await fetch(`${apiBase}/docs/${docId}`);
    if (!res.ok) throw new Error("Failed to load doc meta");
    const m = await res.json();
    setMeta(m);
    return m;
  }, [apiBase, docId]);

  const loadText = useCallback(
    async (whichTab) => {
      try {
        const t = await fetch(`${apiBase}/docs/${docId}/text?type=${whichTab}`).then((r) => r.json());
        setText(t?.content || "");
      } catch {
        setText("");
      }
    },
    [apiBase, docId]
  );

  const loadResults = useCallback(
    async (rowsForOverlay) => {
      try {
        const j = await fetch(`${apiBase}/results/${docId}`).then((r) => r.json());
        setJsonObj(j);

        const base = toTableRows(j);
        setTableRows(mergeSavedRows(base, rowsForOverlay));
        return j;
      } catch {
        setJsonObj(null);
        setTableRows((prev) => mergeSavedRows(prev, rowsForOverlay));
        return null;
      }
    },
    [apiBase, docId]
  );

  const loadAll = useCallback(
    async (whichTab = tab) => {
      if (!docId) return;
      setLoading(true);
      try {
        await loadMeta();
        await loadText(whichTab);
        const rows = await loadSavedRows();
        await loadResults(rows);
      } finally {
        setLoading(false);
      }
    },
    [docId, tab, loadMeta, loadText, loadSavedRows, loadResults]
  );

  useEffect(() => {
    if (!docId) return;
    loadAll("json");
  }, [docId, loadAll]);

  useEffect(() => {
    if (!docId) return;
    loadText(tab);
  }, [tab, docId, loadText]);

  useEffect(() => {
    const base = toTableRows(jsonObj);
    if (base.length) setTableRows(mergeSavedRows(base, savedRows));
  }, [jsonObj, savedRows]);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(text || "");
    } catch {
      alert("Copy failed (browser permission).");
    }
  };

  const saveText = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/docs/${docId}/text`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: tab, content: text }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert("Save failed: " + (err.detail || res.statusText));
        return;
      }

      await loadAll(tab);
    } finally {
      setLoading(false);
    }
  };

  const regenerate = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/docs/${docId}/regenerate-json`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert("Regenerate failed: " + (err.detail || res.statusText));
        return;
      }

      const data = await res.json();
      const nextJson = data?.json ?? data;

      setJsonObj(nextJson);
      setTab("json");
      setTableRows(mergeSavedRows(toTableRows(nextJson), savedRows));

      await loadText("json");
    } finally {
      setLoading(false);
    }
  };

  const deleteDoc = async () => {
    if (!window.confirm("Delete this document and all stored artifacts?")) return;
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/docs/${docId}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert("Delete failed: " + (err.detail || res.statusText));
        return;
      }
      onDeleted?.(docId);
    } finally {
      setLoading(false);
    }
  };

  if (!docId) return null;

  return (
    <Paper sx={{ ...glass, borderRadius: "22px", overflow: "hidden", position: "relative" }}>
      {loading && (
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            bgcolor: "rgba(2, 6, 23, 0.55)",
            backdropFilter: "blur(3px)",
            zIndex: 5,
            display: "grid",
            placeItems: "center",
          }}
        >
          <Stack direction="row" spacing={1.2} alignItems="center">
            <CircularProgress size={18} />
            <Typography sx={{ fontSize: 13.5, color: "rgba(229,231,235,0.85)", fontWeight: 800 }}>
              Working…
            </Typography>
          </Stack>
        </Box>
      )}

      <Box sx={{ p: 2.2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }} justifyContent="space-between">
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 950, fontSize: 14.5, letterSpacing: 0.2 }}>Document</Typography>
            <Typography
              sx={{
                mt: 0.4,
                fontSize: 13,
                color: "rgba(229,231,235,0.75)",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                wordBreak: "break-all",
              }}
            >
              {docId}
            </Typography>

            <Stack direction="row" spacing={1} sx={{ mt: 1.2, flexWrap: "wrap" }} useFlexGap>
              <StatusChip value={meta?.status || doc?.status || "unknown"} />
              {(meta?.filename || doc?.filename) && (
                <Chip
                  size="small"
                  label={meta?.filename || doc?.filename}
                  sx={{
                    bgcolor: "rgba(255,255,255,0.06)",
                    color: "rgba(229,231,235,0.85)",
                    border: "1px solid rgba(148,163,184,0.14)",
                    maxWidth: 420,
                    height: 22,
                    "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" },
                  }}
                />
              )}
            </Stack>
          </Box>

          <Stack direction="row" spacing={1} alignItems="center">
            {originalUrl && (
              <Tooltip title="Open original file">
                <IconButton
                  onClick={() => window.open(originalUrl, "_blank")}
                  sx={{
                    color: "rgba(229,231,235,0.85)",
                    bgcolor: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(148,163,184,0.14)",
                    "&:hover": { bgcolor: "rgba(255,255,255,0.10)" },
                  }}
                >
                  <OpenInNewIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

            <Button
              variant="contained"
              color="error"
              startIcon={<DeleteOutlineIcon />}
              onClick={deleteDoc}
              disabled={loading}
              sx={{ borderRadius: "16px", fontWeight: 950 }}
            >
              Delete
            </Button>
          </Stack>
        </Stack>
      </Box>

      <Divider sx={{ borderColor: "rgba(148,163,184,0.14)" }} />

      <Box
        sx={{
          p: 2.2,
          display: "grid",
          gridTemplateColumns: { xs: "1fr", lg: "1.2fr 1fr" },
          gap: 2,
          alignItems: "start",
        }}
      >
        <Box sx={{ display: "grid", gap: 2 }}>
          <Box>
            <Typography sx={{ fontWeight: 950, fontSize: 13.5, mb: 1 }}>Preview</Typography>

            <Box
              sx={{
                borderRadius: "18px",
                border: "1px solid rgba(148,163,184,0.14)",
                bgcolor: "rgba(255,255,255,0.03)",
                overflow: "hidden",
              }}
            >
              {previewUrl ? (
                <Box component="img" src={previewUrl} alt="preview" sx={{ width: "100%", display: "block", maxHeight: 340, objectFit: "contain" }} />
              ) : (
                <Box sx={{ p: 2 }}>
                  <Typography sx={{ color: "rgba(229,231,235,0.65)", fontSize: 13 }}>No preview available</Typography>
                </Box>
              )}
            </Box>

            {originalUrl && isPdf && (
              <Box
                sx={{
                  mt: 1.2,
                  borderRadius: "18px",
                  border: "1px solid rgba(148,163,184,0.14)",
                  bgcolor: "rgba(255,255,255,0.03)",
                  overflow: "hidden",
                  height: 420,
                }}
              >
                <Box component="iframe" title="pdf" src={originalUrl} sx={{ width: "100%", height: "100%", border: 0 }} />
              </Box>
            )}
          </Box>

          <Box>
            <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
              <Box>
                <Typography sx={{ fontWeight: 950, fontSize: 13.5 }}>Editor</Typography>
                <Typography sx={{ fontSize: 12.5, color: "rgba(229,231,235,0.65)", mt: 0.3 }}>
                  Edit text/JSON, then Save. Regenerate recreates JSON from current editable text.
                </Typography>
              </Box>

              <Stack direction="row" spacing={1} alignItems="center">
                <Tooltip title="Copy editor content">
                  <IconButton
                    onClick={copyToClipboard}
                    sx={{
                      color: "rgba(229,231,235,0.85)",
                      bgcolor: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(148,163,184,0.14)",
                      "&:hover": { bgcolor: "rgba(255,255,255,0.10)" },
                    }}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>

                <Button variant="contained" size="small" startIcon={<SaveIcon />} onClick={saveText} disabled={loading}>
                  Save
                </Button>

                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={regenerate}
                  disabled={loading}
                  sx={{
                    color: "rgba(229,231,235,0.85)",
                    borderColor: "rgba(124,92,255,0.35)",
                    "&:hover": { borderColor: "rgba(124,92,255,0.55)" },
                  }}
                >
                  Regenerate
                </Button>
              </Stack>
            </Stack>

            <Box
              sx={{
                mt: 1.2,
                borderRadius: "18px",
                border: "1px solid rgba(148,163,184,0.14)",
                bgcolor: "rgba(255,255,255,0.03)",
                overflow: "hidden",
              }}
            >
              <Tabs
                value={tab}
                onChange={(_, v) => setTab(v)}
                sx={{
                  px: 1,
                  minHeight: 44,
                  "& .MuiTab-root": {
                    textTransform: "none",
                    fontWeight: 950,
                    minHeight: 44,
                    color: "rgba(229,231,235,0.65)",
                  },
                  "& .Mui-selected": { color: "rgba(229,231,235,0.92)" },
                  "& .MuiTabs-indicator": {
                    height: 3,
                    borderRadius: 3,
                    backgroundColor: "rgba(124,92,255,0.85)",
                  },
                }}
              >
                <Tab value="json" label="JSON" />
                <Tab value="anonymized" label="Anonymized" />
                <Tab value="extracted" label="Extracted" />
              </Tabs>

              <Divider sx={{ borderColor: "rgba(148,163,184,0.14)" }} />

              <Box sx={{ p: 1.2 }}>
                <TextField
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  multiline
                  minRows={14}
                  fullWidth
                  placeholder={tab === "json" ? '{\n  "tests": []\n}' : "Text will appear here…"}
                  sx={{
                    "& .MuiOutlinedInput-root": {
                      borderRadius: "16px",
                      bgcolor: "rgba(2, 6, 23, 0.45)",
                      "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      "&:hover fieldset": { borderColor: "rgba(148,163,184,0.30)" },
                      "&.Mui-focused fieldset": { borderColor: "rgba(124,92,255,0.55)" },
                    },
                  }}
                  InputProps={{
                    style: {
                      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                      color: "#e5e7eb",
                      fontSize: 12.8,
                      lineHeight: 1.6,
                    },
                  }}
                />
              </Box>
            </Box>
          </Box>
        </Box>

        <Box>
          <Typography sx={{ fontWeight: 950, fontSize: 13.5, mb: 1 }}>Table editor</Typography>

          <Box
            sx={{
              borderRadius: "18px",
              border: "1px solid rgba(148,163,184,0.14)",
              bgcolor: "rgba(255,255,255,0.03)",
              p: 1.4,
            }}
          >
            <JsonTableEditor
              apiBase={apiBase}
              docId={docId}
              rows={tableRows}
              setRows={setTableRows}
              onSaved={async () => {
                await loadSavedRows();
              }}
            />
          </Box>
        </Box>
      </Box>
    </Paper>
  );
}
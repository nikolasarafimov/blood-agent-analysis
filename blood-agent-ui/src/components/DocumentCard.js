import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from "@mui/material";

import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveIcon from "@mui/icons-material/Save";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import SyncRoundedIcon from "@mui/icons-material/SyncRounded";

import JsonTableEditor from "./JsonTableEditor";

const glass = {
  background: "rgba(17, 24, 39, 0.72)",
  border: "1px solid rgba(148, 163, 184, 0.14)",
  boxShadow: "0 18px 70px rgba(0,0,0,0.45)",
  backdropFilter: "blur(12px)"
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
      : v.includes("loinc")
      ? { bg: "rgba(34,197,94,0.10)", fg: "rgba(34,197,94,0.95)", br: "rgba(34,197,94,0.28)" }
      : { bg: "rgba(255,255,255,0.06)", fg: "rgba(229,231,235,0.85)", br: "rgba(148,163,184,0.14)" };

  return (
    <Chip
      size="small"
      label={value || "unknown"}
      sx={{
        bgcolor: palette.bg,
        color: palette.fg,
        border: `1px solid ${palette.br}`,
        fontWeight: 950,
        height: 22
      }}
    />
  );
}

function toTableRows(jsonObj) {
  if (!jsonObj) return [];

  const root = jsonObj?.tests
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
    loinc_display: t?.loinc_display ?? null,
    reference_min: t?.reference_min ?? null,
    reference_max: t?.reference_max ?? null
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
      loinc_display: s?.loinc_display ?? rows[idx]?.loinc_display ?? null,
      reference_min: s?.reference_min ?? rows[idx]?.reference_min ?? null,
      reference_max: s?.reference_max ?? rows[idx]?.reference_max ?? null
    };
  }

  return rows;
}

function normalizeRowsResponse(rowsResp) {
  if (Array.isArray(rowsResp)) return rowsResp;
  if (rowsResp && Array.isArray(rowsResp.rows)) return rowsResp.rows;
  return [];
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

export default function DocumentCard({ doc, apiBase, onDeleted, onToast }) {
  const docId = doc?.doc_id;

  const [meta, setMeta] = useState(null);
  const [tab, setTab] = useState("json");
  const [text, setText] = useState("");
  const [jsonObj, setJsonObj] = useState(null);
  const [savedRows, setSavedRows] = useState([]);
  const [tableRows, setTableRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const requestSeq = useRef(0);

  const previewUrl = useMemo(() => meta?.preview_url || doc?.preview_url || "", [meta, doc]);
  const originalUrl = useMemo(() => meta?.original_url || doc?.original_url || "", [meta, doc]);

  const isPdf = useMemo(() => {
    const filename = (meta?.filename || doc?.filename || "").toLowerCase();
    const url = (originalUrl || "").toLowerCase();
    return filename.endsWith(".pdf") || url.includes(".pdf");
  }, [meta, doc, originalUrl]);

  const toast = useCallback(
    (msg, type = "info") => {
      if (typeof onToast === "function") onToast(msg, type);
    },
    [onToast]
  );

  const loadMeta = useCallback(async () => {
    const res = await fetch(`${apiBase}/docs/${docId}`);
    if (!res.ok) {
      const err = await safeJson(res);
      throw new Error(err?.detail || res.statusText || "Failed to load doc meta");
    }
    const m = await res.json();
    setMeta(m);
    return m;
  }, [apiBase, docId]);

  const loadText = useCallback(
    async (whichTab) => {
      const res = await fetch(`${apiBase}/docs/${docId}/text?type=${whichTab}`);
      if (!res.ok) {
        setText("");
        return "";
      }
      const t = await res.json();
      const content = t?.content || "";
      setText(content);
      return content;
    },
    [apiBase, docId]
  );

  const loadSavedRows = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/docs/${docId}/rows`);
      if (!res.ok) return [];
      const rowsResp = await res.json();
      const rows = normalizeRowsResponse(rowsResp);
      setSavedRows(rows);
      return rows;
    } catch {
      setSavedRows([]);
      return [];
    }
  }, [apiBase, docId]);

  const loadResults = useCallback(
    async (rowsForOverlay) => {
      const res = await fetch(`${apiBase}/results/${docId}`);
      if (!res.ok) {
        setJsonObj(null);
        setTableRows((prev) => mergeSavedRows(prev, rowsForOverlay));
        return null;
      }

      const j = await res.json();
      setJsonObj(j);

      const base = toTableRows(j);
      setTableRows(mergeSavedRows(base, rowsForOverlay));
      return j;
    },
    [apiBase, docId]
  );

  const loadAll = useCallback(
    async (whichTab = tab) => {
      if (!docId) return;

      const seq = ++requestSeq.current;
      setLoading(true);

      try {
        const [, rows] = await Promise.all([loadMeta(), loadSavedRows()]);
        if (requestSeq.current !== seq) return;
        await Promise.all([loadResults(rows), loadText(whichTab)]);
      } catch (e) {
        if (requestSeq.current !== seq) return;
        toast(`Load failed: ${e.message}`, "error");
      } finally {
        if (requestSeq.current === seq) setLoading(false);
      }
    },
    [docId, tab, loadMeta, loadSavedRows, loadResults, loadText, toast]
  );

  useEffect(() => {
    if (!docId) return;
    setTab("json");
    loadAll("json");
  }, [docId, loadAll]);

  useEffect(() => {
    if (!docId) return;
    loadText(tab);
  }, [docId, tab, loadText]);

  useEffect(() => {
    const base = toTableRows(jsonObj);
    if (base.length) setTableRows(mergeSavedRows(base, savedRows));
  }, [jsonObj, savedRows]);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(text || "");
      toast("Copied to clipboard.", "success");
    } catch {
      toast("Copy failed (browser permission).", "error");
    }
  };

  const saveText = async () => {
    if (!docId) return;
    setLoading(true);

    try {
      if (tab === "json") {
        let parsed;
        try {
          parsed = JSON.parse(text || "");
        } catch (e) {
          toast(`Invalid JSON: ${e.message}`, "error");
          return;
        }
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          toast("Invalid JSON: top-level must be an object.", "error");
          return;
        }
      }

      const res = await fetch(`${apiBase}/docs/${docId}/text`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: tab, content: text })
      });

      if (!res.ok) {
        const err = await safeJson(res);
        toast(`Save failed: ${err?.detail || res.statusText}`, "error");
        return;
      }

      toast("Saved.", "success");
      await loadAll(tab);
    } finally {
      setLoading(false);
    }
  };

  const regenerate = async () => {
    if (!docId) return;
    setLoading(true);

    try {
      const res = await fetch(`${apiBase}/docs/${docId}/regenerate-json`, { method: "POST" });
      if (!res.ok) {
        const err = await safeJson(res);
        toast(`Regenerate failed: ${err?.detail || res.statusText}`, "error");
        return;
      }

      const data = await res.json();
      const nextJson = data?.json ?? data;

      setJsonObj(nextJson);
      setTab("json");
      setTableRows(mergeSavedRows(toTableRows(nextJson), savedRows));

      await loadText("json");
      toast("Regenerated JSON.", "success");
    } finally {
      setLoading(false);
    }
  };

  const refreshAll = async () => {
    await loadAll(tab);
    toast("Refreshed.", "success");
  };

  const deleteDoc = async () => {
    if (!docId) return;
    setLoading(true);

    try {
      const res = await fetch(`${apiBase}/docs/${docId}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await safeJson(res);
        toast(`Delete failed: ${err?.detail || res.statusText}`, "error");
        return;
      }
      toast("Deleted.", "success");
      onDeleted?.(docId);
    } finally {
      setLoading(false);
      setConfirmOpen(false);
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
            placeItems: "center"
          }}
        >
          <Stack direction="row" spacing={1.2} alignItems="center">
            <CircularProgress size={18} />
            <Typography sx={{ fontSize: 13.5, color: "rgba(229,231,235,0.85)", fontWeight: 900 }}>
              Working…
            </Typography>
          </Stack>
        </Box>
      )}

      <Box sx={{ p: 2.2 }}>
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          alignItems={{ md: "center" }}
          justifyContent="space-between"
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 950, fontSize: 15.2, letterSpacing: 0.2 }}>
              Document workspace
            </Typography>

            <Typography
              sx={{
                mt: 0.6,
                fontSize: 12.6,
                color: "rgba(229,231,235,0.78)",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                wordBreak: "break-all"
              }}
            >
              {docId}
            </Typography>

            <Stack direction="row" spacing={1} sx={{ mt: 1.3, flexWrap: "wrap" }} useFlexGap>
              <StatusChip value={meta?.status || doc?.status || "unknown"} />
              {(meta?.filename || doc?.filename) && (
                <Chip
                  size="small"
                  label={meta?.filename || doc?.filename}
                  sx={{
                    bgcolor: "rgba(255,255,255,0.06)",
                    color: "rgba(229,231,235,0.85)",
                    border: "1px solid rgba(148,163,184,0.14)",
                    maxWidth: 520,
                    height: 22,
                    "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" }
                  }}
                />
              )}
            </Stack>
          </Box>

          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="Refresh">
              <IconButton
                onClick={refreshAll}
                disabled={loading}
                sx={{
                  color: "rgba(229,231,235,0.88)",
                  bgcolor: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(148,163,184,0.14)",
                  "&:hover": { bgcolor: "rgba(255,255,255,0.10)" }
                }}
              >
                <SyncRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            {originalUrl && (
              <Tooltip title="Open original file">
                <IconButton
                  onClick={() => window.open(originalUrl, "_blank")}
                  sx={{
                    color: "rgba(229,231,235,0.88)",
                    bgcolor: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(148,163,184,0.14)",
                    "&:hover": { bgcolor: "rgba(255,255,255,0.10)" }
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
              onClick={() => setConfirmOpen(true)}
              disabled={loading}
              sx={{ borderRadius: 3, fontWeight: 950 }}
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
          alignItems: "start"
        }}
      >
        <Box sx={{ display: "grid", gap: 2 }}>
          <Box>
            <Typography sx={{ fontWeight: 950, fontSize: 13.8, mb: 1 }}>Preview</Typography>

            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid rgba(148,163,184,0.14)",
                bgcolor: "rgba(255,255,255,0.03)",
                overflow: "hidden"
              }}
            >
              {previewUrl ? (
                <Box
                  component="img"
                  src={previewUrl}
                  alt="preview"
                  sx={{ width: "100%", display: "block", maxHeight: 340, objectFit: "contain" }}
                />
              ) : (
                <Box sx={{ p: 2 }}>
                  <Typography sx={{ color: "rgba(229,231,235,0.65)", fontSize: 13 }}>
                    No preview available
                  </Typography>
                </Box>
              )}
            </Box>

            {originalUrl && isPdf && (
              <Box
                sx={{
                  mt: 1.2,
                  borderRadius: 2,
                  border: "1px solid rgba(148,163,184,0.14)",
                  bgcolor: "rgba(255,255,255,0.03)",
                  overflow: "hidden",
                  height: 420
                }}
              >
                <Box component="iframe" title="pdf" src={originalUrl} sx={{ width: "100%", height: "100%", border: 0 }} />
              </Box>
            )}
          </Box>

          <Box>
            <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
              <Box>
                <Typography sx={{ fontWeight: 950, fontSize: 13.8 }}>Editor</Typography>
                <Typography sx={{ fontSize: 12.5, color: "rgba(229,231,235,0.65)", mt: 0.3 }}>
                  Edit text/JSON, then Save. Regenerate recreates JSON from the current editable text.
                </Typography>
              </Box>

              <Stack direction="row" spacing={1} alignItems="center">
                <Tooltip title="Copy editor content">
                  <IconButton
                    onClick={copyToClipboard}
                    sx={{
                      color: "rgba(229,231,235,0.88)",
                      bgcolor: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(148,163,184,0.14)",
                      "&:hover": { bgcolor: "rgba(255,255,255,0.10)" }
                    }}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>

                <Button
                  variant="contained"
                  size="small"
                  startIcon={<SaveIcon />}
                  onClick={saveText}
                  disabled={loading}
                  sx={{ borderRadius: 3, fontWeight: 950 }}
                >
                  Save
                </Button>

                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={regenerate}
                  disabled={loading}
                  sx={{
                    borderRadius: 3,
                    fontWeight: 950,
                    color: "rgba(229,231,235,0.88)",
                    borderColor: "rgba(124,92,255,0.35)",
                    "&:hover": { borderColor: "rgba(124,92,255,0.55)" }
                  }}
                >
                  Regenerate
                </Button>
              </Stack>
            </Stack>

            <Box
              sx={{
                mt: 1.2,
                borderRadius: 2,
                border: "1px solid rgba(148,163,184,0.14)",
                bgcolor: "rgba(255,255,255,0.03)",
                overflow: "hidden"
              }}
            >
              <Tabs
                value={tab}
                onChange={(_, v) => setTab(v)}
                sx={{
                  px: 1,
                  minHeight: 46,
                  "& .MuiTab-root": {
                    textTransform: "none",
                    fontWeight: 950,
                    minHeight: 46,
                    color: "rgba(229,231,235,0.65)"
                  },
                  "& .Mui-selected": { color: "rgba(229,231,235,0.92)" },
                  "& .MuiTabs-indicator": { height: 3, borderRadius: 2, backgroundColor: "rgba(124,92,255,0.85)" }
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
                      borderRadius: 2,
                      bgcolor: "rgba(2, 6, 23, 0.45)",
                      "& fieldset": { borderColor: "rgba(148,163,184,0.18)" },
                      "&:hover fieldset": { borderColor: "rgba(148,163,184,0.30)" },
                      "&.Mui-focused fieldset": { borderColor: "rgba(124,92,255,0.55)" }
                    }
                  }}
                  InputProps={{
                    style: {
                      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                      color: "#e5e7eb",
                      fontSize: 12.9,
                      lineHeight: 1.65
                    }
                  }}
                />
              </Box>
            </Box>
          </Box>
        </Box>

        <Box>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Box>
              <Typography sx={{ fontWeight: 950, fontSize: 13.8 }}>Table editor</Typography>
              <Typography sx={{ fontSize: 12.4, color: "rgba(229,231,235,0.65)", mt: 0.3 }}>
                Edit and save individual rows to persist them into SQLite.
              </Typography>
            </Box>
          </Stack>

          <Box
            sx={{
              borderRadius: 2,
              border: "1px solid rgba(148,163,184,0.14)",
              bgcolor: "rgba(255,255,255,0.03)",
              p: 1.4
            }}
          >
            <JsonTableEditor
              apiBase={apiBase}
              docId={docId}
              rows={tableRows}
              setRows={setTableRows}
              onSaved={async () => {
                const rows = await loadSavedRows();
                setTableRows((prev) => mergeSavedRows(prev, rows));
                toast("Row saved.", "success");
              }}
              onToast={onToast}
            />
          </Box>
        </Box>
      </Box>

      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle sx={{ fontWeight: 950 }}>Delete document?</DialogTitle>
        <DialogContent>
          <Typography sx={{ color: "rgba(229,231,235,0.8)" }}>
            This will delete the document and all stored artifacts (MinIO + DB rows).
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setConfirmOpen(false)} sx={{ borderRadius: 3, fontWeight: 950 }}>
            Cancel
          </Button>
          <Button onClick={deleteDoc} variant="contained" color="error" sx={{ borderRadius: 3, fontWeight: 950 }}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
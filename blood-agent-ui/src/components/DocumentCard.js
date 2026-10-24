import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Box, Paper, Typography, Button, Divider, Tabs, Tab, TextField, Stack,
  Chip, IconButton, Tooltip, CircularProgress, Dialog, DialogTitle,
  DialogContent, DialogActions
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveIcon from "@mui/icons-material/Save";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import SyncRoundedIcon from "@mui/icons-material/SyncRounded";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import GridViewRoundedIcon from "@mui/icons-material/GridViewRounded";
import VerifiedOutlinedIcon from "@mui/icons-material/VerifiedOutlined";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import JsonTableEditor from "./JsonTableEditor";

const line = "rgba(165,175,208,0.16)";
const muted = "rgba(193,205,229,0.70)";

const surface = {
  bgcolor: "rgba(12,18,35,0.78)",
  border: `1px solid ${line}`,
  boxShadow: "0 20px 75px rgba(0,0,0,0.28)",
  backdropFilter: "blur(14px)"
};

const iconButton = {
  color: "rgba(232,237,255,0.88)",
  bgcolor: "rgba(255,255,255,0.045)",
  border: `1px solid ${line}`,
  borderRadius: 2.4,
  "&:hover": {
    bgcolor: "rgba(153,122,255,0.12)",
    borderColor: "rgba(166,139,255,0.4)"
  }
};

function StatusChip({ value }) {
  const status = String(value || "unknown").toLowerCase();

  const rgb = status.includes("error")
    ? "248,113,113"
    : status.includes("loinc") || status.includes("anonym")
      ? "52,211,153"
      : status.includes("json")
        ? "167,139,250"
        : "148,163,184";

  return (
    <Chip
      className="ba-document-status"
      size="small"
      label={value || "unknown"}
      sx={{
        height: 25,
        fontWeight: 800,
        bgcolor: `rgba(${rgb},0.10)`,
        color: `rgba(${rgb},0.95)`,
        border: `1px solid rgba(${rgb},0.27)`
      }}
    />
  );
}

function normalizedMeasurement(value, abnormalFlag) {
  if (typeof value !== "string") {
    return {
      value,
      abnormal_flag: abnormalFlag ?? null
    };
  }

  const number = "([+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?)";
  const trimmed = value.trim();

  const prefix = new RegExp(
    `^([LH])\\s*:?\\s*${number}$`,
    "i"
  ).exec(trimmed);

  const suffix = prefix
    ? null
    : new RegExp(
        `^${number}\\s*([LH])$`,
        "i"
      ).exec(trimmed);

  const flag = prefix?.[1] || suffix?.[2];
  const numberText = prefix?.[2] || suffix?.[1];

  if (
    !flag ||
    !numberText ||
    !Number.isFinite(Number(numberText))
  ) {
    return {
      value,
      abnormal_flag: abnormalFlag ?? null
    };
  }

  return {
    value: Number(numberText),
    abnormal_flag:
      abnormalFlag ??
      (flag.toUpperCase() === "L" ? "low" : "high")
  };
}

function toTableRows(source) {
  const root = source?.tests
    ? source
    : source?.json?.tests
      ? source.json
      : source?.result?.tests
        ? source.result
        : source;

  const tests = Array.isArray(root?.tests)
    ? root.tests
    : [];

  return tests.map((test) => ({
    row_id: test?.row_id ?? null,
    parameter: test?.parameter ?? "",
    ...normalizedMeasurement(
      test?.value ?? "",
      test?.abnormal_flag
    ),
    unit: test?.unit ?? null,
    loinc_code: test?.loinc_code ?? null,
    loinc_display: test?.loinc_display ?? null,
    reference_min: test?.reference_min ?? null,
    reference_max: test?.reference_max ?? null
  }));
}

function mergeSavedRows(baseRows, savedRows) {
  const next = Array.isArray(baseRows)
    ? baseRows.map((row) => ({ ...row }))
    : [];

  const fields = [
    "parameter",
    "value",
    "abnormal_flag",
    "unit",
    "loinc_code",
    "loinc_display",
    "reference_min",
    "reference_max"
  ];

  for (const saved of Array.isArray(savedRows) ? savedRows : []) {
    const index = Number(
      saved?.row_index ?? saved?.row_id
    );

    if (
      !Number.isInteger(index) ||
      index < 0 ||
      index >= next.length
    ) {
      continue;
    }

    const patch = {};

    for (const field of fields) {
      if (
        Object.prototype.hasOwnProperty.call(
          saved,
          field
        )
      ) {
        patch[field] = saved[field];
      }
    }

    const merged = {
      ...next[index],
      ...patch
    };

    next[index] = {
      ...merged,
      ...normalizedMeasurement(
        merged.value,
        merged.abnormal_flag
      )
    };
  }

  return next;
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function responseError(response, payload, fallback) {
  const detail = payload?.detail || payload?.error;

  const message = typeof detail === "string"
    ? detail
    : Array.isArray(detail)
      ? detail.map((x) => x?.msg).filter(Boolean).join("; ")
      : "";

  return new Error(
    message || response.statusText || fallback
  );
}

async function fetchJson(url, fallback, optional = false) {
  const response = await fetch(url, {
    cache: "no-store"
  });

  if (optional && response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw responseError(
      response,
      await safeJson(response),
      fallback
    );
  }

  return response.json();
}

export default function DocumentCard({
  doc,
  apiBase,
  onDeleted,
  onToast
}) {
  const docId = doc?.doc_id;

  const [meta, setMeta] = useState(null);
  const [tab, setTab] = useState("json");
  const [text, setText] = useState("");
  const [textDirty, setTextDirty] = useState(false);
  const [textReady, setTextReady] = useState(false);
  const [textLoading, setTextLoading] = useState(false);
  const [jsonObj, setJsonObj] = useState(null);
  const [tableRows, setTableRows] = useState([]);
  const [savedRowCount, setSavedRowCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [showEmbeddedPdf, setShowEmbeddedPdf] = useState(false);

  const requestSeq = useRef(0);
  const textRequestSeq = useRef(0);
  const onToastRef = useRef(onToast);

  useEffect(() => {
    onToastRef.current = onToast;
  }, [onToast]);

  const toast = useCallback((message, type = "info") => {
    onToastRef.current?.(message, type);
  }, []);

  const filename =
    meta?.filename ||
    doc?.filename ||
    "";

  const previewUrl =
    meta?.preview_url ||
    doc?.preview_url ||
    "";

  const originalUrl =
    meta?.original_url ||
    doc?.original_url ||
    "";

  const isPdf =
    filename.toLowerCase().endsWith(".pdf") ||
    originalUrl.toLowerCase().includes(".pdf");

  const mappedCount = tableRows.filter(
    (row) => Boolean(row?.loinc_code)
  ).length;

  const flaggedCount = tableRows.filter(
    (row) => ["low", "high"].includes(row?.abnormal_flag)
  ).length;

  const busy = loading || textLoading;

  const urls = useMemo(() => {
    const safeId = encodeURIComponent(docId || "");

    return {
      meta: `${apiBase}/docs/${safeId}`,
      rows: `${apiBase}/docs/${safeId}/rows`,
      results: `${apiBase}/results/${safeId}`,
      text: `${apiBase}/docs/${safeId}/text`,
      regenerate: `${apiBase}/docs/${safeId}/regenerate-json`
    };
  }, [apiBase, docId]);

  const loadAll = useCallback(async (showSpinner = true) => {
    if (!docId) return false;

    const seq = ++requestSeq.current;

    if (showSpinner) {
      setLoading(true);
    }

    try {
      const [documentMeta, storedRows, results] = await Promise.all([
        fetchJson(
          urls.meta,
          "Failed to load document metadata"
        ),
        fetchJson(
          urls.rows,
          "Failed to load saved rows"
        ),
        fetchJson(
          urls.results,
          "Failed to load results",
          true
        )
      ]);

      if (seq !== requestSeq.current) {
        return false;
      }

      const saved = Array.isArray(storedRows)
        ? storedRows
        : Array.isArray(storedRows?.rows)
          ? storedRows.rows
          : [];

      setMeta(documentMeta);
      setJsonObj(results);
      setSavedRowCount(saved.length);
      setTableRows(
        mergeSavedRows(
          toTableRows(results),
          saved
        )
      );

      return true;
    } catch (error) {
      if (seq === requestSeq.current) {
        toast(
          `Load failed: ${error.message}`,
          "error"
        );
      }

      return false;
    } finally {
      if (showSpinner && seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }, [docId, urls, toast]);

  const loadText = useCallback(async (type) => {
    if (!docId) return false;

    const seq = ++textRequestSeq.current;

    setTextLoading(true);
    setTextReady(false);

    try {
      const result = await fetchJson(
        `${urls.text}?type=${encodeURIComponent(type)}`,
        `Failed to load ${type}`,
        true
      );

      if (seq !== textRequestSeq.current) {
        return false;
      }

      if (typeof result?.content !== "string") {
        setText("");
        setTextDirty(false);

        toast(
          `${type} text is unavailable.`,
          "info"
        );

        return false;
      }

      setText(result.content);
      setTextDirty(false);
      setTextReady(true);

      return true;
    } catch (error) {
      if (seq === textRequestSeq.current) {
        toast(
          `Load failed: ${error.message}`,
          "error"
        );
      }

      return false;
    } finally {
      if (seq === textRequestSeq.current) {
        setTextLoading(false);
      }
    }
  }, [docId, urls, toast]);

  useEffect(() => {
    if (!docId) return undefined;

    setMeta(null);
    setJsonObj(null);
    setTableRows([]);
    setText("");
    setTextDirty(false);
    setTextReady(false);
    setSavedRowCount(0);
    setShowEmbeddedPdf(false);
    setTab("json");

    loadAll();

    return () => {
      requestSeq.current += 1;
      textRequestSeq.current += 1;
    };
  }, [docId, loadAll]);

  useEffect(() => {
    if (!docId) return undefined;

    setText("");
    setTextReady(false);
    loadText(tab);

    return () => {
      textRequestSeq.current += 1;
    };
  }, [docId, tab, loadText]);

  const saveContent = useCallback(async (type, content) => {
    const response = await fetch(urls.text, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        type,
        content
      })
    });

    if (!response.ok) {
      throw responseError(
        response,
        await safeJson(response),
        "Save failed"
      );
    }

    return safeJson(response);
  }, [urls]);

  const saveText = useCallback(async () => {
    if (
      !docId ||
      loading ||
      textLoading ||
      !textReady ||
      !textDirty
    ) {
      return;
    }

    if (!text.trim()) {
      toast(
        "Cannot save empty document content.",
        "error"
      );
      return;
    }

    if (
      tab === "json" &&
      savedRowCount > 0 &&
      !window.confirm(
        "Saving the complete JSON will clear previously saved table row edits. Continue?"
      )
    ) {
      return;
    }

    if (tab === "json") {
      try {
        const parsed = JSON.parse(text);

        if (
          !parsed ||
          typeof parsed !== "object" ||
          Array.isArray(parsed)
        ) {
          throw new Error(
            "The top-level JSON value must be an object"
          );
        }
      } catch (error) {
        toast(
          `Invalid JSON: ${error.message}`,
          "error"
        );
        return;
      }
    }

    setLoading(true);

    try {
      await saveContent(tab, text);
      setTextDirty(false);

      const loaded = await loadAll(false);
      const editorLoaded = await loadText(tab);

      toast(
        loaded && editorLoaded
          ? "Saved."
          : "Saved, but refreshing the view failed.",
        loaded && editorLoaded
          ? "success"
          : "warning"
      );
    } catch (error) {
      toast(
        `Save failed: ${error.message}`,
        "error"
      );
    } finally {
      setLoading(false);
    }
  }, [
    docId,
    loading,
    textLoading,
    textReady,
    textDirty,
    text,
    tab,
    savedRowCount,
    saveContent,
    loadAll,
    loadText,
    toast
  ]);

  const regenerate = useCallback(async () => {
    if (
      !docId ||
      loading ||
      textLoading ||
      (tab === "anonymized" && !textReady)
    ) {
      return;
    }

    if (
      textDirty &&
      tab !== "anonymized" &&
      !window.confirm(
        "Regenerating JSON will discard unsaved changes in the current editor. Continue?"
      )
    ) {
      return;
    }

    if (
      savedRowCount > 0 &&
      !window.confirm(
        "Regenerating JSON will clear saved table row corrections. Continue?"
      )
    ) {
      return;
    }

    setLoading(true);

    try {
      if (tab === "anonymized") {
        await saveContent("anonymized", text);
      }

      const response = await fetch(urls.regenerate, {
        method: "POST"
      });

      if (!response.ok) {
        throw responseError(
          response,
          await safeJson(response),
          "JSON regeneration failed"
        );
      }

      setTextDirty(false);

      const loaded = await loadAll(false);
      const alreadyOnJson = tab === "json";

      setTab("json");

      const editorLoaded = alreadyOnJson
        ? await loadText("json")
        : true;

      toast(
        loaded && editorLoaded
          ? "JSON regenerated. Previously saved table row edits were cleared."
          : "JSON regenerated, but refreshing the view failed.",
        loaded && editorLoaded
          ? "success"
          : "warning"
      );
    } catch (error) {
      toast(
        `Regenerate failed: ${error.message}`,
        "error"
      );
    } finally {
      setLoading(false);
    }
  }, [
    docId,
    loading,
    textLoading,
    textReady,
    textDirty,
    tab,
    text,
    savedRowCount,
    urls,
    saveContent,
    loadAll,
    loadText,
    toast
  ]);

  const refreshAll = useCallback(async () => {
    if (busy) return;

    if (
      textDirty &&
      !window.confirm(
        "Discard unsaved editor changes and refresh?"
      )
    ) {
      return;
    }

    setLoading(true);

    try {
      const loaded = await loadAll(false);
      const editorLoaded = loaded && await loadText(tab);

      if (loaded && editorLoaded) {
        toast(
          "Refreshed.",
          "success"
        );
      }
    } finally {
      setLoading(false);
    }
  }, [
    busy,
    textDirty,
    loadAll,
    loadText,
    tab,
    toast
  ]);

  const onRowSaved = useCallback(async () => {
    try {
      const storedRows = await fetchJson(
        urls.rows,
        "Failed to load saved rows"
      );

      const saved = Array.isArray(storedRows)
        ? storedRows
        : Array.isArray(storedRows?.rows)
          ? storedRows.rows
          : [];

      setTableRows(
        mergeSavedRows(
          toTableRows(jsonObj),
          saved
        )
      );

      setSavedRowCount(saved.length);

      toast(
        "Row saved.",
        "success"
      );
    } catch {
      toast(
        "Row may have been saved, but the latest rows could not be loaded.",
        "warning"
      );
    }
  }, [urls, jsonObj, toast]);

  const deleteDoc = useCallback(async () => {
    if (!docId || busy) return;

    setLoading(true);

    try {
      const response = await fetch(urls.meta, {
        method: "DELETE"
      });

      if (!response.ok) {
        throw responseError(
          response,
          await safeJson(response),
          "Delete failed"
        );
      }

      onDeleted?.(docId);
    } catch (error) {
      toast(
        `Delete failed: ${error.message}`,
        "error"
      );
    } finally {
      setLoading(false);
      setConfirmOpen(false);
    }
  }, [
    docId,
    busy,
    urls,
    onDeleted,
    toast
  ]);

  const copyContent = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);

      toast(
        "Copied to clipboard.",
        "success"
      );
    } catch {
      toast(
        "Copy failed.",
        "error"
      );
    }
  }, [text, toast]);

  const changeTab = (_event, nextTab) => {
    if (nextTab === tab || busy) return;

    if (
      textDirty &&
      !window.confirm(
        "Discard unsaved editor changes?"
      )
    ) {
      return;
    }

    setTextDirty(false);
    setTextReady(false);
    setTab(nextTab);
  };

  if (!docId) return null;

  return (
    <Paper
      className="ba-document-card"
      sx={{
        ...surface,
        position: "relative",
        overflow: "hidden",
        borderRadius: {
          xs: 3,
          md: 4
        },
        minWidth: 0
      }}
    >
      {loading && (
        <Box
          className="ba-processing-overlay"
          sx={{
            position: "absolute",
            inset: 0,
            zIndex: 5,
            display: "grid",
            placeItems: "center",
            bgcolor: "rgba(4,8,20,0.70)",
            backdropFilter: "blur(5px)"
          }}
        >
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
            sx={{
              p: 2.5,
              borderRadius: 3,
              bgcolor: "#151c33",
              border: `1px solid ${line}`
            }}
          >
            <CircularProgress
              size={19}
              sx={{ color: "#b6a0ff" }}
            />

            <Typography
              sx={{
                fontSize: 13,
                fontWeight: 800
              }}
            >
              Updating document…
            </Typography>
          </Stack>
        </Box>
      )}

      <Box
        sx={{
          p: {
            xs: 2,
            md: 2.8
          },
          background:
            "linear-gradient(110deg,rgba(88,67,160,.13),transparent 52%)"
        }}
      >
        <Stack
          direction={{
            xs: "column",
            lg: "row"
          }}
          spacing={2}
          alignItems={{
            lg: "center"
          }}
          justifyContent="space-between"
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 850,
                letterSpacing: 2,
                color: "#b9a7ff",
                mb: 0.6
              }}
            >
              DOCUMENT INTELLIGENCE
            </Typography>

            <Typography
              component="h2"
              sx={{
                fontWeight: 850,
                fontSize: {
                  xs: 18,
                  md: 21
                },
                letterSpacing: "-0.025em",
                wordBreak: "break-word"
              }}
            >
              {filename || "Document workspace"}
            </Typography>

            <Typography
              title={docId}
              sx={{
                mt: 0.6,
                fontSize: 11,
                color: muted,
                fontFamily:
                  "ui-monospace, SFMono-Regular, Menlo, monospace",
                overflowWrap: "anywhere"
              }}
            >
              ID: {docId}
            </Typography>

            <Stack
              direction="row"
              useFlexGap
              flexWrap="wrap"
              spacing={0.8}
              sx={{ mt: 1.4 }}
            >
              <StatusChip
                value={
                  meta?.status ||
                  doc?.status ||
                  "unknown"
                }
              />

              <Chip
                size="small"
                label={
                  isPdf
                    ? "PDF DOCUMENT"
                    : "IMAGE DOCUMENT"
                }
                icon={<DescriptionRoundedIcon />}
                sx={{
                  height: 25,
                  bgcolor: "rgba(157,174,216,.09)",
                  border: `1px solid ${line}`,
                  fontSize: 10.5,
                  fontWeight: 800
                }}
              />

              {textDirty && (
                <Chip
                  size="small"
                  label="Unsaved changes"
                  sx={{
                    height: 25,
                    bgcolor: "rgba(255,196,95,.09)",
                    color: "#ffc76c",
                    border: "1px solid rgba(255,196,95,.28)",
                    fontWeight: 800
                  }}
                />
              )}
            </Stack>
          </Box>

          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            useFlexGap
            flexWrap="wrap"
          >
            <Tooltip title="Refresh document">
              <span>
                <IconButton
                  aria-label="Refresh document"
                  disabled={busy}
                  onClick={refreshAll}
                  sx={iconButton}
                >
                  <SyncRoundedIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>

            {originalUrl && (
              <Tooltip title="Open original file">
                <IconButton
                  aria-label="Open original file"
                  onClick={() =>
                    window.open(
                      originalUrl,
                      "_blank",
                      "noopener,noreferrer"
                    )
                  }
                  sx={iconButton}
                >
                  <OpenInNewIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

            <Button
              variant="contained"
              color="error"
              startIcon={<DeleteOutlineIcon />}
              disabled={busy}
              onClick={() => setConfirmOpen(true)}
              sx={{
                borderRadius: 2.5,
                fontWeight: 800,
                px: 2,
                boxShadow: "0 12px 25px rgba(233,70,90,.15)"
              }}
            >
              Delete
            </Button>
          </Stack>
        </Stack>
      </Box>

      <Divider sx={{ borderColor: line }} />

      <Box
        sx={{
          px: {
            xs: 1.5,
            md: 2.8
          },
          py: 1.7,
          display: "flex",
          flexWrap: "wrap",
          gap: 1
        }}
      >
        <Chip
          className="ba-metric-chip"
          icon={<GridViewRoundedIcon />}
          label={`${tableRows.length} parameters`}
        />

        <Chip
          className="ba-metric-chip"
          icon={<VerifiedOutlinedIcon />}
          label={`${mappedCount} LOINC mapped`}
        />

        <Chip
          className="ba-metric-chip"
          label={`${flaggedCount} explicitly flagged`}
        />

        {savedRowCount > 0 && (
          <Chip
            className="ba-metric-chip"
            label={`${savedRowCount} saved row corrections`}
          />
        )}
      </Box>

      <Divider sx={{ borderColor: line }} />

      <Box
        className="ba-document-grid"
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "minmax(0, 1fr)",
            xl: "minmax(310px, .75fr) minmax(0, 1.65fr)"
          },
          alignItems: "start",
          gap: 2.3,
          p: {
            xs: 1.4,
            md: 2.3
          }
        }}
      >
        <Box
          className="ba-preview-column"
          sx={{
            display: "grid",
            gap: 2.2,
            minWidth: 0
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{ mb: 1 }}
            >
              <Typography
                sx={{
                  fontSize: 13.2,
                  fontWeight: 850
                }}
              >
                Document preview
              </Typography>

              {originalUrl && isPdf && (
                <Button
                  size="small"
                  variant="text"
                  endIcon={
                    <KeyboardArrowDownRoundedIcon
                      sx={{
                        transform: showEmbeddedPdf
                          ? "rotate(180deg)"
                          : "none",
                        transition: "transform .2s"
                      }}
                    />
                  }
                  onClick={() =>
                    setShowEmbeddedPdf((v) => !v)
                  }
                  sx={{
                    color: "#c5b5ff",
                    fontSize: 11.5
                  }}
                >
                  {showEmbeddedPdf
                    ? "Hide PDF"
                    : "View full PDF"}
                </Button>
              )}
            </Stack>

            <Box
              className="ba-preview-frame"
              sx={{
                borderRadius: 3,
                border: `1px solid ${line}`,
                overflow: "hidden",
                bgcolor: "rgba(7,11,25,.55)",
                display: "grid",
                placeItems: "center",
                minHeight: 180
              }}
            >
              {previewUrl ? (
                <Box
                  component="img"
                  src={previewUrl}
                  alt={filename || "Document preview"}
                  sx={{
                    display: "block",
                    width: "100%",
                    maxHeight: 355,
                    objectFit: "contain"
                  }}
                />
              ) : (
                <Typography
                  sx={{
                    color: muted,
                    p: 3,
                    fontSize: 12.5
                  }}
                >
                  No preview available
                </Typography>
              )}
            </Box>

            {originalUrl && isPdf && showEmbeddedPdf && (
              <Box
                className="ba-preview-frame"
                sx={{
                  mt: 1.2,
                  overflow: "hidden",
                  border: `1px solid ${line}`,
                  borderRadius: 3,
                  height: 440
                }}
              >
                <Box
                  component="iframe"
                  title={filename || "PDF document"}
                  src={originalUrl}
                  sx={{
                    width: "100%",
                    height: "100%",
                    border: 0
                  }}
                />
              </Box>
            )}
          </Box>

          <Box sx={{ minWidth: 0 }}>
            <Stack
              direction="row"
              alignItems="flex-start"
              justifyContent="space-between"
              spacing={1}
              useFlexGap
              flexWrap="wrap"
              sx={{ mb: 1.1 }}
            >
              <Box>
                <Typography
                  sx={{
                    fontSize: 13.2,
                    fontWeight: 850
                  }}
                >
                  Artifact editor
                </Typography>

                <Typography
                  sx={{
                    mt: 0.3,
                    fontSize: 11.8,
                    color: muted
                  }}
                >
                  Inspect and edit extracted text,
                  anonymized text, or JSON.
                </Typography>
              </Box>

              <Stack
                direction="row"
                spacing={0.7}
                alignItems="center"
                useFlexGap
                flexWrap="wrap"
              >
                <Tooltip title="Copy editor content">
                  <span>
                    <IconButton
                      aria-label="Copy editor content"
                      onClick={copyContent}
                      disabled={!textReady || busy}
                      size="small"
                      sx={iconButton}
                    >
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>

                <Button
                  className="ba-primary-action"
                  variant="contained"
                  size="small"
                  startIcon={<SaveIcon />}
                  onClick={saveText}
                  disabled={busy || !textReady || !textDirty}
                  sx={{
                    fontWeight: 850,
                    borderRadius: 2.3
                  }}
                >
                  Save
                </Button>

                <Tooltip
                  title="Recreate JSON from anonymized text. Saved row edits will be cleared."
                >
                  <span>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<RefreshIcon />}
                      onClick={regenerate}
                      disabled={busy}
                      sx={{
                        color: "#d6cbff",
                        borderColor: "rgba(166,139,255,.35)",
                        borderRadius: 2.3,
                        fontWeight: 800
                      }}
                    >
                      Regenerate
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            </Stack>

            <Box
              className="ba-editor-panel"
              sx={{
                minWidth: 0,
                borderRadius: 3,
                overflow: "hidden",
                border: `1px solid ${line}`
              }}
            >
              <Tabs
                className="ba-editor-tabs"
                value={tab}
                onChange={changeTab}
                variant="fullWidth"
                aria-label="Document editor content type"
                sx={{
                  minHeight: 43,
                  "& .MuiTab-root": {
                    fontSize: 11.8,
                    textTransform: "none",
                    fontWeight: 800,
                    minHeight: 43,
                    minWidth: 0,
                    px: 0.6
                  },
                  "& .MuiTabs-indicator": {
                    height: 3,
                    bgcolor: "#9d7cff",
                    borderRadius: 2
                  }
                }}
              >
                <Tab value="json" label="JSON" />
                <Tab value="anonymized" label="Anonymized" />
                <Tab value="extracted" label="Extracted" />
              </Tabs>

              <Divider sx={{ borderColor: line }} />

              <Box
                sx={{
                  p: 1.1,
                  position: "relative"
                }}
              >
                {textLoading && (
                  <CircularProgress
                    size={17}
                    sx={{
                      position: "absolute",
                      top: 18,
                      right: 18,
                      zIndex: 2
                    }}
                  />
                )}

                <TextField
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    setTextDirty(true);
                  }}
                  disabled={busy || !textReady}
                  multiline
                  minRows={14}
                  maxRows={24}
                  fullWidth
                  placeholder={
                    tab === "json"
                      ? '{\n  "tests": []\n}'
                      : "Text will appear here…"
                  }
                  sx={{
                    "& .MuiOutlinedInput-root": {
                      bgcolor: "rgba(3,8,23,.64)",
                      borderRadius: 2.2,
                      alignItems: "flex-start"
                    },
                    "& textarea": {
                      fontFamily:
                        "ui-monospace, SFMono-Regular, Menlo, monospace",
                      fontSize: 12.3,
                      lineHeight: 1.7,
                      overflowWrap: "anywhere"
                    }
                  }}
                />
              </Box>
            </Box>

            <Typography
              sx={{
                mt: 1,
                color: "rgba(186,199,224,.58)",
                fontSize: 10.8,
                lineHeight: 1.5
              }}
            >
              Regenerate uses the saved anonymized text
              and clears previously saved table row edits.
            </Typography>
          </Box>
        </Box>

        <Box
          className="ba-results-column"
          sx={{
            minWidth: 0,
            width: "100%"
          }}
        >
          <Stack
            direction={{
              xs: "column",
              sm: "row"
            }}
            justifyContent="space-between"
            alignItems={{
              sm: "center"
            }}
            spacing={1}
            sx={{ mb: 1.2 }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography
                sx={{
                  fontSize: 13.2,
                  fontWeight: 850
                }}
              >
                Laboratory results
              </Typography>

              <Typography
                sx={{
                  fontSize: 11.8,
                  color: muted,
                  mt: 0.4,
                  lineHeight: 1.6
                }}
              >
                Edit individual rows and save them to SQLite.
                Flags must reflect explicit report markings.
              </Typography>
            </Box>

            <Chip
              className="ba-metric-chip"
              label="ROW EDITOR"
              sx={{
                alignSelf: "flex-start"
              }}
            />
          </Stack>

          <Box
            className="ba-table-shell"
            aria-busy={loading}
            sx={{
              minWidth: 0,
              width: "100%",
              maxWidth: "100%",
              overflow: "hidden",
              borderRadius: 3,
              border: `1px solid ${line}`,
              p: {
                xs: 0.7,
                sm: 1.25
              },
              bgcolor: "rgba(7,12,28,.44)",
              pointerEvents: loading
                ? "none"
                : "auto",
              opacity: loading ? 0.65 : 1
            }}
          >
            <JsonTableEditor
              apiBase={apiBase}
              docId={docId}
              rows={tableRows}
              setRows={setTableRows}
              onSaved={onRowSaved}
              onToast={onToast}
            />
          </Box>
        </Box>
      </Box>

      <Dialog
        open={confirmOpen}
        onClose={() =>
          !loading && setConfirmOpen(false)
        }
        PaperProps={{
          sx: {
            ...surface,
            borderRadius: 3.3,
            width: "min(440px,92vw)"
          }
        }}
      >
        <DialogTitle
          sx={{
            fontWeight: 850,
            letterSpacing: "-.02em"
          }}
        >
          Delete document?
        </DialogTitle>

        <DialogContent>
          <Typography
            sx={{
              color: muted,
              lineHeight: 1.7,
              fontSize: 13.4
            }}
          >
            This permanently removes the document,
            its stored artifacts, and saved database rows.
            This action cannot be undone.
          </Typography>
        </DialogContent>

        <DialogActions
          sx={{
            p: 2.2,
            gap: 0.7
          }}
        >
          <Button
            onClick={() => setConfirmOpen(false)}
            disabled={loading}
          >
            Cancel
          </Button>

          <Button
            variant="contained"
            color="error"
            startIcon={<DeleteOutlineIcon />}
            disabled={busy}
            onClick={deleteDoc}
            sx={{
              borderRadius: 2.2,
              fontWeight: 800
            }}
          >
            Delete document
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
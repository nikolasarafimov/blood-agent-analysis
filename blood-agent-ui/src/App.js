import React, { useMemo, useRef, useState } from "react";
import {
  Avatar,
  Box,
  Button,
  Chip,
  CssBaseline,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
  CircularProgress
} from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import ChatRoundedIcon from "@mui/icons-material/ChatRounded";
import GridViewRoundedIcon from "@mui/icons-material/GridViewRounded";

import { useDropzone } from "react-dropzone";
import DocumentCard from "./components/DocumentCard";

const API_BASE = (process.env.REACT_APP_API_URL || "http://localhost:8000").replace(/\/$/, "");

const theme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#070A12",
      paper: "#0B1020"
    },
    primary: {
      main: "#7C5CFF"
    },
    success: {
      main: "#22C55E"
    },
    error: {
      main: "#EF4444"
    },
    text: {
      primary: "rgba(237,242,250,0.92)",
      secondary: "rgba(237,242,250,0.62)"
    }
  },
  shape: {
    borderRadius: 16
  },
  typography: {
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
    h6: { fontWeight: 900 },
    button: { textTransform: "none", fontWeight: 900 }
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          border: "1px solid rgba(148,163,184,0.14)"
        }
      }
    }
  }
});

const glass = {
  background: "rgba(11, 16, 32, 0.72)",
  border: "1px solid rgba(148, 163, 184, 0.14)",
  boxShadow: "0 22px 80px rgba(0,0,0,0.55)",
  backdropFilter: "blur(14px)"
};

function Bubble({ role, children }) {
  const isUser = role === "user";
  return (
    <Box sx={{ display: "flex", gap: 1.2, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {!isUser && (
        <Avatar
          sx={{
            width: 34,
            height: 34,
            bgcolor: "rgba(124,92,255,0.16)",
            border: "1px solid rgba(124,92,255,0.30)"
          }}
        >
          <AutoAwesomeRoundedIcon fontSize="small" />
        </Avatar>
      )}

      <Box
        sx={{
          width: "fit-content",
          maxWidth: "min(1100px, calc(100vw - 160px))",
          borderRadius: 3,
          px: 2,
          py: 1.4,
          bgcolor: isUser ? "rgba(124,92,255,0.14)" : "rgba(255,255,255,0.06)",
          border: "1px solid rgba(148,163,184,0.14)",
          boxShadow: isUser ? "0 14px 44px rgba(124,92,255,0.14)" : "none",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word"
        }}
      >
        {children}
      </Box>

      {isUser && (
        <Avatar
          sx={{
            width: 34,
            height: 34,
            bgcolor: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(148,163,184,0.14)"
          }}
        >
          <Typography sx={{ fontSize: 12, fontWeight: 950 }}>You</Typography>
        </Avatar>
      )}
    </Box>
  );
}

function DocItem({ doc, active, onClick }) {
  const status = (doc?.status || "unknown").toLowerCase();
  const badge =
    status.includes("error")
      ? { bg: "rgba(239,68,68,0.10)", fg: "rgba(239,68,68,0.95)", br: "rgba(239,68,68,0.28)" }
      : status.includes("loinc")
      ? { bg: "rgba(34,197,94,0.10)", fg: "rgba(34,197,94,0.95)", br: "rgba(34,197,94,0.28)" }
      : status.includes("json")
      ? { bg: "rgba(124,92,255,0.10)", fg: "rgba(124,92,255,0.95)", br: "rgba(124,92,255,0.28)" }
      : { bg: "rgba(255,255,255,0.05)", fg: "rgba(237,242,250,0.78)", br: "rgba(148,163,184,0.14)" };

  return (
    <Box
      onClick={onClick}
      sx={{
        cursor: "pointer",
        borderRadius: 3,
        px: 1.2,
        py: 1.1,
        border: active ? "1px solid rgba(124,92,255,0.55)" : "1px solid rgba(148,163,184,0.14)",
        bgcolor: active ? "rgba(124,92,255,0.10)" : "rgba(255,255,255,0.03)",
        "&:hover": { bgcolor: active ? "rgba(124,92,255,0.12)" : "rgba(255,255,255,0.06)" }
      }}
    >
      <Stack direction="row" spacing={1.2} alignItems="center">
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: 2.5,
            display: "grid",
            placeItems: "center",
            bgcolor: "rgba(2,6,23,0.55)",
            border: "1px solid rgba(148,163,184,0.14)",
            overflow: "hidden"
          }}
        >
          {doc?.preview_url ? (
            <Box component="img" src={doc.preview_url} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            <DescriptionRoundedIcon sx={{ color: "rgba(237,242,250,0.70)" }} fontSize="small" />
          )}
        </Box>

        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontSize: 12.3, fontWeight: 950, lineHeight: 1.2 }} noWrap>
            {doc?.filename || "Document"}
          </Typography>
          <Typography sx={{ fontSize: 11.5, color: "rgba(237,242,250,0.62)" }} noWrap>
            {doc?.doc_id || ""}
          </Typography>
        </Box>

        <Chip
          size="small"
          label={doc?.status || "unknown"}
          sx={{
            height: 22,
            fontWeight: 950,
            bgcolor: badge.bg,
            color: badge.fg,
            border: `1px solid ${badge.br}`
          }}
        />
      </Stack>
    </Box>
  );
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [docs, setDocs] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(null);

  const [files, setFiles] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);

  const [view, setView] = useState("chat");

  const [messages, setMessages] = useState([
    { id: "m0", role: "assistant", text: "Upload a PDF/image, type what you want, and press Run (or Enter)." }
  ]);

  const scrollRef = useRef(null);

  const selectedDoc = useMemo(
    () => docs.find((d) => d.doc_id === selectedDocId) || null,
    [docs, selectedDocId]
  );

  const addFiles = (incoming) => {
    const arr = Array.from(incoming || []);
    if (!arr.length) return;
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}_${f.size}`));
      const next = [...prev];
      for (const f of arr) {
        const k = `${f.name}_${f.size}`;
        if (!seen.has(k)) next.push(f);
      }
      return next;
    });
  };

  const removeFile = (name) => setFiles((prev) => prev.filter((f) => f.name !== name));
  const clearFiles = () => setFiles([]);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: (accepted) => addFiles(accepted),
    noClick: true,
    noKeyboard: true,
    multiple: true
  });

  const pushMessage = (role, text) => {
    const id = `m_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    setMessages((prev) => [...prev, { id, role, text }]);
    setTimeout(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, 50);
    return id;
  };

  const replaceMessage = (id, nextText) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, text: nextText } : m)));
  };

  const startNew = () => {
    setFiles([]);
    setPrompt("");
    setMessages([{ id: `m0_${Date.now()}`, role: "assistant", text: "Upload a PDF/image, type what you want, and press Run (or Enter)." }]);
    setSelectedDocId(null);
    setView("chat");
  };

  const canRun = files.length > 0 && Boolean(prompt.trim()) && !loading;

  const run = async () => {
    if (!canRun) return;

    const promptToSend = prompt.trim();
    const filesToSend = files.slice();

    setPrompt("");
    setFiles([]);

    pushMessage("user", promptToSend);
    const pendingId = pushMessage("assistant", "Processing…");
    setLoading(true);

    const formData = new FormData();
    filesToSend.forEach((f) => formData.append("files", f));
    formData.append("prompt", promptToSend);

    try {
      const res = await fetch(`${API_BASE}/run-agent`, { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText || "Server error");
      }
      const data = await res.json();
      const created = Array.isArray(data) ? data : [];

      setDocs((prev) => [...created, ...prev]);
      if (created?.[0]?.doc_id) {
        setSelectedDocId(created[0].doc_id);
        setView("workspace");
      }

      const summary = created
        .slice(0, 6)
        .map((d) => {
          const name = d?.filename ? ` (${d.filename})` : "";
          return `• ${d.doc_id}${name} — ${d.status || "unknown"}`;
        })
        .join("\n");

      replaceMessage(
        pendingId,
        created.length ? `Done.\n\nCreated documents:\n${summary}\n\nOpen Workspace to review the preview, JSON, and rows.` : "Done, but no documents were returned."
      );
    } catch (e) {
      replaceMessage(pendingId, `Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const onDeleted = (docId) => {
    setDocs((prev) => prev.filter((d) => d.doc_id !== docId));
    setSelectedDocId((prev) => (prev === docId ? null : prev));
    if (selectedDocId === docId) setView("chat");
  };

  const LeftSidebar = (
    <Box
      sx={{
        width: 330,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid rgba(148,163,184,0.14)",
        bgcolor: "rgba(9, 12, 22, 0.72)",
        backdropFilter: "blur(14px)"
      }}
    >
      <Box sx={{ p: 1.8 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.2} alignItems="center">
            <Avatar
              sx={{
                width: 42,
                height: 42,
                bgcolor: "rgba(124,92,255,0.16)",
                border: "1px solid rgba(124,92,255,0.30)"
              }}
            >
              <AutoAwesomeRoundedIcon />
            </Avatar>
            <Box>
              <Typography sx={{ fontWeight: 950, fontSize: 13.8, lineHeight: 1.1 }}>Blood Agent</Typography>
              <Typography sx={{ fontSize: 12, color: "rgba(237,242,250,0.62)" }}>OCR → Anonymize → JSON → LOINC</Typography>
            </Box>
          </Stack>

          <Tooltip title="New">
            <IconButton
              onClick={startNew}
              sx={{
                color: "rgba(237,242,250,0.78)",
                bgcolor: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(148,163,184,0.14)",
                borderRadius: 3
              }}
            >
              <AddRoundedIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        <Button
          fullWidth
          variant="contained"
          onClick={startNew}
          startIcon={<AddRoundedIcon />}
          sx={{
            mt: 1.6,
            borderRadius: 3,
            fontWeight: 950,
            backgroundImage: "linear-gradient(135deg, rgba(124,92,255,0.98), rgba(124,92,255,0.60))",
            border: "1px solid rgba(124,92,255,0.55)",
            boxShadow: "0 18px 70px rgba(124,92,255,0.16)"
          }}
        >
          New
        </Button>

        <Stack direction="row" spacing={1} sx={{ mt: 1.2 }}>
          <Button
            fullWidth
            onClick={() => setView("chat")}
            startIcon={<ChatRoundedIcon />}
            variant={view === "chat" ? "contained" : "outlined"}
            sx={{
              borderRadius: 3,
              fontWeight: 950,
              ...(view === "chat"
                ? {
                    backgroundImage: "linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02))",
                    border: "1px solid rgba(148,163,184,0.18)"
                  }
                : { borderColor: "rgba(148,163,184,0.22)", color: "rgba(237,242,250,0.85)" })
            }}
          >
            Chat
          </Button>
          <Button
            fullWidth
            onClick={() => setView("workspace")}
            startIcon={<GridViewRoundedIcon />}
            disabled={!selectedDoc}
            variant={view === "workspace" ? "contained" : "outlined"}
            sx={{
              borderRadius: 3,
              fontWeight: 950,
              ...(view === "workspace"
                ? {
                    backgroundImage: "linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02))",
                    border: "1px solid rgba(148,163,184,0.18)"
                  }
                : { borderColor: "rgba(148,163,184,0.22)", color: "rgba(237,242,250,0.85)" })
            }}
          >
            Workspace
          </Button>
        </Stack>
      </Box>

      <Divider sx={{ borderColor: "rgba(148,163,184,0.14)" }} />

      <Box sx={{ p: 1.4, flex: 1, overflow: "auto" }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.2 }}>
          <Chip
            size="small"
            label={`${docs.length} documents`}
            sx={{
              bgcolor: "rgba(255,255,255,0.05)",
              color: "rgba(237,242,250,0.82)",
              border: "1px solid rgba(148,163,184,0.14)",
              fontWeight: 950,
              height: 24
            }}
          />
          {selectedDoc && (
            <Chip
              size="small"
              label={selectedDoc.status || "selected"}
              sx={{
                bgcolor: "rgba(124,92,255,0.10)",
                color: "rgba(124,92,255,0.95)",
                border: "1px solid rgba(124,92,255,0.25)",
                fontWeight: 950,
                height: 24
              }}
            />
          )}
        </Stack>

        {docs.length === 0 ? (
          <Paper sx={{ ...glass, p: 2.2, borderRadius: 3 }}>
            <Typography sx={{ fontWeight: 950, fontSize: 13.5 }}>No documents yet</Typography>
            <Typography sx={{ mt: 0.7, fontSize: 12.5, color: "rgba(237,242,250,0.62)" }}>
              Attach a file and run the agent.
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={1.1}>
            {docs.map((d) => (
              <DocItem
                key={d.doc_id}
                doc={d}
                active={d.doc_id === selectedDocId}
                onClick={() => {
                  setSelectedDocId(d.doc_id);
                  setView("workspace");
                }}
              />
            ))}
          </Stack>
        )}
      </Box>

      <Divider sx={{ borderColor: "rgba(148,163,184,0.14)" }} />

      <Box sx={{ p: 1.4 }}>
        <Typography sx={{ fontSize: 11.5, color: "rgba(237,242,250,0.55)" }}>API: {API_BASE}</Typography>
      </Box>
    </Box>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box
        sx={{
          height: "100vh",
          display: "flex",
          overflow: "hidden",
          background:
            "radial-gradient(1200px 700px at 20% -10%, rgba(124,92,255,0.22), transparent 60%), radial-gradient(900px 600px at 90% 10%, rgba(34,197,94,0.12), transparent 55%), radial-gradient(900px 600px at 60% 110%, rgba(255,255,255,0.06), transparent 60%), #070A12"
        }}
      >
        <Box sx={{ display: { xs: "none", md: "block" } }}>{LeftSidebar}</Box>

        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <Box
            sx={{
              px: 1.6,
              py: 1.2,
              borderBottom: "1px solid rgba(148,163,184,0.14)",
              bgcolor: "rgba(9, 12, 22, 0.62)",
              backdropFilter: "blur(14px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1
            }}
          >
            <Stack direction="row" spacing={1} alignItems="center">
              <IconButton
                onClick={() => setSidebarOpen(true)}
                sx={{
                  display: { xs: "inline-flex", md: "none" },
                  color: "rgba(237,242,250,0.78)",
                  bgcolor: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(148,163,184,0.14)",
                  borderRadius: 3
                }}
              >
                <MenuRoundedIcon />
              </IconButton>

              <Typography sx={{ fontWeight: 950, fontSize: 14.8 }}>
                {view === "chat" ? "Chat" : "Workspace"}
              </Typography>

              {selectedDoc && (
                <Chip
                  size="small"
                  label={selectedDoc.filename || selectedDoc.doc_id}
                  sx={{
                    ml: 0.6,
                    maxWidth: 420,
                    bgcolor: "rgba(255,255,255,0.05)",
                    color: "rgba(237,242,250,0.86)",
                    border: "1px solid rgba(148,163,184,0.14)",
                    "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" }
                  }}
                />
              )}
            </Stack>

            <Stack direction="row" spacing={1} alignItems="center">
              <Chip
                size="small"
                label={loading ? "Working…" : "Ready"}
                sx={{
                  bgcolor: loading ? "rgba(124,92,255,0.10)" : "rgba(34,197,94,0.10)",
                  color: loading ? "rgba(124,92,255,0.95)" : "rgba(34,197,94,0.95)",
                  border: loading ? "1px solid rgba(124,92,255,0.22)" : "1px solid rgba(34,197,94,0.22)",
                  fontWeight: 950
                }}
              />
            </Stack>
          </Box>

          {view === "chat" ? (
            <>
              <Box
                ref={scrollRef}
                sx={{
                  flex: 1,
                  overflow: "auto",
                  px: { xs: 1.2, md: 2.2 },
                  py: 2.2
                }}
              >
                <Box sx={{ width: "100%" }}>
                  <Stack spacing={1.6}>
                    {messages.map((m) => (
                      <Bubble key={m.id} role={m.role}>
                        <Typography sx={{ fontSize: 14.4, lineHeight: 1.75, color: "rgba(237,242,250,0.92)" }}>
                          {m.text}
                        </Typography>
                      </Bubble>
                    ))}
                  </Stack>
                </Box>
              </Box>

              <Box
                {...getRootProps()}
                sx={{
                  px: { xs: 1.2, md: 2.2 },
                  pb: 2,
                  pt: 1.2,
                  borderTop: "1px solid rgba(148,163,184,0.14)",
                  bgcolor: "rgba(9, 12, 22, 0.62)",
                  backdropFilter: "blur(16px)"
                }}
              >
                <input {...getInputProps()} />

                <Paper
                  sx={{
                    ...glass,
                    width: "100%",
                    borderRadius: 4,
                    p: 1.4,
                    outline: isDragActive ? "1px dashed rgba(124,92,255,0.75)" : "none"
                  }}
                >
                  <Stack spacing={1.1}>
                    <TextField
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          run();
                        }
                      }}
                      multiline
                      minRows={2}
                      maxRows={7}
                      placeholder="Write something…"
                      fullWidth
                      sx={{
                        "& .MuiOutlinedInput-root": {
                          borderRadius: 3,
                          bgcolor: "rgba(2, 6, 23, 0.42)",
                          "& fieldset": { borderColor: "rgba(148,163,184,0.20)" },
                          "&:hover fieldset": { borderColor: "rgba(148,163,184,0.32)" },
                          "&.Mui-focused fieldset": { borderColor: "rgba(124,92,255,0.60)" }
                        },
                        "& textarea": {
                          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                          fontSize: 13.4,
                          lineHeight: 1.65,
                          color: "rgba(237,242,250,0.92)"
                        }
                      }}
                    />

                    <Stack
                      direction={{ xs: "column", md: "row" }}
                      spacing={1}
                      alignItems={{ md: "center" }}
                      justifyContent="space-between"
                    >
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: "wrap" }} useFlexGap>
                        <Chip
                          icon={<UploadFileRoundedIcon />}
                          label={files.length ? `${files.length} file(s) attached` : "Attach a PDF/image"}
                          size="small"
                          sx={{
                            bgcolor: "rgba(255,255,255,0.05)",
                            color: "rgba(237,242,250,0.82)",
                            border: "1px solid rgba(148,163,184,0.14)",
                            fontWeight: 950
                          }}
                        />

                        {files.slice(0, 6).map((f) => (
                          <Chip
                            key={`${f.name}_${f.size}`}
                            label={f.name}
                            onDelete={() => removeFile(f.name)}
                            size="small"
                            sx={{
                              maxWidth: 380,
                              bgcolor: "rgba(255,255,255,0.05)",
                              color: "rgba(237,242,250,0.88)",
                              border: "1px solid rgba(148,163,184,0.14)",
                              "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" }
                            }}
                          />
                        ))}

                        {files.length > 6 && (
                          <Chip
                            label={`+${files.length - 6} more`}
                            size="small"
                            sx={{
                              bgcolor: "rgba(124,92,255,0.10)",
                              color: "rgba(124,92,255,0.95)",
                              border: "1px solid rgba(124,92,255,0.25)",
                              fontWeight: 950
                            }}
                          />
                        )}
                      </Stack>

                      <Stack direction="row" spacing={1} alignItems="center" justifyContent="flex-end">
                        <Button
                          variant="outlined"
                          onClick={open}
                          startIcon={<UploadFileRoundedIcon />}
                          disabled={loading}
                          sx={{
                            borderRadius: 3,
                            fontWeight: 950,
                            color: "rgba(237,242,250,0.86)",
                            borderColor: "rgba(148,163,184,0.24)",
                            "&:hover": { borderColor: "rgba(148,163,184,0.38)" }
                          }}
                        >
                          Attach
                        </Button>

                        <Button
                          variant="text"
                          onClick={clearFiles}
                          disabled={loading || files.length === 0}
                          startIcon={<DeleteOutlineRoundedIcon />}
                          sx={{ color: "rgba(237,242,250,0.65)", fontWeight: 950, borderRadius: 3 }}
                        >
                          Clear
                        </Button>

                        <Button
                          variant="contained"
                          onClick={run}
                          disabled={!canRun}
                          endIcon={loading ? <CircularProgress size={16} sx={{ color: "white" }} /> : <SendRoundedIcon />}
                          sx={{
                            borderRadius: 3,
                            px: 2,
                            fontWeight: 950,
                            backgroundImage: "linear-gradient(135deg, rgba(124,92,255,0.98), rgba(124,92,255,0.60))",
                            border: "1px solid rgba(124,92,255,0.55)",
                            boxShadow: "0 18px 70px rgba(124,92,255,0.16)",
                            "&:hover": {
                              backgroundImage: "linear-gradient(135deg, rgba(124,92,255,1), rgba(124,92,255,0.68))"
                            }
                          }}
                        >
                          {loading ? "Running…" : "Run"}
                        </Button>
                      </Stack>
                    </Stack>

                    <Typography sx={{ fontSize: 11.5, color: "rgba(237,242,250,0.55)" }}>
                      Tip: Enter sends. Shift+Enter makes a new line. Drag & drop files anywhere in this area.
                    </Typography>
                  </Stack>
                </Paper>
              </Box>
            </>
          ) : (
            <Box sx={{ flex: 1, overflow: "auto", p: { xs: 1.2, md: 2.2 } }}>
              {selectedDoc ? (
                <Paper sx={{ ...glass, borderRadius: 4, p: { xs: 1.2, md: 1.6 } }}>
                  <DocumentCard doc={selectedDoc} apiBase={API_BASE} onDeleted={onDeleted} />
                </Paper>
              ) : (
                <Paper sx={{ ...glass, borderRadius: 4, p: 2.2 }}>
                  <Typography sx={{ fontWeight: 950, fontSize: 14.5 }}>No document selected</Typography>
                  <Typography sx={{ mt: 0.8, color: "rgba(237,242,250,0.62)" }}>
                    Run the agent or pick a document from the left sidebar.
                  </Typography>
                </Paper>
              )}
            </Box>
          )}
        </Box>

        <Drawer
          anchor="left"
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          sx={{ display: { xs: "block", md: "none" } }}
          PaperProps={{
            sx: {
              width: 330,
              bgcolor: "rgba(9, 12, 22, 0.86)",
              backdropFilter: "blur(14px)"
            }
          }}
        >
          {LeftSidebar}
        </Drawer>
      </Box>
    </ThemeProvider>
  );
}
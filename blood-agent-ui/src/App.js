import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
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
  CircularProgress,
  InputAdornment,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText
} from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import GridViewRoundedIcon from "@mui/icons-material/GridViewRounded";
import ChatRoundedIcon from "@mui/icons-material/ChatRounded";
import PersonRoundedIcon from "@mui/icons-material/PersonRounded";
import MoreVertRoundedIcon from "@mui/icons-material/MoreVertRounded";

import { useDropzone } from "react-dropzone";
import DocumentCard from "./components/DocumentCard";

const API_BASE = (process.env.REACT_APP_API_URL || "http://localhost:8000").replace(/\/$/, "");

const theme = createTheme({
  palette: {
    mode: "dark",
    background: { default: "#070A12", paper: "#0B1020" },
    primary: { main: "#7C5CFF" },
    success: { main: "#22C55E" },
    error: { main: "#EF4444" },
    text: { primary: "rgba(237,242,250,0.92)", secondary: "rgba(237,242,250,0.62)" }
  },
  shape: { borderRadius: 16 },
  typography: {
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
    h6: { fontWeight: 950 },
    button: { textTransform: "none", fontWeight: 900 }
  },
  components: {
    MuiPaper: { styleOverrides: { root: { border: "1px solid rgba(148,163,184,0.14)" } } }
  }
});

const glass = {
  background: "rgba(11, 16, 32, 0.72)",
  border: "1px solid rgba(148, 163, 184, 0.14)",
  boxShadow: "0 22px 80px rgba(0,0,0,0.55)",
  backdropFilter: "blur(14px)"
};

const railGlass = {
  background: "rgba(9, 12, 22, 0.86)",
  borderRight: "1px solid rgba(148,163,184,0.14)",
  backdropFilter: "blur(16px)"
};

function nowId(prefix = "id") {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function LogoAvatar({ size = 40 }) {
  return (
    <Avatar
      src="/logo.png"
      variant="circular"
      sx={{
        width: size,
        height: size,
        bgcolor: "rgba(124,92,255,0.14)",
        border: "1px solid rgba(124,92,255,0.35)"
      }}
    />
  );
}

function StatusPill({ loading }) {
  const label = loading ? "Working…" : "Ready";
  const bg = loading ? "rgba(124,92,255,0.12)" : "rgba(34,197,94,0.12)";
  const fg = loading ? "rgba(124,92,255,0.95)" : "rgba(34,197,94,0.95)";
  const br = loading ? "rgba(124,92,255,0.25)" : "rgba(34,197,94,0.25)";
  return (
    <Chip size="small" label={label} sx={{ bgcolor: bg, color: fg, border: `1px solid ${br}`, fontWeight: 950 }} />
  );
}

function FileRow({ names = [] }) {
  if (!names.length) return null;
  return (
    <Stack direction="row" spacing={0.8} flexWrap="wrap" useFlexGap sx={{ mt: 0.7 }}>
      {names.map((n) => (
        <Chip
          key={n}
          size="small"
          icon={<UploadFileRoundedIcon />}
          label={n}
          sx={{
            height: 24,
            bgcolor: "rgba(255,255,255,0.05)",
            color: "rgba(237,242,250,0.84)",
            border: "1px solid rgba(148,163,184,0.14)",
            fontWeight: 900,
            "& .MuiChip-label": { maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis" }
          }}
        />
      ))}
    </Stack>
  );
}

function Bubble({ role, children }) {
  const isUser = role === "user";
  return (
    <Box sx={{ display: "flex", gap: 1.1, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {!isUser && <LogoAvatar size={32} />}

      <Box
        sx={{
          width: "fit-content",
          maxWidth: "min(980px, calc(100vw - 160px))",
          borderRadius: 2,
          px: 2.2,
          py: 1.6,
          bgcolor: isUser ? "rgba(124,92,255,0.12)" : "rgba(255,255,255,0.05)",
          border: "1px solid rgba(148,163,184,0.18)",
          boxShadow: isUser ? "0 10px 34px rgba(124,92,255,0.10)" : "0 10px 30px rgba(0,0,0,0.22)",
          position: "relative",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          "&::before": {
            content: '""',
            position: "absolute",
            inset: 0,
            borderRadius: "inherit",
            pointerEvents: "none",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)"
          }
        }}
      >
        {children}
      </Box>

      {isUser && (
        <Avatar
          sx={{
            width: 32,
            height: 32,
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

function SessionCard({ s, active, onClick, onOpenMenu }) {
  const title = s?.title || "Chat";
  const subtitle = s?.subtitle || "No results yet";
  const docCount = Array.isArray(s?.docs) ? s.docs.length : 0;

  return (
    <Box
      onClick={onClick}
      sx={{
        cursor: "pointer",
        borderRadius: 3,
        p: 1.2,
        border: active ? "1px solid rgba(124,92,255,0.55)" : "1px solid rgba(148,163,184,0.14)",
        bgcolor: active ? "rgba(124,92,255,0.10)" : "rgba(255,255,255,0.03)",
        "&:hover": { bgcolor: active ? "rgba(124,92,255,0.12)" : "rgba(255,255,255,0.06)" }
      }}
    >
      <Stack direction="row" spacing={1.2} alignItems="center">
        <Box
          sx={{
            width: 42,
            height: 42,
            borderRadius: 2.5,
            display: "grid",
            placeItems: "center",
            bgcolor: "rgba(2,6,23,0.55)",
            border: "1px solid rgba(148,163,184,0.14)",
            overflow: "hidden"
          }}
        >
          {s?.coverUrl ? (
            <Box component="img" src={s.coverUrl} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            <DescriptionRoundedIcon sx={{ color: "rgba(237,242,250,0.70)" }} fontSize="small" />
          )}
        </Box>

        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontSize: 12.6, fontWeight: 950, lineHeight: 1.15 }} noWrap>
            {title}
          </Typography>
          <Typography sx={{ fontSize: 11.5, color: "rgba(237,242,250,0.62)" }} noWrap>
            {subtitle}
          </Typography>
        </Box>

        <Stack spacing={0.7} alignItems="flex-end">
          <Chip
            size="small"
            label={`${docCount} docs`}
            sx={{
              height: 22,
              fontWeight: 950,
              bgcolor: "rgba(255,255,255,0.05)",
              color: "rgba(237,242,250,0.82)",
              border: "1px solid rgba(148,163,184,0.14)"
            }}
          />
        </Stack>

        <Tooltip title="More">
          <IconButton
            size="small"
            onClick={(e) => {
              // IMPORTANT: prevent selecting the chat when clicking the menu button
              e.preventDefault();
              e.stopPropagation();
              onOpenMenu?.(e, s.id);
            }}
            sx={{
              ml: 0.4,
              color: "rgba(237,242,250,0.72)",
              bgcolor: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(148,163,184,0.14)",
              "&:hover": { bgcolor: "rgba(255,255,255,0.08)" }
            }}
          >
            <MoreVertRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Stack>
    </Box>
  );
}

function Toast({ open, message, type, onClose }) {
  if (!open) return null;

  const palette =
    type === "success"
      ? { bg: "rgba(34,197,94,0.14)", fg: "rgba(34,197,94,0.95)", br: "rgba(34,197,94,0.28)" }
      : type === "error"
      ? { bg: "rgba(239,68,68,0.14)", fg: "rgba(239,68,68,0.95)", br: "rgba(239,68,68,0.28)" }
      : { bg: "rgba(255,255,255,0.06)", fg: "rgba(237,242,250,0.90)", br: "rgba(148,163,184,0.16)" };

  return (
    <Box
      sx={{
        position: "fixed",
        right: 18,
        bottom: 18,
        zIndex: 2000
      }}
    >
      <Paper
        sx={{
          ...glass,
          px: 1.6,
          py: 1.2,
          borderRadius: 3,
          border: `1px solid ${palette.br}`,
          bgcolor: palette.bg,
          color: palette.fg,
          cursor: "pointer"
        }}
        onClick={onClose}
      >
        <Typography sx={{ fontSize: 13.2, fontWeight: 950 }}>{message}</Typography>
      </Paper>
    </Box>
  );
}

export default function App() {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);

  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);

  const [view, setView] = useState("chat");
  const [loading, setLoading] = useState(false);

  const [search, setSearch] = useState("");
  const [files, setFiles] = useState([]);
  const [prompt, setPrompt] = useState("");

  const [toast, setToast] = useState({ open: false, message: "", type: "info" });

  // --- per-chat menu state (⋮)
  const [chatMenu, setChatMenu] = useState({ anchorEl: null, sessionId: null });
  const chatMenuOpen = Boolean(chatMenu.anchorEl);

  const scrollRef = useRef(null);

  const railWidth = 72;
  const minSidebarWidth = 300;
  const maxSidebarWidth = 460;
  const defaultSidebarWidth = 340;

  const [sidebarWidth, setSidebarWidth] = useState(defaultSidebarWidth);
  const [isResizing, setIsResizing] = useState(false);

  const showToast = useCallback((message, type = "info") => {
    setToast({ open: true, message, type });
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => setToast((t) => ({ ...t, open: false })), 2800);
  }, []);
  useEffect(() => {
    return () => {
      if (showToast._t) window.clearTimeout(showToast._t);
    };
  }, [showToast]);

  const activeSession = useMemo(() => sessions.find((s) => s.id === activeSessionId) || null, [sessions, activeSessionId]);

  const displayedSessions = useMemo(() => {
    const q = (search || "").trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => `${s?.title || ""} ${s?.subtitle || ""}`.toLowerCase().includes(q));
  }, [sessions, search]);

  const messages = useMemo(() => {
    const base = [
      {
        id: "m_welcome",
        role: "assistant",
        text: "Attach a PDF/image to begin. Then write something and press Run (or Enter)."
      }
    ];
    if (!activeSession) return base;
    return Array.isArray(activeSession.messages) && activeSession.messages.length ? activeSession.messages : base;
  }, [activeSession]);

  const selectedDocId = useMemo(() => activeSession?.selectedDocId || null, [activeSession]);
  const selectedDoc = useMemo(() => {
    if (!activeSession || !selectedDocId) return null;
    return (activeSession.docs || []).find((d) => d.doc_id === selectedDocId) || null;
  }, [activeSession, selectedDocId]);

  const updateSession = useCallback((sessionId, updater) => {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        const next = typeof updater === "function" ? updater(s) : { ...s, ...updater };
        return next;
      })
    );
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, 50);
  }, []);

  const appendMessage = useCallback(
    (sessionId, role, text, meta = undefined) => {
      const id = nowId("m");
      updateSession(sessionId, (s) => ({
        ...s,
        messages: [...(s.messages || []), { id, role, text, ...(meta ? { meta } : {}) }]
      }));
      scrollToBottom();
      return id;
    },
    [scrollToBottom, updateSession]
  );

  const replaceMessage = useCallback(
    (sessionId, msgId, nextText) => {
      updateSession(sessionId, (s) => ({
        ...s,
        messages: (s.messages || []).map((m) => (m.id === msgId ? { ...m, text: nextText } : m))
      }));
    },
    [updateSession]
  );

  const createNewSession = useCallback(() => {
    const newId = nowId("s");
    const session = {
      id: newId,
      createdAt: Date.now(),
      title: "New chat",
      subtitle: "No results yet",
      status: "idle",
      messages: [],
      docs: [],
      selectedDocId: null,
      coverUrl: ""
    };
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(newId);
    return newId;
  }, []);

  const hasValidActiveSession = useCallback(
    () => !!(activeSessionId && sessions.some((s) => s.id === activeSessionId)),
    [activeSessionId, sessions]
  );

  const addFiles = useCallback((incoming) => {
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
  }, []);

  const removeFile = useCallback((name) => setFiles((prev) => prev.filter((f) => f.name !== name)), []);
  const clearFiles = useCallback(() => setFiles([]), []);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: (accepted) => addFiles(accepted),
    noClick: true,
    noKeyboard: true,
    multiple: true
  });

  const startNewChat = useCallback(() => {
    setView("chat");
    setFiles([]);
    setPrompt("");
    setSidebarMobileOpen(false);
    setActiveSessionId(null);
    setTimeout(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = 0;
    }, 0);
  }, []);

  const ensureSessionForSend = useCallback(() => {
    if (hasValidActiveSession()) return activeSessionId;
    return createNewSession();
  }, [activeSessionId, createNewSession, hasValidActiveSession]);

  const canRun = files.length > 0 && !loading;

  const run = useCallback(async () => {
    if (!canRun) {
      if (!files.length) showToast("Attach at least 1 file.", "error");
      return;
    }

    const sid = ensureSessionForSend();

    const rawPrompt = (prompt || "").trim();
    const filesToSend = files.slice();
    const fileNames = filesToSend.map((f) => f.name);
    const promptToSend = rawPrompt || "Process the attached document(s).";

    setPrompt("");
    setFiles([]);

    appendMessage(sid, "user", rawPrompt || "(attached files)", { files: fileNames });

    const pendingId = appendMessage(sid, "assistant", "Processing…");
    updateSession(sid, { status: "working", subtitle: "Processing…" });
    setLoading(true);

    const formData = new FormData();
    filesToSend.forEach((f) => formData.append("files", f));
    formData.append("prompt", promptToSend);

    try {
      const res = await fetch(`${API_BASE}/run-agent`, { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || res.statusText || "Server error");
      }

      const data = await res.json();
      const created = Array.isArray(data) ? data : [];
      const firstOk = created.find((d) => d && d.doc_id);

      const summary = created
        .slice(0, 6)
        .map((d) => {
          const name = d?.filename ? ` (${d.filename})` : "";
          return `• ${d.doc_id}${name} — ${d.status || "showing"}`;
        })
        .join("\n");

      replaceMessage(
        sid,
        pendingId,
        created.length
          ? `Done.\n\nCreated documents:\n${summary}\n\nOpen Workspace to review the preview, JSON, and rows.`
          : "Done, but no documents were returned."
      );

      updateSession(sid, (s) => {
        const docs = [...(created || []), ...(s.docs || [])];
        const coverUrl = firstOk?.preview_url || s.coverUrl || "";
        const title = firstOk?.filename ? firstOk.filename : s.title || "Chat";
        const subtitle = created.length ? `${created.length} document(s) processed` : s.subtitle || "No results yet";
        const status = (firstOk?.status || s.status || "idle").toLowerCase();
        const selectedDocIdNext = firstOk?.doc_id ? firstOk.doc_id : s.selectedDocId;
        return { ...s, docs, coverUrl, title, subtitle, status, selectedDocId: selectedDocIdNext };
      });

      if (firstOk?.doc_id) setView("workspace");
      showToast("Run complete.", "success");
    } catch (e) {
      replaceMessage(sid, pendingId, `Error: ${e.message}`);
      updateSession(sid, { status: "error", subtitle: "Error" });
      setView("chat");
      showToast(`Error: ${e.message}`, "error");
    } finally {
      setLoading(false);
    }
  }, [appendMessage, canRun, ensureSessionForSend, files, prompt, replaceMessage, showToast, updateSession]);

  const onDeleted = useCallback(
    (docId) => {
      if (!activeSessionId) return;

      updateSession(activeSessionId, (s) => {
        const nextDocs = (s.docs || []).filter((d) => d.doc_id !== docId);
        const nextSelected = s.selectedDocId === docId ? nextDocs[0]?.doc_id || null : s.selectedDocId;
        const coverUrl = nextDocs[0]?.preview_url || "";
        const subtitle = nextDocs.length ? `${nextDocs.length} document(s) processed` : "No results yet";
        const status = nextDocs[0]?.status || (nextDocs.length ? s.status : "idle");
        return { ...s, docs: nextDocs, selectedDocId: nextSelected, coverUrl, subtitle, status };
      });

      setView((v) => (v === "workspace" ? "chat" : v));
      showToast("Document removed from session.", "success");
    },
    [activeSessionId, showToast, updateSession]
  );

  // ---- Sidebar resize
  const startResize = useCallback(
    (e) => {
      if (!sidebarExpanded) return;
      e.preventDefault();
      e.stopPropagation();
      setIsResizing(true);
    },
    [sidebarExpanded]
  );

  useEffect(() => {
    if (!isResizing) return;

    const onMove = (e) => {
      const x = e.clientX;
      const next = Math.max(minSidebarWidth, Math.min(maxSidebarWidth, x));
      setSidebarWidth(next);
    };

    const onUp = () => setIsResizing(false);

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isResizing]);

  const expandSidebar = useCallback(() => {
    setSidebarExpanded(true);
    if (sidebarWidth < minSidebarWidth) setSidebarWidth(defaultSidebarWidth);
  }, [sidebarWidth]);

  const collapseSidebar = useCallback(() => {
    setSidebarExpanded(false);
    setIsResizing(false);
  }, []);

  // ---- Chat (⋮) menu handlers
  const openChatMenu = useCallback((e, sessionId) => {
    setChatMenu({ anchorEl: e.currentTarget, sessionId });
  }, []);

  const closeChatMenu = useCallback(() => {
    setChatMenu({ anchorEl: null, sessionId: null });
  }, []);

  const deleteSession = useCallback(
    (sessionId) => {
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));

      // If deleting the active one, clear selection and go back to chat
      setActiveSessionId((prevActive) => {
        if (prevActive === sessionId) return null;
        return prevActive;
      });

      setView("chat");
      showToast("Chat deleted.", "success");
    },
    [showToast]
  );

  const SidebarExpanded = (
    <Box
      sx={{
        width: sidebarWidth,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        ...railGlass,
        position: "relative",
        transition: "width 240ms cubic-bezier(0.2, 0.8, 0.2, 1)"
      }}
    >
      <Box sx={{ p: 1.6, transition: "opacity 180ms ease, transform 220ms ease", opacity: 1, transform: "translateX(0)" }}>
        <Stack direction="row" spacing={1.2} alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.2} alignItems="center" sx={{ minWidth: 0 }}>
            <LogoAvatar size={40} />
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 950, fontSize: 13.8, lineHeight: 1.1 }} noWrap>
                Blood Agent
              </Typography>
              <Typography sx={{ fontSize: 11.8, color: "rgba(237,242,250,0.62)" }} noWrap>
                OCR → Anonymize → JSON → LOINC
              </Typography>
            </Box>
          </Stack>

          <Tooltip title="Collapse">
            <IconButton
              onClick={collapseSidebar}
              sx={{
                color: "rgba(237,242,250,0.78)",
                bgcolor: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(148,163,184,0.14)",
                borderRadius: 3
              }}
            >
              <ChevronLeftRoundedIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        <Button
          fullWidth
          variant="contained"
          onClick={startNewChat}
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
          New chat
        </Button>

        <TextField
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search chats..."
          fullWidth
          sx={{
            mt: 1.2,
            "& .MuiOutlinedInput-root": {
              borderRadius: 3,
              bgcolor: "rgba(2, 6, 23, 0.42)",
              "& fieldset": { borderColor: "rgba(148,163,184,0.20)" },
              "&:hover fieldset": { borderColor: "rgba(148,163,184,0.32)" },
              "&.Mui-focused fieldset": { borderColor: "rgba(124,92,255,0.60)" }
            }
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRoundedIcon sx={{ color: "rgba(237,242,250,0.55)" }} />
              </InputAdornment>
            )
          }}
        />
      </Box>

      <Divider sx={{ borderColor: "rgba(148,163,184,0.14)" }} />

      <Box sx={{ p: 1.4, flex: 1, overflow: "auto" }}>
        <Chip
          size="small"
          label={`${sessions.length} chats`}
          sx={{
            mb: 1.2,
            bgcolor: "rgba(255,255,255,0.05)",
            color: "rgba(237,242,250,0.82)",
            border: "1px solid rgba(148,163,184,0.14)",
            fontWeight: 950,
            height: 24
          }}
        />

        {displayedSessions.length === 0 ? (
          <Paper sx={{ ...glass, p: 2.1, borderRadius: 2 }}>
            <Typography sx={{ fontWeight: 950, fontSize: 13.5 }}>No chats yet</Typography>
            <Typography sx={{ mt: 0.7, fontSize: 12.5, color: "rgba(237,242,250,0.62)" }}>
              Chats appear after you send your first message.
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={1.1}>
            {displayedSessions.map((s) => (
              <SessionCard
                key={s.id}
                s={s}
                active={s.id === activeSessionId}
                onOpenMenu={openChatMenu}
                onClick={() => {
                  setActiveSessionId(s.id);
                  setView("chat");
                  setSidebarMobileOpen(false);
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

      <Box
        onMouseDown={startResize}
        sx={{
          position: "absolute",
          top: 0,
          right: 0,
          width: 10,
          height: "100%",
          cursor: "col-resize",
          zIndex: 20,
          opacity: isResizing ? 1 : 0,
          transition: "opacity 160ms ease",
          "&:hover": { opacity: 1 },
          "&::before": {
            content: '""',
            position: "absolute",
            top: 8,
            bottom: 8,
            right: 3,
            width: 2,
            borderRadius: 99,
            background: "rgba(124,92,255,0.45)",
            boxShadow: "0 0 0 1px rgba(124,92,255,0.18)"
          }
        }}
      />

      {/* Chat menu (⋮) */}
      <Menu
        anchorEl={chatMenu.anchorEl}
        open={chatMenuOpen}
        onClose={closeChatMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        PaperProps={{
          sx: {
            ...glass,
            borderRadius: 2,
            p: 0.4,
            minWidth: 180
          }
        }}
      >
        <MenuItem
          onClick={() => {
            const sid = chatMenu.sessionId;
            closeChatMenu();
            if (sid) deleteSession(sid);
          }}
          sx={{
            borderRadius: 1.5,
            "&:hover": { bgcolor: "rgba(239,68,68,0.10)" }
          }}
        >
          <ListItemIcon>
            <DeleteOutlineRoundedIcon fontSize="small" sx={{ color: "rgba(239,68,68,0.92)" }} />
          </ListItemIcon>
          <ListItemText
            primary="Delete chat"
            primaryTypographyProps={{ fontWeight: 950, sx: { color: "rgba(237,242,250,0.92)" } }}
          />
        </MenuItem>
      </Menu>
    </Box>
  );

  const SidebarRail = (
    <Box
      sx={{
        width: railWidth,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 1.2,
        gap: 1.2,
        position: "relative",
        ...railGlass
      }}
    >
      <Box
        sx={{
          width: 52,
          height: 52,
          borderRadius: 999,
          position: "relative",
          display: "grid",
          placeItems: "center",
          overflow: "hidden",
          "&:hover .logoLayer": { opacity: 0 },
          "&:hover .arrowLayer": { opacity: 1 }
        }}
      >
        <Box
          className="logoLayer"
          sx={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeItems: "center",
            opacity: 1,
            transition: "opacity 160ms ease",
            pointerEvents: "none"
          }}
        >
          <LogoAvatar size={44} />
        </Box>

        <Box
          className="arrowLayer"
          sx={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeItems: "center",
            opacity: 0,
            transition: "opacity 160ms ease",
            pointerEvents: "auto"
          }}
        >
          <IconButton
            onClick={expandSidebar}
            sx={{
              color: "rgba(237,242,250,0.88)",
              bgcolor: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(148,163,184,0.14)",
              "&:hover": { bgcolor: "rgba(255,255,255,0.10)" }
            }}
          >
            <ChevronRightRoundedIcon />
          </IconButton>
        </Box>

        <Box
          sx={{
            position: "absolute",
            inset: 0,
            borderRadius: 999,
            border: "1px solid rgba(124,92,255,0.20)",
            boxShadow: "0 18px 55px rgba(124,92,255,0.10)",
            pointerEvents: "none"
          }}
        />
      </Box>

      <Box sx={{ mt: 0.4, display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
        <Tooltip title="New chat">
          <IconButton
            onClick={startNewChat}
            sx={{
              width: 44,
              height: 44,
              color: "rgba(237,242,250,0.86)",
              bgcolor: "rgba(124,92,255,0.10)",
              border: "1px solid rgba(124,92,255,0.24)",
              "&:hover": { bgcolor: "rgba(124,92,255,0.14)" }
            }}
          >
            <AddRoundedIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title="Search chats">
          <IconButton
            onClick={expandSidebar}
            sx={{
              width: 44,
              height: 44,
              color: "rgba(237,242,250,0.86)",
              bgcolor: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(148,163,184,0.14)",
              "&:hover": { bgcolor: "rgba(255,255,255,0.08)" }
            }}
          >
            <SearchRoundedIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Box sx={{ flex: 1 }} />

      <Tooltip title="Profile">
        <IconButton
          sx={{
            width: 44,
            height: 44,
            color: "rgba(237,242,250,0.86)",
            bgcolor: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(148,163,184,0.14)",
            "&:hover": { bgcolor: "rgba(255,255,255,0.08)" }
          }}
        >
          <PersonRoundedIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );

  const sidebarContainerWidth = sidebarExpanded ? sidebarWidth : railWidth;

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
        <Box
          sx={{
            display: { xs: "none", md: "block" },
            width: sidebarContainerWidth,
            transition: "width 240ms cubic-bezier(0.2, 0.8, 0.2, 1)"
          }}
        >
          <Box sx={{ width: "100%", height: "100%", position: "relative" }}>
            <Box
              sx={{
                position: "absolute",
                inset: 0,
                opacity: sidebarExpanded ? 1 : 0,
                transform: sidebarExpanded ? "translateX(0)" : "translateX(-8px)",
                transition: "opacity 180ms ease, transform 240ms cubic-bezier(0.2, 0.8, 0.2, 1)",
                pointerEvents: sidebarExpanded ? "auto" : "none",
                visibility: sidebarExpanded ? "visible" : "hidden"
              }}
            >
              {SidebarExpanded}
            </Box>

            <Box
              sx={{
                position: "absolute",
                inset: 0,
                opacity: sidebarExpanded ? 0 : 1,
                transition: "opacity 180ms ease",
                pointerEvents: sidebarExpanded ? "none" : "auto"
              }}
            >
              {SidebarRail}
            </Box>
          </Box>
        </Box>

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
                onClick={() => setSidebarMobileOpen(true)}
                sx={{
                  display: { xs: "inline-flex", md: "none" },
                  color: "rgba(237,242,250,0.78)",
                  bgcolor: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(148,163,184,0.14)",
                  borderRadius: 3
                }}
              >
                <ChevronRightRoundedIcon />
              </IconButton>

              <Typography sx={{ fontWeight: 950, fontSize: 14.8 }}>{view === "chat" ? "Chat" : "Workspace"}</Typography>
            </Stack>

            <StatusPill loading={loading} />
          </Box>

          <Box sx={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <Box sx={{ px: { xs: 1.2, md: 2.6 }, pt: 1.6 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Button
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

            {view === "chat" ? (
              <>
                <Box ref={scrollRef} sx={{ flex: 1, overflow: "auto", px: { xs: 1.2, md: 2.6 }, py: 2.2 }}>
                  <Stack spacing={1.6}>
                    {messages.map((m) => (
                      <Bubble key={m.id} role={m.role}>
                        <Typography sx={{ fontSize: 13.4, lineHeight: 1.52, color: "rgba(237,242,250,0.92)" }}>
                          {m.text}
                        </Typography>
                        {m.role === "user" && Array.isArray(m?.meta?.files) ? <FileRow names={m.meta.files} /> : null}
                      </Bubble>
                    ))}
                  </Stack>
                </Box>

                <Box
                  {...getRootProps()}
                  sx={{
                    px: { xs: 1.2, md: 2.6 },
                    pt: 1.4,
                    pb: "calc(18px + env(safe-area-inset-bottom))",
                    borderTop: "1px solid rgba(148,163,184,0.14)",
                    bgcolor: "rgba(9, 12, 22, 0.62)",
                    backdropFilter: "blur(16px)",
                    overflow: "visible"
                  }}
                >
                  <input {...getInputProps()} />

                  <Paper
                    sx={{
                      ...glass,
                      width: "100%",
                      borderRadius: 2,
                      p: { xs: 1.2, md: 1.4 },
                      overflow: "visible",
                      boxShadow: "0 18px 70px rgba(0,0,0,0.45)",
                      border: "1px solid rgba(148,163,184,0.18)",
                      outline: isDragActive ? "1px dashed rgba(124,92,255,0.75)" : "none",
                      position: "relative"
                    }}
                  >
                    <Stack spacing={1.0}>
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
                        maxRows={6}
                        placeholder="Write something…"
                        fullWidth
                        sx={{
                          "& .MuiOutlinedInput-root": {
                            borderRadius: 2,
                            bgcolor: "rgba(255,255,255,0.02)",
                            alignItems: "flex-start",
                            "& fieldset": { borderColor: "rgba(148,163,184,0.14)" },
                            "&:hover fieldset": { borderColor: "rgba(148,163,184,0.24)" },
                            "&.Mui-focused fieldset": { borderColor: "rgba(124,92,255,0.55)" }
                          },
                          "& textarea": {
                            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                            fontSize: 13.0,
                            lineHeight: 1.52,
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
                            label={files.length ? `${files.length} file(s) attached` : "0 files attached"}
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
                              borderRadius: 999,
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
                            sx={{
                              color: "rgba(237,242,250,0.62)",
                              fontWeight: 950,
                              borderRadius: 999
                            }}
                          >
                            Clear
                          </Button>

                          <Button
                            variant="contained"
                            onClick={run}
                            disabled={!canRun}
                            endIcon={loading ? <CircularProgress size={16} sx={{ color: "white" }} /> : <SendRoundedIcon />}
                            sx={{
                              borderRadius: 999,
                              px: 2.2,
                              fontWeight: 950,
                              backgroundImage: "linear-gradient(135deg, rgba(124,92,255,0.98), rgba(124,92,255,0.60))",
                              border: "1px solid rgba(124,92,255,0.55)",
                              boxShadow: "0 18px 70px rgba(124,92,255,0.16)"
                            }}
                          >
                            {loading ? "Running…" : "Run"}
                          </Button>
                        </Stack>
                      </Stack>
                    </Stack>
                  </Paper>
                </Box>
              </>
            ) : (
              <Box sx={{ flex: 1, overflow: "auto", p: { xs: 1.2, md: 2.6 } }}>
                {selectedDoc ? (
                  <Paper sx={{ ...glass, borderRadius: 2, p: { xs: 1.2, md: 1.6 } }}>
                    <DocumentCard doc={selectedDoc} apiBase={API_BASE} onDeleted={onDeleted} onToast={showToast} />
                  </Paper>
                ) : (
                  <Paper sx={{ ...glass, borderRadius: 4, p: 2.2 }}>
                    <Typography sx={{ fontWeight: 950, fontSize: 14.5 }}>No document selected</Typography>
                    <Typography sx={{ mt: 0.8, color: "rgba(237,242,250,0.62)" }}>
                      Run the agent to create results, then open Workspace.
                    </Typography>
                  </Paper>
                )}
              </Box>
            )}
          </Box>
        </Box>

        <Drawer
          anchor="left"
          open={sidebarMobileOpen}
          onClose={() => setSidebarMobileOpen(false)}
          sx={{ display: { xs: "block", md: "none" } }}
          PaperProps={{
            sx: { width: Math.min(380, sidebarWidth), bgcolor: "rgba(9, 12, 22, 0.90)", backdropFilter: "blur(16px)" }
          }}
        >
          <Box sx={{ width: "100%", height: "100%" }}>{SidebarExpanded}</Box>
        </Drawer>

        <Toast
          open={toast.open}
          message={toast.message}
          type={toast.type}
          onClose={() => setToast((t) => ({ ...t, open: false }))}
        />
      </Box>
    </ThemeProvider>
  );
}
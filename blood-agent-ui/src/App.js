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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
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
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import DeleteRoundedIcon from "@mui/icons-material/DeleteRounded";
import PushPinRoundedIcon from "@mui/icons-material/PushPinRounded";

import { useDropzone } from "react-dropzone";
import DocumentCard from "./components/DocumentCard";

const API_BASE = (process.env.REACT_APP_API_URL || "http://localhost:8000").replace(/\/$/, "");
const DEMO_MODE = process.env.REACT_APP_DEMO_MODE === "true";
const MAX_FILES = 5;
const STORAGE_KEY = "blood_agent_sessions_v1";

function loadPersistedSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { sessions: [], activeSessionId: null };

    const parsed = JSON.parse(raw);
    const sessions = Array.isArray(parsed?.sessions) ? parsed.sessions : [];
    const activeSessionId = typeof parsed?.activeSessionId === "string" ? parsed.activeSessionId : null;

    const normalizedSessions = sessions.map((s) => {
      const pinned = !!s?.pinned;
      const pinnedAt = typeof s?.pinnedAt === "number" ? s.pinnedAt : null;
      return { ...s, pinned, pinnedAt };
    });

    const validActive =
      activeSessionId && normalizedSessions.some((s) => s?.id === activeSessionId) ? activeSessionId : null;

    return { sessions: normalizedSessions, activeSessionId: validActive };
  } catch {
    return { sessions: [], activeSessionId: null };
  }
}

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

function baseName(filename = "") {
  const clean = (filename || "").trim();
  if (!clean) return "Document";
  const lastSlash = Math.max(clean.lastIndexOf("/"), clean.lastIndexOf("\\"));
  const justName = lastSlash >= 0 ? clean.slice(lastSlash + 1) : clean;
  const dot = justName.lastIndexOf(".");
  return dot > 0 ? justName.slice(0, dot) : justName;
}

function smartSessionTitle(fileNames = [], maxLen = 42) {
  if (!fileNames.length) return "New chat";
  const clamp = (t) => (t.length > maxLen ? t.slice(0, maxLen - 1) + "…" : t);

  const first = baseName(fileNames[0] || "");
  if (fileNames.length === 1) return clamp(first);

  const plus = fileNames.length - 1;
  return clamp(`${first} +${plus} file${plus === 1 ? "" : "s"}`);
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
  return <Chip size="small" label={label} sx={{ bgcolor: bg, color: fg, border: `1px solid ${br}`, fontWeight: 950 }} />;
}

function FileRow({ names = [] }) {
  if (!names.length) return null;
  return (
    <Stack spacing={0.7} sx={{ mt: 1.0 }}>
      {names.map((n) => (
        <Box
          key={n}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            px: 1.1,
            py: 0.75,
            borderRadius: 2,
            bgcolor: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(148,163,184,0.14)",
            maxWidth: 560
          }}
        >
          <UploadFileRoundedIcon sx={{ fontSize: 18, color: "rgba(237,242,250,0.72)" }} />
          <Typography
            sx={{
              fontSize: 12.2,
              fontWeight: 900,
              color: "rgba(237,242,250,0.84)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}
            title={n}
          >
            {n}
          </Typography>
        </Box>
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
          <PersonRoundedIcon sx={{ fontSize: 18, color: "rgba(237,242,250,0.85)" }} />
        </Avatar>
      )}
    </Box>
  );
}

function SessionCard({ s, active, onClick, onRename, onDelete, onTogglePin }) {
  const title = s?.title || "Chat";
  const subtitle = s?.subtitle || "No results yet";
  const docCount = (Array.isArray(s?.docs) ? s.docs.length : 0) + (s?.queuedDocs || 0);
  const pinned = !!s?.pinned;

  const [menuAnchor, setMenuAnchor] = useState(null);
  const menuOpen = Boolean(menuAnchor);

  const openMenu = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  };

  const closeMenu = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setMenuAnchor(null);
  };

  const handleRename = (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeMenu(e);
    onRename?.(s);
  };

  const handleTogglePin = (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeMenu(e);
    onTogglePin?.(s);
  };

  const handleDelete = (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeMenu(e);
    onDelete?.(s);
  };

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
            overflow: "hidden",
            flex: "0 0 auto"
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

        <Stack direction="row" spacing={0.8} alignItems="center" sx={{ flex: "0 0 auto" }}>
          <Chip
            size="small"
            label={`${docCount} file(s)`}
            sx={{
              height: 22,
              fontWeight: 950,
              bgcolor: "rgba(255,255,255,0.05)",
              color: "rgba(237,242,250,0.82)",
              border: "1px solid rgba(148,163,184,0.14)"
            }}
          />

          <IconButton
            onClick={openMenu}
            sx={{
              width: 34,
              height: 34,
              color: "rgba(237,242,250,0.78)",
              bgcolor: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(148,163,184,0.14)",
              borderRadius: 2.5,
              "&:hover": { bgcolor: "rgba(255,255,255,0.08)" }
            }}
          >
            <MoreVertRoundedIcon fontSize="small" />
          </IconButton>

          <Menu
            anchorEl={menuAnchor}
            open={menuOpen}
            onClose={closeMenu}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
            PaperProps={{
              sx: {
                ...glass,
                minWidth: 160,
                borderRadius: 1.5,
                p: 0.25,
                background: "rgba(10, 14, 28, 0.92)",
                border: "1px solid rgba(148,163,184,0.16)",
                boxShadow: "0 18px 55px rgba(0,0,0,0.60)",
                backdropFilter: "blur(16px)"
              }
            }}
          >
            <MenuItem
              onClick={handleTogglePin}
              sx={{
                borderRadius: 1.5,
                px: 1.0,
                py: 0.6,
                fontWeight: 900,
                fontSize: 12.5,
                minHeight: 34,
                "&:hover": { bgcolor: "rgba(255,255,255,0.06)" }
              }}
            >
              <ListItemIcon sx={{ minWidth: 30, color: "rgba(237,242,250,0.70)" }}>
                <PushPinRoundedIcon fontSize="small" />
              </ListItemIcon>
              {pinned ? "Unpin" : "Pin"}
            </MenuItem>

            <MenuItem
              onClick={handleRename}
              sx={{
                borderRadius: 1.5,
                px: 1.0,
                py: 0.6,
                fontWeight: 900,
                fontSize: 12.5,
                minHeight: 34,
                "&:hover": { bgcolor: "rgba(255,255,255,0.06)" }
              }}
            >
              <ListItemIcon sx={{ minWidth: 30, color: "rgba(237,242,250,0.70)" }}>
                <EditRoundedIcon fontSize="small" />
              </ListItemIcon>
              Rename
            </MenuItem>

            <MenuItem
              onClick={handleDelete}
              sx={{
                borderRadius: 1.5,
                px: 1.0,
                py: 0.6,
                fontWeight: 900,
                fontSize: 12.5,
                minHeight: 34,
                color: "rgba(239,68,68,0.95)",
                "&:hover": { bgcolor: "rgba(239,68,68,0.10)" }
              }}
            >
              <ListItemIcon sx={{ minWidth: 30, color: "rgba(239,68,68,0.95)" }}>
                <DeleteRoundedIcon fontSize="small" />
              </ListItemIcon>
              Delete
            </MenuItem>
          </Menu>
        </Stack>
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
    <Box sx={{ position: "fixed", right: 18, bottom: 18, zIndex: 2000 }}>
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

function makeDemoDocs(fileNames = []) {
  const names = fileNames.length ? fileNames : ["demo-blood-test.pdf"];

  return names.map((filename, index) => ({
    doc_id: `demo_doc_${Date.now()}_${index + 1}`,
    filename,
    status: "ready",
    preview_url: "",
    json_url: "",
    rows_url: "",
    mode: "demo",
    summary:
      "Demo result generated from anonymized sample data. No real medical document was uploaded or processed.",
    extracted_text:
      "Patient: [ANONYMIZED]\nHemoglobin: 14.2 g/dL\nWhite blood cells: 6.1 x10^9/L\nGlucose: 92 mg/dL\nPlatelets: 245 x10^9/L",
    structured_json: {
      patient: "[ANONYMIZED]",
      disclaimer: "Demo output only. Not for medical diagnosis or clinical use.",
      observations: [
        {
          test_name: "Hemoglobin",
          value: 14.2,
          unit: "g/dL",
          loinc: "718-7",
          interpretation: "within typical adult reference range"
        },
        {
          test_name: "White blood cells",
          value: 6.1,
          unit: "10^9/L",
          loinc: "6690-2",
          interpretation: "within typical adult reference range"
        },
        {
          test_name: "Glucose",
          value: 92,
          unit: "mg/dL",
          loinc: "2345-7",
          interpretation: "within typical fasting reference range"
        },
        {
          test_name: "Platelets",
          value: 245,
          unit: "10^9/L",
          loinc: "777-3",
          interpretation: "within typical adult reference range"
        }
      ]
    }
  }));
}

function DemoDocumentCard({ doc }) {
  const observations = doc?.structured_json?.observations || [];

  return (
    <Stack spacing={2}>
      <Box>
        <Typography sx={{ fontWeight: 950, fontSize: 16 }}>
          Demo blood analysis result
        </Typography>

        <Typography sx={{ mt: 0.6, color: "rgba(237,242,250,0.62)", fontSize: 13 }}>
          {doc?.filename || "demo-blood-test.pdf"}
        </Typography>

        <Chip
          size="small"
          label="Safe demo data"
          sx={{
            mt: 1,
            bgcolor: "rgba(124,92,255,0.14)",
            color: "rgba(237,242,250,0.92)",
            border: "1px solid rgba(124,92,255,0.35)",
            fontWeight: 950
          }}
        />
      </Box>

      <Paper
        sx={{
          p: 1.6,
          borderRadius: 2,
          bgcolor: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(148,163,184,0.14)"
        }}
      >
        <Typography sx={{ fontWeight: 950, mb: 1 }}>Extracted text</Typography>
        <Typography
          component="pre"
          sx={{
            m: 0,
            whiteSpace: "pre-wrap",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 12.5,
            color: "rgba(237,242,250,0.82)"
          }}
        >
          {doc?.extracted_text}
        </Typography>
      </Paper>

      <Paper
        sx={{
          p: 1.6,
          borderRadius: 2,
          bgcolor: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(148,163,184,0.14)"
        }}
      >
        <Typography sx={{ fontWeight: 950, mb: 1 }}>Structured observations</Typography>

        <Stack spacing={1}>
          {observations.map((item, index) => (
            <Box
              key={`${item.test_name}_${index}`}
              sx={{
                p: 1.2,
                borderRadius: 2,
                bgcolor: "rgba(2,6,23,0.38)",
                border: "1px solid rgba(148,163,184,0.12)"
              }}
            >
              <Typography sx={{ fontWeight: 950, fontSize: 13.5 }}>
                {item.test_name}
              </Typography>

              <Typography sx={{ mt: 0.5, fontSize: 13, color: "rgba(237,242,250,0.78)" }}>
                Value: {item.value} {item.unit}
              </Typography>

              <Typography sx={{ mt: 0.3, fontSize: 12.5, color: "rgba(237,242,250,0.58)" }}>
                LOINC: {item.loinc}
              </Typography>

              <Typography sx={{ mt: 0.3, fontSize: 12.5, color: "rgba(34,197,94,0.88)" }}>
                {item.interpretation}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Paper>

      <Paper
        sx={{
          p: 1.4,
          borderRadius: 2,
          bgcolor: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.20)"
        }}
      >
        <Typography sx={{ fontSize: 12.5, color: "rgba(237,242,250,0.78)" }}>
          Demo output only. Not for medical diagnosis or clinical use. Real OCR, MinIO storage,
          LLM extraction, and backend processing are disabled in this public demo.
        </Typography>
      </Paper>
    </Stack>
  );
}

export default function App() {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);

  const [renameOpen, setRenameOpen] = useState(false);
  const [renameSessionId, setRenameSessionId] = useState(null);
  const [renameValue, setRenameValue] = useState("");

  const [sessions, setSessions] = useState(() => loadPersistedSessions().sessions);
  const [activeSessionId, setActiveSessionId] = useState(() => loadPersistedSessions().activeSessionId);

  const [view, setView] = useState("chat");
  const [loading, setLoading] = useState(false);

  const [search, setSearch] = useState("");
  const [files, setFiles] = useState([]);
  const [prompt, setPrompt] = useState("");

  const [toast, setToast] = useState({ open: false, message: "", type: "info" });

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

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessions, activeSessionId }));
    } catch {}
  }, [sessions, activeSessionId]);

  const activeSession = useMemo(() => sessions.find((s) => s.id === activeSessionId) || null, [sessions, activeSessionId]);

  const displayedSessions = useMemo(() => {
    const q = (search || "").trim().toLowerCase();
    const filtered = !q
      ? sessions
      : sessions.filter((s) => `${s?.title || ""} ${s?.subtitle || ""}`.toLowerCase().includes(q));

    const pinnedSortKey = (s) => (typeof s?.pinnedAt === "number" ? s.pinnedAt : 0);
    const createdKey = (s) => (typeof s?.createdAt === "number" ? s.createdAt : 0);

    return [...filtered].sort((a, b) => {
      const ap = a?.pinned ? 1 : 0;
      const bp = b?.pinned ? 1 : 0;
      if (ap !== bp) return bp - ap;

      if (a?.pinned && b?.pinned) {
        const pa = pinnedSortKey(a);
        const pb = pinnedSortKey(b);
        if (pa !== pb) return pb - pa;
      }

      return createdKey(b) - createdKey(a);
    });
  }, [sessions, search]);

  const messages = useMemo(() => {
      const base = [
        {
          id: "m_welcome",
          role: "assistant",
          text: DEMO_MODE
            ? `Safe Demo Mode is enabled. Attach any sample PDF/image file to simulate the Blood Analysis Agent workflow. Real upload, OCR, MinIO storage, and AI processing are disabled in this public demo.`
            : `Attach up to ${MAX_FILES} PDF/image files to begin. Then write something and press Run (or Enter).`
        }
      ];
      if (!activeSession) return base;
      return Array.isArray(activeSession.messages) && activeSession.messages.length ? activeSession.messages : base;
 }, [activeSession]);

  const sessionDocs = useMemo(() => {
    const docs = activeSession?.docs;
    return Array.isArray(docs) ? docs : [];
  }, [activeSession]);

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
      queuedDocs: 0,
      coverUrl: "",
      userRenamed: false,
      pinned: false,
      pinnedAt: null
    };
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(newId);
    return newId;
  }, []);

  const hasValidActiveSession = useCallback(
    () => !!(activeSessionId && sessions.some((s) => s.id === activeSessionId)),
    [activeSessionId, sessions]
  );

  const addFiles = useCallback(
    (incoming) => {
      const arr = Array.from(incoming || []);
      if (!arr.length) return;

      setFiles((prev) => {
        const seen = new Set(prev.map((f) => `${f.name}_${f.size}`));
        const next = [...prev];

        for (const f of arr) {
          const k = `${f.name}_${f.size}`;
          if (seen.has(k)) continue;
          next.push(f);
          seen.add(k);
        }

        if (next.length > MAX_FILES) {
          const allowed = next.slice(0, MAX_FILES);
          showToast(`Maximum ${MAX_FILES} files allowed. Extra files were not added.`, "error");
          return allowed;
        }

        return next;
      });
    },
    [showToast]
  );

  const openRename = useCallback((session) => {
    if (!session?.id) return;
    setRenameSessionId(session.id);
    setRenameValue(session.title || "Chat");
    setRenameOpen(true);
  }, []);

  const closeRename = useCallback(() => {
    setRenameOpen(false);
    setRenameSessionId(null);
    setRenameValue("");
  }, []);

  const confirmRename = useCallback(() => {
    const nextTitle = (renameValue || "").trim();
    if (!renameSessionId) return closeRename();
    if (!nextTitle) return;

    setSessions((prev) =>
      prev.map((s) => (s.id === renameSessionId ? { ...s, title: nextTitle, userRenamed: true } : s))
    );
    closeRename();
  }, [closeRename, renameSessionId, renameValue]);

  const togglePin = useCallback((session) => {
    const sid = session?.id;
    if (!sid) return;

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sid) return s;
        const nextPinned = !s?.pinned;
        return { ...s, pinned: nextPinned, pinnedAt: nextPinned ? Date.now() : null };
      })
    );
  }, []);

  const deleteSession = useCallback(
    (session) => {
      const sid = session?.id;
      if (!sid) return;

      setSessions((prev) => {
        const remaining = prev.filter((s) => s.id !== sid);

        if (activeSessionId === sid) {
          const nextId = remaining[0]?.id || null;
          setActiveSessionId(nextId);

          if (!nextId) {
            setView("chat");
            setFiles([]);
            setPrompt("");
          }
        }

        return remaining;
      });
    },
    [activeSessionId]
  );

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
      if (!files.length) showToast(`Attach 1–${MAX_FILES} file(s) first.`, "error");
      return;
    }

    if (files.length > MAX_FILES) {
      showToast(`Maximum ${MAX_FILES} files allowed.`, "error");
      return;
    }

    const sid = ensureSessionForSend();

    const rawPrompt = (prompt || "").trim();
    const filesToSend = files.slice(0, MAX_FILES);
    const sentCount = filesToSend.length;

    const fileNames = filesToSend.map((f) => f.name);
    const autoTitle = smartSessionTitle(fileNames);

    const promptToSend = rawPrompt || "Process the attached file(s).";

    setPrompt("");
    setFiles([]);

    appendMessage(sid, "user", rawPrompt || "(attached files)", { files: fileNames });

    updateSession(sid, (s) => ({
      ...s,
      queuedDocs: (s.queuedDocs || 0) + sentCount,
      title: s.userRenamed ? s.title : autoTitle,
      subtitle: `Processing ${sentCount} file(s)…`,
      status: "working"
    }));

    const pendingId = appendMessage(sid, "assistant", "Processing…");
    setLoading(true);

    const formData = new FormData();
    filesToSend.forEach((f) => formData.append("files", f));
    formData.append("prompt", promptToSend);

    try {
      if (DEMO_MODE) {
        await new Promise((resolve) => setTimeout(resolve, 900));

        const okDocs = makeDemoDocs(fileNames);

        const summary = okDocs
          .map((d) => {
            const name = d?.filename ? ` (${d.filename})` : "";
            return `• ${d.doc_id}${name} — demo ready`;
          })
          .join("\n");

        replaceMessage(
          sid,
          pendingId,
            `Demo complete.

            Created demo documents:
            ${summary}
            
            This public demo uses anonymized sample data only. Real file upload, OCR, MinIO storage, and LLM processing are disabled for privacy and cost control.
            
            Open Workspace to review the demo result.`
        );

        updateSession(sid, (s) => {
          const nextQueued = Math.max(0, (s.queuedDocs || 0) - sentCount);
          const docs = [...okDocs, ...(s.docs || [])];

          return {
            ...s,
            docs,
            coverUrl: "",
            subtitle: `${docs.length} demo document(s) processed`,
            status: "demo",
            queuedDocs: nextQueued
          };
        });

        setView("workspace");
        showToast("Demo run complete.", "success");
        return;
      }

  const res = await fetch(`${API_BASE}/run-agent`, { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || res.statusText || "Server error");
      }

      const data = await res.json();
      const created = Array.isArray(data) ? data : [];
      const okDocs = created.filter((d) => d && d.doc_id);
      const failed = created.filter((d) => d && !d.doc_id);

      const summary = okDocs
        .slice(0, 8)
        .map((d) => {
          const name = d?.filename ? ` (${d.filename})` : "";
          return `• ${d.doc_id}${name} — ${d.status || "ready"}`;
        })
        .join("\n");

      const failedSummary = failed.length
        ? `\n\nFailed:\n${failed
            .slice(0, 6)
            .map((d, i) => `• File #${i + 1} — ${d?.status || "error"}`)
            .join("\n")}`
        : "";

      replaceMessage(
        sid,
        pendingId,
        okDocs.length
          ? `Done.\n\nCreated documents:\n${summary}${failedSummary}\n\nOpen Workspace to review previews, JSON, and rows.`
          : `Done, but no documents were returned.${failedSummary}`
      );

      updateSession(sid, (s) => {
        const nextQueued = Math.max(0, (s.queuedDocs || 0) - sentCount);
        const docs = [...okDocs, ...(s.docs || [])];
        const coverUrl = okDocs[0]?.preview_url || s.coverUrl || "";
        const subtitle = docs.length ? `${docs.length} document(s) processed` : "No results yet";
        const status = (okDocs[0]?.status || s.status || "idle").toLowerCase();

        return { ...s, docs, coverUrl, subtitle, status, queuedDocs: nextQueued };
      });

      if (okDocs.length) setView("workspace");
      showToast("Run complete.", "success");
    } catch (e) {
      replaceMessage(sid, pendingId, `Error: ${e.message}`);

      updateSession(sid, (s) => ({
        ...s,
        queuedDocs: Math.max(0, (s.queuedDocs || 0) - sentCount),
        status: "error",
        subtitle: "Error"
      }));

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
        const coverUrl = nextDocs[0]?.preview_url || "";
        const subtitle = nextDocs.length ? `${nextDocs.length} document(s) processed` : "No results yet";
        const status = nextDocs[0]?.status || (nextDocs.length ? s.status : "idle");
        return { ...s, docs: nextDocs, coverUrl, subtitle, status };
      });

      showToast("Document deleted.", "success");
    },
    [activeSessionId, showToast, updateSession]
  );

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
                onClick={() => {
                  setActiveSessionId(s.id);
                  setView("chat");
                  setSidebarMobileOpen(false);
                }}
                onRename={openRename}
                onDelete={deleteSession}
                onTogglePin={togglePin}
              />
            ))}
          </Stack>
        )}
      </Box>

      <Divider sx={{ borderColor: "rgba(148,163,184,0.14)" }} />

      <Box sx={{ p: 1.4 }}>
        <Typography sx={{ fontSize: 11.5, color: "rgba(237,242,250,0.55)" }}>{DEMO_MODE ? "Mode: Safe demo, no backend calls" : `API: ${API_BASE}`}</Typography>
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

                        <Stack direction="row" spacing={1} alignItems="center">
              {DEMO_MODE && (
                <Chip
                  size="small"
                  label="Safe Demo Mode"
                  sx={{
                    bgcolor: "rgba(124,92,255,0.14)",
                    color: "rgba(237,242,250,0.92)",
                    border: "1px solid rgba(124,92,255,0.35)",
                    fontWeight: 950
                  }}
                />
              )}
              <StatusPill loading={loading} />
            </Stack>
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
                  disabled={!sessionDocs.length}
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
                            label={`${files.length} file(s) attached`}
                            size="small"
                            sx={{
                              bgcolor: "rgba(255,255,255,0.05)",
                              color: "rgba(237,242,250,0.82)",
                              border: "1px solid rgba(148,163,184,0.14)",
                              fontWeight: 950
                            }}
                          />

                          {files.slice(0, MAX_FILES).map((f) => (
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
                        </Stack>

                        <Stack direction="row" spacing={1} alignItems="center" justifyContent="flex-end">
                          <Button
                            variant="outlined"
                            onClick={open}
                            startIcon={<UploadFileRoundedIcon />}
                            disabled={loading || files.length >= MAX_FILES}
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
                {sessionDocs.length ? (
                  <Stack spacing={2}>
                    {sessionDocs.map((d) => (
                      <Paper key={d.doc_id} sx={{ ...glass, borderRadius: 2, p: { xs: 1.2, md: 1.6 } }}>
                        {DEMO_MODE || d?.mode === "demo" ? (
                          <DemoDocumentCard doc={d} />
                        ) : (
                          <DocumentCard doc={d} apiBase={API_BASE} onDeleted={onDeleted} onToast={showToast} />
                        )}
                      </Paper>
                    ))}
                  </Stack>
                ) : (
                  <Paper sx={{ ...glass, borderRadius: 4, p: 2.2 }}>
                    <Typography sx={{ fontWeight: 950, fontSize: 14.5 }}>No documents yet</Typography>
                    <Typography sx={{ mt: 0.8, color: "rgba(237,242,250,0.62)" }}>
                      Run the agent (with up to {MAX_FILES} files) to create results, then open Workspace.
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
            sx: {
              width: Math.min(380, sidebarWidth),
              bgcolor: "rgba(9, 12, 22, 0.90)",
              backdropFilter: "blur(16px)"
            }
          }}
        >
          <Box sx={{ width: "100%", height: "100%" }}>{SidebarExpanded}</Box>
        </Drawer>

        <Dialog
          open={renameOpen}
          onClose={closeRename}
          PaperProps={{
            sx: {
              ...glass,
              borderRadius: 2,
              width: "min(520px, calc(100vw - 32px))"
            }
          }}
        >
          <DialogTitle sx={{ fontWeight: 950 }}>Rename chat</DialogTitle>
          <DialogContent sx={{ pt: 1.2 }}>
            <TextField
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              autoFocus
              fullWidth
              placeholder="Enter a chat name…"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  confirmRename();
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  closeRename();
                }
              }}
              sx={{
                mt: 0.5,
                "& .MuiOutlinedInput-root": {
                  borderRadius: 3,
                  bgcolor: "rgba(2, 6, 23, 0.42)",
                  "& fieldset": { borderColor: "rgba(148,163,184,0.20)" },
                  "&:hover fieldset": { borderColor: "rgba(148,163,184,0.32)" },
                  "&.Mui-focused fieldset": { borderColor: "rgba(124,92,255,0.60)" }
                }
              }}
            />
          </DialogContent>
          <DialogActions sx={{ px: 2.2, pb: 1.8 }}>
            <Button onClick={closeRename} variant="text" sx={{ borderRadius: 999, fontWeight: 950, color: "rgba(237,242,250,0.72)" }}>
              Cancel
            </Button>
            <Button
              onClick={confirmRename}
              variant="contained"
              sx={{
                borderRadius: 999,
                fontWeight: 950,
                backgroundImage: "linear-gradient(135deg, rgba(124,92,255,0.98), rgba(124,92,255,0.60))",
                border: "1px solid rgba(124,92,255,0.55)"
              }}
            >
              Save
            </Button>
          </DialogActions>
        </Dialog>

        <Toast open={toast.open} message={toast.message} type={toast.type} onClose={() => setToast((t) => ({ ...t, open: false }))} />
      </Box>
    </ThemeProvider>
  );
}
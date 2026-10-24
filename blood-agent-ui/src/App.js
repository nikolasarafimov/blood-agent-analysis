import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Avatar, Box, Button, Chip, CircularProgress, CssBaseline, Dialog,
  DialogActions, DialogContent, DialogTitle, Divider, Drawer, IconButton,
  InputAdornment, ListItemIcon, Menu, MenuItem, Paper, Stack, TextField,
  Tooltip, Typography
} from "@mui/material";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import ChatRoundedIcon from "@mui/icons-material/ChatRounded";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import DeleteRoundedIcon from "@mui/icons-material/DeleteRounded";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import GridViewRoundedIcon from "@mui/icons-material/GridViewRounded";
import MoreVertRoundedIcon from "@mui/icons-material/MoreVertRounded";
import PersonRoundedIcon from "@mui/icons-material/PersonRounded";
import PushPinRoundedIcon from "@mui/icons-material/PushPinRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import { useDropzone } from "react-dropzone";
import DocumentCard from "./components/DocumentCard";

const API_BASE = (process.env.REACT_APP_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const OCR_LANGUAGE = process.env.REACT_APP_OCR_LANGUAGE || "mkd+eng";
const MAX_FILES = 5;
const MAX_UPLOAD_MB = 20;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const STORAGE_KEY = "blood_agent_sessions_v1";
const PERSIST_SESSIONS = process.env.REACT_APP_PERSIST_SESSIONS === "true";
const ACCEPTED_EXTENSIONS = new Set([".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"]);
const border = "1px solid rgba(165,175,208,0.16)";
const subtle = "rgba(237,242,250,0.65)";

const glass = {
  bgcolor: "rgba(12,18,35,0.85)",
  border,
  boxShadow: "0 22px 70px rgba(0,0,0,0.32)",
  backdropFilter: "blur(16px)"
};

const theme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#070a14",
      paper: "#101729"
    },
    primary: {
      main: "#9375ff",
      contrastText: "#ffffff"
    },
    success: {
      main: "#35d99a"
    },
    error: {
      main: "#f87171"
    },
    text: {
      primary: "#eff3ff",
      secondary: "#a6b2d0"
    }
  },
  shape: {
    borderRadius: 16
  },
  typography: {
    fontFamily: 'Inter, "Segoe UI Variable", ui-sans-serif, system-ui, sans-serif',
    button: {
      textTransform: "none",
      fontWeight: 750
    }
  },
  components: {
    MuiButton: {
      defaultProps: {
        disableElevation: true
      },
      styleOverrides: {
        root: {
          transition: "transform 200ms ease, box-shadow 200ms ease, border-color 200ms ease"
        }
      }
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderColor: "rgba(165,175,208,0.16)"
        }
      }
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          transition: "background 200ms ease, box-shadow 200ms ease"
        }
      }
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          background: "#192137",
          border: "1px solid rgba(167,139,250,0.24)",
          borderRadius: 10,
          padding: "8px 11px"
        }
      }
    }
  }
});

const makeId = (prefix) =>
  `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;

function titleFromFiles(names) {
  if (!names.length) return "New chat";

  const first = names[0]
    .replace(/^.*[\\/]/, "")
    .replace(/\.[^.]+$/, "");

  const title = names.length === 1
    ? first
    : `${first} +${names.length - 1} files`;

  return title.length > 42
    ? `${title.slice(0, 41)}…`
    : title;
}

function loadSessions() {
  if (!PERSIST_SESSIONS) {
    return {
      sessions: [],
      activeSessionId: null
    };
  }

  try {
    const parsed = JSON.parse(
      sessionStorage.getItem(STORAGE_KEY) || "null"
    );

    const sessions = (
      Array.isArray(parsed?.sessions)
        ? parsed.sessions
        : []
    )
      .filter((s) => s && typeof s.id === "string")
      .slice(0, 100)
      .map((s) => {
        const interrupted =
          s.status === "working" ||
          Number(s.queuedDocs) > 0;

        return {
          ...s,
          pinned: Boolean(s.pinned),
          pinnedAt: typeof s.pinnedAt === "number"
            ? s.pinnedAt
            : null,
          docs: Array.isArray(s.docs) ? s.docs : [],
          queuedDocs: 0,
          status: interrupted ? "interrupted" : s.status,
          subtitle: interrupted
            ? "Previous upload was interrupted"
            : s.subtitle,
          messages: (
            Array.isArray(s.messages)
              ? s.messages
              : []
          ).map((m) =>
            interrupted &&
            m?.role === "assistant" &&
            m?.text === "Processing…"
              ? {
                  ...m,
                  text: "Upload interrupted by a page reload. Check the API before retrying."
                }
              : m
          )
        };
      });

    const activeSessionId = sessions.some(
      (s) => s.id === parsed?.activeSessionId
    )
      ? parsed.activeSessionId
      : null;

    return {
      sessions,
      activeSessionId
    };
  } catch {
    return {
      sessions: [],
      activeSessionId: null
    };
  }
}

function Logo({ size = 40 }) {
  return (
    <Avatar
      className="ba-logo"
      src="/logo.png"
      alt="Blood Agent"
      sx={{
        width: size,
        height: size,
        bgcolor: "#211a42",
        border: "1px solid rgba(165,135,255,0.4)"
      }}
    />
  );
}


function Status({ busy }) {
  return (
    <Box
      role="status"
      aria-live="polite"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 1.2,
        px: 1.8,
        py: 0.9,
        minHeight: 35,
        borderRadius: "999px",
        whiteSpace: "nowrap",
        flexShrink: 0,
        bgcolor: busy
          ? "rgba(147,117,255,0.12)"
          : "rgba(52,211,153,0.09)",
        border: busy
          ? "1px solid rgba(167,139,250,0.32)"
          : "1px solid rgba(52,211,153,0.26)",
        boxShadow: busy
          ? "0 0 20px rgba(147,117,255,0.10)"
          : "0 0 20px rgba(52,211,153,0.06)",
        transition: "all 250ms ease"
      }}
    >
      <Box
        sx={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          flexShrink: 0,
          bgcolor: busy ? "#B9A3FF" : "#49E6A9",
          boxShadow: busy
            ? "0 0 12px rgba(185,163,255,0.6)"
            : "0 0 12px rgba(73,230,169,0.5)",
          animation: busy
            ? "ba-beacon 1.8s ease-in-out infinite"
            : "none"
        }}
      />

      <Typography
        component="span"
        sx={{
          fontSize: 12.5,
          fontWeight: 750,
          letterSpacing: "0.025em",
          lineHeight: 1,
          color: busy ? "#D3C6FF" : "#A1F3CD"
        }}
      >
        {busy ? "Processing…" : "Ready"}
      </Typography>
    </Box>
  );
}

function FileList({ names }) {
  if (!Array.isArray(names) || !names.length) {
    return null;
  }

  return (
    <Stack spacing={0.7} sx={{ mt: 1.2 }}>
      {names.map((name, i) => (
        <Stack
          key={`${i}_${name}`}
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{
            px: 1.3,
            py: 0.8,
            borderRadius: 2,
            border,
            bgcolor: "rgba(255,255,255,.035)",
            maxWidth: 560
          }}
        >
          <DescriptionRoundedIcon
            sx={{
              fontSize: 18,
              color: "#b2a0ff"
            }}
          />
          <Typography
            noWrap
            title={name}
            sx={{ fontSize: 12.5 }}
          >
            {name}
          </Typography>
        </Stack>
      ))}
    </Stack>
  );
}

function Message({ entry }) {
  const user = entry.role === "user";

  return (
    <Stack
      className="ba-message"
      direction="row"
      spacing={1.25}
      justifyContent={
        user ? "flex-end" : "flex-start"
      }
      alignItems="flex-start"
    >
      {!user && <Logo size={32} />}

      <Paper
        className={
          user
            ? "ba-message-user"
            : "ba-message-agent"
        }
        sx={{
          ...glass,
          maxWidth: "min(960px, 85%)",
          minWidth: 0,
          px: 2.2,
          py: 1.6,
          borderRadius: 3,
          wordBreak: "break-word"
        }}
      >
        <Typography
          sx={{
            whiteSpace: "pre-wrap",
            lineHeight: 1.65,
            fontSize: 13.3
          }}
        >
          {entry.text}
        </Typography>

        {user && (
          <FileList names={entry.meta?.files} />
        )}
      </Paper>

      {user && (
        <Avatar
          sx={{
            width: 32,
            height: 32,
            bgcolor: "rgba(255,255,255,.06)",
            border
          }}
        >
          <PersonRoundedIcon
            sx={{ fontSize: 18 }}
          />
        </Avatar>
      )}
    </Stack>
  );
}

function SessionCard({
  session,
  active,
  onSelect,
  onRename,
  onDelete,
  onPin
}) {
  const [anchor, setAnchor] = useState(null);

  const close = (event) => {
    event?.stopPropagation?.();
    setAnchor(null);
  };

  const action = (handler) => (event) => {
    event.stopPropagation();
    setAnchor(null);
    handler(session);
  };

  const count =
    (session.docs?.length || 0) +
    (session.queuedDocs || 0);

  return (
    <Box
      className={
        active
          ? "ba-session-card is-active"
          : "ba-session-card"
      }
      role="button"
      tabIndex={0}
      aria-current={active ? "true" : undefined}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (
          e.target === e.currentTarget &&
          ["Enter", " "].includes(e.key)
        ) {
          e.preventDefault();
          onSelect();
        }
      }}
      sx={{
        borderRadius: 3,
        border: active
          ? "1px solid rgba(147,117,255,.6)"
          : border,
        bgcolor: active
          ? "rgba(147,117,255,.11)"
          : "rgba(255,255,255,.025)",
        p: 1.1,
        cursor: "pointer"
      }}
    >
      <Stack
        direction="row"
        spacing={1.15}
        alignItems="center"
      >
        <Box
          sx={{
            width: 43,
            height: 43,
            flexShrink: 0,
            overflow: "hidden",
            borderRadius: 2.5,
            border,
            bgcolor: "rgba(5,9,24,.7)",
            display: "grid",
            placeItems: "center"
          }}
        >
          {session.coverUrl ? (
            <Box
              component="img"
              alt=""
              src={session.coverUrl}
              sx={{
                height: "100%",
                width: "100%",
                objectFit: "cover"
              }}
            />
          ) : (
            <DescriptionRoundedIcon
              sx={{ color: "#bdaaff" }}
            />
          )}
        </Box>

        <Box
          sx={{
            flex: 1,
            minWidth: 0
          }}
        >
          <Typography
            noWrap
            sx={{
              fontSize: 12.8,
              fontWeight: 800
            }}
          >
            {session.title || "Chat"}
          </Typography>

          <Typography
            noWrap
            sx={{
              fontSize: 11.3,
              color: subtle
            }}
          >
            {session.subtitle || "No results yet"}
          </Typography>
        </Box>

        <Chip
          size="small"
          label={`${count} file(s)`}
          sx={{
            height: 23,
            fontSize: 10,
            bgcolor: "rgba(255,255,255,.05)",
            border
          }}
        />

        <IconButton
          aria-label="Chat actions"
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            setAnchor(e.currentTarget);
          }}
          sx={{
            bgcolor: "rgba(255,255,255,.05)",
            border,
            borderRadius: 2
          }}
        >
          <MoreVertRoundedIcon fontSize="small" />
        </IconButton>
      </Stack>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={close}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right"
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right"
        }}
        slotProps={{
          paper: {
            sx: {
              ...glass,
              borderRadius: 2,
              minWidth: 175,
              p: 0.5
            }
          }
        }}
      >
        <MenuItem
          onClick={action(onPin)}
          sx={{
            borderRadius: 1.5,
            fontSize: 13
          }}
        >
          <ListItemIcon>
            <PushPinRoundedIcon fontSize="small" />
          </ListItemIcon>
          {session.pinned ? "Unpin" : "Pin"}
        </MenuItem>

        <MenuItem
          onClick={action(onRename)}
          sx={{
            borderRadius: 1.5,
            fontSize: 13
          }}
        >
          <ListItemIcon>
            <EditRoundedIcon fontSize="small" />
          </ListItemIcon>
          Rename
        </MenuItem>

        <MenuItem
          onClick={action(onDelete)}
          sx={{
            borderRadius: 1.5,
            fontSize: 13,
            color: "#f58b98"
          }}
        >
          <ListItemIcon>
            <DeleteRoundedIcon
              fontSize="small"
              sx={{ color: "#f58b98" }}
            />
          </ListItemIcon>
          Remove chat
        </MenuItem>
      </Menu>
    </Box>
  );
}

function Notice({ data, onClose }) {
  if (!data.open) return null;

  return (
    <Box
      sx={{
        position: "fixed",
        right: 20,
        bottom: 20,
        zIndex: 2000,
        maxWidth: "min(430px,calc(100vw - 32px))"
      }}
    >
      <Paper
        className="ba-toast"
        role={
          data.type === "error"
            ? "alert"
            : "status"
        }
        onClick={onClose}
        sx={{
          ...glass,
          cursor: "pointer",
          p: 1.7,
          borderRadius: 3,
          borderColor:
            data.type === "error"
              ? "#bb5160"
              : data.type === "success"
                ? "#2c926d"
                : "#6955a5"
        }}
      >
        <Typography
          sx={{
            fontSize: 13,
            fontWeight: 750
          }}
        >
          {data.message}
        </Typography>
      </Paper>
    </Box>
  );
}

export default function App() {
  const [persisted] = useState(loadSessions);

  const [sessions, setSessions] = useState(persisted.sessions);
  const [activeSessionId, setActiveSessionId] = useState(persisted.activeSessionId);
  const [view, setView] = useState("chat");
  const [files, setFiles] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState({
    open: false,
    message: "",
    type: "info"
  });

  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(340);
  const [isResizing, setIsResizing] = useState(false);
  const [renameSessionId, setRenameSessionId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [removeChatId, setRemoveChatId] = useState(null);

  const scrollRef = useRef(null);
  const timeoutRef = useRef(null);
  const runRef = useRef(false);
  const activeIdRef = useRef(activeSessionId);

  const notify = useCallback((message, type = "info") => {
    setToast({
      open: true,
      message,
      type
    });

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(
      () =>
        setToast((t) => ({
          ...t,
          open: false
        })),
      3200
    );
  }, []);

  useEffect(() => {
    activeIdRef.current = activeSessionId;
  }, [activeSessionId]);

  useEffect(
    () => () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    },
    []
  );

  useEffect(() => {
    try {
      if (PERSIST_SESSIONS) {
        sessionStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            sessions,
            activeSessionId
          })
        );
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch {}
  }, [sessions, activeSessionId]);

  const activeSession = useMemo(
    () =>
      sessions.find(
        (s) => s.id === activeSessionId
      ) || null,
    [sessions, activeSessionId]
  );

  const sessionDocs = useMemo(
    () => activeSession?.docs || [],
    [activeSession]
  );

  const messages = useMemo(
    () =>
      activeSession?.messages?.length
        ? activeSession.messages
        : [],
    [activeSession]
  );

  const shownSessions = useMemo(() => {
    const q = search.trim().toLowerCase();

    return sessions
      .filter(
        (s) =>
          !q ||
          `${s.title || ""} ${s.subtitle || ""}`
            .toLowerCase()
            .includes(q)
      )
      .sort(
        (a, b) =>
          Number(Boolean(b.pinned)) -
            Number(Boolean(a.pinned)) ||
          (a.pinned
            ? (b.pinnedAt || 0) -
              (a.pinnedAt || 0)
            : 0) ||
          (b.createdAt || 0) -
            (a.createdAt || 0)
      );
  }, [sessions, search]);

  const updateSession = useCallback(
    (id, update) =>
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== id) return s;

          return typeof update === "function"
            ? update(s)
            : { ...s, ...update };
        })
      ),
    []
  );

  const newSession = useCallback(() => {
    const id = makeId("s");

    const session = {
      id,
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
    activeIdRef.current = id;
    setActiveSessionId(id);

    return id;
  }, []);

  const newChat = useCallback(() => {
    activeIdRef.current = null;
    setActiveSessionId(null);
    setView("chat");
    setFiles([]);
    setPrompt("");
    setSidebarMobileOpen(false);

    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, []);

  const appendMessage = useCallback(
    (sid, role, text, meta) => {
      const id = makeId("m");

      updateSession(sid, (s) => ({
        ...s,
        messages: [
          ...(s.messages || []),
          {
            id,
            role,
            text,
            ...(meta ? { meta } : {})
          }
        ]
      }));

      return id;
    },
    [updateSession]
  );

  const replaceMessage = useCallback(
    (sid, messageId, text) =>
      updateSession(sid, (s) => ({
        ...s,
        messages: (s.messages || []).map(
          (m) =>
            m.id === messageId
              ? { ...m, text }
              : m
        )
      })),
    [updateSession]
  );

  const addFiles = useCallback(
    (incoming) => {
      if (runRef.current) {
        return notify(
          "Finish the current upload before attaching more files.",
          "info"
        );
      }

      const received = Array.from(incoming || []);

      if (!received.length) return;

      const supported = received.filter((f) => {
        const ext =
          (f.name || "")
            .toLowerCase()
            .match(/\.[^.]+$/)?.[0] || "";

        return ACCEPTED_EXTENSIONS.has(ext);
      });

      if (supported.length !== received.length) {
        notify(
          "Only supported PDF/image formats are allowed.",
          "error"
        );
      }

      const nonempty = supported.filter(
        (f) => f.size > 0
      );

      if (nonempty.length !== supported.length) {
        notify(
          "Empty files cannot be attached.",
          "error"
        );
      }

      const valid = nonempty.filter(
        (f) => f.size <= MAX_UPLOAD_BYTES
      );

      if (valid.length !== nonempty.length) {
        notify(
          `Each file must be ${MAX_UPLOAD_MB} MiB or smaller.`,
          "error"
        );
      }

      setFiles((current) => {
        const next = [...current];

        const seen = new Set(
          next.map(
            (f) =>
              `${f.name}:${f.size}:${f.lastModified}`
          )
        );

        for (const f of valid) {
          const key =
            `${f.name}:${f.size}:${f.lastModified}`;

          if (!seen.has(key)) {
            next.push(f);
            seen.add(key);
          }
        }

        if (next.length > MAX_FILES) {
          notify(
            `Maximum ${MAX_FILES} files. Extra files were not added.`,
            "error"
          );
        }

        return next.slice(0, MAX_FILES);
      });
    },
    [notify]
  );

  const {
    getRootProps,
    getInputProps,
    isDragActive,
    open: openFilePicker
  } = useDropzone({
    onDrop: addFiles,
    onDropRejected: () =>
      notify(
        "One or more files could not be attached.",
        "error"
      ),
    noClick: true,
    noKeyboard: true,
    multiple: true,
    maxFiles: MAX_FILES,
    maxSize: MAX_UPLOAD_BYTES,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
        ".webp"
      ]
    }
  });

  const removeFile = (file) =>
    setFiles((current) =>
      current.filter(
        (f) =>
          !(
            f.name === file.name &&
            f.size === file.size &&
            f.lastModified === file.lastModified
          )
      )
    );

  const run = useCallback(async () => {
    if (runRef.current || loading) return;

    if (!files.length) {
      return notify(
        "Attach a PDF or image first.",
        "error"
      );
    }

    if (files.length > MAX_FILES) {
      return notify(
        `Maximum ${MAX_FILES} files allowed.`,
        "error"
      );
    }

    runRef.current = true;

    const sid =
      activeSessionId &&
      sessions.some(
        (s) => s.id === activeSessionId
      )
        ? activeSessionId
        : newSession();

    const selected = files.slice(0, MAX_FILES);
    const names = selected.map((f) => f.name);
    const count = selected.length;
    const note = prompt.trim();

    setFiles([]);
    setPrompt("");

    appendMessage(
      sid,
      "user",
      note || "(attached files)",
      { files: names }
    );

    updateSession(sid, (s) => ({
      ...s,
      queuedDocs: (s.queuedDocs || 0) + count,
      title: s.userRenamed
        ? s.title
        : titleFromFiles(names),
      subtitle: `Processing ${count} file(s)…`,
      status: "working"
    }));

    const pendingId = appendMessage(
      sid,
      "assistant",
      "Processing…"
    );

    setLoading(true);

    const body = new FormData();

    selected.forEach((f) =>
      body.append("files", f)
    );

    body.append("prompt", "Process these documents");
    body.append("language", OCR_LANGUAGE);

    try {
      const res = await fetch(
        `${API_BASE}/run-agent`,
        {
          method: "POST",
          body
        }
      );

      if (!res.ok) {
        const err = await res
          .json()
          .catch(() => ({}));

        const detail =
          typeof err?.detail === "string"
            ? err.detail
            : Array.isArray(err?.detail)
              ? err.detail
                  .map((e) => e?.msg)
                  .filter(Boolean)
                  .join("; ")
              : "";

        throw new Error(
          (
            detail ||
            res.statusText ||
            `HTTP ${res.status}`
          ).slice(0, 300)
        );
      }

      const response = await res.json();

      if (!Array.isArray(response)) {
        throw new Error(
          "Unexpected response format from the API."
        );
      }

      const returned = response.slice(0, count);

      const successful = returned.filter(
        (d) =>
          d?.success === true &&
          d?.doc_id
      );

      const failed = [
        ...returned.filter(
          (d) =>
            d?.success !== true ||
            !d?.doc_id
        ),
        ...Array.from(
          {
            length: Math.max(
              0,
              count - returned.length
            )
          },
          () => ({
            error: "No result returned by the API"
          })
        )
      ];

      const details = successful
        .slice(0, 8)
        .map(
          (d) =>
            `• ${d.doc_id}${
              d.filename
                ? ` (${d.filename})`
                : ""
            } — ${d.status || "ready"}`
        )
        .join("\n");

      const problems = failed.length
        ? `\n\nFailed:\n${failed
            .slice(0, 6)
            .map(
              (d, i) =>
                `• ${
                  d.filename ||
                  `File #${i + 1}`
                } — ${
                  d.error ||
                  d.status ||
                  "Processing failed"
                }`
            )
            .join("\n")}`
        : "";

      replaceMessage(
        sid,
        pendingId,
        successful.length
          ? `Done.\n\nCreated documents:\n${details}${problems}\n\nOpen Workspace to inspect results.`
          : `Done, but no documents were processed.${problems}`
      );

      updateSession(sid, (s) => {
        const docs = [
          ...successful,
          ...(s.docs || [])
        ];

        return {
          ...s,
          docs,
          queuedDocs: Math.max(
            0,
            (s.queuedDocs || 0) - count
          ),
          coverUrl:
            successful[0]?.preview_url ||
            s.coverUrl ||
            "",
          status: (
            successful[0]?.status ||
            s.status ||
            "idle"
          ).toLowerCase(),
          subtitle: docs.length
            ? `${docs.length} document(s) processed`
            : "No results yet"
        };
      });

      if (activeIdRef.current === sid) {
        setView(
          successful.length
            ? "workspace"
            : "chat"
        );
      }

      notify(
        failed.length
          ? successful.length
            ? "Some files failed to process."
            : "Processing failed."
          : "Processing complete.",
        failed.length
          ? successful.length
            ? "info"
            : "error"
          : "success"
      );
    } catch (error) {
      replaceMessage(
        sid,
        pendingId,
        `Error: ${error.message}`
      );

      updateSession(sid, (s) => ({
        ...s,
        queuedDocs: Math.max(
          0,
          (s.queuedDocs || 0) - count
        ),
        status: "error",
        subtitle: "Error"
      }));

      if (activeIdRef.current === sid) {
        setView("chat");

        setFiles((current) =>
          current.length
            ? current
            : selected
        );

        setPrompt((current) =>
          current || note
        );
      }

      notify(
        `Error: ${error.message}`,
        "error"
      );
    } finally {
      runRef.current = false;
      setLoading(false);
    }
  }, [
    loading,
    files,
    activeSessionId,
    sessions,
    newSession,
    appendMessage,
    updateSession,
    replaceMessage,
    prompt,
    notify
  ]);

  const onDeleted = useCallback(
    (sid, docId) => {
      updateSession(sid, (s) => {
        const docs = (
          s.docs || []
        ).filter(
          (d) => d.doc_id !== docId
        );

        return {
          ...s,
          docs,
          coverUrl:
            docs[0]?.preview_url || "",
          subtitle: docs.length
            ? `${docs.length} document(s) processed`
            : "No results yet",
          status:
            docs[0]?.status ||
            (docs.length
              ? s.status
              : "idle")
        };
      });

      notify(
        "Document deleted.",
        "success"
      );
    },
    [updateSession, notify]
  );

  const startResize = (event) => {
    if (!sidebarExpanded) return;

    event.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    if (!isResizing) return;

    const move = (e) =>
      setSidebarWidth(
        Math.max(
          300,
          Math.min(460, e.clientX)
        )
      );

    const stop = () =>
      setIsResizing(false);

    window.addEventListener(
      "mousemove",
      move
    );

    window.addEventListener(
      "mouseup",
      stop
    );

    return () => {
      window.removeEventListener(
        "mousemove",
        move
      );

      window.removeEventListener(
        "mouseup",
        stop
      );
    };
  }, [isResizing]);

  const closeRename = () => {
    setRenameSessionId(null);
    setRenameValue("");
  };

  const saveRename = () => {
    const value = renameValue.trim();

    if (!renameSessionId || !value) {
      return;
    }

    updateSession(renameSessionId, {
      title: value,
      userRenamed: true
    });

    closeRename();
  };

  const pinSession = (session) =>
    updateSession(
      session.id,
      (s) => ({
        ...s,
        pinned: !s.pinned,
        pinnedAt: s.pinned
          ? null
          : Date.now()
      })
    );

  const confirmDeleteChat = () => {
    if (
      !removeChatId ||
      runRef.current
    ) {
      return;
    }

    const remaining = sessions.filter(
      (s) => s.id !== removeChatId
    );

    setSessions(remaining);

    if (
      activeSessionId ===
      removeChatId
    ) {
      const next =
        remaining[0]?.id || null;

      activeIdRef.current = next;
      setActiveSessionId(next);
      setView("chat");

      if (!next) {
        setFiles([]);
        setPrompt("");
      }
    }

    setRemoveChatId(null);

    notify(
      "Chat removed locally. Server documents remain stored.",
      "info"
    );
  };

  const selectSession = (id) => {
    activeIdRef.current = id;
    setActiveSessionId(id);
    setView("chat");
    setSidebarMobileOpen(false);
  };

  const Sidebar = (
    <Box
      className="ba-sidebar"
      sx={{
        width: sidebarWidth,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        minWidth: 0
      }}
    >
      <Box sx={{ p: 1.8 }}>
        <Stack
          direction="row"
          spacing={1.25}
          alignItems="center"
        >
          <Logo size={42} />

          <Box
            sx={{
              minWidth: 0,
              flex: 1
            }}
          >
            <Typography
              noWrap
              sx={{
                fontWeight: 850,
                fontSize: 14.5
              }}
            >
              Blood Agent
            </Typography>

            <Typography
              noWrap
              sx={{
                fontSize: 10.6,
                color: subtle
              }}
            >
              OCR → Anonymize → JSON → LOINC
            </Typography>
          </Box>

          <Tooltip title="Collapse sidebar">
            <IconButton
              aria-label="Collapse sidebar"
              onClick={() => {
                setSidebarExpanded(false);
                setSidebarMobileOpen(false);
              }}
              sx={{
                border,
                bgcolor: "rgba(255,255,255,.04)"
              }}
            >
              <ChevronLeftRoundedIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        <Button
          fullWidth
          variant="contained"
          className="ba-primary-action"
          startIcon={<AddRoundedIcon />}
          onClick={newChat}
          sx={{
            mt: 2,
            borderRadius: 2.5,
            minHeight: 43
          }}
        >
          New chat
        </Button>

        <TextField
          value={search}
          onChange={(e) =>
            setSearch(e.target.value)
          }
          placeholder="Search chats..."
          size="small"
          fullWidth
          sx={{
            mt: 1.3,
            "& .MuiOutlinedInput-root": {
              borderRadius: 2.7,
              bgcolor: "rgba(3,8,22,.45)"
            }
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRoundedIcon
                  sx={{
                    color: subtle,
                    fontSize: 20
                  }}
                />
              </InputAdornment>
            )
          }}
        />
      </Box>

      <Divider
        sx={{
          borderColor: "rgba(165,175,208,.12)"
        }}
      />

      <Box
        sx={{
          flex: 1,
          overflowY: "auto",
          minHeight: 0,
          p: 1.3
        }}
      >
        <Typography
          sx={{
            color: subtle,
            fontWeight: 800,
            fontSize: 10.5,
            letterSpacing: 1.3,
            px: 0.8,
            py: 1
          }}
        >
          YOUR WORKSPACES · {sessions.length}
        </Typography>

        <Stack spacing={1}>
          {shownSessions.map(
            (session) => (
              <SessionCard
                key={session.id}
                session={session}
                active={
                  session.id === activeSessionId
                }
                onSelect={() =>
                  selectSession(session.id)
                }
                onRename={(s) => {
                  setRenameSessionId(s.id);
                  setRenameValue(s.title || "");
                }}
                onDelete={(s) => {
                  if (!runRef.current) {
                    setRemoveChatId(s.id);
                  } else {
                    notify(
                      "Finish the current upload first.",
                      "error"
                    );
                  }
                }}
                onPin={pinSession}
              />
            )
          )}

          {!shownSessions.length && (
            <Box
              sx={{
                ...glass,
                borderRadius: 3,
                p: 2
              }}
            >
              <Typography
                sx={{
                  fontWeight: 800,
                  fontSize: 13
                }}
              >
                No chats found
              </Typography>

              <Typography
                sx={{
                  color: subtle,
                  fontSize: 12,
                  mt: 0.7
                }}
              >
                Your sessions appear here after the first upload.
              </Typography>
            </Box>
          )}
        </Stack>
      </Box>

      <Divider
        sx={{
          borderColor: "rgba(165,175,208,.12)"
        }}
      />

      <Box sx={{ p: 1.6 }}>
        <Typography
          noWrap
          title={API_BASE}
          sx={{
            fontSize: 11,
            color: subtle
          }}
        >
          API: {API_BASE}
        </Typography>
      </Box>

      <Box
        onMouseDown={startResize}
        sx={{
          position: "absolute",
          right: 0,
          top: 0,
          height: "100%",
          width: 8,
          cursor: "col-resize",
          zIndex: 6,
          "&:hover": {
            bgcolor: "rgba(159,128,255,.13)"
          }
        }}
      />
    </Box>
  );

  const Rail = (
    <Box
      className="ba-sidebar-rail"
      sx={{
        width: 72,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 1.4,
        gap: 1.3
      }}
    >
      <Tooltip title="Expand sidebar">
        <IconButton
          onClick={() =>
            setSidebarExpanded(true)
          }
          aria-label="Expand sidebar"
          sx={{
            p: 0.5,
            border: "1px solid rgba(166,140,255,.25)"
          }}
        >
          <Logo size={42} />
        </IconButton>
      </Tooltip>

      <Tooltip title="New chat">
        <IconButton
          onClick={newChat}
          sx={{
            mt: 0.9,
            border,
            color: "#c3b3ff",
            bgcolor: "rgba(147,117,255,.12)"
          }}
        >
          <AddRoundedIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title="Search chats">
        <IconButton
          onClick={() =>
            setSidebarExpanded(true)
          }
          sx={{ border }}
        >
          <SearchRoundedIcon />
        </IconButton>
      </Tooltip>

      <Box sx={{ flex: 1 }} />

      <Tooltip title="Demo mode: user accounts are not enabled">
        <span>
          <IconButton
            disabled
            sx={{ border }}
          >
            <PersonRoundedIcon />
          </IconButton>
        </span>
      </Tooltip>
    </Box>
  );

  const Welcome = (
    <Box
      className="ba-welcome"
      role="region"
      aria-label="Blood Agent analysis home"
    >
      <Box
        className="ba-welcome-glow"
        aria-hidden="true"
      />

      <Box className="ba-welcome-content">
        <Box className="ba-eyebrow">
          <span className="ba-eyebrow-dot" />
          LABORATORY INTELLIGENCE
        </Box>

        <Typography
          component="h1"
          className="ba-welcome-title"
        >
          Your lab reports,{" "}
          <Box
            component="span"
            className="ba-gradient-text"
          >
            structured.
          </Box>
        </Typography>

        <Typography className="ba-welcome-description">
          Turn laboratory PDFs and images into reviewable,
          structured data. Extract text, anonymize identifiers,
          and inspect every result in one place.
        </Typography>

        <Box
          className={`ba-upload-zone${isDragActive ? " is-active" : ""}`}
          aria-label="Document upload area"
          sx={{ mt: 3 }}
        >
          <Box
            className="ba-upload-icon"
            aria-hidden="true"
          >
            <UploadFileRoundedIcon
              sx={{ fontSize: 27 }}
            />
          </Box>

          <Typography className="ba-upload-heading">
            {isDragActive
              ? "Drop documents to attach"
              : "Drag & drop laboratory reports here"}
          </Typography>

          <Typography className="ba-upload-details">
            PDF, PNG, JPG, TIFF, BMP, WebP · Up to {MAX_FILES} files ·{" "}
            {MAX_UPLOAD_MB} MiB each
          </Typography>

          <Button
            variant="contained"
            className="ba-primary-action ba-upload-browse"
            startIcon={<UploadFileRoundedIcon />}
            disabled={loading || files.length >= MAX_FILES}
            onClick={openFilePicker}
            sx={{
              mt: 1.6,
              borderRadius: 2.5
            }}
          >
            Browse files
          </Button>

          {files.length > 0 && (
            <Typography
              className="ba-upload-selected"
              role="status"
            >
              {files.length}{" "}
              {files.length === 1 ? "file" : "files"} selected
              — review below, then click Run
            </Typography>
          )}
        </Box>

        <Box className="ba-process-heading">
          HOW IT WORKS
        </Box>

        <Box
          className="ba-process-grid"
          aria-label="Processing workflow (not live status)"
        >
          <Box className="ba-process-step">
            <span>01</span>
            <UploadFileRoundedIcon />
            <strong>OCR</strong>
          </Box>

          <Box className="ba-process-step">
            <span>02</span>
            <DescriptionRoundedIcon />
            <strong>Anonymize</strong>
          </Box>

          <Box className="ba-process-step">
            <span>03</span>
            <GridViewRoundedIcon />
            <strong>Extract JSON</strong>
          </Box>

          <Box className="ba-process-step">
            <span>04</span>
            <DescriptionRoundedIcon />
            <strong>Map LOINC</strong>
          </Box>
        </Box>

        <Typography className="ba-welcome-disclaimer">
          Demo environment. Outputs require independent
          verification and must not be used for clinical decisions.
        </Typography>
      </Box>
    </Box>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />

      <Box
        className="ba-app"
        sx={{
          height: "100dvh",
          overflow: "hidden",
          display: "flex"
        }}
      >
        <Box
          sx={{
            display: {
              xs: "none",
              md: "block"
            },
            flex: "0 0 auto",
            width: sidebarExpanded
              ? sidebarWidth
              : 72,
            transition: "width .24s cubic-bezier(.22,1,.36,1)"
          }}
        >
          {sidebarExpanded
            ? Sidebar
            : Rail}
        </Box>

        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column"
          }}
        >
          <Box
            className="ba-topbar"
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 2,
              px: {
                xs: 1.5,
                md: 3
              },
              py: 1.4
            }}
          >
            <Stack
              direction="row"
              alignItems="center"
              spacing={1.5}
            >
              <IconButton
                onClick={() =>
                  setSidebarMobileOpen(true)
                }
                aria-label="Open navigation"
                sx={{
                  display: {
                    xs: "inline-flex",
                    md: "none"
                  },
                  border
                }}
              >
                <ChevronRightRoundedIcon />
              </IconButton>

              <Box>
                <Typography
                  sx={{
                    fontSize: 10,
                    color: subtle,
                    fontWeight: 800,
                    letterSpacing: 1.4
                  }}
                >
                  BLOOD AGENT
                </Typography>

                <Typography
                  sx={{
                    fontSize: 15.5,
                    fontWeight: 850
                  }}
                >
                  {view === "chat"
                    ? "Chat"
                    : "Workspace"}
                </Typography>
              </Box>
            </Stack>

            <Status busy={loading} />
          </Box>

          <Box
            sx={{
              px: {
                xs: 1.2,
                md: 3
              },
              pt: 1.6,
              pb: 0.4
            }}
          >
            <Stack
              className="ba-view-tabs"
              direction="row"
              alignItems="center"
              spacing={0.5}
            >
              <Button
                className={
                  view === "chat"
                    ? "is-current"
                    : ""
                }
                variant={
                  view === "chat"
                    ? "contained"
                    : "text"
                }
                startIcon={<ChatRoundedIcon />}
                onClick={() =>
                  setView("chat")
                }
              >
                Chat
              </Button>

              <Button
                className={
                  view === "workspace"
                    ? "is-current"
                    : ""
                }
                variant={
                  view === "workspace"
                    ? "contained"
                    : "text"
                }
                startIcon={<GridViewRoundedIcon />}
                disabled={!sessionDocs.length}
                onClick={() =>
                  setView("workspace")
                }
              >
                Workspace
              </Button>
            </Stack>
          </Box>


        {view === "chat" ? (
          <Box
            {...getRootProps()}
            sx={{
              display: "flex",
              flexDirection: "column",
              flex: 1,
              minHeight: 0
            }}
          >
              <Box
                className="ba-chat-scroll"
                ref={scrollRef}
                sx={{
                  flex: 1,
                  overflowY: "auto",
                  minHeight: 0,
                  px: {
                    xs: 1.2,
                    md: 3
                  },
                  py: 2.2
                }}
              >
                {!messages.length && Welcome}

                <Stack
                  spacing={1.8}
                  sx={{
                    mt: messages.length
                      ? 0
                      : 2
                  }}
                >
                  {messages.map(
                    (entry) => (
                      <Message
                        key={entry.id}
                        entry={entry}
                      />
                    )
                  )}
                </Stack>
              </Box>

              <Box
                className="ba-composer-wrap"
                sx={{
                  px: {
                    xs: 1.2,
                    md: 3
                  },
                  py: 1.6,
                  bgcolor: "rgba(7,11,24,.8)"
                }}
              >
                <input {...getInputProps()} />

                <Paper
                  className={
                    isDragActive
                      ? "ba-composer is-drag-over"
                      : "ba-composer"
                  }
                  sx={{
                    ...glass,
                    borderRadius: 3,
                    p: {
                      xs: 1.2,
                      sm: 1.6
                    }
                  }}
                >
                  <TextField
                    value={prompt}
                    onChange={(e) =>
                      setPrompt(e.target.value)
                    }
                    multiline
                    minRows={2}
                    maxRows={6}
                    fullWidth
                    placeholder="Optional note for this chat (does not change the analysis)…"
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey
                      ) {
                        e.preventDefault();
                        run();
                      }
                    }}
                    sx={{
                      "& .MuiOutlinedInput-root": {
                        borderRadius: 2,
                        bgcolor: "rgba(5,8,24,.3)"
                      },
                      "& textarea": {
                        fontSize: 13.2,
                        lineHeight: 1.6
                      }
                    }}
                  />

                  <Stack
                    direction="row"
                    useFlexGap
                    flexWrap="wrap"
                    spacing={0.7}
                    alignItems="center"
                    sx={{ mt: 1.2 }}
                  >
                    <Chip
                      size="small"
                      icon={<UploadFileRoundedIcon />}
                        label={
                          files.length
                            ? `${files.length} ${
                                files.length === 1 ? "file" : "files"
                              } selected`
                            : "No files selected"
                        }
                      sx={{
                        fontWeight: 750,
                        bgcolor: "rgba(255,255,255,.05)",
                        border
                      }}
                    />

                    {files.map(
                      (file) => (
                        <Chip
                          key={`${file.name}:${file.size}:${file.lastModified}`}
                          label={file.name}
                          onDelete={() =>
                            removeFile(file)
                          }
                          size="small"
                          sx={{
                            maxWidth: 280,
                            border,
                            bgcolor: "rgba(145,115,255,.10)"
                          }}
                        />
                      )
                    )}
                  </Stack>

                  <Stack
                    direction="row"
                    useFlexGap
                    flexWrap="wrap"
                    alignItems="center"
                    justifyContent="flex-end"
                    spacing={1}
                    sx={{ mt: 1.4 }}
                  >
                    <Button
                      variant="outlined"
                      startIcon={<UploadFileRoundedIcon />}
                      onClick={openFilePicker}
                      disabled={
                        loading ||
                        files.length >= MAX_FILES
                      }
                      sx={{
                        borderRadius: 2.3
                      }}
                    >
                      Attach
                    </Button>

                    <Button
                      variant="text"
                      startIcon={<DeleteOutlineRoundedIcon />}
                      disabled={
                        loading ||
                        !files.length
                      }
                      onClick={() =>
                        setFiles([])
                      }
                    >
                      Clear
                    </Button>

                    <Button
                      className="ba-primary-action"
                      variant="contained"
                      sx={{
                        borderRadius: 2.3,
                        px: 2.5
                      }}
                      disabled={
                        loading ||
                        !files.length
                      }
                      onClick={run}
                      endIcon={
                        loading ? (
                          <CircularProgress
                            size={16}
                            sx={{
                              color: "white"
                            }}
                          />
                        ) : (
                          <SendRoundedIcon />
                        )
                      }
                    >
                      {loading
                        ? "Running…"
                        : "Run"}
                    </Button>
                  </Stack>
                </Paper>
              </Box>
            </Box>
          ) : (
            <Box
              className="ba-workspace-scroll"
              sx={{
                flex: 1,
                overflowY: "auto",
                minWidth: 0,
                px: {
                  xs: 1,
                  md: 3
                },
                py: 2.4
              }}
            >
              <Stack spacing={2.1}>
                {sessionDocs.map(
                  (doc) => (
                    <Box
                      className="ba-workspace-item"
                      key={doc.doc_id}
                      sx={{
                        minWidth: 0
                      }}
                    >
                      <DocumentCard
                        doc={doc}
                        apiBase={API_BASE}
                        onDeleted={(docId) =>
                          onDeleted(
                            activeSessionId,
                            docId
                          )
                        }
                        onToast={notify}
                      />
                    </Box>
                  )
                )}
              </Stack>
            </Box>
          )}
        </Box>

        <Drawer
          anchor="left"
          open={sidebarMobileOpen}
          onClose={() =>
            setSidebarMobileOpen(false)
          }
          sx={{
            display: {
              xs: "block",
              md: "none"
            }
          }}
          PaperProps={{
            sx: {
              width: "min(380px, calc(100vw - 24px))",
              background: "#0a1021"
            }
          }}
        >
          {Sidebar}
        </Drawer>

        <Dialog
          open={Boolean(renameSessionId)}
          onClose={closeRename}
          PaperProps={{
            sx: {
              ...glass,
              borderRadius: 3,
              width: "min(500px, 92vw)"
            }
          }}
        >
          <DialogTitle
            sx={{
              fontWeight: 850
            }}
          >
            Rename workspace
          </DialogTitle>

          <DialogContent>
            <TextField
              autoFocus
              fullWidth
              value={renameValue}
              onChange={(e) =>
                setRenameValue(e.target.value)
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  saveRename();
                }
              }}
              placeholder="Workspace name"
              sx={{ mt: 1 }}
            />
          </DialogContent>

          <DialogActions
            sx={{
              px: 3,
              pb: 2.5
            }}
          >
            <Button onClick={closeRename}>
              Cancel
            </Button>

            <Button
              variant="contained"
              className="ba-primary-action"
              disabled={!renameValue.trim()}
              onClick={saveRename}
            >
              Save
            </Button>
          </DialogActions>
        </Dialog>

        <Dialog
          open={Boolean(removeChatId)}
          onClose={() =>
            setRemoveChatId(null)
          }
          PaperProps={{
            sx: {
              ...glass,
              borderRadius: 3,
              width: "min(500px, 92vw)"
            }
          }}
        >
          <DialogTitle
            sx={{
              fontWeight: 850
            }}
          >
            Remove chat locally?
          </DialogTitle>

          <DialogContent>
            <Typography
              sx={{
                fontSize: 13.5,
                lineHeight: 1.75,
                color: "#acb8d2"
              }}
            >
              Removing this chat only clears its local session.
              Documents already uploaded to the API and MinIO
              remain on the server. Delete documents in Workspace
              first if you also want them removed from storage.
            </Typography>
          </DialogContent>

          <DialogActions
            sx={{
              px: 3,
              pb: 2.5
            }}
          >
            <Button
              onClick={() =>
                setRemoveChatId(null)
              }
            >
              Cancel
            </Button>

            <Button
              color="error"
              variant="contained"
              onClick={confirmDeleteChat}
            >
              Remove chat
            </Button>
          </DialogActions>
        </Dialog>

        <Notice
          data={toast}
          onClose={() =>
            setToast((t) => ({
              ...t,
              open: false
            }))
          }
        />
      </Box>
    </ThemeProvider>
  );
}
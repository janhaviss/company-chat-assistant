import { useEffect, useState, useRef } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";
const WS_URL = "ws://127.0.0.1:8000";

function App() {
  const [messages, setMessages] = useState([]);
  const [menu, setMenu] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [stage, setStage] = useState(null);
  const [needsResume, setNeedsResume] = useState(false);
  const [jobOptions, setJobOptions] = useState([]);
  const [uploading, setUploading] = useState(false);

  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const fileInputRef = useRef(null);

  // One session id per browser tab/session, sent as part of the WS path
  // and reused for the separate resume-upload HTTP request.
  const sessionIdRef = useRef(
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );

  // Fetch suggested questions (unchanged — still a plain REST endpoint)
  useEffect(() => {
    fetch(`${API_URL}/menu`)
      .then((response) => response.json())
      .then((data) => setMenu(data))
      .catch((error) => console.error("Failed to load menu:", error));
  }, []);

  // Open the real-time chat connection once per session
  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/${sessionIdRef.current}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onclose = () => setConnected(false);

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error("Failed to parse WS message:", error);
        return;
      }

      setLoading(false);
      setStage(data.stage || null);
      setNeedsResume(Boolean(data.needs_resume));
      setJobOptions(data.job_options || []);

      setMessages((prev) => [
        ...prev,
        { sender: data.sender || "bot", text: data.text },
      ]);
    };

    return () => ws.close();
  }, []);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Send chat message over the WebSocket
  const sendMessage = (question) => {
    if (!question.trim() || loading) return;

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "Still connecting — please try again in a moment." },
      ]);
      return;
    }

    setMessages((prev) => [...prev, { sender: "user", text: question }]);
    setInput("");
    setLoading(true);
    setJobOptions([]);

    wsRef.current.send(JSON.stringify({ text: question }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    sendMessage(input);
  };

  // --------------------------------
  // Resume upload (job-applicant flow)
  // --------------------------------

  const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];
  const MAX_FILE_SIZE_MB = 5;

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow re-selecting the same file later
    if (!file) return;

    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "Please attach a PDF or Word document (.pdf, .doc, .docx)." },
      ]);
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: `That file is too large — please keep it under ${MAX_FILE_SIZE_MB}MB.` },
      ]);
      return;
    }

    setUploading(true);
    setMessages((prev) => [...prev, { sender: "user", text: `📎 ${file.name}` }]);

    const formData = new FormData();
    formData.append("session_id", sessionIdRef.current);
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/api/upload-resume`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Upload failed");
      }

      setNeedsResume(false);
    } catch (error) {
      console.error("Resume upload error:", error);
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "Sorry, that upload didn't go through. Please try again." },
      ]);
    } finally {
      setUploading(false);
    }
  };

  const showSuggestions = stage === "READY" && messages.length <= 4;

  return (
    <div className="app">
      <div className="chat-container">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-header-text">
            <h1>Company Assistant</h1>
            <div className="status">
              <span className="status-dot" style={{ opacity: connected ? 1 : 0.3 }}></span>
              {connected ? "Online" : "Connecting…"}
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {messages.map((message, index) => (
            <div key={index} className={`message-row ${message.sender}`}>
              <div className="message-content">
                <div className="message">{message.text}</div>
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {loading && (
            <div className="message-row bot">
              <div className="message-content">
                <div className="message typing-bubble">
                  <span className="dot"></span>
                  <span className="dot"></span>
                  <span className="dot"></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Questions */}
        {showSuggestions && (
          <div className="suggestions">
            <p>Try asking</p>
            <div className="suggestion-list">
              {menu.slice(0, 6).map((item) => (
                <button key={item.question_id} onClick={() => sendMessage(item.question)}>
                  {item.question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Job opening options — shown when the bot is asking which role */}
        {jobOptions.length > 0 && (
          <div className="suggestions">
            <p>Choose a role</p>
            <div className="suggestion-list">
              {jobOptions.map((title) => (
                <button key={title} onClick={() => sendMessage(title)}>
                  {title}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Resume attachment prompt — only shown while mandatory */}
        {needsResume && (
          <div className="resume-attach-bar">
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.doc,.docx"
              style={{ display: "none" }}
              onChange={handleFileSelected}
            />
            <button type="button" onClick={handleAttachClick} disabled={uploading}>
              {uploading ? "Uploading…" : "📎 Attach your resume"}
            </button>
          </div>
        )}

        {/* Input */}
        <form className="chat-input" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Ask something..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
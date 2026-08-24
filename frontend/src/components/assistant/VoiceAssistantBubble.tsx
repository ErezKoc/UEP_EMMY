import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { processAssistantCommand } from "../../api/client";
import { useToast } from "../ui/toast";
import { formatTime } from "../../lib/format";
import type { AssistantAction } from "../../types";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  action?: AssistantAction;
  timestamp: string;
}

export default function VoiceAssistantBubble() {
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "assistant",
      text: "Hi! I'm Emmy, your voice & command assistant. Speak or type commands like 'create me a calendar event for Jan 6 at 12:30' or 'take me to my pets'.",
      timestamp: formatTime(new Date()),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);

  // Ref hooks to prevent stale closure values in async event callbacks
  const inputTextRef = useRef(inputText);
  const liveTranscriptRef = useRef("");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recognitionRef = useRef<any>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputTextRef.current = inputText;
  }, [inputText]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (isOpen) {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  // Speech synthesis helper
  const speakText = (text: string) => {
    if (!ttsEnabled || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const handleProcessResponse = (
    userText: string,
    response_text: string,
    action?: AssistantAction
  ) => {
    const timeStr = formatTime(new Date());

    if (userText) {
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(),
          sender: "user",
          text: userText,
          timestamp: timeStr,
        },
      ]);
    }

    setMessages((prev) => [
      ...prev,
      {
        id: Math.random().toString(),
        sender: "assistant",
        text: response_text,
        action,
        timestamp: timeStr,
      },
    ]);

    speakText(response_text);
    toast(response_text, "info");

    if (action?.nav_target) {
      setTimeout(() => {
        navigate(action.nav_target!);
      }, 600);
    }
  };

  const submitCommand = async (audioBlob?: Blob | null, textContent?: string) => {
    const queryText = textContent || inputTextRef.current;
    if (!audioBlob && (!queryText || !queryText.trim())) return;
    setIsProcessing(true);

    try {
      const res = await processAssistantCommand(audioBlob, queryText.trim() || undefined);
      handleProcessResponse(res.transcript || queryText || "", res.response_text, res.action);
    } catch (err: any) {
      const errorMsg = err.message || "Failed to process command. Please try again.";
      toast(errorMsg, "error");
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(),
          sender: "assistant",
          text: "Sorry, I had trouble processing that request.",
          timestamp: formatTime(new Date()),
        },
      ]);
    } finally {
      setIsProcessing(false);
      setInputText("");
      liveTranscriptRef.current = "";
    }
  };

  // Start Voice Recording
  const startRecording = async () => {
    audioChunksRef.current = [];
    liveTranscriptRef.current = "";
    setInputText("");
    setIsRecording(true);

    // Try starting browser Web Speech API for real-time live typing
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognitionRef.current = recognition;
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onresult = (event: any) => {
          let currentTranscript = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            currentTranscript += event.results[i][0].transcript;
          }
          if (currentTranscript.trim()) {
            liveTranscriptRef.current = currentTranscript;
            setInputText(currentTranscript);
          }
        };

        recognition.onerror = (e: any) => {
          console.warn("Web Speech API error", e);
        };

        recognition.start();
      } catch (e) {
        console.warn("Web Speech API init failed", e);
      }
    }

    // MediaRecorder audio chunk recording
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const finalRecordedText = liveTranscriptRef.current || inputTextRef.current;
        const audioBlob = audioChunksRef.current.length > 0 ? new Blob(audioChunksRef.current, { type: "audio/webm" }) : null;

        if (finalRecordedText.trim()) {
          submitCommand(null, finalRecordedText.trim());
        } else if (audioBlob && audioBlob.size > 0) {
          submitCommand(audioBlob, undefined);
        }
      };

      mediaRecorder.start();
    } catch (err) {
      setIsRecording(false);
      toast("Microphone access permission denied or unavailable.", "error");
    }
  };

  const stopRecording = () => {
    setIsRecording(false);

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
  };

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isProcessing) return;
    submitCommand(null, inputText.trim());
  };

  /*
   * Out of the way on the symptom checker, on phones.
   *
   * A floating control anchored to the bottom-right corner sits on top of
   * whatever is behind it, and on a 390px viewport that is answer chips, the
   * validation message under a question, and the Back/Continue row. On a form
   * someone is filling in about a sick animal, an assistant launcher is not
   * worth a single obscured answer. It stays on every other page, and returns
   * here at `sm` and above where there is room beside the content.
   */
  const hideOnMobile = location.pathname.startsWith("/symptom-check");

  return (
    <div
      /*
        z-40, not z-9999.
        At 9999 this floated above everything including open dialogs, which sit
        at z-50 — so on a phone the launcher covered the bottom-right corner of
        every modal, which is exactly where their Save, Confirm and Delete
        buttons are. An assistant that blocks the button you opened the dialog
        to press is worse than no assistant.
        Below the dialogs and above the page: the header is also z-40 but lives
        at the opposite end of the screen, so the two never meet.
      */
      className={`fixed bottom-6 right-6 z-40 flex-col items-end ${
        hideOnMobile ? "hidden sm:flex" : "flex"
      }`}
      // Keeps the launcher clear of the home indicator on notched phones.
      style={{ marginBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      {/* Floating Chat Modal */}
      {isOpen && (
        <div className="mb-4 flex h-[520px] w-96 max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-900/10 transition-all duration-200 ease-out">
          {/* Header */}
          <div className="flex items-center justify-between bg-gradient-to-r from-primary-600 to-teal-600 px-4 py-3 text-white">
            <div className="flex items-center gap-3">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-full bg-white/20 font-bold backdrop-blur">
                <span>🤖</span>
                <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-primary-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold leading-tight">Emmy Voice Assistant</h3>
                <p className="text-xs text-primary-100">Live Voice & Whisper API</p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setTtsEnabled((prev) => !prev)}
                title={ttsEnabled ? "Mute Voice Response" : "Enable Voice Response"}
                className={`rounded-lg p-1.5 transition ${
                  ttsEnabled ? "bg-white/20 text-white" : "text-white/60 hover:bg-white/10"
                }`}
              >
                {ttsEnabled ? "🔊" : "🔇"}
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1.5 text-white/80 transition hover:bg-white/20 hover:text-white"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.sender === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
                    msg.sender === "user"
                      ? "bg-primary-600 text-white rounded-br-none"
                      : "bg-white text-slate-800 border border-slate-200/80 rounded-bl-none"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

                  {/* Action Summary Pill */}
                  {msg.action && msg.action.action_type !== "general_reply" && (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2 text-xs font-medium text-primary-700">
                      <span className="rounded bg-primary-50 px-2 py-0.5 border border-primary-100">
                        ⚡ {msg.action.summary}
                      </span>
                      {msg.action.nav_target && (
                        <span className="text-slate-500">→ {msg.action.nav_target}</span>
                      )}
                    </div>
                  )}
                </div>
                <span className="mt-1 px-1 text-[10px] text-slate-400">{msg.timestamp}</span>
              </div>
            ))}

            {isProcessing && (
              <div className="flex items-center gap-2 rounded-xl bg-white p-3 text-xs text-slate-500 border border-slate-200 shadow-sm w-fit">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
                <span>Thinking & processing action...</span>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Quick Command Chips */}
          <div className="border-t border-slate-100 bg-white px-3 py-2">
            <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
              <button
                type="button"
                onClick={() => submitCommand(null, "create me a calendar event for jan 6 at 12.30")}
                className="whitespace-nowrap rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:bg-primary-50 hover:text-primary-700 transition"
              >
                📅 Jan 6 Event
              </button>
              <button
                type="button"
                onClick={() => submitCommand(null, "add a dog named Max")}
                className="whitespace-nowrap rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:bg-primary-50 hover:text-primary-700 transition"
              >
                🐾 Add Pet Max
              </button>
              <button
                type="button"
                onClick={() => submitCommand(null, "take me to my pets")}
                className="whitespace-nowrap rounded-full bg-slate-100 px-3 py-1 text-slate-700 hover:bg-primary-50 hover:text-primary-700 transition"
              >
                📋 My Pets
              </button>
            </div>
          </div>

          {/* Input Footer */}
          <div className="border-t border-slate-200 bg-white p-3">
            <form onSubmit={handleTextSubmit} className="flex items-center gap-2">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={isRecording ? "Listening to your voice..." : "Type or speak command..."}
                disabled={isProcessing}
                className={`flex-1 rounded-xl border px-3.5 py-2 text-sm focus:outline-none transition ${
                  isRecording
                    ? "border-rose-400 bg-rose-50 text-rose-900 ring-2 ring-rose-300"
                    : "border-slate-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                }`}
              />

              {/* Voice Recording Button */}
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessing}
                title={isRecording ? "Stop Recording & Send" : "Click to Speak"}
                className={`relative flex h-10 w-10 items-center justify-center rounded-xl transition-all ${
                  isRecording
                    ? "bg-rose-500 text-white animate-pulse shadow-md ring-4 ring-rose-200"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900"
                }`}
              >
                {isRecording ? "🔴" : "🎙️"}
              </button>

              {/* Send Button */}
              <button
                type="submit"
                disabled={!inputText.trim() || isProcessing}
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-600 text-white transition hover:bg-primary-700 disabled:opacity-40"
              >
                ➔
              </button>
            </form>
          </div>
        </div>
      )}

      {/*
        Floating Trigger Bubble.

        The label is desktop-only. On a phone the pill was wide enough to sit on
        top of the answer chips behind it — a symptom checker asking someone to
        tap a sign they cannot see — so below `sm` this collapses to the circular
        microphone alone and keeps its accessible name in aria-label.
      */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? "Close Assistant" : "Voice Assistant"}
        aria-expanded={isOpen}
        className="group flex items-center gap-2.5 rounded-full bg-gradient-to-r from-primary-600 to-teal-600 p-3 text-white shadow-xl ring-4 ring-white transition-all hover:scale-105 active:scale-95 sm:px-4 sm:py-3"
      >
        <span className="relative flex h-6 w-6 items-center justify-center text-lg">
          🎙️
          <span className="absolute -top-1 -right-1 flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-300 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
          </span>
        </span>
        <span className="hidden text-sm font-semibold tracking-wide sm:inline">
          {isOpen ? "Close Assistant" : "Voice Assistant"}
        </span>
      </button>
    </div>
  );
}

import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { processAssistantCommand } from "../../api/client";
import { useToast } from "../ui/toast";
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
  const { toast } = useToast();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "assistant",
      text: "Hi! I'm Emmy, your voice & command assistant. Try saying 'create me a calendar event for Jan 6 at 12:30' or 'take me to my pets'.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (isOpen) {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  // Speech synthesis helper
  const speakText = (text: string) => {
    if (!ttsEnabled || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel(); // Stop any active speech
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
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Add user message if not already added
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

    // Add assistant response
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

    // Perform voice playback
    speakText(response_text);

    // Toast notification
    toast(response_text, "info");

    // Perform navigation if specified by assistant action
    if (action?.nav_target) {
      setTimeout(() => {
        navigate(action.nav_target!);
      }, 600);
    }
  };

  const submitCommand = async (audioBlob?: Blob | null, textContent?: string) => {
    if (!audioBlob && (!textContent || !textContent.trim())) return;
    setIsProcessing(true);

    try {
      const res = await processAssistantCommand(audioBlob, textContent);
      handleProcessResponse(res.transcript || textContent || "", res.response_text, res.action);
    } catch (err: any) {
      const errorMsg = err.message || "Failed to process command. Please try again.";
      toast(errorMsg, "error");
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(),
          sender: "assistant",
          text: "Sorry, I had trouble processing that request.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsProcessing(false);
      setInputText("");
    }
  };

  // Start audio recording via MediaRecorder API
  const startRecording = async () => {
    audioChunksRef.current = [];
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
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        submitCommand(audioBlob, undefined);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      toast("Microphone access permission denied or unavailable.", "error");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isProcessing) return;
    submitCommand(null, inputText.trim());
  };

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col items-end">
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
                <p className="text-xs text-primary-100">Whisper & Ollama Powered</p>
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
                placeholder={isRecording ? "Listening..." : "Type or speak command..."}
                disabled={isRecording || isProcessing}
                className="flex-1 rounded-xl border border-slate-300 px-3.5 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-slate-50"
              />

              {/* Voice Recording Button */}
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessing}
                title={isRecording ? "Stop Recording & Send" : "Hold or Click to Speak"}
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

      {/* Floating Trigger Bubble (Reference Image Style) */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="group flex items-center gap-2.5 rounded-full bg-gradient-to-r from-primary-600 to-teal-600 px-4 py-3 text-white shadow-xl ring-4 ring-white transition-all hover:scale-105 active:scale-95"
      >
        <span className="relative flex h-6 w-6 items-center justify-center text-lg">
          🎙️
          <span className="absolute -top-1 -right-1 flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-300 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
          </span>
        </span>
        <span className="text-sm font-semibold tracking-wide">
          {isOpen ? "Close Assistant" : "Voice Assistant"}
        </span>
      </button>
    </div>
  );
}
